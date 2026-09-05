"""inews 的用例。

用例只覆盖不出网的部分:地址构造、搜索页解析、合并排序、HTML 渲染,以及
"取正文失败时把服务端原话留在页面上"这一条 —— 兜底文案顶掉真实错误是本仓库
反复出事的地方。
"""
from __future__ import annotations

import json
from typing import Any
from html import escape
from pathlib import Path

import pytest

from inews import cli as paywall_cli
from inews import keywords, render, run
from inews.sites import ft as ftsearch
from inews import ledger as ledger_store
from inews import archive, runlog, translate
from inews import stats

SEARCH_HTML = """
<html><body>
  <div class="o-teaser">
    <a href="/content/aaaaaaaa-1111-2222-3333-444444444444">
      OpenAI launches a new AI agent for enterprises</a>
    <time datetime="2026-08-18T09:30:00Z">Aug 18 2026</time>
    <span class="o-teaser__tag">Artificial intelligence</span>
  </div>
  <div class="o-teaser">
    <a href="https://www.ft.com/content/bbbbbbbb-5555-6666-7777-888888888888">
      Nvidia chip demand keeps data centre spending high</a>
    <time datetime="2026-08-17T06:00:00Z">Aug 17 2026</time>
  </div>
  <a href="/topics/artificial-intelligence">AI topic page</a>
</body></html>
"""


def test_search_url_encodes_keyword_and_sorts_by_date():
    url = ftsearch.search_url("AI agent", page=2)
    assert "q=AI+agent" in url
    assert "sort=date" in url
    assert "page=2" in url


def test_parse_search_results_yields_title_time_link():
    rows = ftsearch.parse_search_results(SEARCH_HTML, "AI agent")
    assert len(rows) == 2, "只应收下 /content/ 文章链接,不含专题页"
    first = rows[0]
    assert first["title_en"].startswith("OpenAI launches")
    assert first["url"] == (
        "https://www.ft.com/content/aaaaaaaa-1111-2222-3333-444444444444"
    )
    assert first["published_at"] == "2026-08-18T09:30:00Z"
    assert first["keywords"] == ["AI agent"]


def test_merge_records_every_keyword_that_hit_the_same_article():
    rows: dict[str, dict] = {}
    ftsearch.merge(rows, ftsearch.parse_search_results(SEARCH_HTML, "AI agent"))
    fresh = ftsearch.merge(
        rows, ftsearch.parse_search_results(SEARCH_HTML, "AI coding")
    )
    assert fresh == 0
    merged = next(iter(rows.values()))
    assert merged["keywords"] == ["AI agent", "AI coding"]


def test_newest_first_keeps_undated_rows_last_instead_of_dropping_them():
    rows = [
        {"article_id": "a", "published_at": "2026-08-01T00:00:00Z"},
        {"article_id": "b", "published_at": ""},
        {"article_id": "c", "published_at": "2026-08-09T00:00:00Z"},
    ]
    assert [row["article_id"] for row in ftsearch.newest_first(rows)] == [
        "c",
        "a",
        "b",
    ]


def test_keyword_groups_cover_the_declared_vocabulary():
    everything = keywords.keywords_for("all")
    for word in ("AI agent", "AI coding", "enterprise AI", "AI chip", "GPU"):
        assert word in everything
    # 9-01 砍掉的九个词不许再出现:中文四词是填充重灾区,GitHub Copilot /
    # Cursor AI 命中的是播客广告读稿,另外三个短语被 FT 拆词宽松匹配。
    for word in ("智能体", "具身智能", "AI 应用", "AI 编程", "GitHub Copilot",
                 "Cursor AI", "foundation model", "retrieval augmented generation",
                 "inference cost"):
        assert word not in everything
    with pytest.raises(KeyError):
        keywords.keywords_for("不存在的组")


def _fake_listing(html: str):
    def fetch(url: str) -> tuple[str, str]:
        return html, url

    return fetch


def test_collect_survives_one_failing_keyword_and_says_so():
    def fetch(url: str) -> tuple[str, str]:
        if "boom" in url:
            raise RuntimeError("浏览器超时")
        return SEARCH_HTML, url

    rows, notes, _sources = run.collect(["boom", "AI agent"], fetch_listing=fetch, pace_seconds=0)
    assert len(rows) == 2
    assert any("浏览器超时" in note for note in notes)


def test_fetch_bodies_keeps_the_real_error_text():
    rows = ftsearch.parse_search_results(SEARCH_HTML, "AI agent")

    def fetch_body(row: dict) -> dict:
        raise RuntimeError("FT 返回的是付费墙拦截页")

    run.fetch_bodies(rows, fetch_body=fetch_body)
    assert "FT 返回的是付费墙拦截页" in rows[0]["body_error"]
    assert "付费墙拦截页" in render.render_article(rows[0])
    assert "暂无内容" not in render.render_article(rows[0])


def test_write_site_emits_index_and_one_page_per_article(tmp_path: Path):
    rows, _notes, _sources = run.collect(
        ["AI agent"], fetch_listing=_fake_listing(SEARCH_HTML), pace_seconds=0
    )
    run.fetch_bodies(
        rows,
        fetch_body=lambda row: {"body": "第一段\n第二段", "extractor": "test"},
    )
    index = run.write_site(
        rows, tmp_path, keywords=["AI agent"], generated_at="2026-08-19T10:00:00+08:00"
    )
    text = index.read_text(encoding="utf-8")
    assert "OpenAI launches" in text
    assert "2026-08-18T09:30:00Z" in text
    assert "https://www.ft.com/content/aaaaaaaa" in text
    body_page = (tmp_path / render.article_filename(rows[0])).read_text(encoding="utf-8")
    assert "<p>第一段</p><p>第二段</p>" in body_page


