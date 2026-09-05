"""关键词表:**一个词就是一次搜索页打开**,所以宁可少而准。

按语义分组,理由:
组内的词问的是同一件事,统计命中时按组算才不会把"正中靶心的那篇"当成凑数剔掉。
"""
from __future__ import annotations

# 旧台账只记过一个笼统的专题标签；新数据按具体栏目保存，才能区分 AI 栏目和
# 半导体栏目。旧标签继续读，避免一次迁移让历史筛选失效。
TOPIC_LABEL = "FT 专题"
AI_HUB_LABEL = "FT · AI 专题"
SEMICONDUCTOR_HUB_LABEL = "FT · 半导体专题"
TOPIC_GROUP = "FT 专题页"

# 站长 2026-08-19 给的初始词表。改词表只改这里,不改抓取代码。
#
# 9-01 砍掉九个词(站长裁决:「都砍吧,我要精不要多」)。判据是当天对 353 篇
# 非科技版「正稿」的逐篇抽查,四种系统性假阳性各有名单为证:
# - 中文四词(AI 应用 / 智能体 / AI 编程 / 具身智能):FT 的英文索引匹配不了,
#   站方拿最近的生活方式稿填结果页(Garmin 手表、河边小玩意都进来了);
# - GitHub Copilot / Cursor AI:命中的多是播客文字稿里的**赞助商广告读稿**
#   (Farage/Burnham 政治播客、哥本哈根游记);
# - foundation model / retrieval augmented generation / inference cost:
#   被拆词宽松匹配 —— 慈善基金会、财政成本、艺博会全对上了。
# 它们的真命中几乎都被留下的词盖着(Nvidia / OpenAI / large language model 还在)。
KEYWORD_GROUPS: dict[str, tuple[str, ...]] = {
    "模型应用 · 通用组1": (
        "AI agent",
        "agentic AI",
        "AI coding",
        "embodied AI",
        "humanoid robot",
    ),
    "模型应用 · 通用组2": (
        "enterprise AI",
        "AI search",
        "AI chatbot",
        "AI assistant",
    ),
    "AI 芯片 · GPU/CPU": (
        "AI chip",
        "GPU",
        "semiconductor",
    ),
    # 以下六组是 2026-08-21 补的。原来的词表只问「AI 拿来做什么」和「芯片」,
    # 于是监管、电力、估值这三条 FT 写得最多的线整条漏在外面 —— 漏的不是几篇,
    # 是几个视角。
    "监管与政策": (
        "AI regulation",
        "AI Act",
        "chip export controls",
        "AI copyright",
    ),
    "算力与能源": (
        "AI data centre",
        "AI power demand",
        "data centre electricity",
        "AI infrastructure spending",
    ),
    "资本与公司": (
        "OpenAI",
        "Anthropic",
        "Nvidia",
        "TSMC",
        "AI valuation",
        "AI capex",
    ),
    "劳动力与社会": (
        "AI jobs",
        "AI layoffs",
        "AI in education",
    ),
    "模型与成本": (
        "large language model",
        "open-source model",
        "AI training data",
    ),
    "安全与地缘": (
        "AI safety",
        "deepfake",
        "China AI",
        "sovereign AI",
    ),
    # 专题页不是搜索词,但它是一条独立的召回线:编辑判定的「这是 AI 稿」。
    # 放进词表是为了让它在清单筛选和统计里和别的组一样有名有姓。
    "FT 专题页": (TOPIC_LABEL, AI_HUB_LABEL, SEMICONDUCTOR_HUB_LABEL),
}

# 比语义组粗一层的**主题域**。存在的理由是画图:分类色板只有八个槽,而
# 第九个类别**不许生成一个新颜色**(那会让两个色在色盲视角下分不开)。
# 语义组比色槽多(9-01 砍词后还有十个),主题域正好八个带色 + 一个中性。
#
# 这是「哪些组问的是同一个大话题」的声明,不是质量评价 —— 三个「模型应用」
# 组问的都是「AI 拿来做什么」,合成一域;专题页是一条召回线而不是一个话题,
# 所以它进中性那一档。
OTHER_DOMAIN = "其他"
DOMAINS: dict[str, tuple[str, ...]] = {
    "模型应用": ("模型应用 · 通用组1", "模型应用 · 通用组2"),
    "AI 芯片": ("AI 芯片 · GPU/CPU",),
    "监管与政策": ("监管与政策",),
    "算力与能源": ("算力与能源",),
    "资本与公司": ("资本与公司",),
    "劳动力与社会": ("劳动力与社会",),
    "模型与成本": ("模型与成本",),
    "安全与地缘": ("安全与地缘",),
    OTHER_DOMAIN: (TOPIC_GROUP,),
}

# 默认只跑这一组,先把链路跑通;要全量就 `--group all`。
DEFAULT_GROUP = "模型应用 · 通用组1"


def keywords_for(group: str) -> tuple[str, ...]:
    """按组名取词;``all`` 取全部并去重(保持声明顺序)。

    **专题标签不是搜索词**,永远不出现在这里 —— 否则程序会老老实实去 FT 的
    搜索框里搜「FT 专题」这四个汉字。它是另一条召回线的名字。
    """
    if group == "all":
        seen: dict[str, None] = {}
        for words in KEYWORD_GROUPS.values():
            for word in words:
                if word not in {TOPIC_LABEL, AI_HUB_LABEL, SEMICONDUCTOR_HUB_LABEL}:
                    seen.setdefault(word, None)
        return tuple(seen)
    if group == TOPIC_GROUP:
        return ()
    if group not in KEYWORD_GROUPS:
        raise KeyError(
            f"没有这一组关键词:{group};可选 {', '.join(KEYWORD_GROUPS)} 或 all"
        )
    return KEYWORD_GROUPS[group]


def group_of(word: str) -> str:
    """这个词属于哪个语义组;没声明的词自成一组。

    凑数判定按组计票而不按词计票 —— 「AI agent」和「agentic AI」问的是同一件事,
    一篇正中靶心的稿子同时命中它们是**真命中**的特征,不是凑数的特征。
    """
    for name, words in KEYWORD_GROUPS.items():
        if word in words:
            return name
    return f"单词:{word}"


def domain_of(group: str) -> str:
    """这个语义组属于哪个主题域;没声明的归到中性那一档。

    **不猜**:新加一个组而忘了归域,它只会变成灰色的「其他」,不会去顶掉
    某个已经有颜色的域 —— 颜色跟着实体走,不跟着排名走。
    """
    for name, groups in DOMAINS.items():
        if group in groups:
            return name
    return OTHER_DOMAIN


def domain_of_word(word: str) -> str:
    return domain_of(group_of(word))
