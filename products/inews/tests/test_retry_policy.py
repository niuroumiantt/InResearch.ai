"""取正文失败之后,什么时候再试一次。

9-03 站长:「可能真的抓取不到,总是尝试也无意义,但是可能是能抓取到的也说不定,
所以针对这样的没有抓取到的,可以设置为时间间隔长一些去再次抓取。」

于是策略是**退避**而不是「每轮都试」或「一次失败就永别」:

- 每轮重试全部失败条目 = 把每小时那一轮拖成几十次注定失败的浏览器打开;
- 一次失败就永不再试 = 一次登录态过期,那几篇就永久停在「正文未取到」。

退避写成一张明表(6h → 24h → 72h),第几次试就等多久;试满之后不再自动重试,
交给手动的「修复未抓取」——**自动放弃不等于永久放弃**,只是不再每轮白开窗口。
"""
from __future__ import annotations

from typing import Any

from inews import archive
from inews import ledger as ledger_store
from inews import run


def _entry(status: str, crawled_at: str, attempts: int = 0) -> dict[str, object]:
    entry: dict[str, object] = {
        "url": "https://www.bloomberg.com/news/articles/2026-09-02/x",
        "title": "Boehringer Signs Deal for Owkin AI",
        "published_at": "2026-09-02",
        "keywords": ["Bloomberg 专题"],
        "crawled_at": crawled_at,
        "body_status": status,
    }
    if status == "failed":
        entry["body_error"] = "BrowserBypassError: 超时"
        entry["body_attempts"] = attempts
    return entry


def test_the_backoff_table_grows_and_then_stops():
    """退避是一张明表,不是一个魔法公式 —— 读的人要能一眼看出「试几次、隔多久」。"""
    assert run.RETRY_BACKOFF_HOURS == (6, 24, 72)


def test_a_fresh_failure_waits_out_the_first_gap():
    entries = {"a": _entry("failed", "2026-09-03T08:00:00+08:00", attempts=1)}
    # 才过一小时:还不到 6 小时那一档
    assert run.due_for_retry(entries, now="2026-09-03T09:00:00+08:00") == []
    # 过了 6 小时:该再试一次
    due = run.due_for_retry(entries, now="2026-09-03T14:30:00+08:00")
    assert [row["article_id"] for row in due] == ["a"]


def test_each_further_failure_waits_longer():
    """第二次失败等 24 小时,第三次等 72 —— 同一个坑不许每轮再踩一遍。"""
    entries = {"a": _entry("failed", "2026-09-03T08:00:00+08:00", attempts=2)}
    assert run.due_for_retry(entries, now="2026-09-03T20:00:00+08:00") == []
    assert run.due_for_retry(entries, now="2026-09-04T09:00:00+08:00")


def test_after_the_table_runs_out_the_hourly_round_stops_trying():
    """表有三档 = 三次自动重试(第 1/2/3 次失败之后各一次);第四次失败之后
    就不再**自动**重试。手动的「修复未抓取」仍然会捡起它 —— 自动放弃不是
    永久放弃,只是不再每轮白开一次浏览器窗口。"""
    entries = {"a": _entry("failed", "2026-01-01T08:00:00+08:00", attempts=4)}
    assert run.due_for_retry(entries, now="2026-09-03T08:00:00+08:00") == []
    # 手动那条路认的是「所有失败的」,与退避无关
    assert [row["article_id"] for row in run.failed_rows(entries)] == ["a"]


def test_only_failures_are_retried():
    """取到过的和压根没取过的都不在重试范围里。"""
    entries = {
        "ok": _entry("ok", "2026-01-01T08:00:00+08:00"),
        "skipped": _entry("skipped", "2026-01-01T08:00:00+08:00"),
    }
    assert run.due_for_retry(entries, now="2026-09-03T08:00:00+08:00") == []


def test_an_unreadable_timestamp_is_due_rather_than_stuck():
    """时间读不出来就当「早该试了」—— 宁可多试一次,不可让一条烂时间把它
    永久卡住(**不猜时间**,但也不拿读不懂当「刚试过」)。"""
    entries = {"a": _entry("failed", "", attempts=1)}
    assert [row["article_id"] for row in run.due_for_retry(entries, now="2026-09-03T08:00:00+08:00")] == ["a"]


def test_the_ledger_counts_attempts_so_the_backoff_can_grow():
    """次数得有人记。台账是唯一的持久状态,所以它记 —— 老条目没有这个字段,
    当作「刚失败第一次」,照读不误。"""
    entries: dict[str, dict[str, object]] = {}
    row = {
        "article_id": "a", "url": "https://www.bloomberg.com/news/articles/2026-09-02/x",
        "title_en": "t", "body_error": "boom",
    }
    ledger_store.record(entries, [row], crawled_at="2026-09-03T08:00:00+08:00")
    assert entries["a"]["body_attempts"] == 1
    ledger_store.record(entries, [row], crawled_at="2026-09-03T15:00:00+08:00")
    assert entries["a"]["body_attempts"] == 2
    # 取到正文的那一刻,计数归零 —— 它记的是「连续失败几次」。
    ledger_store.record(
        entries, [{**row, "body": "正文" * 400, "body_error": ""}],
        crawled_at="2026-09-03T16:00:00+08:00",
    )
    assert entries["a"]["body_status"] == "ok"
    assert "body_attempts" not in entries["a"]