def test_render_escapes_titles_from_the_site():
    row = {
        "article_id": "x",
        "title_en": "<script>alert(1)</script>",
        "url": "https://www.ft.com/content/x",
        "published_at": "",
        "keywords": [],
    }
    html = render.render_index(
        [row], keywords=["AI"], generated_at="now"
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


# ---------------- 深挖:多页、时间窗、正序、凑数剔除 ----------------


def _page_html(article_id: str, title: str, published: str) -> str:
    return f"""
    <html><body><div class="o-teaser">
      <a href="/content/{article_id}">{title}</a>
      <time datetime="{published}">x</time>
    </div></body></html>
    """


def test_collect_walks_pages_and_stops_at_the_first_empty_one():
    seen: list[str] = []

    def fetch(url: str) -> tuple[str, str]:
        seen.append(url)
        if "page=1" in url:
            return _page_html("aaaaaaaa-1", "first page story about agents", "2026-08-10T00:00:00Z"), url
        if "page=2" in url:
            return _page_html("bbbbbbbb-2", "second page story about agents", "2026-08-09T00:00:00Z"), url
        return "<html><body></body></html>", url

    rows, notes, _sources = run.collect(
        ["AI agent"], pages=4, fetch_listing=fetch, pace_seconds=0
    )
    assert len(rows) == 2
    # 第 3 页 0 条即停,不该白开第 4 页(只数搜索页:专题页是另一条线)
    assert len([url for url in seen if "/search" in url]) == 3
    assert any("0 条,停止翻页" in note for note in notes)


def test_collect_since_filters_by_publication_time():
    def fetch(url: str) -> tuple[str, str]:
        if "page=1" not in url:
            return "<html></html>", url
        return (
            _page_html("aaaaaaaa-1", "新的那篇 recent one", "2026-08-18T00:00:00Z")
            + _page_html("bbbbbbbb-2", "旧的那篇 old one", "2024-01-05T00:00:00Z")
        ), url

    rows, notes, _sources = run.collect(
        ["AI agent"], fetch_listing=fetch, since="2026-08-01", pace_seconds=0
    )
    assert [row["article_id"] for row in rows] == ["aaaaaaaa-1"]
    assert any("之前剔除 1" in note for note in notes)


def test_collect_can_list_oldest_first():
    def fetch(url: str) -> tuple[str, str]:
        if "page=1" not in url:
            return "<html></html>", url
        return (
            _page_html("aaaaaaaa-1", "新的那篇 recent one", "2026-08-18T00:00:00Z")
            + _page_html("bbbbbbbb-2", "旧的那篇 older one", "2026-08-02T00:00:00Z")
        ), url

    rows, _notes, _sources = run.collect(
        ["AI agent"], fetch_listing=fetch, order="oldest", pace_seconds=0
    )
    assert [row["article_id"] for row in rows] == ["bbbbbbbb-2", "aaaaaaaa-1"]


def test_padding_is_counted_by_group_so_a_bullseye_hit_survives():
    """同一主题组内的多次命中是**真命中**的特征,不能当凑数删。"""
    rows = {
        # 四个词全命中,但都属于「通用组1」这一个语义组 → 留下
        "bullseye": {
            "article_id": "bullseye",
            "keywords": ["AI agent", "agentic AI", "AI coding", "embodied AI"],
        },
        # 横跨三个语义组 → 每个查询都返回它,是站方的填充稿
        "filler": {
            "article_id": "filler",
            "keywords": ["AI agent", "enterprise AI", "GPU"],
        },
    }
    dropped = ftsearch.drop_padding(
        rows, ["AI agent", "agentic AI", "enterprise AI", "AI chatbot", "GPU"]
    )
    assert dropped == ["filler"]
    assert "bullseye" in rows


def test_padding_does_not_judge_when_too_few_groups_were_searched():
    rows = {"x": {"article_id": "x", "keywords": ["AI agent", "agentic AI"]}}
    assert ftsearch.drop_padding(rows, ["AI agent", "agentic AI"]) == []
    assert "x" in rows


def test_limit_zero_means_no_truncation():
    def fetch(url: str) -> tuple[str, str]:
        if "page=1" not in url:
            return "<html></html>", url
        return "".join(
            _page_html(f"aaaaaaaa-{index}", f"a long enough headline number {index}", "2026-08-1"
                       f"{index}T00:00:00Z")
            for index in range(1, 6)
        ), url

    rows, _notes, _sources = run.collect(
        ["AI agent"], limit=0, fetch_listing=fetch, pace_seconds=0
    )
    assert len(rows) == 5


# ---------------- 命令行入口:整条接线走一遍 ----------------


def test_main_writes_the_site_end_to_end(tmp_path: Path, monkeypatch):
    """跑一次真正的 ``main()``。

    2026-08-19 的教训:``write_site`` 少了 ``order`` 形参,而 CLI 一直在传它 ——
    站长抓完 90 页搜索结果后在写盘那一步崩掉,一条都没留下。当时的用例只分别
    调 ``collect``/``write_site``,**从没跑过一次入口**,于是接线错误全程隐形。
    """
    monkeypatch.setattr(
        run, "_listing_fetcher_for", lambda site: lambda url: (SEARCH_HTML, url)
    )
    code = paywall_cli.main(
        [
            "--keyword", "AI agent",
            "--limit", "5",
            "--order", "oldest",
            "--no-body",
            "--out", str(tmp_path),
        ]
    )
    assert code == 0
    text = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "OpenAI launches" in text
    assert "正序(旧 → 新)" in text


def test_main_returns_nonzero_when_nothing_was_collected(tmp_path: Path, monkeypatch):
    """一条都没抓到时退出码非 0 —— 静默的「全绿」会让链路断了也没人知道。"""
    monkeypatch.setattr(
        run, "_listing_fetcher_for", lambda site: lambda url: ("<html></html>", url)
    )
    code = paywall_cli.main(
        ["--keyword", "AI agent", "--no-body", "--out", str(tmp_path)]
    )
    assert code == 1


def test_main_keeps_the_listing_when_body_fetching_blows_up(tmp_path: Path, monkeypatch):
    """清单先落盘:正文阶段整个炸掉,搜索那几十次浏览器打开的成果也不该丢。"""
    monkeypatch.setattr(
        run, "_listing_fetcher_for", lambda site: lambda url: (SEARCH_HTML, url)
    )

    def explode(*_args, **_kwargs):
        raise KeyboardInterrupt("站长按了 Ctrl-C")

    monkeypatch.setattr(run, "fetch_bodies", explode)
    with pytest.raises(KeyboardInterrupt):
        paywall_cli.main(["--keyword", "AI agent", "--out", str(tmp_path)])
    assert "OpenAI launches" in (tmp_path / "index.html").read_text(encoding="utf-8")


# ---------------- 爬取台账:爬过的不再爬 ----------------


def test_ledger_skips_articles_already_crawled(tmp_path: Path, monkeypatch):
    """第二轮:同样的搜索结果,一篇正文都不该再取。"""
    monkeypatch.setattr(
        run, "_listing_fetcher_for", lambda site: lambda url: (SEARCH_HTML, url)
    )
    fetched: list[str] = []

    def fake_body(row: dict) -> dict:
        fetched.append(row["article_id"])
        return {"body": "正文", "extractor": "test"}

    monkeypatch.setattr(run, "_body_fetcher_for", lambda site: fake_body)
    argv = ["--keyword", "AI agent", "--out", str(tmp_path)]

    assert paywall_cli.main(argv) == 0
    assert len(fetched) == 2

    fetched.clear()
    assert paywall_cli.main(argv) == 0
    assert fetched == [], "台账里有的不该再爬一次"
    # 新增为 0 是每小时一轮的常态:退出码 0,而且清单**照样列着库里那两篇** ——
    # 页面不会因为这一轮没新东西就清空。
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "本轮没有命中任何文章" not in index
    assert "OpenAI launches" in index and "Nvidia chip demand" in index


def test_ledger_does_not_record_listing_only_rows(tmp_path: Path, monkeypatch):
    """``--no-body`` 只取了标题,不该把这些篇永久封在「爬过」状态里。"""
    monkeypatch.setattr(
        run, "_listing_fetcher_for", lambda site: lambda url: (SEARCH_HTML, url)
    )
    fetched: list[str] = []
    monkeypatch.setattr(
        run,
        "_body_fetcher_for",
        lambda site: lambda row: (fetched.append(row["article_id"]), {"body": "正文"})[1],
    )
    out = ["--keyword", "AI agent", "--out", str(tmp_path)]

    assert paywall_cli.main([*out, "--no-body"]) == 0
    assert paywall_cli.main(out) == 0
    assert len(fetched) == 2, "只列过清单的稿子,后面仍要能取正文"


def test_ledger_treats_a_changed_url_as_a_new_article():
    entries = {"abc": {"url": "https://www.ft.com/content/abc"}}
    same = {"article_id": "abc", "url": "https://www.ft.com/content/abc"}
    moved = {"article_id": "abc", "url": "https://www.ft.com/content/abc-2"}
    assert ledger_store.is_seen(entries, same)
    assert not ledger_store.is_seen(entries, moved)


def test_ledger_refuses_to_erase_a_corrupted_file(tmp_path: Path):
    """损坏不能冒充空账；否则下一轮会用局部新账覆盖全部历史。"""
    path = tmp_path / "ledger.json"
    path.write_text("{ 半截的 json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="状态文件损坏"):
        ledger_store.load(path)


def test_ledger_recovers_the_previous_atomic_snapshot(tmp_path: Path):
    path = tmp_path / "ledger.json"
    ledger_store.save(path, {"old": {"url": "https://example.com/old"}})
    ledger_store.save(path, {"new": {"url": "https://example.com/new"}})
    path.write_text("truncated", encoding="utf-8")
    assert set(ledger_store.load(path)) == {"old"}


def test_ledger_records_failed_bodies_so_they_are_not_retried_forever(tmp_path: Path):
    entries: dict = {}
    rows = [
        {"article_id": "ok", "url": "u1", "body": "正文"},
        {"article_id": "bad", "url": "u2", "body_error": "付费墙拦截页"},
        {"article_id": "listing", "url": "u3"},
    ]
    ledger_store.record(entries, rows, crawled_at="2026-08-20T00:00:00+00:00")
    assert set(entries) == {"ok", "bad"}
    assert entries["bad"]["body_status"] == "failed"


# ---------------- 分析页与首页筛选 ----------------

_STATS_ROWS = [
    {
        "article_id": "a",
        "title_en": "Rewiring sport: how technology helps athletes",
        "url": "https://www.ft.com/content/a",
        "published_at": "2026-07-01T04:00:00+0000",
        "keywords": ["humanoid robot", "AI chip"],
        "body": "正文",
    },
    {
        "article_id": "b",
        "title_en": "Nvidia discloses stake in SpaceX",
        "url": "https://www.ft.com/content/b",
        "published_at": "2026-08-14T00:00:00Z",
        "keywords": ["GPU"],
        "body_error": "付费墙拦截页",
    },
    {
        "article_id": "c",
        "title_en": "An article with no date at all",
        "url": "https://www.ft.com/content/c",
        "published_at": "",
        "keywords": ["AI agent"],
    },
]


def test_stats_count_only_structural_facts():
    summary = stats.summary(_STATS_ROWS)
    assert dict(summary["语义组"])["模型应用 · 通用组1"] == 2
    # humanoid robot 与 AI chip 分属两组,这一篇在两组里各算一次
    assert dict(summary["语义组"])["AI 芯片 · GPU/CPU"] == 2
    assert dict(summary["发布月份"]) == {
        "2026-07": 1,
        "2026-08": 1,
        "时间未知": 1,
    }
    assert dict(summary["正文状态"]) == {
        "已取到正文": 1,
        "取正文失败": 1,
        "只有清单": 1,
    }
    assert dict(summary["一篇命中几个词"]) == {"1 个词": 2, "2 个词": 1}


def test_index_and_dashboard_link_to_each_other(tmp_path: Path):
    """两页互相到得了。分析那几张表现在住在后台里 —— 见「后台吸收关键词分析」。"""
    run.write_site(
        _STATS_ROWS,
        tmp_path,
        keywords=["AI agent"],
        generated_at="2026-08-20T10:00:00+08:00",
    )
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    page = (tmp_path / "dashboard.html").read_text(encoding="utf-8")
    assert 'href="dashboard.html"' in index
    assert 'href="index.html"' in page
    assert "一篇命中几个词" in page


def test_published_editorial_reference_contains_no_private_body_or_error(tmp_path: Path):
    row = {
        "article_id": "private", "url": "https://www.ft.com/content/private",
        "title_en": "OpenAI builds a data center", "published_at": "2026-09-03",
        "body": "付费正文绝不能进入投影", "body_status": "ok",
        "body_error": "含内部诊断的失败原话", "score": 70, "keywords": ["OpenAI"],
    }
    run.write_site([row], tmp_path, keywords=["OpenAI"], generated_at="now")
    raw = (tmp_path / "editorial-reference.json").read_text(encoding="utf-8")
    payload = json.loads(raw)
    assert payload["articles"][0] == {
        "title": row["title_en"], "published_at": row["published_at"],
        "score": 70, "body_status": "ok",
    }
    assert row["body"] not in raw and row["body_error"] not in raw


def test_index_carries_filter_metadata_for_every_row(tmp_path: Path):
    """筛选靠每行自带的语义组与检索文本,没有它就只是个死清单。"""
    run.write_site(
        _STATS_ROWS,
        tmp_path,
        keywords=["AI agent"],
        generated_at="now",
    )
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert index.count("data-groups=") == len(_STATS_ROWS)
    assert "rewiring sport" in index  # data-search 用小写,便于不区分大小写匹配
    assert 'id="q"' in index and 'class="stream"' in index


def test_limit_applies_after_the_ledger_so_the_crawl_advances(tmp_path: Path, monkeypatch):
    """``--limit`` 截断的是**新增**,不是命中。

    2026-08-20:截断原先发生在剔台账之前 —— 每轮都是同样那 N 篇最旧的,
    全在台账里,于是「新增 0」永远为 0,第 N+1 篇永远轮不到。
    """
    pages = "".join(
        _page_html(f"aaaaaaaa-{index}", f"headline number {index} about agents",
                   f"2026-08-{index:02d}T00:00:00Z")
        for index in range(1, 6)
    )
    monkeypatch.setattr(run, "_listing_fetcher_for", lambda site: lambda url: (pages, url))
    done: list[str] = []
    monkeypatch.setattr(
        run,
        "_body_fetcher_for",
        lambda site: lambda row: (done.append(row["article_id"]), {"body": "正文"})[1],
    )
    argv = ["--keyword", "AI agent", "--limit", "2", "--order", "oldest",
            "--out", str(tmp_path)]

    assert paywall_cli.main(argv) == 0
    assert done == ["aaaaaaaa-1", "aaaaaaaa-2"]

    done.clear()
    assert paywall_cli.main(argv) == 0
    assert done == ["aaaaaaaa-3", "aaaaaaaa-4"], "第二轮要接着往下走,而不是原地打转"


def test_write_site_emits_the_shared_stylesheet(tmp_path: Path):
    """页面 `<link>` 了 site.css,产出目录里就必须真有这个文件 ——
    少一个文件不会让任何一步报错,只会让站点在浏览器里变成裸 HTML。"""
    rows, _notes, _sources = run.collect(
        ["AI agent"], fetch_listing=_fake_listing(SEARCH_HTML), pace_seconds=0
    )
    index = run.write_site(
        rows, tmp_path, keywords=["AI agent"], generated_at="2026-08-20T10:00:00+08:00"
    )
    assert render.STYLESHEET_NAME in index.read_text(encoding="utf-8")
    assert (tmp_path / render.STYLESHEET_NAME).read_text(encoding="utf-8").strip()
    article = (tmp_path / render.article_filename(rows[0])).read_text(encoding="utf-8")
    assert render.STYLESHEET_NAME in article


# ---------------- 累积库:清单列全部爬过的,不只是本轮 ----------------


def test_ledger_remembers_what_the_index_needs_to_redraw_a_row():
    """台账要能独自重画一行清单:标题、时间、关键词、正文状态。

    少一样都会让累积库退化 —— 上一轮的稿子只剩个链接,分不了组也筛不了。
    """
    entries: dict[str, dict] = {}
    ledger_store.record(
        entries,
        [{
            "article_id": "aaaa",
            "url": "https://www.ft.com/content/aaaa",
            "title_en": "an agent story",
            "description": "A concise AI infrastructure summary.",
            "published_at": "2026-08-18T09:30:00Z",
            "keywords": ["AI agent", "AI coding"],
            "section": "Technology",
            "body": "正文",
        }],
        crawled_at="2026-08-20T00:00:00+08:00",
    )
    row = ledger_store.rows(entries)[0]
    assert row["title_en"] == "an agent story"
    assert row["description"] == "A concise AI infrastructure summary."
    assert row["keywords"] == ["AI agent", "AI coding"]
    assert row["section"] == "Technology"
    assert row["published_at"] == "2026-08-18T09:30:00Z"
    assert row["body_status"] == "ok"


def test_ledger_merge_discovery_refreshes_nonempty_description_on_same_url():
    entries = {
        "aaaa": {
            "url": "https://www.ft.com/content/aaaa",
            "title": "an agent story",
            "description": "Old summary.",
            "body_status": "ok",
        }
    }
    changed = ledger_store.merge_discovery(
        entries,
        [{
            "article_id": "aaaa",
            "url": "https://www.ft.com/content/aaaa?utm_source=listing",
            "title_en": "an agent story",
            "description": "New AI infrastructure summary.",
        }],
    )
    assert changed == 1
    assert ledger_store.rows(entries)[0]["description"] == (
        "New AI infrastructure summary."
    )


def test_library_rows_prefers_ledger_description_for_the_same_url():
    entries = {
        "aaaa": {
            "url": "https://www.ft.com/content/aaaa",
            "title": "an agent story",
            "description": "Latest AI infrastructure summary.",
            "published_at": "2026-08-18T09:30:00Z",
            "body_status": "ok",
        }
    }
    archived = [{
        "article_id": "aaaa",
        "url": "https://www.ft.com/content/aaaa?utm_source=archive",
        "title_en": "an agent story",
        "description": "Stale summary from the original crawl.",
        "published_at": "2026-08-18T09:30:00Z",
        "body": "正文",
    }]
    library = run.library_rows(entries, archived)
    assert library[0]["description"] == "Latest AI infrastructure summary."
    assert archived[0]["description"] == "Latest AI infrastructure summary."


def test_index_lists_the_whole_library_while_pages_are_written_only_for_this_round(tmp_path: Path):
    """每小时跑一轮时,清单必须是**累积**的:这轮 1 篇,页面上要有 2 篇。

    正文页只给本轮这篇写 —— 上一轮那篇的 HTML 已经在盘上,重写要么得重新
    出网取一次正文,要么就是拿空正文把它盖掉。
    """
    old = {
        "article_id": "old-1",
        "url": "https://www.ft.com/content/old-1",
        "title_en": "yesterday chips story",
        "published_at": "2026-08-18T09:30:00Z",
        "keywords": ["AI chip"],
        "body_status": "ok",
    }
    fresh = {
        "article_id": "new-1",
        "url": "https://www.ft.com/content/new-1",
        "title_en": "today agent story",
        "published_at": "2026-08-19T09:30:00Z",
        "keywords": ["AI agent"],
        "body": "正文",
    }
    index = run.write_site(
        [fresh],
        tmp_path,
        keywords=["AI agent"],
        generated_at="now",
        library=[fresh, old],
    )
    text = index.read_text(encoding="utf-8")
    assert "today agent story" in text
    assert "yesterday chips story" in text
    assert (tmp_path / render.article_filename(fresh)).exists()
    assert not (tmp_path / render.article_filename(old)).exists()
    # 库里那篇正文取到过,清单上就不该挂「正文未取到」的红标
    assert text.count("正文未取到") == 0


def test_render_reads_body_status_from_the_ledger_row(tmp_path: Path):
    """上一轮取正文失败的那篇,重画时红标要还在 —— 失败不能因为换了一轮就消失。"""
    html = render.render_index(
        [{
            "article_id": "old-2",
            "url": "https://www.ft.com/content/old-2",
            "title_en": "a walled story",
            "published_at": "2026-08-18T09:30:00Z",
            "keywords": [],
            "body_status": "failed",
        }],
        keywords=["AI"],
        generated_at="now",
    )
    assert "正文未取到" in html


# ---------------- 时间硬地板:2025-01-01 之前的一律不抓 ----------------


def test_collect_never_returns_anything_older_than_the_hard_floor():
    """硬地板不靠人记得传 `--since`。

    2026-08-21:站长少传了一次 `--since`,积压从 276 涨到 1370 —— 一个「永远不做
    的事」如果只写在命令行习惯里,它就总有一天不生效。
    """
    def fetch(url: str) -> tuple[str, str]:
        if "page=1" not in url:
            return "<html></html>", url
        return (
            _page_html("aaaaaaaa-1", "recent story about agents", "2026-08-18T00:00:00Z")
            + _page_html("bbbbbbbb-2", "ancient story about agents", "2024-06-01T00:00:00Z")
        ), url

    rows, notes, _sources = run.collect(["AI agent"], fetch_listing=fetch, pace_seconds=0)
    assert [row["article_id"] for row in rows] == ["aaaaaaaa-1"]
    assert any(ftsearch.EARLIEST in note for note in notes)


def test_since_can_narrow_the_window_but_never_widen_it_past_the_floor():
    def fetch(url: str) -> tuple[str, str]:
        if "page=1" not in url:
            return "<html></html>", url
        return _page_html("bbbbbbbb-2", "ancient story about agents", "2024-06-01T00:00:00Z"), url

    rows, _notes, _sources = run.collect(
        ["AI agent"], fetch_listing=fetch, since="2020-01-01", pace_seconds=0
    )
    assert rows == [], "比硬地板更早的 --since 不该放宽窗口"


# ---------------- 正文存档:文本单独留一份,全站可重渲染 ----------------


def test_archive_keeps_the_body_text_so_the_site_can_be_redrawn(tmp_path: Path):
    """正文只以 HTML 存在时,换版式就得重爬一次。存档是为了不再有这回事。"""
    rows = [{
        "article_id": "aaaa", "url": "https://www.ft.com/content/aaaa",
        "title_en": "an agent story", "published_at": "2026-08-18T09:30:00Z",
        "description": "A concise AI infrastructure summary.",
        "keywords": ["AI agent"], "section": "Technology",
        "body": "第一段\n第二段", "extractor": "test",
    }]
    run.write_site(rows, tmp_path, keywords=["AI agent"], generated_at="now")
    restored = archive.load(tmp_path)
    assert len(restored) == 1
    assert restored[0]["body"] == "第一段\n第二段"
    assert restored[0]["keywords"] == ["AI agent"]
    assert restored[0]["title_en"] == "an agent story"
    assert restored[0]["description"] == "A concise AI infrastructure summary."


def test_render_only_redraws_every_page_without_going_out(tmp_path: Path, monkeypatch):
    """`--render-only` 一个请求都不该发:它的全部输入就是盘上的存档。"""
    rows = [{
        "article_id": "aaaa", "url": "https://www.ft.com/content/aaaa",
        "title_en": "an agent story", "published_at": "2026-08-18T09:30:00Z",
        "keywords": ["AI agent"], "section": "Technology", "body": "第一段\n第二段",
    }]
    run.write_site(rows, tmp_path, keywords=["AI agent"], generated_at="now")
    page_path = tmp_path / render.article_filename(rows[0])
    page_path.unlink()
    failed = {
        "article_id": "bbbb", "url": "https://www.ft.com/content/bbbb",
        "title_en": "OpenAI agent deployment fails security review",
        "published_at": "2026-08-19T09:30:00Z", "keywords": ["AI agent"],
        "section": "Technology", "body_error": "测试中的明确失败原因",
    }
    entries: dict[str, dict] = {}
    ledger_store.record(entries, [failed], crawled_at="2026-08-19T10:00:00Z")
    ledger_store.save(ledger_store.path_for(tmp_path), entries)
    failed_path = tmp_path / render.article_filename(failed)
    assert not failed_path.exists()

    def boom(*_args, **_kwargs):
        raise AssertionError("--render-only 不该出网")

    monkeypatch.setattr(run, "_listing_fetcher_for", lambda site: boom)
    monkeypatch.setattr(run, "_body_fetcher_for", lambda site: boom)
    assert paywall_cli.main(["--render-only", "--out", str(tmp_path)]) == 0
    page = page_path.read_text(encoding="utf-8")
    assert "第一段" in page, "正文页应该从存档重画出来,而不是空着"
    assert "an agent story" in (tmp_path / "index.html").read_text(encoding="utf-8")
    failed_page = failed_path.read_text(encoding="utf-8")
    assert "测试中的明确失败原因" in failed_page
    assert '<a class="back" href="../../index.html">' in failed_page
    assert '<a class="back" href="index.html">' not in failed_page


# ---------------- 跑批记录:链路断了要看得见 ----------------


def test_runlog_keeps_the_last_rounds_and_counts_consecutive_failures(tmp_path: Path):
    log = tmp_path / "runs.json"
    runlog.record(log, {"finished_at": "2026-08-21T01:00:00+08:00", "ok": True, "new": 20})
    runlog.record(log, {"finished_at": "2026-08-21T02:00:00+08:00", "ok": False, "error": "登录态失效"})
    runlog.record(log, {"finished_at": "2026-08-21T03:00:00+08:00", "ok": False, "error": "登录态失效"})
    entries = runlog.load(log)
    assert len(entries) == 3
    assert runlog.consecutive_failures(entries) == 2
    assert "登录态失效" in runlog.last_error(entries)


# ---------------- dashboard ----------------


def test_dashboard_shows_every_title_with_its_body_status(tmp_path: Path):
    """后台要的是「标题 + 有没有取到正文」,一眼扫完,不用翻日志。"""
    rows = [
        {"article_id": "a", "title_en": "story one", "url": "https://www.ft.com/content/a",
         "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip"], "body_status": "ok"},
        {"article_id": "b", "title_en": "story two", "url": "https://www.ft.com/content/b",
         "published_at": "2026-08-17T09:30:00Z", "keywords": ["AI agent"],
         "body_status": "failed", "body_error": "FT 返回的是付费墙拦截页"},
    ]
    html = render.render_dashboard(
        rows, generated_at="now", keywords=["AI chip", "AI agent"], runs=[], notes=[],
        floor=ftsearch.EARLIEST,
    )
    assert "story one" in html and "story two" in html
    # 失败要带原话,不能被兜底文案顶掉
    assert "FT 返回的是付费墙拦截页" in html
    assert "2025-01-01" in html, "要看得见还差多远到硬地板"


# ---------------- 第二条召回线:FT 专题页 ----------------


def test_topic_label_is_never_used_as_a_search_query():
    """「FT 专题」是一条召回线的名字,不是一个搜索词。

    它混进搜索词表的话,程序会老老实实去 FT 搜索框里搜「FT 专题」四个汉字。
    """
    assert keywords.TOPIC_LABEL not in keywords.keywords_for("all")
    assert keywords.group_of(keywords.TOPIC_LABEL) == "FT 专题页"


def test_collect_merges_hub_pages_with_the_keyword_search():
    """分类页是编辑判定的「这是 AI 稿」,和关键词匹配是两套逻辑,要合并去重。"""
    def fetch(url: str) -> tuple[str, str]:
        if "/search" in url and "page=1" in url:
            return _page_html("aaaaaaaa-1", "found by keyword search", "2026-08-18T00:00:00Z"), url
        if "artificial-intelligence" in url:
            return (
                _page_html("aaaaaaaa-1", "found by keyword search", "2026-08-18T00:00:00Z")
                + _page_html("cccccccc-3", "only the editors filed this one", "2026-08-17T00:00:00Z")
            ), url
        return "<html></html>", url

    rows, notes, _sources = run.collect(["AI agent"], fetch_listing=fetch, pace_seconds=0)
    ids = [row["article_id"] for row in rows]
    assert "cccccccc-3" in ids, "分类页独有的稿子该被收进来"
    assert ids.count("aaaaaaaa-1") == 1, "两条线都命中的同一篇只能有一条"
    both = next(row for row in rows if row["article_id"] == "aaaaaaaa-1")
    assert keywords.AI_HUB_LABEL in both["keywords"] and "AI agent" in both["keywords"]
    assert {tuple(sorted(origin.items())) for origin in both["origins"]} == {
        (("kind", "hub"), ("name", "artificial-intelligence")),
        (("kind", "search"), ("name", "AI agent")),
    }
    assert any("分类" in note for note in notes)


# ---------------- 召回来源记账:哪条路值不值,让数据说 ----------------


def test_collect_reports_cost_and_yield_per_source():
    """每条召回线各自记账:开了几页(成本)、命中几篇、首次带来几篇(价值)。

    站长的猜想是「站内搜索比分类页高效」。这个模块不替他下结论 —— 它只保证
    **判断这件事所需要的数字每轮都被记下来**,几周之后回头看真账。
    """
    def fetch(url: str) -> tuple[str, str]:
        if "/search" in url and "page=1" in url:
            return _page_html("aaaaaaaa-1", "found by the keyword lane", "2026-08-18T00:00:00Z"), url
        if "artificial-intelligence" in url:
            return (
                _page_html("aaaaaaaa-1", "found by the keyword lane", "2026-08-18T00:00:00Z")
                + _page_html("cccccccc-3", "only the hub had this one", "2026-08-17T00:00:00Z")
            ), url
        return "<html></html>", url

    rows, _notes, sources = run.collect(["AI agent"], fetch_listing=fetch, pace_seconds=0)
    by_name = {source["name"]: source for source in sources}
    assert by_name["AI agent"]["kind"] == "search"
    assert by_name["AI agent"]["first"] == 1
    hub = by_name["artificial-intelligence"]
    assert hub["kind"] == "hub"
    # 两篇都命中了,但只有一篇是这条线**先**带来的 —— 另一篇搜索已经拿到了
    assert hub["hits"] == 2 and hub["first"] == 1
    assert by_name["AI agent"]["pages"] == 1 and hub["pages"] == 1
    # 空手而归的那几条线也要有账 —— 「开了 0 页」和「没这条线」不是一回事
    # (technology / cyber-security 已下架,见 sites/ft.py 的 HUBS)
    assert by_name["semiconductors"]["hits"] == 0
    assert {row["found_via"] for row in rows} == {"AI agent", "artificial-intelligence"}


def test_every_declared_hub_is_walked():
    """四个分类页都是站长在浏览器里核对过的路径,一个都不该被漏掉。"""
    seen: list[str] = []

    def fetch(url: str) -> tuple[str, str]:
        seen.append(url)
        return "<html></html>", url

    run.collect(["AI agent"], fetch_listing=fetch, pace_seconds=0)
    for slug in ftsearch.HUBS:
        assert any(f"/{slug}?" in url for url in seen), f"没有走 {slug}"


def test_dashboard_ranks_sources_by_pages_spent_per_new_article():
    """后台要能回答「哪条路每开一页换来几篇新稿」—— 那是成本与价值的比值。"""
    runs = [{
        "finished_at": "2026-08-21T01:00:00+08:00", "ok": True, "new": 3,
        "sources": [
            {"name": "AI agent", "kind": "search", "pages": 5, "hits": 90, "first": 4, "ledger_new": 2},
            {"name": "semiconductors", "kind": "hub", "pages": 5, "hits": 40, "first": 1, "ledger_new": 1},
        ],
    }]
    html = render.render_dashboard(
        [], generated_at="now", keywords=["AI agent"], runs=runs, notes=[], floor="2025-01-01"
    )
    assert "semiconductors" in html and "AI agent" in html
    assert "每页新增" in html


# ---------------- 本轮记录:留原话,但别把页面淹了 ----------------


def test_failed_notes_always_say_shibai():
    """失败的记录里必须有「失败」两个字 —— 渲染层靠它把失败挑出来单独放。"""
    def fetch(url: str) -> tuple[str, str]:
        raise RuntimeError("日常 Chrome 文章列表读取失败:tab id 没了")

    _rows, notes, _sources = run.collect(["AI agent"], fetch_listing=fetch, pace_seconds=0)
    assert any("失败" in note for note in notes)
    assert any("tab id 没了" in note for note in notes), "原话不能被兜底文案顶掉"


def test_run_log_collapses_the_routine_lines_but_surfaces_failures():
    """一轮上百条记录不该整片摊在页顶。

    失败留在外面(那是要被看见的),其余折叠起来 —— 但一条都不能少。
    """
    notes = [
        "「AI agent」第 1 页失败:日常 Chrome 文章列表读取失败",
        "「AI agent」268 命中 / 156 新 / 5 页",
        "「GPU」214 命中 / 83 新 / 4 页",
    ]
    html = render.render_dashboard([], generated_at="now", keywords=[], runs=[],
                                    notes=notes, floor="2025-01-01")
    for note in notes:
        assert escape(note) in html, "记录一条都不能丢"
    # 只看「本轮记录」这一块:页面上别处也有折叠(比如全部标题那张表)
    log = html[html.index('class="log"'):]
    assert "<details" in log, "常规记录要折叠"
    fold = log.index("<details")
    assert log.index(escape(notes[0])) < fold, "失败要留在折叠外面"
    assert log.index(escape(notes[1])) > fold, "常规记录在折叠里"


def test_dashboard_keeps_the_run_log_out_of_the_way():
    """后台第一眼要是链路和明细,不是本轮日志 —— 日志排在牌面后面。"""
    html = render.render_dashboard(
        [], generated_at="now", keywords=["AI agent"], runs=[],
        notes=["「AI agent」268 命中 / 156 新 / 5 页"], floor="2025-01-01",
    )
    assert html.index('class="board"') < html.index("本轮记录")


# ---------------- 产出目录的形状 ----------------


def test_article_pages_live_under_a_dated_folder():
    """正文页按「年-月」分层,文件名保持 uuid —— uuid 是站方给的唯一身份。"""
    row = {"article_id": "aaaaaaaa-1", "title_en": "t", "url": "https://www.ft.com/content/a",
           "published_at": "2026-08-18T09:30:00Z", "keywords": []}
    assert render.article_filename(row) == "p/2026-08/aaaaaaaa-1.html"


def test_undated_articles_get_their_own_folder_not_a_guessed_month():
    """读不到时间就归到 undated —— 不拿抓取时间凑一个月份出来。"""
    row = {"article_id": "bbbbbbbb-2", "title_en": "t", "url": "https://www.ft.com/content/b",
           "published_at": "", "keywords": []}
    assert render.article_filename(row) == "p/undated/bbbbbbbb-2.html"


def test_article_page_links_back_up_to_the_shared_stylesheet(tmp_path: Path):
    """正文页深了两层,样式表和「回到清单」都得是能走通的相对路径。"""
    row = {"article_id": "aaaaaaaa-1", "title_en": "t", "url": "https://www.ft.com/content/a",
           "published_at": "2026-08-18T09:30:00Z", "keywords": [], "body": "hi"}
    html = render.render_article(row)
    assert f'href="../../site.css?v={render.STYLESHEET_FINGERPRINT}"' in html
    assert html.count('<a class="back" href="../../index.html">') == 2
    assert 'href="index.html"' not in html
    run.write_site([row], tmp_path, keywords=[], generated_at="now")
    page = tmp_path / "p" / "2026-08" / "aaaaaaaa-1.html"
    assert page.is_file()
    assert (page.parent / "../../site.css").resolve() == (tmp_path / "site.css").resolve()


def test_crawl_state_lives_under_data(tmp_path: Path):
    """台账、跑批记录、正文存档都是抓取的内部状态,收进 data/ 一处。"""
    assert ledger_store.path_for(tmp_path) == tmp_path / "data" / "ledger.json"
    assert runlog.path_for(tmp_path) == tmp_path / "data" / "runs.json"
    assert archive.dir_for(tmp_path) == tmp_path / "data" / "articles"


def test_state_from_the_old_flat_layout_is_adopted_not_orphaned(tmp_path: Path):
    """老布局里的台账不能就地变成孤儿 —— 那等于把爬过的几百篇忘光,全部重爬。"""
    (tmp_path / "ledger.json").write_text('{"version": 2, "entries": {"a": {"url": "u"}}}',
                                          encoding="utf-8")
    (tmp_path / "articles").mkdir()
    (tmp_path / "articles" / "a.json").write_text('{"article_id": "a", "body": "hi"}',
                                                  encoding="utf-8")
    assert ledger_store.load(ledger_store.path_for(tmp_path)) == {"a": {"url": "u"}}
    assert [row["article_id"] for row in archive.load(tmp_path)] == ["a"]
    assert not (tmp_path / "ledger.json").exists(), "搬过去之后旧的不该还留着"


# ---------------- 后台:看图,不看一大段字 ----------------


def _dash_rows() -> list[dict[str, Any]]:
    return [
        {"article_id": f"aaaaaaaa-{n}", "title_en": f"story {n}",
         "url": f"https://www.ft.com/content/{n}", "published_at": "2026-08-18T09:30:00Z",
         "keywords": ["AI chip"], "body_status": "ok"}
        for n in range(3)
    ]


def test_dashboard_leads_with_numbers_and_charts_not_paragraphs():
    """后台第一屏是指标条和图,明细与日志都收在折叠里。"""
    html = render.render_dashboard(
        _dash_rows(), generated_at="now", keywords=["AI chip"],
        runs=[{"finished_at": "now", "ok": True, "new": 2, "hits": 9, "backlog": 4,
               "processed": 2, "sources": []}],
        notes=["「AI chip」9 命中 / 2 新 / 5 页"], floor="2025-01-01",
    )
    kpis = html.index('class="kpis"')
    assert kpis < html.index('class="board"'), "指标条在最上面"
    assert html.index('class="board"') < html.index("本轮记录"), "日志在最后"
    # 明细那一长串标题折起来,不再占掉整个第一屏
    detail = html.index("全部标题")
    assert html.rindex("<details", 0, detail) > html.index('class="board"')


def test_dashboard_body_status_is_a_bar_not_three_sentences():
    """正文状态画成一条堆叠条:三个数一眼比得出来。"""
    rows = _dash_rows() + [
        {"article_id": "cccccccc-9", "title_en": "bad", "url": "https://www.ft.com/content/9",
         "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip"],
         "body_status": "failed", "body_error": "拦截页"},
    ]
    html = render.render_dashboard(rows, generated_at="now", keywords=["AI chip"],
                                   runs=[], notes=[], floor="2025-01-01")
    assert 'class="stack"' in html
    assert "拦截页" in html, "失败原话不能被图表吃掉"


