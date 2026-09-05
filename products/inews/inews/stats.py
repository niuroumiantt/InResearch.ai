"""清单的统计投影(纯函数,不出网、不写盘)。

**统计只数结构性事实**:这篇挂在哪些关键词下、属于哪些语义组、什么时候发的、
正文取到没有。**不打分、不判「值不值得」** —— 那是站长看着数据做的决定,
不是这个模块该替他做的。
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from inews import keywords as kw
from inews.textutil import parse_datetime


def has_body(row: dict[str, Any]) -> bool:
    """这篇的正文取到了没有。

    本轮的行手里有正文本身;从台账摊回来的行只有一个状态字。两种来源同一个
    问题,判断只留一处 —— 否则累积库里那些老稿子会被当成「没取到」,
    一整片红标全是假的。
    """
    return bool(row.get("body")) or row.get("body_status") == "ok"


def body_failed(row: dict[str, Any]) -> bool:
    # 有正文是更强的事实。旧版重试曾会留下「有正文 + 旧失败」
    # 的矛盾行;统计层不能把它再算成失败。
    return not has_body(row) and (
        bool(row.get("body_error")) or row.get("body_status") == "failed"
    )


def by_keyword(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """每个关键词下挂了几篇;一篇挂在多个词下就每个都算一次。"""
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update(set(row.get("keywords", [])))
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def by_group(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """每个语义组下有几篇;同组内命中多个词只算一次。"""
    counter: Counter[str] = Counter()
    for row in rows:
        counter.update({kw.group_of(word) for word in row.get("keywords", [])})
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def by_month(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """按发布月份;没有时间的归到「时间未知」,不丢掉也不假装有时间。"""
    counter: Counter[str] = Counter()
    for row in rows:
        published = parse_datetime(row.get("published_at", ""))
        counter[published.strftime("%Y-%m") if published else "时间未知"] += 1
    return sorted(counter.items())


def by_body_status(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """正文取到没有。失败单独一档 —— 混进「没取」里就看不出墙在哪。"""
    counter: Counter[str] = Counter()
    for row in rows:
        if has_body(row):
            counter["已取到正文"] += 1
        elif body_failed(row):
            counter["取正文失败"] += 1
        else:
            counter["只有清单"] += 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def overlap(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """一篇同时挂在几个关键词下的分布。

    这是判断「搜索到底有没有在筛」的直接证据:如果绝大多数稿子都挂在十几个
    词下,说明站方返回的是同一批最新新闻,而不是各词各自的命中。
    """
    counter: Counter[int] = Counter(
        len(set(row.get("keywords", []))) for row in rows
    )
    return [(f"{count} 个词", n) for count, n in sorted(counter.items())]


def summary(rows: list[dict[str, Any]]) -> dict[str, list[tuple[str, int]]]:
    return {
        "语义组": by_group(rows),
        "关键词": by_keyword(rows),
        "发布月份": by_month(rows),
        "正文状态": by_body_status(rows),
        "一篇命中几个词": overlap(rows),
    }


def by_day(rows: list[dict[str, Any]], days: int = 30) -> list[tuple[str, int]]:
    """最近若干个**有稿子的日子**各入库多少(缺时间的不进这张表)。

    不补零:补出来的空日子会让「那天没新闻」和「那天没跑」长得一样。
    """
    counter: Counter[str] = Counter()
    for row in rows:
        published = parse_datetime(row.get("published_at", ""))
        if published:
            counter[published.strftime("%Y-%m-%d")] += 1
    return sorted(counter.items())[-days:]


def keyword_weeks(
    rows: list[dict[str, Any]],
    weeks: int = 12,
) -> tuple[list[str], list[tuple[str, list[int]]]]:
    """关键词 × 周 的计数矩阵,返回 (周标签, [(关键词, 每周篇数)])。

    这是「AI 领域这几周在往哪偏」最直接的一张图:某个词突然连着几周变粗,
    通常意味着有事发生,而不是我们的搜索变准了。
    """
    seen: Counter[str] = Counter()
    grid: dict[str, Counter[str]] = {}
    for row in rows:
        published = parse_datetime(row.get("published_at", ""))
        if not published:
            continue
        year, week, _day = published.isocalendar()
        label = f"{year}-W{week:02d}"
        seen[label] += 1
        for word in set(row.get("keywords", [])):
            grid.setdefault(word, Counter())[label] += 1
    labels = sorted(seen)[-weeks:]
    table = [
        (word, [counts.get(label, 0) for label in labels])
        for word, counts in grid.items()
    ]
    table.sort(key=lambda item: (-sum(item[1]), item[0]))
    return labels, table


def by_section(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """FT 自己的栏目(Technology / Markets / …)。

    这是站方**自己**给的分类,和我们的关键词是两套独立的判据 —— 两边对不上
    的地方,通常就是我们的词表漏了一条线。读不到就记「未标注」,不猜。
    """
    counter: Counter[str] = Counter()
    for row in rows:
        counter[str(row.get("section") or "").strip() or "未标注"] += 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _week_of(row: dict[str, Any]) -> str:
    published = parse_datetime(row.get("published_at", ""))
    if not published:
        return ""
    year, week, _day = published.isocalendar()
    return f"{year}-W{week:02d}"


def week_over_week(
    rows: list[dict[str, Any]],
    top: int = 12,
) -> list[tuple[str, int, int, int]]:
    """最近一周比上一周,每个词多了/少了几篇。返回 (词, 差值, 本周, 上周)。

    **只报差值,不解释。** 一个词变粗可能是那边真出了事,也可能只是我们这轮
    多翻了两页 —— 这个模块不替站长挑其中一种说法。
    """
    weeks = sorted({label for label in map(_week_of, rows) if label})
    if len(weeks) < 2:
        return []
    now_label, before_label = weeks[-1], weeks[-2]
    now: Counter[str] = Counter()
    before: Counter[str] = Counter()
    for row in rows:
        label = _week_of(row)
        if label == now_label:
            now.update(set(row.get("keywords", [])))
        elif label == before_label:
            before.update(set(row.get("keywords", [])))
    moves = [
        (word, now[word] - before[word], now[word], before[word])
        for word in set(now) | set(before)
    ]
    # 按变化幅度排,升的和降的都要看得见 —— 只留上涨的那半边就成了报喜。
    moves.sort(key=lambda item: (-abs(item[1]), item[0]))
    return moves[:top]


def co_occurrence(
    rows: list[dict[str, Any]],
    top: int = 12,
) -> list[tuple[tuple[str, str], int]]:
    """哪两个词老在同一篇里出现。

    「一篇同时挂 A 和 B」是结构性事实,不是相似度模型的判断。同组内的配对
    (`AI agent`/`agentic AI`)天然很高,那正说明这两个词问的是同一件事。
    """
    counter: Counter[tuple[str, str]] = Counter()
    for row in rows:
        words = sorted(set(row.get("keywords", [])))
        for i, left in enumerate(words):
            for right in words[i + 1:]:
                counter[(left, right)] += 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:top]


def domain_weeks(
    rows: list[dict[str, Any]],
    weeks: int = 12,
) -> tuple[list[str], list[tuple[str, list[int]]]]:
    """主题域 × 周,一域一条线(小倍数用)。

    一篇稿子可能同时落在两个域下,两边都算一次 —— 它确实同时是这两件事。
    """
    seen: Counter[str] = Counter()
    grid: dict[str, Counter[str]] = {}
    for row in rows:
        label = _week_of(row)
        if not label:
            continue
        seen[label] += 1
        for domain in {kw.domain_of_word(word) for word in row.get("keywords", [])}:
            grid.setdefault(domain, Counter())[label] += 1
    labels = sorted(seen)[-weeks:]
    series = [
        (domain, [counts.get(label, 0) for label in labels])
        # 顺序跟着**声明顺序**走,不跟着篇数走:颜色跟实体,不跟排名 ——
        # 否则数据一变,每条线的颜色都会换一遍。
        for domain in kw.DOMAINS
        if (counts := grid.get(domain))
    ]
    return labels, series


def coverage(rows: list[dict[str, Any]]) -> tuple[str, str]:
    """库里最早、最晚的发布日期;一篇有时间的都没有就返回两个空串。"""
    days = sorted(
        published.strftime("%Y-%m-%d")
        for published in (
            parse_datetime(row.get("published_at", "")) for row in rows
        )
        if published
    )
    return (days[0], days[-1]) if days else ("", "")


# 取正文失败的几种。**这几句话是本仓库自己生成的**(fetch.py 的
# `_short_body_reason` 和那两条 raise),所以按固定措辞归类是结构性事实,不是猜。
# 顺序即优先级:一条原话可能同时含「未配置 cookie」和「浏览器兜底也失败」,
# 先命中的那条才是这次真正卡住的地方。
FAILURE_KINDS = (
    ("付费墙拦截页", "付费墙拦截页"),
    ("登录态", "登录态失效"),
    ("正文提取过短", "正文提取过短"),
    ("浏览器兜底也失败", "浏览器兜底也失败"),
    ("正文仍不完整", "浏览器打开后仍不完整"),
    ("空正文", "抓取返回了空正文"),
)
OTHER_REASON = "其他"


def failure_kind(text: str) -> str:
    """一句失败原话属于哪一类。归不进去就是「其他」——**不硬塞**。"""
    for needle, label in FAILURE_KINDS:
        if needle in text:
            return label
    return OTHER_REASON


def by_failure_reason(rows: list[dict[str, Any]]) -> list[tuple[str, int]]:
    """按原因数一数取正文失败。回答的是「是不是同一个原因」这一个问题。"""
    counter: Counter[str] = Counter()
    for row in rows:
        if not body_failed(row):
            continue
        counter[failure_kind(str(row.get("body_error") or ""))] += 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def hub_coverage(
    rows: list[dict[str, Any]],
    *,
    hub_ids: set[str],
    hub_oldest: str,
) -> dict[str, list[dict[str, Any]]]:
    """搜索线召回的文章,有多少也出现在某个分类页的快照上。

    站长 2026-09-01 的猜想:「想要的文章都在 /technology 下,不搜也能拿到」。
    8-24 下架 technology 否的是**准度**(它带进来的多数不是 AI 稿);这里
    回答的是**覆盖度** —— 两个问题要两份证据,不能拿一份裁决盖两次章。

    只比较、不下结论,四档互斥:
    - ``covered`` / ``missed``:快照够得着的时间窗内,在不在分类页上 ——
      ``missed`` 非空就是「只爬分类页会漏稿」的直接证据,漏的每一篇都列名;
    - ``out_of_reach``:比快照最老一条还早。分类页翻不到那么深不是词表的
      功劳,也不是分类页的罪 —— 记成「漏」会冤枉地压低覆盖率;
    - ``undated``:时间未知的不猜(猜一个时间等于替数据表态)。

    分母只算搜索线(挂着真实关键词的);只从专题线进来的本来就不靠搜索,
    算进去会稀释答案。快照上一条带时间的都没有时如实拒绝 —— 横不出比较
    窗口还硬比,得出的覆盖率没有任何一档敢认领。
    """
    floor = parse_datetime(hub_oldest)
    if floor is None:
        raise ValueError("分类页快照里没有可解析的时间,横不出比较窗口")
    report: dict[str, list[dict[str, Any]]] = {
        "covered": [], "missed": [], "out_of_reach": [], "undated": [],
    }
    for row in rows:
        words = set(row.get("keywords", [])) - {kw.TOPIC_LABEL}
        if not words:
            continue
        published = parse_datetime(row.get("published_at", ""))
        if published is None:
            report["undated"].append(row)
        elif published < floor:
            report["out_of_reach"].append(row)
        elif row.get("article_id") in hub_ids:
            report["covered"].append(row)
        else:
            report["missed"].append(row)
    return report


def is_mention_only(row: dict[str, Any]) -> bool:
    """这篇是不是只在正文里**提及**了关键词,而不是在写它。

    判据全是结构性事实(标题与正文中的位置和密度),不是质量评价:
    - 标题有明确 AI 词或本轮搜索词 → 在写它;
    - 否则按正文命中段落占比与导语位置判断，而不是任一词机械出现三次;
    - **没有正文就不判**:把取正文失败的当提及型藏起来,等于用一个技术故障
      冒充一次编辑判断。
    """
    from inews import sites
    from inews import quality

    if quality.title_strength(row, sites.TOPIC_LABELS):
        return False
    if not row.get("body"):
        return False
    central, _share, _lead = quality.body_evidence(row, sites.TOPIC_LABELS)
    return not central
