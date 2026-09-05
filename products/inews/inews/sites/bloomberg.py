"""Bloomberg:仅栏目页召回,不配搜索线。

9-02 站长的思路:「一个确定性比不确定性更方便……每个页面找到最优路径,
最快找到文章就好了。如果网站的头版头条都找不到的,那么这个新闻的价值没有
想象的那么高。」Bloomberg 是这个思路的实验组 —— 只爬官方 AI 栏目页,
再用标题与站方文章 slug 挡掉侧栏混入的非 AI 稿;FT 保持混合召回当对照组,
跑一周拿产出对比。

**未经浏览器核验的假设,列在各自的声明旁边。** ft.py 的规矩同样适用:
「没核实过的分类页不往这里加 —— 猜错了只会每轮白开页面」。站长开通
Bloomberg 订阅并在浏览器里核对 /ai 页与正文容器之前,这个站不该进定时任务。
"""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from inews.sites import _shared
from inews.textutil import canonical_url, clean_text, parse_datetime

KEY = "bloomberg"
NAME = "Bloomberg"
HOME = "https://www.bloomberg.com"
LABEL = "BLOOMBERG.COM"
TAGLINE = "AI 栏目清单"
OUT_DIR = "BLOOMBERG.COM"

# 不配搜索线是这个站的立场,不是缺功能:确定性优先,栏目页负责召回,
# 标题/slug 的二次复核负责挡住页面侧栏和推荐区的漏项。
SEARCHABLE = False
# 栏目页依赖浏览器中的订阅登录态与动态展开。
LISTING_FETCHER = None
# 专题线专属标签。**不是搜索词**,和 FT 那个「FT 专题」同一性质 ——
# 它只标记发现来源,不能替代下面的二次主题复核。
TOPIC_LABEL = "Bloomberg 专题"
# 抓取规则,印在清单页顶上给人看。只写被测试钉住的事实,不写愿望。
RULES = (
    "只爬官方 AI 栏目页,不配关键词、不搜索;标题与文章 slug 再做一次 AI/算力/供应链复核",
    "只收带日期的正稿与特稿链接;Five Things 这类拼盘简报在地址上就被挡掉",
    "纯债券、股价、财报、招聘和个人动态不入库;OpenAI 融资、AI 数据中心债务等产业融资保留",
    "每轮点开栏目页末尾的「Load more」直到展开完(最多 8 次),不只收首屏那一屏",
    "时间以卡片标注为准,读不懂就用文章地址里的日期;早于时间地板的一律不收",
)

# 栏目页。9-02 站长在浏览器里核对过:路径就是 /ai,页面上部是编辑板块,
# 下部「More AI news」是按时间排的懒加载河。
HUBS = ("ai",)
HUB_LABELS = {"ai": TOPIC_LABEL}
# Bloomberg /ai 是本次质量参照系：先经过本适配器的结构与主题复核，再把留下的
# 栏目稿视为可信参照；评分负责排序，不再用 FT 全文搜索的噪声规则误伤它。
HUB_TIERS = {"ai": "trusted"}

# 每轮滚到页底。**光滚是不够的**(9-02 那版实测:滚 25 轮命中仍是 25 条)——
# 河真正的续接靠下面那个按钮。留着滚动是为了让按钮进到视口里、并把懒加载的
# 图片位撑开;真正把河拉长的是 LOAD_MORE_TEXT。
LISTING_SCROLLS = True

# 河的末尾是一个「Load more」按钮(9-03 站长截图核实)—— **不是无限滚动**,
# 所以 9-02 那版只滚不点的修法一条也没多收。按可见文字认这个按钮:类名是
# 构建时哈希出来的,随一次发布就失效;按钮上的字是给人看的,改动慢得多。
LOAD_MORE_TEXT = "load more"

# 只收带日期的正稿与特稿。newsletters(Five Things 这类拼盘简报)在**地址上**
# 就被挡掉 —— 路径形态是结构性事实,不是质量评价;这正是站长在 FT 那边对
# FirstFT 的不满,这里从源头不收。
LINK_PATTERN = r"/news/(?:articles|features)/\d{4}-\d{2}-\d{2}/[a-z0-9%.\-]+"
_ARTICLE_RX = re.compile(
    r"/news/(?:articles|features)/(\d{4}-\d{2}-\d{2})/([a-z0-9%.\-]+?)/?$"
)