# ---------------- 正文页没了的那些:不许链到 404 ----------------


def test_index_does_not_link_to_a_page_that_is_not_on_disk(tmp_path: Path):
    """库里有、但本地没有正文页的那几篇,标题不能还是个本地链接。

    2026-08-22:存档上线之前爬的 23 篇正文只存在于 HTML 里,重画时画不出来,
    清单却照旧链过去 —— 点进去 404。清单必须**照实**说这一页不在本地。
    """
    archived = {"article_id": "aaaa", "url": "https://www.ft.com/content/a",
                "title_en": "有页面的那篇", "published_at": "2026-08-18T09:30:00Z",
                "keywords": ["AI chip"], "body": "正文"}
    lost = {"article_id": "bbbb", "url": "https://www.ft.com/content/b",
            "title_en": "正文页没了的那篇", "published_at": "2026-08-17T09:30:00Z",
            "keywords": ["AI agent"], "body_status": "ok"}
    run.write_site([archived], tmp_path, keywords=[], generated_at="now",
                   library=[archived, lost])
    text = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert render.article_filename(archived) in text
    assert render.article_filename(lost) not in text, "没有的页面不该出现在链接里"
    assert "正文页没了的那篇" in text, "但这一篇本身还得在清单上"
    assert "无本地页" in text