# ---------------- 接线:每小时那一轮真的会捡起到点的失败条目 ----------------
# 下面三条是 9-03 写这一版时靠读代码发现的两个洞,补上用例钉住:
#   1. 重试**仍然失败**的那些不写回台账 → 次数不涨,退避永远停在第一档;
#   2. 重试**补回来**的那些不进 write_site 的 rows → 正文取回来了,页面却不写。
# 两个都属于「跑起来看着正常、下一轮才露馅」那一类,只有整条接线走一遍才看得见。

from pathlib import Path  # noqa: E402  接线用例要用,放在这里离它们近

from inews import cli as paywall_cli  # noqa: E402

_HUB_HTML = """
<html><body><div class="card">
<a href="/news/articles/2026-09-02/boehringer-signs-deal-for-owkin-ai">
  Boehringer Signs Deal for Owkin AI, Joining Astra and Sanofi</a>
<time datetime="2026-09-02T10:00:00Z"></time>
</div></body></html>
"""


def _round(tmp_path: Path, monkeypatch, *, body: str | None) -> None:
    """跑一轮 bloomberg:正文要么取到(body),要么如实失败(None)。"""
    monkeypatch.setattr(
        run, "_listing_fetcher_for", lambda site: lambda url: (_HUB_HTML, url)
    )

    def fetch_body(row: dict[str, Any]) -> dict[str, Any]:
        if body is None:
            raise RuntimeError("超时")
        return {"body": body, "extractor": "test"}

    monkeypatch.setattr(run, "_body_fetcher_for", lambda site: fetch_body)
    assert paywall_cli.main([
        "--site", "bloomberg", "--limit", "0",
        "--no-translate", "--no-score", "--out", str(tmp_path),
    ]) == 0


def test_a_failed_body_is_recorded_with_its_attempt_count(tmp_path: Path, monkeypatch):
    _round(tmp_path, monkeypatch, body=None)
    entries = ledger_store.load(ledger_store.path_for(tmp_path))
    entry = next(iter(entries.values()))
    assert entry["body_status"] == "failed"
    assert entry["body_attempts"] == 1


def test_a_retry_that_fails_again_bumps_the_count_instead_of_repeating_forever(
    tmp_path: Path, monkeypatch,
):
    """第二轮把时间推到退避之后:它该被再试一次,而且**这次的失败也要写回去** ——
    不写,下一轮它又「到点了」,6/24/72 那张表形同虚设。"""
    _round(tmp_path, monkeypatch, body=None)
    path = ledger_store.path_for(tmp_path)
    entries = ledger_store.load(path)
    key = next(iter(entries))
    entries[key]["crawled_at"] = "2026-01-01T00:00:00+08:00"  # 假装很久以前失败的
    ledger_store.save(path, entries)

    _round(tmp_path, monkeypatch, body=None)
    entry = ledger_store.load(path)[key]
    assert entry["body_attempts"] == 2, "重试仍然失败也要记一次,退避才会变长"


def test_a_retry_that_succeeds_gets_its_article_page_written(
    tmp_path: Path, monkeypatch,
):
    """补回来的正文要真的落到页面上 —— 否则清单上照旧挂着「正文未取到」。"""
    _round(tmp_path, monkeypatch, body=None)
    path = ledger_store.path_for(tmp_path)
    entries = ledger_store.load(path)
    key = next(iter(entries))
    entries[key]["crawled_at"] = "2026-01-01T00:00:00+08:00"
    ledger_store.save(path, entries)

    _round(tmp_path, monkeypatch, body="第一段\n第二段")
    assert ledger_store.load(path)[key]["body_status"] == "ok"
    pages = list((tmp_path / "p").rglob("*.html"))
    assert pages, "补回正文的那一篇要有自己的正文页"
    assert "第一段" in pages[0].read_text(encoding="utf-8")


def test_manual_retry_success_clears_failure_from_cli_archive_and_page(
    tmp_path: Path, monkeypatch, capsys,
):
    """手动「修复未抓取」成功后,终端、台账、存档和页面必须同时转绿。"""
    _round(tmp_path, monkeypatch, body=None)
    capsys.readouterr()  # 下面只检查手动重试这一轮的输出

    monkeypatch.setattr(
        run, "_body_fetcher_for",
        lambda site: lambda row: {"body": "第一段\n第二段", "extractor": "test"},
    )
    assert paywall_cli.main([
        "--site", "bloomberg", "--retry-failed", "--limit", "1",
        "--no-translate", "--no-score", "--out", str(tmp_path),
    ]) == 0

    output = capsys.readouterr().out
    assert "补回 1 篇 / 重试 1 篇" in output
    assert "仍然失败" not in output
    entry = next(iter(ledger_store.load(ledger_store.path_for(tmp_path)).values()))
    assert entry["body_status"] == "ok"
    assert "body_error" not in entry
    [stored] = archive.load(tmp_path)
    assert "body_error" not in stored
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "修复未抓取" not in index
