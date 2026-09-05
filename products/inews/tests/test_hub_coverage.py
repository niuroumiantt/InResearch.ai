"""站长 2026-09-01 的猜想:「想要的文章都在 /technology 下,不搜也能拿到」。

这个猜想 8-24 被否过一次,但那次否的是**准度**(technology 线进来的多数不是
AI 稿);这次问的是**覆盖度**(搜索召回的是不是都在它下面)—— 两个问题,
两份证据。这里钉的是比较逻辑本身,让「验证」有一个不会被措辞挪动的判据:

- 分母只算**搜索线**召回的:只挂专题标签的那些本来就不靠关键词,算进去
  会稀释答案;
- 分类页快照有边界:比快照里最老一条还早的文章,不算「漏」,算「够不着」——
  把够不着的记成漏,覆盖率会被冤枉地压低;
- 时间未知的不猜,单独一档 —— 猜一个时间等于替数据表态。
"""
from __future__ import annotations

import pytest

from inews import stats
from inews.keywords import TOPIC_LABEL


def _row(article_id: str, keywords: list[str], published: str) -> dict:
    return {
        "article_id": article_id,
        "title_en": "标题足够长不被当噪音",
        "keywords": keywords,
        "published_at": published,
    }


def test_keyword_article_on_the_hub_counts_as_covered():
    report = stats.hub_coverage(
        [_row("aaa", ["AI agent"], "2026-08-30")],
        hub_ids={"aaa"},
        hub_oldest="2026-08-20",
    )
    assert [r["article_id"] for r in report["covered"]] == ["aaa"]
    assert report["missed"] == []


def test_keyword_article_absent_from_the_hub_is_the_evidence():
    """这一档就是猜想的裁决:它非空,「只爬分类页」就会漏稿。"""
    report = stats.hub_coverage(
        [_row("bbb", ["AI capex"], "2026-08-30")],
        hub_ids={"aaa"},
        hub_oldest="2026-08-20",
    )
    assert [r["article_id"] for r in report["missed"]] == ["bbb"]


def test_topic_only_rows_stay_out_of_the_denominator():
    """只从专题线进来的那些,本来就不是「搜索找到的」,不该参与投票。"""
    report = stats.hub_coverage(
        [_row("ccc", [TOPIC_LABEL], "2026-08-30")],
        hub_ids=set(),
        hub_oldest="2026-08-20",
    )
    assert report["covered"] == [] and report["missed"] == []


def test_articles_older_than_the_snapshot_are_out_of_reach_not_missed():
    report = stats.hub_coverage(
        [_row("ddd", ["GPU"], "2026-07-01")],
        hub_ids=set(),
        hub_oldest="2026-08-20",
    )
    assert [r["article_id"] for r in report["out_of_reach"]] == ["ddd"]
    assert report["missed"] == []


def test_undated_rows_are_reported_separately_not_guessed():
    report = stats.hub_coverage(
        [_row("eee", ["AI safety"], "")],
        hub_ids={"eee"},
        hub_oldest="2026-08-20",
    )
    assert [r["article_id"] for r in report["undated"]] == ["eee"]
    assert report["covered"] == [] and report["missed"] == []


def test_a_snapshot_without_dates_cannot_bound_the_comparison():
    """快照上一条带时间的都没有,比较窗口横不出来 —— 如实拒绝,不硬比。"""
    with pytest.raises(ValueError):
        stats.hub_coverage(
            [_row("fff", ["AI jobs"], "2026-08-30")],
            hub_ids=set(),
            hub_oldest="",
        )
