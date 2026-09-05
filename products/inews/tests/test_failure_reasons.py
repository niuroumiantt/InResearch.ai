"""取正文失败的原因,要留得下来、看得见、查得动。

2026-08-24:库里 160 篇有 31 篇取正文失败(19%),站长问「是不是同一个原因」——
**答不了**。`fetch_body` 明明能分出四类原话(cookie 失效 / 拦截页 / 正文过短 /
浏览器兜底也失败),可那句话只活在那一轮的内存里:台账只记 body_status,存档只存
有正文的,进度日志只打标题。一轮跑完,原因就没了。

这里钉三件事:原话进台账、原话进日志、能把失败的那些单独重试一遍。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from inews import archive
from inews import ledger as ledger_store
from inews import run
from inews.storage import write_json_atomic


def _row(i: int, **extra: Any) -> dict[str, Any]:
    return {"article_id": f"id{i}", "url": f"https://www.ft.com/content/{i}",
            "title_en": f"T{i}", "published_at": "2026-08-20T09:00:00Z",
            "keywords": ["AI chip"], **extra}


def test_the_ledger_keeps_the_reason_a_body_failed():
    """失败原话进台账。**不进的话,重画一次页面就把原因抹掉了。**"""
    entries: dict[str, dict[str, Any]] = {}
    ledger_store.record(entries, [
        _row(1, body_error="拿到的是付费墙拦截页(仅 120 字):登录态可能已失效"),
    ], crawled_at="2026-08-24T00:00:00+08:00")
    kept = entries["id1"]
    assert kept["body_status"] == "failed"
    assert "付费墙拦截页" in kept["body_error"], "原话要逐字留着,不许换说法"


def test_a_successful_body_carries_no_stale_reason():
    """取到了就不该还挂着上一次的失败原因 —— 那会让页面一直显示一条假警报。"""
    entries: dict[str, dict[str, Any]] = {}
    ledger_store.record(entries, [_row(2, body="正文" * 500)],
                        crawled_at="2026-08-24T00:00:00+08:00")
    assert entries["id2"]["body_status"] == "ok"
    assert not entries["id2"].get("body_error")


def test_the_rebuilt_row_still_carries_the_reason():
    """从台账重画出来的行也要带着原话 —— 后台那张失败清单就是这么来的。"""
    entries = {"id3": {"url": "u", "title": "T", "published_at": "",
                       "keywords": [], "body_status": "failed",
                       "body_error": "TimeoutError: 浏览器兜底也失败"}}
    row = ledger_store.rows(entries)[0]
    assert "TimeoutError" in row["body_error"]


def test_the_progress_log_says_why_a_body_failed():
    """每小时一轮跑在后台,没人盯着终端 —— 原因不进日志就等于没有。"""
    said: list[str] = []
    rows = [_row(4)]

    def boom(_row: dict[str, Any]) -> dict[str, Any]:
        raise RuntimeError("拿到的是付费墙拦截页(仅 88 字)")

    run.fetch_bodies(rows, fetch_body=boom, progress=said.append)
    assert any("付费墙拦截页" in line for line in said), "失败原话要打进进度日志"


def test_a_successful_retry_clears_the_old_failure_on_the_working_row():
    """重试的页面和终端都直接读当前行,不只读最后写好的台账。"""
    row = _row(5, body_status="failed", body_error="旧的登录态失效")

    run.fetch_bodies(
        [row], fetch_body=lambda _row: {"body": "已取回的完整正文", "extractor": "test"}
    )

    assert row["body_status"] == "ok"
    assert "body_error" not in row


def test_an_old_archive_with_a_body_and_stale_error_is_normalized_on_read(tmp_path: Path):
    """旧版已经把矛盾状态写进盘了;升级后重画不能继续报假警。"""
    target = archive.path_for(tmp_path, "legacy")
    target.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(target, {
        "article_id": "legacy", "url": "https://example.com/legacy",
        "title_en": "Legacy", "body": "完整正文", "body_error": "旧的登录态失效",
    }, backup=False)

    [loaded] = archive.load(tmp_path)
    assert loaded["body"] == "完整正文"
    assert "body_error" not in loaded


def test_failed_rows_can_be_retried_on_their_own(tmp_path: Path):
    """把台账里记着 failed 的那些单独挑出来重试 —— 这是问出「为什么」的最短路径。

    只挑 failed:`skipped` 是压根没取过(那是 --no-body 的正常状态),
    `ok` 是已经有了,两种都不该被这条命令拖进来重跑。
    """
    entries = {
        "a": {"url": "https://www.ft.com/content/a", "title": "A", "published_at": "",
              "keywords": [], "body_status": "failed", "body_error": "旧原话"},
        "b": {"url": "https://www.ft.com/content/b", "title": "B", "published_at": "",
              "keywords": [], "body_status": "ok"},
        "c": {"url": "https://www.ft.com/content/c", "title": "C", "published_at": "",
              "keywords": [], "body_status": "skipped"},
    }
    picked = run.failed_rows(entries)
    assert [row["article_id"] for row in picked] == ["a"]


def test_reasons_are_grouped_by_what_actually_happened():
    """把原话归成几类,才答得了「是不是同一个原因」。

    **判据是结构性事实**:这几句话是本仓库自己生成的(见 fetch.py 的
    `_short_body_reason` 和两条 raise),所以按它们的固定措辞分类,不是猜。
    归不进去的一律进「其他」并**原样保留**,不硬塞。
    """
    from inews import stats

    rows = [
        {"body_status": "failed", "body_error": "拿到的是付费墙拦截页(仅 120 字):登录态可能已失效"},
        {"body_status": "failed", "body_error": "拿到的是付费墙拦截页(仅 88 字):登录态可能已失效"},
        {"body_status": "failed", "body_error": "正文提取过短(仅 300 字),可能是直播/图集/摘要页:https://x"},
        {"body_status": "failed", "body_error": "未配置 ft.com cookie;浏览器兜底也失败:BrowserBypassError: 超时"},
        {"body_status": "failed", "body_error": "谁也没见过的一句话"},
        {"body_status": "ok"},
    ]
    pairs = dict(stats.by_failure_reason(rows))
    assert pairs["付费墙拦截页"] == 2, "同一类要合并计数"
    assert pairs["正文提取过短"] == 1
    assert pairs["浏览器兜底也失败"] == 1
    assert pairs["其他"] == 1, "归不进去的不硬塞"
    assert sum(pairs.values()) == 5, "只数失败的那些"