# Bloomberg 的 /ai 页面不只包含 AI 主河，也会带全站侧栏/推荐链接。9-04 实测
# ``SoftBank Group Prices ¥1 Trillion Retail Bond at 4.75%`` 就这样混了进来。
# 因此专题页只能负责召回，打开正文前还要用人能复核的标题（以及站方 slug，供
# 图片锚点暂时只有摄影署名时兜底）做一次窄主题准入。
_AI_TOPIC_RX = re.compile(
    r"\b(?:artificial intelligence|generative ai|genai|machine learning|deep learning|"
    r"ai|llms?|large language models?|foundation models?|frontier models?|"
    r"reasoning models?|agentic|ai agents?|model training|model inference|"
    r"open[ -]?source (?:ai )?models?|closed[ -]?source (?:ai )?models?|gemma|"
    r"openai|chatgpt|anthropic|claude|deepmind|gemini|deepseek|hugging ?face|"
    r"mistral|llama|qwen|grok|xai|space ?xai|perplexity|scale ai|moonshot|"
    r"minimax|z[.]?ai)\b",
    re.I,
)
_INFRA_RX = re.compile(
    r"\b(?:data[ -]?cent(?:er|re)s?|datacent(?:er|re)s?|gpu(?:s| cloud)?|hbm\d*|"
    r"high.bandwidth memory|dram|nand|memory chips?|"
    r"memory (?:crunch|shortage|supply|demand|market|plants?|fabs?)|"
    r"ai chips?|accelerators?|"
    r"hyperscalers?|neoclouds?|servers?|racks?|semiconductors?|chipmakers?|"
    r"chipmaking|chip (?:boom|tax|demand|supply|shortage|industry|production|exports?)|"
    r"centros? de datos|foundr(?:y|ies)|fabs?|cowos|advanced packaging|optical|photonics?|"
    r"interconnects?|infiniband|nvlink|ethernet|networking chips?|"
    r"liquid cooling|immersion cooling|cloud infrastructure|compute capacity|"
    r"supply chain)\b",
    re.I,
)
_POWER_RX = re.compile(
    r"\b(?:grids?|power grids?|power supply|electricity demand|energy demand|transformers?|"
    r"switchgear)\b",
    re.I,
)
# 这些公司的名称本身就是明确 AI 产品/算力业务证据；不能把 SoftBank 这类广泛
# 投资集团放进来，否则一笔普通零售债又会因为公司名字被错误放行。
_AI_NATIVE_ENTITY_RX = re.compile(
    r"\b(?:coreweave|crusoe|cerebras|groq|nscale|yotta|lambda labs?|cohere|"
    r"elevenlabs|waymo|figure ai|humain|plusai|cognition)\b",
    re.I,
)
_SUPPLY_ENTITY_RX = re.compile(
    r"\b(?:nvidia|amd|tsmc|sk hynix|micron|broadcom|marvell|asml|supermicro|"
    r"equinix|mediatek|cxmt|kioxia|samsung)\b",
    re.I,
)
_SUPPLY_DEAL_RX = re.compile(
    r"\b(?:supply|contracts?|deals?|partners?|agreements?)\b", re.I
)
_FINANCING_RX = re.compile(
    r"\b(?:bonds?|notes?|debt|loans?|credit facilit(?:y|ies)|financ(?:e|es|ed|ing)|"
    r"funding|fundrais(?:e|es|ing)|raises?\b.{0,28}\b(?:million|billion|funds?)|"
    r"ipos?|initial public offering|spac merger|capital raise)\b",
    re.I,
)
# 二级市场和经营数据不是一回事：股价走势始终排除；销售/利润若同时揭示
# memory crunch、AI server demand 等供给事实则保留，不能误杀用户点名的产业链。
_STOCK_MARKET_RX = re.compile(
    r"\b(?:market cap|market value|price target|record stock runs?|favorite stock|"
    r"fund bets?|taking stock|nasdaq|dow|s&p)\b|"
    r"\b(?:shares?|stocks?)\b.{0,34}\b(?:rise|rises|rose|soar|soars|surge|surges|"
    r"jump|jumps|climb|climbs|gain|gains|fall|falls|drop|drops|tumble|tumbles|"
    r"slide|slides|sink|sinks|rally|rallies)\b|"
    r"\b(?:rise|rises|rose|soar|soars|surge|surges|jump|jumps|climb|climbs|"
    r"gain|gains|fall|falls|drop|drops|tumble|tumbles|slide|slides|sink|sinks)\b"
    r".{0,34}\b(?:shares?|stocks?)\b",
    re.I,
)
_FINANCIAL_RESULTS_RX = re.compile(
    r"\b(?:earnings|quarterly results?|profits?|revenue|sales (?:forecast|outlook|"
    r"guidance|estimates?|miss|beat|rise|rises|rose|jump|jumps|soar|soars|fall|falls)|"
    r"miss(?:es|ed)?\b.{0,30}\b(?:sales|revenue|earnings)?\s*estimates?)\b",
    re.I,
)
_FINANCE_COMMENTARY_RX = re.compile(
    r"\b(?:bond yields?|convertible bonds?|investor frenzy|strips? safeguards?|"
    r"market can absorb|credit markets?)\b",
    re.I,
)
_MACRO_WEAK_RX = re.compile(
    r"\b(?:econom(?:y|ies)|fiscal buffers?|trade gap|currency market|"
    r"manufacturing gauge)\b",
    re.I,
)
_PERIPHERAL_RX = re.compile(
    r"\b(?:almost anyone|homeowners?|households?|"
    r"make money selling electricity|sell(?:ing)? excess energy)\b",
    re.I,
)
_PERSONNEL_RX = re.compile(
    r"\b(?:hires?|hiring|joins?|appoints?|names?)\b.{0,70}"
    r"\b(?:executive|chief|ceo|president|board|revenue officer)\b|"
    r"\b(?:hires?|hiring|takes? the reins|pay targets?|compensation|bonuses?|salary|"
    r"successor|succession|steps down|resigns?|retires?|layoffs?|job cuts?)\b",
    re.I,
)
_CHATTER_RX = re.compile(
    r"\b(?:says?|sees?|expects?|urges?|blasts?|rebukes?|warns?|argues?|believes?|"
    r"predicts?|reassures?|touts?|claims?|fumbled at communicating|"
    r"looks? to\b.{0,45}\bfor growth|banking on\b.{0,45}\bfor growth)\b",
    re.I,
)
_MATERIAL_EVENT_RX = re.compile(
    r"\b(?:acquir(?:e|es|ed|ing)|agrees? to buy|buys?|deal|contracts?|"
    r"partner(?:s|ed|ing)?|launch(?:es|ed|ing)?|releas(?:e|es|ed|ing)|"
    r"roll(?:s|ed|ing)? out|unveil(?:s|ed|ing)?|build(?:s|ing)?|construction|"
    r"expand(?:s|ed|ing)?|production|supply|shortage|capacity|orders?|"
    r"ship(?:s|ped|ping|ments?)|goes? online|rules?|regulat(?:e|ion)|"
    r"ban(?:s|ned|ning)?|lawsuit|sues?|court|outages?|hack(?:s|ed|ing)?)\b",
    re.I,
)
_NEW_MODEL_RX = re.compile(
    r"\b(?:new|more powerful|cheaper|better)\b.{0,45}\b(?:ai )?models?\b|"
    r"\b(?:ai )?models?\b.{0,45}\b(?:outperforms?|cheaper|better)\b",
    re.I,
)