def test_refill_finds_what_the_ledger_claims_but_the_archive_lacks(tmp_path: Path):
    """台账说爬过、存档里却没有的,就是要补的那些。"""
    entries = {
        "aaaa": {"url": "https://www.ft.com/content/a", "body_status": "ok"},
        "bbbb": {"url": "https://www.ft.com/content/b", "body_status": "ok"},
        "cccc": {"url": "https://www.ft.com/content/c", "body_status": "skipped"},
    }
    archive.save(tmp_path, [{"article_id": "aaaa", "url": "u", "body": "有正文"}])
    missing = run.missing_from_archive(entries, tmp_path)
    assert [row["article_id"] for row in missing] == ["bbbb"], (
        "只补台账说取到过、存档里却没有的;没取过正文的不算缺"
    )
    assert missing[0]["url"] == "https://www.ft.com/content/b"


def test_refill_repairs_the_hole_and_leaves_the_rest_alone(tmp_path: Path, monkeypatch):
    """`--refill` 只去取缺的那几篇,取回来落进存档,页面跟着重画出来。"""
    ledger_store.save(ledger_store.path_for(tmp_path), {
        "aaaa": {"url": "https://www.ft.com/content/aaaa", "title": "缺正文的那篇",
                 "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip"],
                 "body_status": "ok"},
    })
    asked: list[str] = []

    def fake_body(row: dict) -> dict:
        asked.append(row["url"])
        return {"body": "补回来的正文", "extractor": "假的"}

    monkeypatch.setattr(run, "_body_fetcher_for", lambda site: fake_body)
    monkeypatch.setattr(run, "_listing_fetcher_for",
                        lambda site: lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("--refill 不搜索")))
    assert paywall_cli.main(["--refill", "--out", str(tmp_path)]) == 0
    assert asked == ["https://www.ft.com/content/aaaa"]
    stored = archive.load(tmp_path)
    assert [row["article_id"] for row in stored] == ["aaaa"]
    assert "补回来的正文" in stored[0]["body"]
    page = tmp_path / render.article_filename({"article_id": "aaaa",
                                               "published_at": "2026-08-18T09:30:00Z"})
    assert "补回来的正文" in page.read_text(encoding="utf-8")


