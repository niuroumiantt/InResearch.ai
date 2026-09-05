from __future__ import annotations

from inews import render, run, runlog
from inews.sites import axios, bloomberg, cnbc, ft, reuters, wsj


def _snapshot(site, *, articles: int, failed: bool = False):
    rows = [
        {
            "article_id": f"{site.KEY}-{i}",
            "title_en": f"Story {i}",
            "published_at": "2026-09-03T10:00:00Z",
            "body_status": "failed" if failed and i == 0 else "ok",
            "body_error": "正文提取过短" if failed and i == 0 else "",
            "body": "" if failed and i == 0 else "body",
            "keywords": ["AI agent"] if site.SEARCHABLE else [site.TOPIC_LABEL],
        }
        for i in range(articles)
    ]
    return {
        "site": site,
        "rows": rows,
        "runs": [{
            "finished_at": "2026-09-03T11:00:00Z",
            "ok": True,
            "new": articles,
            "backlog": 0,
        }],
        "keywords": ["AI agent"] if site.SEARCHABLE else [],
        "summary": {
            "key": site.KEY,
            "label": site.LABEL,
            "articles": articles,
            "with_body": articles - int(failed),
            "failed": int(failed),
            "backlog": 0,
            "last_at": "2026-09-03T11:00:00Z",
            "last_new": articles,
            "last_ok": True,
        },
    }


def test_unified_dashboard_combines_health_but_keeps_separate_listings():
    html = render.render_unified_dashboard(
        [
            _snapshot(ft, articles=2, failed=True),
            _snapshot(bloomberg, articles=1),
            _snapshot(cnbc, articles=3),
            _snapshot(wsj, articles=4),
            _snapshot(reuters, articles=5),
            _snapshot(axios, articles=6),
        ],
        generated_at="2026-09-03T12:00:00Z",
    )

    assert "订阅正文库 · 统一后台" in html
    assert "FT.COM · 运行状态" in html
    assert "BLOOMBERG.COM · 运行状态" in html
    assert "CNBC.COM · 运行状态" in html
    assert "WSJ.COM · 运行状态" in html
    assert "REUTERS.COM · 运行状态" in html
    assert "AXIOS.COM · 运行状态" in html
    assert "正文失败" in html
    assert "21</strong><span>库内文章" in html
    assert "https://inews.today/rawarticle/ft/index.html" in html
    assert "https://inews.today/rawarticle/bloomberg/index.html" in html
    assert "https://inews.today/rawarticle/cnbc/index.html" in html
    assert "https://inews.today/rawarticle/wsj/index.html" in html
    assert "https://inews.today/rawarticle/reuters/index.html" in html
    assert "https://inews.today/rawarticle/axios/index.html" in html
    assert html.count("打开独立清单") == 6


def test_first_failed_run_is_visible_even_before_a_ledger_exists(tmp_path):
    """发现阶段首次就断链时没有 ledger，但不能因此冒充“还没跑过”。"""
    base = tmp_path / wsj.OUT_DIR
    runlog.record(
        runlog.path_for(base),
        {
            "finished_at": "2026-09-04T02:58:29+08:00",
            "ok": False,
            "new": 0,
            "hits": 0,
            "backlog": 0,
            "error": "日常 Chrome 文章列表没有响应",
        },
    )

    snapshots = run.library_snapshots(tmp_path)
    item = next(row for row in snapshots if row["site"] is wsj)

    assert not item.get("missing")
    assert item["rows"] == []
    assert item["runs"][-1]["ok"] is False
    assert item["summary"]["articles"] == 0
    assert item["summary"]["last_ok"] is False

    html = render.render_unified_dashboard(
        snapshots, generated_at="2026-09-04T03:00:00+08:00"
    )
    assert "日常 Chrome 文章列表没有响应" in html


def test_wsj_dashboard_describes_its_real_numbered_pagination():
    second = render._stages(wsj, [])[1]

    assert second[0] == "分页历史河"
    assert "?page=N" in second[2]
    assert "只收首屏" not in second[2]