# 正文容器,按信任度从高到低。〔待核验:前两条是按 Bloomberg 页面常见结构写的
# 猜测,article/main 是兜底 —— 第一批正文抓回来后按 extractor 字段核对。〕
BODY_SELECTORS = (
    "div.body-content",
    "div[data-component='article-body']",
    "article",
    "main",
)
BODY_PARAGRAPH_SELECTORS: tuple[str, ...] = ()
RAW_HTML_REJECT_PATTERNS: tuple[str, ...] = ()
ALLOW_TRAFILATURA = True
MIN_BODY_CHARS = 600
MIN_BODY_WORDS = 0
MIN_BODY_COVERAGE = 0.0
REQUIRES_AUTH = True

# 时间硬地板,与 FT 同一条:比这更早的一律不抓,写在代码里不靠命令行记得传。
EARLIEST = "2025-01-01"

# 付费墙/真人验证的指纹。〔待核验:按 Bloomberg 拦截页的公开文案写的,
# 第一次撞墙时用失败原话校对。〕
BARRIER_RX = re.compile(
    r"(subscribe to continue|to continue, please|are you a robot|"
    r"bloomberg\.com/subscriptions|get unlimited access|unusual activity)",
    re.I,
)


def article_id(url: str) -> str:
    """``日期-slug`` 当身份:slug 是站方发的,加上日期防同名;文件名安全。"""
    from urllib.parse import urlsplit

    match = _ARTICLE_RX.search(urlsplit(url).path)
    return f"{match.group(1)}-{match.group(2)}" if match else ""