def test_stylesheet_link_carries_a_fingerprint_of_its_content():
    """样式表链接带内容指纹,改了版式浏览器才会真的去取新的。

    2026-08-22:后台改完发布上去,站长看到的还是旧版式 —— HTML 是新的,
    `site.css` 被浏览器和 Caddy 按老路径缓存着。**改了却看不见** 比没改更坏:
    人会以为是代码没生效,回头去查一个根本不存在的 bug。
    """
    html = render.render_index([], keywords=[], generated_at="now")
    assert f"{render.STYLESHEET_NAME}?v={render.STYLESHEET_FINGERPRINT}" in html
    assert len(render.STYLESHEET_FINGERPRINT) >= 8
    # 指纹跟着内容走:内容没变,指纹就不该变(否则每次发布都白白让缓存失效)
    assert render.STYLESHEET_FINGERPRINT == render._fingerprint(render.STYLESHEET)
    assert render._fingerprint(render.STYLESHEET + " ") != render.STYLESHEET_FINGERPRINT


def test_article_page_stylesheet_is_fingerprinted_too(tmp_path: Path):
    """正文页深两层,指纹和相对前缀都得在。"""
    row = {"article_id": "aaaa", "title_en": "t", "url": "https://www.ft.com/content/a",
           "published_at": "2026-08-18T09:30:00Z", "keywords": [], "body": "hi"}
    html = render.render_article(row)
    assert f'href="../../{render.STYLESHEET_NAME}?v={render.STYLESHEET_FINGERPRINT}"' in html


# ---------------- 后台吸收关键词分析:两页本来就是一件事 ----------------


def test_dashboard_carries_every_distribution_the_stats_page_used_to():
    """语义组 / 关键词 / 发布月份 / 正文状态 / 一篇命中几个词 —— 一个都不能少。"""
    rows = [
        {"article_id": "aaaa", "title_en": "one", "url": "https://www.ft.com/content/a",
         "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip", "GPU"],
         "body_status": "ok"},
        {"article_id": "bbbb", "title_en": "two", "url": "https://www.ft.com/content/b",
         "published_at": "2026-07-18T09:30:00Z", "keywords": ["AI agent"],
         "body_status": "failed", "body_error": "拦截页"},
    ]
    html = render.render_dashboard(rows, generated_at="now", keywords=["AI chip"],
                                   runs=[], notes=[], floor="2025-01-01")
    for title in stats.summary(rows):
        assert title in html, f"「{title}」这张表没搬过来"
    assert "2026-07" in html and "2026-08" in html


def test_the_site_no_longer_ships_a_separate_stats_page(tmp_path: Path):
    """两页合成一页之后,就不该再留一个半新不旧的 stats.html 在那里。"""
    rows = [{"article_id": "aaaa", "title_en": "t", "url": "https://www.ft.com/content/a",
             "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip"], "body": "正文"}]
    index = run.write_site(rows, tmp_path, keywords=["AI chip"], generated_at="now")
    assert not (tmp_path / "stats.html").exists()
    text = index.read_text(encoding="utf-8")
    assert "stats.html" not in text, "清单页不该再链到一个不存在的页面"
    assert text.count("dashboard.html") >= 1


def test_dashboard_says_how_long_since_the_last_round(tmp_path: Path):
    """「上一轮是什么时候」要能一眼看出来 —— 链路死了的第一个症状就是它不动了。"""
    runs = [{"finished_at": "2026-08-22T10:00:00+08:00", "ok": True, "new": 1,
             "hits": 9, "processed": 1, "backlog": 0, "sources": []}]
    html = render.render_dashboard([], generated_at="2026-08-22T13:30:00+08:00",
                                   keywords=[], runs=runs, notes=[], floor="2025-01-01")
    assert "距上一轮" in html
    assert "3 小时" in html


# ---------------- 主题域:比语义组粗一层,正好配得上八个色槽 ----------------


def test_every_group_belongs_to_exactly_one_domain():
    """每个语义组都要有归属 —— 漏一个,它在图上就没有颜色也没有名字。"""
    for group in keywords.KEYWORD_GROUPS:
        assert keywords.domain_of(group), f"{group} 没有主题域"


def test_domains_fit_the_eight_colour_slots():
    """分类色板只有八个槽,第九个不许生成新色 —— 所以带色的域最多八个。

    多出来的(专题页那条召回线)统一走中性灰,它本来也不是一个话题。
    """
    coloured = [d for d in keywords.DOMAINS if d != keywords.OTHER_DOMAIN]
    assert len(coloured) <= 8, f"带色的主题域有 {len(coloured)} 个,超过色槽数"
    assert keywords.domain_of(keywords.TOPIC_GROUP) == keywords.OTHER_DOMAIN


# ---------------- 新的观察角度 ----------------