def search_url(keyword: str, page: int = 1) -> str:
    raise RuntimeError("Bloomberg 未配搜索线:确定性优先,只走栏目页召回")


def hub_url(slug: str, page: int = 1) -> str:
    """栏目页地址。**没有分页**:Bloomberg 栏目页是无限滚动,?page=N 不存在,
    第 2 页就是第 1 页 —— 翻页循环靠「没有新的」自然停下,假装有分页只会白开窗口。
    """
    return f"{HOME}/{str(slug).strip('/')}"


def admission_reason(title: str, identifier: str = "") -> str:
    """返回打开正文前的准入理由；空串表示栏目页的侧栏/推荐漏项。

    ``identifier`` 只补标题锚点暂时是摄影署名的卡片。它来自 Bloomberg 自己的
    文章 slug，不拿正文或搜索命中猜主题。融资稿必须明确指向 AI、算力基础设施
    或 AI 原生公司；公司广泛涉足 AI（例如 SoftBank）本身不构成证据。
    """
    title = clean_text(title)
    slug = clean_text(identifier[11:].replace("-", " ")) if identifier else ""
    evidence = f"{title} {slug}"
    direct_ai = bool(_AI_TOPIC_RX.search(evidence))
    strong_infra = bool(_INFRA_RX.search(evidence))
    native_entity = bool(_AI_NATIVE_ENTITY_RX.search(evidence))
    supply_entities = {
        match.group(0).lower() for match in _SUPPLY_ENTITY_RX.finditer(evidence)
    }
    supply_entity = bool(supply_entities)
    supply_deal = bool(
        len(supply_entities) >= 2 and _SUPPLY_DEAL_RX.search(evidence)
    )
    power_in_context = bool(
        _POWER_RX.search(evidence)
        and (direct_ai or strong_infra or native_entity or supply_entity)
    )
    infra = strong_infra or power_in_context or supply_deal
    if not (direct_ai or infra or native_entity):
        return ""

    # 负向判断只看当前标题：Bloomberg 会在不改 URL 的情况下重写标题（现场有
    # ``mediatek-shares-soar`` 后来改成 Nvidia/MediaTek AI 芯片交易的实例）。
    # 旧 slug 只能补正向主题证据，不能推翻站方现在展示的明确产业标题。
    if _STOCK_MARKET_RX.search(title):
        return ""
    if _FINANCIAL_RESULTS_RX.search(title) and not strong_infra:
        return ""
    if _PERSONNEL_RX.search(title):
        return ""
    if _PERIPHERAL_RX.search(title):
        return ""

    financing = bool(_FINANCING_RX.search(evidence))
    if _FINANCE_COMMENTARY_RX.search(title) and not infra:
        return ""
    if _MACRO_WEAK_RX.search(title) and not infra:
        return ""
    # 对话/喊话只有同时交代真实产业动作才留下。数据中心债务、AI 公司融资本身
    # 就是可核验的产业事件；新模型发布/比较也属于用户明确关注的模型动态。
    if _CHATTER_RX.search(title) and not (
        _MATERIAL_EVENT_RX.search(title)
        or _NEW_MODEL_RX.search(title)
        or (financing and infra)
    ):
        return ""

    if financing and not (direct_ai or infra or native_entity):
        return ""
    return "core_infrastructure" if infra else "ai_article"


def parse_search_results(
    html: str,
    keyword: str,
    page_url: str = "",
) -> list[dict[str, Any]]:
    """解析一页栏目页:凡是匹配文章路径形态的链接都收,时间从卡片里的
    ``<time datetime>`` 读,读不到就空着 —— **不猜时间**,归 undated。"""
    base = page_url or HOME
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    # 标题来自「包着 <img> 的锚点」的行 —— 那种锚点的文字是图注/署名
    # (9-02 第二轮实测:「Andrey Rudakov/Bloomberg」被当成了标题),
    # 等着被同一篇文章不包图的正题锚点顶替。只有图锚点的行照收:召回优先。
    credit_titled: set[str] = set()
    for link in soup.find_all("a", href=re.compile(LINK_PATTERN)):
        url = canonical_url(link["href"], base)
        identifier = article_id(url)
        title = clean_text(link.get_text(" ", strip=True))
        if not identifier or len(title) < 12:
            continue
        wraps_image = link.find("img") is not None
        if identifier in by_id:
            if identifier in credit_titled and not wraps_image:
                by_id[identifier]["title_en"] = title
                credit_titled.discard(identifier)
            continue
        published = ""
        node = link
        # 上溯找同一张卡片里的时间;有 <time> 以它为准(带时分,更精确)。
        for _step in range(5):
            node = node.parent
            if node is None or node.name in {"body", "html"}:
                break
            time_node = node.find("time")
            if time_node is not None:
                published = clean_text(
                    time_node.get("datetime") or time_node.get_text(" ", strip=True)
                )
                break
        # 9-02 首轮实测:/ai 页的卡片上没有 <time>,九十多篇全进了 undated/;
        # 二轮又见到有 <time> 却只写「Sep 1」「2 hours ago」的 —— 非空但解析
        # 不出时刻,一样进 undated/。判据是「解析得出」而不是「非空」:
        # 解析不出就读文章路径里的 YYYY-MM-DD(article_id 前十位)——
        # 那是站方发的结构性事实,读它不是猜时间。
        if not parse_datetime(published):
            published = identifier[:10]
        row = {
            "article_id": identifier,
            "title_en": title,
            "url": url,
            "published_at": published,
            "section": "",
            "keywords": [keyword],
        }
        by_id[identifier] = row
        if wraps_image:
            credit_titled.add(identifier)
        rows.append(row)
    admitted: list[dict[str, Any]] = []
    for row in rows:
        reason = admission_reason(row["title_en"], row["article_id"])
        if not reason:
            continue
        row["admission_reason"] = reason
        admitted.append(row)
    return admitted


def barrier_before_body(text: str, title: str) -> bool:
    return _shared.barrier_before_body(text, title, BARRIER_RX)


def drop_padding(
    rows: dict[str, dict[str, Any]],
    searched: list[str],
) -> list[str]:
    """没有搜索线就没有凑数问题:凑数的指纹是「搜什么都返回它」,
    而这里根本不搜。"""
    return []


merge = _shared.merge


def admitted_rows(
    rows: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """同一准入作用于存量视图；只隐藏，不删除 ledger/archive 正本。"""
    values = list(rows.values()) if isinstance(rows, dict) else list(rows)
    return [
        row
        for row in values
        if admission_reason(
            str(row.get("title_en") or row.get("title") or ""),
            str(row.get("article_id") or ""),
        )
    ]


newest_first = _shared.newest_first
oldest_first = _shared.oldest_first


def floor_for(since: str) -> str:
    return _shared.floor_for(since, EARLIEST)


def within_window(row: dict[str, Any], since: str) -> bool:
    return _shared.within_window(row, since, EARLIEST)