def _rows_across_two_weeks() -> list[dict[str, Any]]:
    return [
        {"article_id": "a1", "title_en": "one", "url": "u1", "section": "Technology",
         "published_at": "2026-08-10T09:00:00Z", "keywords": ["AI chip", "GPU"]},
        {"article_id": "a2", "title_en": "two", "url": "u2", "section": "Technology",
         "published_at": "2026-08-11T09:00:00Z", "keywords": ["AI chip"]},
        {"article_id": "b1", "title_en": "three", "url": "u3", "section": "Markets",
         "published_at": "2026-08-18T09:00:00Z", "keywords": ["AI chip", "GPU", "Nvidia"]},
        {"article_id": "b2", "title_en": "four", "url": "u4", "section": "",
         "published_at": "2026-08-19T09:00:00Z", "keywords": ["Nvidia"]},
    ]


def test_by_section_counts_the_desk_that_filed_it():
    """FT 自己的栏目是一个现成的分类角度 —— 读不到就记「未标注」,不猜。"""
    pairs = dict(stats.by_section(_rows_across_two_weeks()))
    assert pairs["Technology"] == 2
    assert pairs["Markets"] == 1
    assert pairs["未标注"] == 1


def test_week_over_week_says_which_words_got_thicker():
    """本周比上周多了几篇 —— 这是「AI 领域在往哪偏」最直接的一个数。

    **只报差值,不解释**:变粗可能是有事发生,也可能是我们搜得更准了。
    """
    moves = dict((word, delta) for word, delta, _now, _before in
                 stats.week_over_week(_rows_across_two_weeks()))
    assert moves["Nvidia"] == 2, "上周 0 篇、本周 2 篇"
    assert moves["AI chip"] == -1, "上周 2 篇、本周 1 篇"
    assert moves["GPU"] == 0


def test_co_occurrence_finds_the_pairs_that_travel_together():
    """哪两个词老在同一篇里出现 —— 一篇稿子同时挂两个词是结构性事实。"""
    pairs = stats.co_occurrence(_rows_across_two_weeks())
    assert pairs[0][0] == ("AI chip", "GPU") and pairs[0][1] == 2
    assert ("GPU", "Nvidia") in [p for p, _n in pairs]


def test_domain_weeks_gives_one_line_per_domain():
    """主题域 × 周:八条小倍数,一眼看出哪条线在抬头。"""
    labels, series = stats.domain_weeks(_rows_across_two_weeks())
    assert len(labels) == 2
    by_name = dict(series)
    assert sum(by_name["AI 芯片"]) == 3, "三篇挂着芯片组的词"


# ---------------- 后台:颜色要有含义,不是装饰 ----------------


def test_dashboard_paints_domains_and_keeps_a_label_next_to_every_colour():
    """颜色只编码主题域;每个色块旁边永远有名字和数字。

    色板在浅色纸面上有几个槽低于 3:1 对比度 —— 规范要求那时必须有可见标签,
    颜色不能是唯一的身份线索。
    """
    html = render.render_dashboard(_rows_across_two_weeks(), generated_at="now",
                                   keywords=["AI chip"], runs=[], notes=[], floor="2025-01-01")
    assert "--domain-" in html, "主题域的色变量要落在样式里"
    for name in ("AI 芯片", "资本与公司"):
        assert name in html, f"{name} 只有颜色没有名字"
    assert "本周对上周" in html
    assert "常一起出现" in html
    # 9-03 起这张牌的标题从站点词汇表来(FT.COM 栏目 / BLOOMBERG.COM 栏目),
    # 不再写死「FT」—— 后台是哪个库的,页面上每一句都得跟着变。
    assert "FT.COM 栏目" in html


# ---------------- 清单页的筛选 ----------------


def test_hidden_rows_actually_disappear():
    """`hidden` 属性给的是 display:none,而 .row 是 display:grid —— **后者赢**。

    2026-08-22 站长报:输入关键词后计数变成「显示 0 / 40 篇」,四十行却一行不少
    地留在那里。计数和列表说的不是同一件事,比两边都错更难查。
    """
    css = render.STYLESHEET
    assert "[hidden]" in css, "要有一条压得住 display:grid 的规则"
    rule = css[css.index("[hidden]"):]
    assert "display: none" in rule[:80]
    assert "!important" in rule[:80], "不加 !important 就压不住 .row 的 display:grid"


def test_rows_do_not_carry_a_meaningless_serial_number():
    """右边那个 01/02 只是「第几行」—— 筛一下就全变了,不指向任何事实。"""
    rows = [{"article_id": "aaaa", "title_en": "一条", "url": "https://www.ft.com/content/a",
             "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip"]}]
    html = render.render_index(rows, keywords=["AI chip"], generated_at="now")
    assert 'class="rank"' not in html


# ---------------- 标题中文化 ----------------


def test_translation_only_asks_for_titles_that_have_none(monkeypatch):
    """已经有译文的不再翻。

    每小时一轮时库里几百篇、新增两三篇 —— 成本必须随「新增」走,
    不随「库存」走,否则每天多花几百次调用买回同一批译文。
    """
    asked: list[str] = []

    def fake(text: str) -> str:
        asked.append(text)
        return f"译:{text}"

    rows = [
        {"article_id": "a", "title_en": "chips", "title_zh": "芯片"},
        {"article_id": "b", "title_en": "robots"},
    ]
    done = translate.fill_titles(rows, translate_one=fake)
    assert asked == ["robots"], "有译文的那篇不该再问一次"
    assert rows[1]["title_zh"] == "译:robots"
    assert done == 1


def test_translation_failure_keeps_the_server_wording(monkeypatch):
    """翻译失败留**原话**,不拿英文标题冒充「翻过了」。"""
    def boom(text: str) -> str:
        raise RuntimeError("Cloudflare 返回 403:token 没有 Workers AI 权限")

    rows = [{"article_id": "a", "title_en": "chips"}]
    assert translate.fill_titles(rows, translate_one=boom) == 0
    assert "title_zh" not in rows[0], "失败不能留下一个空译文占着位置"
    assert "403" in rows[0]["title_zh_error"]


def test_missing_credentials_say_what_to_do(monkeypatch):
    """没配凭据是**常态**,不是崩溃 —— 但必须说清楚缺什么、放哪儿。"""
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("INEWS_SECRETS_DIR", "/nonexistent-on-purpose")
    status = translate.status()
    assert status["ok"] is False
    assert "secrets/cloudflare.json" in status["note"]
    assert "CLOUDFLARE_API_TOKEN" in status["note"]


def test_credentials_come_from_the_secrets_file_too(tmp_path: Path, monkeypatch):
    """和 ft.cookies 同一个目录约定:secrets/ 已经被 .gitignore 和守卫挡着。"""
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    (tmp_path / "cloudflare.json").write_text(
        '{"account_id": "acct-1", "api_token": "tok-1"}', encoding="utf-8")
    monkeypatch.setenv("INEWS_SECRETS_DIR", str(tmp_path))
    creds = translate.credentials()
    assert creds.account_id == "acct-1" and creds.api_token == "tok-1"
    assert translate.status()["ok"] is True


def test_the_index_shows_the_chinese_title_and_keeps_the_original():
    """中文当标题,英文原题留在下面一行 —— 核对时要看得到**站方给的那一串**。"""
    rows = [{"article_id": "aaaa", "url": "https://www.ft.com/content/a",
             "title_en": "China eases limits on Nvidia H200 chips",
             "title_zh": "中国放宽对英伟达 H200 芯片的限制",
             "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip"]}]
    html = render.render_index(rows, keywords=["AI chip"], generated_at="now")
    assert "中国放宽对英伟达 H200 芯片的限制" in html
    assert "China eases limits on Nvidia H200 chips" in html
    # 没译文的照旧显示英文,不留空
    plain = render.render_index(
        [{**rows[0], "title_zh": ""}], keywords=["AI chip"], generated_at="now")
    assert "China eases limits on Nvidia H200 chips" in plain


def test_translations_survive_a_redraw(tmp_path: Path):
    """译文进存档:`--render-only` 重画时不该把它丢了,更不该重新翻一遍。"""
    rows = [{"article_id": "aaaa", "url": "https://www.ft.com/content/a",
             "title_en": "chips", "title_zh": "芯片",
             "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip"],
             "body": "正文"}]
    run.write_site(rows, tmp_path, keywords=["AI chip"], generated_at="now")
    assert archive.load(tmp_path)[0]["title_zh"] == "芯片"


def test_a_round_translates_the_new_titles_and_says_so(tmp_path: Path, monkeypatch):
    """跑一轮要真的把新增标题翻掉,并把结果写进「本轮记录」。

    接线断了是最难发现的一种坏:翻译模块自己的用例全绿,而页面上一条译文都没有。
    """
    monkeypatch.setattr(translate, "status", lambda: {"ok": True, "note": "假凭据"})
    monkeypatch.setattr(
        translate, "fill_titles",
        lambda rows, **kw: sum(bool(row.__setitem__("title_zh", "译文")) or 1 for row in rows),
    )
    monkeypatch.setattr(run, "_listing_fetcher_for", lambda site: _fake_listing(SEARCH_HTML))
    monkeypatch.setattr(run, "_body_fetcher_for",
                        lambda site: lambda row: {"body": "正文一段", "extractor": "direct"})
    code = paywall_cli.main(["--keyword", "AI agent", "--out", str(tmp_path)])
    assert code == 0
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "译文" in index, "译好的标题要出现在清单上"
    assert "标题翻译" in index, "本轮记录里要说翻了几条"


def test_the_guard_refuses_to_commit_the_cloudflare_token():
    """secrets/cloudflare.json 是一把 token —— 守卫要认得它,不能只靠 .gitignore。"""
    import importlib.util  # noqa: PLC0415 只在这条用例里用

    path = Path(__file__).resolve().parents[1] / "tools" / "guard_standalone.py"
    spec = importlib.util.spec_from_file_location("guard_standalone", path)
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert "cloudflare.json" in guard.SECRET_NAMES


def test_retitle_finds_every_row_without_a_chinese_title(tmp_path: Path):
    """存量补译:库里哪些行还没有中文标题,台账一看就知道。"""
    entries: dict[str, dict] = {}
    ledger_store.record(entries, [
        {"article_id": "a", "url": "u1", "title_en": "one", "title_zh": "一",
         "keywords": [], "body": "正文"},
        {"article_id": "b", "url": "u2", "title_en": "two", "keywords": [], "body": "正文"},
    ], crawled_at="now")
    holes = run.missing_titles(entries)
    assert [row["article_id"] for row in holes] == ["b"]


def test_retitle_writes_the_translation_back_into_the_ledger(tmp_path: Path, monkeypatch):
    """补完要**写回台账**:不写回,下一轮重画又是英文,而且会再翻一遍花一次钱。"""
    monkeypatch.setattr(translate, "status", lambda: {"ok": True, "note": "假凭据"})
    monkeypatch.setattr(
        translate, "fill_titles",
        lambda rows, **kw: sum(bool(row.__setitem__("title_zh", "译文")) or 1 for row in rows),
    )
    ledger_path = ledger_store.path_for(tmp_path)
    entries: dict[str, dict] = {}
    ledger_store.record(entries, [
        {"article_id": "aaaa", "url": "https://www.ft.com/content/a", "title_en": "chips",
         "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip"], "body": "正文"},
    ], crawled_at="now")
    ledger_store.save(ledger_path, entries)

    assert paywall_cli.main(["--retitle", "--out", str(tmp_path)]) == 0
    again = ledger_store.load(ledger_path)
    assert again["aaaa"]["title_zh"] == "译文"
    assert "译文" in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_a_timeout_is_retried_once():
    """超时重试一次:请求根本没被处理,再问一遍不会有第二个副作用。

    2026-08-23 站长补 40 条标题,3 条撞上超时 —— 那条链路对他那边就是不稳。
    """
    attempts: list[str] = []

    def flaky(text: str) -> str:
        attempts.append(text)
        if len(attempts) == 1:
            raise TimeoutError("The read operation timed out")
        return "译文"

    translate.RETRY_PAUSE_SECONDS = 0          # 用例里不等那两秒
    rows = [{"article_id": "a", "title_en": "chips"}]
    assert translate.fill_titles(rows, translate_one=flaky) == 1
    assert len(attempts) == 2, "超时要再试一次"
    assert rows[0]["title_zh"] == "译文"


def test_a_permission_error_is_not_retried():
    """403 / 429 不重试。**重试它们一次都不会成功**,只会把真问题拖成「慢」——
    而且 429 是额度用完,再问一遍是往枪口上撞。"""
    attempts: list[str] = []

    def denied(text: str) -> str:
        attempts.append(text)
        raise RuntimeError("Cloudflare 返回 403:token 没有 Workers AI 权限")

    rows = [{"article_id": "a", "title_en": "chips"}]
    assert translate.fill_titles(rows, translate_one=denied) == 0
    assert len(attempts) == 1, "权限错误不该重试"
    assert "403" in rows[0]["title_zh_error"]


def test_a_second_timeout_keeps_the_original_wording():
    """重试之后还是超时,就**如实失败**,原话照留 —— 不把它说成别的。"""
    translate.RETRY_PAUSE_SECONDS = 0
    def always_slow(text: str) -> str:
        raise TimeoutError("The read operation timed out")

    rows = [{"article_id": "a", "title_en": "chips"}]
    assert translate.fill_titles(rows, translate_one=always_slow) == 0
    assert "timed out" in rows[0]["title_zh_error"]


# ---------------- 清单页上的抓取节奏 ----------------


def _runs(*specs: tuple[str, bool]) -> list[dict[str, Any]]:
    return [
        {"finished_at": at, "ok": ok, "new": 3, "hits": 9,
         "error": "" if ok else "登录态失效"}
        for at, ok in specs
    ]


def test_index_shows_the_last_five_runs_and_no_more():
    """站长要在清单页上直接看到「前 5 次抓取的时间」——不必先跳到后台。

    只列 5 条:再往前的时间戳对「它还在跑吗」这个问题没有帮助,却会把清单顶下去。
    """
    runs = _runs(
        ("2026-08-23T02:00:00+08:00", True),
        ("2026-08-23T03:00:00+08:00", True),
        ("2026-08-23T04:00:00+08:00", True),
        ("2026-08-23T05:00:00+08:00", True),
        ("2026-08-23T06:00:00+08:00", True),
        ("2026-08-23T07:00:00+08:00", True),
        ("2026-08-23T08:00:00+08:00", True),
    )
    html = render.render_index(
        [], keywords=[], generated_at="2026-08-23T08:10:00+08:00", runs=runs
    )
    for at in ("04:00", "05:00", "06:00", "07:00", "08:00"):
        assert at in html, f"最近 5 轮里的 {at} 该出现在清单页上"
    assert "02:00" not in html and "03:00" not in html, "只列最近 5 轮"


def test_index_keeps_the_failure_wording_from_the_run_log():
    """失败轮在清单页上要留原话,不许被「抓取异常」这种兜底文案顶掉。"""
    html = render.render_index(
        [], keywords=[], generated_at="2026-08-23T08:10:00+08:00",
        runs=_runs(("2026-08-23T08:00:00+08:00", False)),
    )
    assert "登录态失效" in html


def test_index_does_not_claim_a_schedule_when_nothing_has_run():
    """一轮都没跑过的时候,不许写「每小时一轮」——那正是要查的东西。"""
    html = render.render_index([], keywords=[], generated_at="now", runs=[])
    assert "还没有跑过" in html
    assert "每小时一轮" not in html


def test_index_calls_out_a_schedule_that_stopped_firing():
    """定时停了的症状就是「距上一轮」不再变小。页面要说出来,不能一直绿着。

    每小时一轮的东西超过三小时没动,只有两种可能:任务没装上,或者它在静默失败。
    两种都要人去看一眼。
    """
    stalled = render.render_index(
        [], keywords=[], generated_at="2026-08-23T08:00:00+08:00",
        runs=_runs(("2026-08-23T02:00:00+08:00", True)),
    )
    assert "定时" in stalled and "6 小时" in stalled
    assert "每小时一轮" not in stalled

    fresh = render.render_index(
        [], keywords=[], generated_at="2026-08-23T08:00:00+08:00",
        runs=_runs(("2026-08-23T07:30:00+08:00", True)),
    )
    assert "每小时一轮" in fresh


def test_index_run_button_reaches_the_local_listener():
    """按钮按下去要**真的**在站长那台机器上跑起来 —— 敲的是本机监听那个口子。

    页面本身仍然是静态的:抓取必须在本机开一个带登录态的可见 Chrome。所以按钮
    做的是敲 127.0.0.1 上常驻的那个监听,由它去启动 `tools/hourly.sh`。
    **监听没开时不许假装成功**:那时退回到把命令交到手上,并留下浏览器的原话。
    """
    html = render.render_index([], keywords=[], generated_at="now", runs=[])
    assert "抓一轮" in html
    assert "127.0.0.1" in html and "/run" in html, "按钮要敲本机监听"
    assert "tools/hourly.sh" in html, "监听没开时要给出那条能真的跑起来的命令"
    assert "假装成功" in html or "不会假装" in html, "这条退路要写在页面上"


def test_write_site_puts_the_run_times_on_the_index(tmp_path):
    """端到端:跑批记录要真的流到清单页,不是只有渲染函数支持。"""
    rows = [{"article_id": "aaaa", "title_en": "一条",
             "url": "https://www.ft.com/content/a",
             "published_at": "2026-08-18T09:30:00Z", "keywords": ["AI chip"]}]
    index = run.write_site(
        rows, tmp_path, keywords=["AI chip"],
        generated_at="2026-08-23T08:10:00+08:00",
        runs=_runs(("2026-08-23T08:00:00+08:00", True)),
    )
    assert "2026-08-23T08:00:00+08:00" in index.read_text(encoding="utf-8")
