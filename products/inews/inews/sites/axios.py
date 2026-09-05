"""Axios：固定 Latest 搜索结果中的核心 AI 文字稿。

Axios 没有把搜索结果做成稳定的服务端分页；页面的 ``Show 10 more
results`` 会在原 DOM 中继续追加卡片。本适配器因此只声明一个固定入口，把展开
动作交给共享浏览器契约，然后在打开正文前再做一次严格、可解释的主题复核。

Axios 的 Smart Brevity 是短稿格式。正文仍同时检查字符数和英文词数，只是站点
门槛按这种体裁设定，不能沿用 WSJ 长文的 900 字硬门槛。
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from bs4 import BeautifulSoup, Tag

from inews.sites import _shared
from inews.textutil import canonical_url, clean_text, parse_datetime

KEY = "axios"
NAME = "Axios"
HOME = "https://www.axios.com"
LABEL = "AXIOS.COM"
TAGLINE = "Latest 核心 AI 文字稿"
OUT_DIR = "AXIOS.COM"

LATEST_AI_URL = (
    "https://www.axios.com/results?q=artificial%20intelligence&sort=2"
)
SEARCHABLE = False
LISTING_FETCHER = None
TOPIC_LABEL = "Axios AI Latest"
HUBS = ("artificial-intelligence-latest",)
HUB_LABELS = {HUBS[0]: TOPIC_LABEL}
# 这不是对 Axios 搜索排序的盲目信任：只有通过 admission_reason 的条目才进入
# 清单。通过后的标题已经由站点层证明是核心 AI，因此交给统一质量层直接准入，
# 也避免没有字面 ``AI`` 的 HBM / 数据中心标题被统一弱证据规则反向隐藏。
HUB_TIERS = {HUBS[0]: "trusted"}

# 页面不是无限滚动；共享浏览器会按可见文字逐批点击，等待每一批链接稳定后再点
# 下一次，并受统一的 8 次点击预算约束。
LISTING_SCROLLS = False
LOAD_MORE_TEXT = "show 10 more results"

RULES = (
    "只打开 Axios Latest 固定搜索页（artificial intelligence，sort=2），不做全站任意关键词搜索",
    "由共享浏览器逐次点击 Show 10 more results；每批 DOM 稳定后再继续，最多使用统一点击预算",
    "发现后复核模型研发、数据中心、关键器件与供应链，以及会改变这些产业的政策事件",
    "保留核心 AI 企业的融资估值、并购合作、商业模式和领头人战略动作；二级市场行情不入库",
    "医疗、教育、军用、消费电子、个人生活、纯人物口水、地方新闻和视频活动在正文前剔除",
    "Smart Brevity 正文需同时达到 450 字符与 75 个英文词；短视频说明和空壳摘要不能过关",
)

# Axios 正常文字稿是顶层日期路径。Local、newsletters、podcasts、events 等路径
# 天然不匹配，先用 URL 结构挡掉，不能等抓完正文才猜类型。
LINK_PATTERN = r"/\d{4}/\d{2}/\d{2}/[a-z0-9%._~-]+/?$"
_ARTICLE_RX = re.compile(
    r"/(\d{4})/(\d{2})/(\d{2})/([a-z0-9%._~-]+)/?$", re.I
)

BODY_SELECTORS = (
    '.gtmView[data-vars-page-type="story"] > div:last-child '
    '> div[data-chromatic="ignore"]',
)
# ``extract_bs4`` 在上面的容器内相对执行 selector；实页的九段 Smart Brevity
# 正文都在 p 中。不能改成 ``main p``，否则会吞入 Google preferred source 与图注。
BODY_PARAGRAPH_SELECTORS = ("p",)
RAW_HTML_REJECT_PATTERNS: tuple[str, ...] = ()
# 精确公开正文容器失效应如实失败；通用猜测会重新引入容器前的推广与图注。
ALLOW_TRAFILATURA = False
MIN_BODY_CHARS = 450
MIN_BODY_WORDS = 75
MIN_BODY_COVERAGE = 0.0
REQUIRES_AUTH = False
EARLIEST = "2025-01-01"

BARRIER_RX = re.compile(
    r"(?:just a moment|verify you are human|are you a robot|access denied|"
    r"enable javascript and cookies to continue)",
    re.I,
)

_AI_RX = re.compile(
    r"(?<![a-z0-9])(?:ai|a\.i\.|agi)(?![a-z0-9])|"
    r"\b(?:artificial[- ]intelligence|generative ai|genai|machine learning|"
    r"deep learning|large language models?|foundation[- ]models?|"
    r"frontier[- ]models?|reasoning[- ]models?|multimodal[- ]models?|"
    r"model providers?|"
    r"ai agents?|ai labs?|frontier labs?|model developers?|model[- ]audits?|"
    r"agentic|"
    r"model[- ]training|model[- ]inference|model[- ]registration|"
    r"openai|chatgpt|anthropic|claude|deepmind|gemini|gemma|"
    r"deepseek|hugging ?face|mistral|llama|qwen|grok|xai|perplexity|cohere|"
    r"scale ai|kimi|command r|gpt[- ]?\d+)\b",
    re.I,
)
_AI_LAB_RX = re.compile(
    r"\b(?:openai|anthropic|deepmind|xai|mistral|perplexity|cohere|"
    r"hugging ?face|humain)\b",
    re.I,
)
_AI_NATIVE_ENTITY_RX = re.compile(
    r"\b(?:openai|anthropic|deepmind|xai|mistral|perplexity|cohere|"
    r"hugging ?face|humain|coreweave|crusoe|cerebras|"
    r"groq|lambda(?: labs?)?|nscale|yotta)\b",
    re.I,
)
_KEY_LEADER_RX = re.compile(
    r"\b(?:elon musk|musk|sam altman|jensen huang|dario amodei|demis hassabis|"
    r"mark zuckerberg|satya nadella|lisa su|c\.?\s*c\.? wei)\b",
    re.I,
)
_STRATEGIC_ENTITY_RX = re.compile(
    r"\b(?:openai|anthropic|deepmind|xai|mistral|perplexity|cohere|"
    r"hugging ?face|humain|coreweave|crusoe|cerebras|groq|lambda(?: labs?)?|"
    r"nscale|yotta|nvidia|amd|tsmc|sk hynix|kioxia|cxmt|micron|samsung|"
    r"broadcom|marvell|intel|qualcomm|asml|arm|supermicro|meta|google|"
    r"microsoft|amazon|oracle|alibaba|tencent|bytedance|softbank|spacex)\b",
    re.I,
)
_STRATEGIC_MODEL_ENTITY_RX = re.compile(
    r"\b(?:nvidia|meta|google|microsoft|amazon|alibaba|tencent)\b",
    re.I,
)
_MODEL_ARTIFACT_RX = re.compile(
    r"\b(?:open[- ]weight|open[- ]source models?|closed[- ]source models?|"
    r"proprietary models?|model weights?|frontier[- ]level|"
    r"state[- ]of[- ]the[- ]art|scaling laws?)\b",
    re.I,
)
_MODEL_OBJECT_RX = re.compile(
    r"\b(?:ai agents?|ai models?|large language models?|foundation[- ]models?|"
    r"frontier[- ]models?|reasoning[- ]models?|multimodal[- ]models?|open[- ]weight|"
    r"open[- ]source models?|closed[- ]source models?|proprietary models?|"
    r"model[- ]training|model[- ]inference|model weights?|scaling laws?|"
    r"chatgpt|claude|gemini|gemma|deepseek|mistral|llama|qwen|grok|kimi|"
    r"command r|(?:compute|capability|scaling) power laws?|"
    r"laws? of (?:ai )?scaling|ai capability laws?|"
    r"gpt(?:[- ]?\d+)?)\b",
    re.I,
)
_MODEL_EVENT_OBJECT_RX = re.compile(
    rf"(?:{_MODEL_OBJECT_RX.pattern})|\bmodels?\b",
    re.I,
)
_VERSIONED_MODEL_ID_RX = re.compile(
    r"\b(?:gpt|claude|gemini|gemma|llama|qwen|grok|kimi|mistral)"
    r"[- ]?(?:v?\d+(?:\.\d+)?)\b",
    re.I,
)
_GENERIC_MODEL_RX = re.compile(r"\bmodels?\b", re.I)
_NON_TECH_MODEL_RX = re.compile(
    r"\b(?:business|pricing|revenue|operating|economic) models?\b", re.I
)
_MODEL_LIFECYCLE_ACTION_RX = re.compile(
    r"\b(?:launch(?:es|ed|ing)?|debut(?:s|ed)?|release[sd]?|"
    r"unveil(?:s|ed|ing)?|"
    r"publish(?:es|ed|ing)?|ship(?:s|ped|ping)?|roll(?:s|ed|ing)? out|"
    r"train(?:s|ed)?|(?<!model-)(?<!model )training|develop(?:s|ed|ing)?|"
    r"retir(?:e|es|ed|ing)|"
    r"(?:begin|begins|began|start|starts|started)\b.{0,30}\btraining|"
    r"(?:limit|limits|limited|restrict|restricts|restricted) access|"
    r"(?:make|makes|made)\b.{0,55}\b(?:available|the default|open source)|"
    r"open[- ]sources|open[- ]sourced|"
    r"open sources|open sourced)\b",
    re.I,
)
_MODEL_CHANGE_ACTION_RX = re.compile(
    r"\b(?:improv(?:e|es|ed|ing)|upgrad(?:e|es|ed|ing)|"
    r"enhanc(?:e|es|ed|ing)|extend(?:s|ed|ing)?|add(?:s|ed|ing)?|"
    r"double(?:s|d|ing)?|boost(?:s|ed|ing)?|giv(?:e|es|en|ing)|"
    r"compress(?:es|ed|ing)?|distill(?:s|ed|ing)?|refresh(?:es|ed|ing)?|"
    r"teach(?:es|ing)|taught|integrat(?:e|es|ed|ing)|outperform(?:s|ed|ing)?|"
    r"updat(?:e|es|ed|ing)|introduc(?:e|es|ed|ing)|deploy(?:s|ed|ing)?|"
    r"fine[- ]tun(?:e|es|ed|ing)|expand(?:s|ed|ing)?|"
    r"modif(?:y|ies|ied|ying)|redesign(?:s|ed|ing)?|"
    r"widen(?:s|ed|ing)?|equip(?:s|ped|ping)?|"
    r"cut(?:s|ting)?|lower(?:s|ed|ing)?|reduc(?:e|es|ed|ing)|"
    r"fall(?:s|ing)?|fell|drop(?:s|ped|ping)?|declin(?:e|es|ed|ing)|"
    r"pare(?:s|d|ing)?|switch(?:es|ed|ing)?|port(?:s|ed|ing)?|"
    r"reveal(?:s|ed|ing)?|tout(?:s|ed|ing)?|announc(?:e|es|ed|ing)|"
    r"tests?\b.{0,20}\b(?:new way|capabilit(?:y|ies)|reasoning|tools?|"
    r"benchmarks?|safety)|"
    r"set(?:s|ting)?\b.{0,24}\b(?:standard|record)|"
    r"(?:forecast|forecasts|forecasted|detail|details|detailed)\b.{0,35}"
    r"\b(?:scaling[- ]costs?|model costs?|training costs?))\b",
    re.I,
)
_MODEL_SUBSTANCE_RX = re.compile(
    r"\b(?:new\b.{0,35}\bmodels?|models?\b.{0,35}\bnew|"
    r"capabilit(?:y|ies)|benchmark(?:s|ed|ing)?|outperform(?:s|ed|ing)?|"
    r"reasoning|coding|architectures?|attention designs?|context windows?|"
    r"limit(?:s|ed|ing)? access|restrict(?:s|ed|ing)? access|model access|"
    r"post[- ]training|pre[- ]training|distillation|training compute|"
    r"training data|model architecture|scaling laws?|model weights?|"
    r"scaling[- ]costs?|inference costs?|cheaper inference|"
    r"mixture[- ]of[- ]experts|moe routing|sparse[- ]attention|"
    r"parameter count|persistent memory|speculative decoding|"
    r"tool[- ]use|tool calling|call tools?|retrieval)\b|"
    r"\btests?\b.{0,20}\b(?:new way|capabilit(?:y|ies)|reasoning|tools?|"
    r"benchmarks?|safety)\b",
    re.I,
)
_MODEL_STRONG_SUBSTANCE_RX = re.compile(
    r"\b(?:new\b.{0,35}\bmodels?|models?\b.{0,35}\bnew|"
    r"capabilit(?:y|ies)\b.{0,24}\b(?:launch|release|benchmark|improv)|"
    r"benchmark(?:s|ed|ing)?|outperform(?:s|ed|ing)?|architectures?|"
    r"attention designs?|context windows?|post[- ]training|pre[- ]training|"
    r"distillation|training compute|training data|model architecture|"
    r"scaling laws?|model weights?|mixture[- ]of[- ]experts|open[- ]weight|"
    r"open[- ]source models?)\b",
    re.I,
)
_MODEL_RESULT_ASSERTION_RX = re.compile(
    r"\b(?:new\b.{0,35}\bmodels?|models?\b.{0,35}\bnew)\b.{0,70}"
    r"\b(?:cheaper|better|faster|stronger|benchmark(?:s|ed|ing)?|"
    r"outperform(?:s|ed|ing)?|frontier[- ]level|results?|standard)\b|"
    r"\b(?:open[- ]weight|open[- ]source)\b.{0,55}"
    r"\b(?:benchmark(?:s|ed|ing)?|outperform(?:s|ed|ing)?|"
    r"frontier[- ]level|results?)\b",
    re.I,
)
_NON_MODEL_DELIVERABLE_RX = re.compile(
    r"\b(?:annual reports?|usage reports?|hiring initiatives?|employee surveys?|"
    r"employees?|new office|product managers?|cookbooks?|branded merchandise|"
    r"merchandise|themed office|team benefits?|guides?|documentation|manuals?|"
    r"handbooks?|tutorials?)\b",
    re.I,
)
_AI_OPERATIONAL_EVENT_RX = re.compile(
    r"\b(?:outages?|breach(?:es|ed)?|hack(?:s|ed|ing)?|"
    r"vulnerabilit(?:y|ies)|shutdown)\b",
    re.I,
)
_INTRINSIC_INFRA_RX = re.compile(
    r"\b(?:ai chips?|accelerators?|gpus?|hbm\d*|high.bandwidth memory|dram|"
    r"nand|memory chips?|memory (?:makers?|supply|demand|shortage|crunch|plants?)|"
    r"\d+(?:\.\d+)?nm chips?|chip taxes?|semiconductor taxes?|"
    r"data[ -]?cent(?:er|re)s?|datacenters?|ai infrastructure|ai servers?|"
    r"server racks?|compute clusters?|ai clusters?|inference[- ]clusters?|"
    r"compute fleet|"
    r"compute capacity|compute futures?|training infrastructure|"
    r"supercomputers?|hyperscalers?|"
    r"neoclouds?|semiconductors?|chipmakers?|chipmaking tools?|chip boom|"
    r"chips? (?:exports?|supply|demand|production|capacity)|"
    r"semiconductor equipment|chip production|supplier networks?|"
    r"foundr(?:y|ies)|fabs?|cowos|"
    r"advanced packaging|chip packaging|packaging shortage|wafers?|lithography|"
    r"interconnects?|infiniband|nvlink|cxl|photonics?|"
    r"networking chips?|data center network(?:s|ing)?|optical(?: networks?|"
    r"interconnects?|transceivers?)|liquid[- ]cooling|immersion[- ]cooling|"
    r"data center power|enterprise storage|flash memory|tpus?|rubin|"
    r"falcon shores|"
    r"blackwell(?: ultra)?|"
    r"h100|h200|b100|b200|gb200|gb300|mi300x?|mi325x|mi350x?)\b",
    re.I,
)
_CONTEXTUAL_INFRA_RX = re.compile(
    r"\b(?:servers?|ssds?|nvme|hard[- ]drives?|hdds?|ethernet|subsea cables?|"
    r"cooling systems?|chillers?|power purchase agreements?|ppas?|gas turbines?|"
    r"ai campuses?|private fiber networks?|fiber networks?|networking units?|"
    r"optical circuit switches?|nuclear (?:power|plants?)|power supply|"
    r"power consumption|electricity demand|energy demand|energy use|water use|"
    r"energy (?:and|or) water|grid capacity|power grids?|electric grids?|grids?|"
    r"transformers?|switchgear|supply chains?|storage systems?)\b",
    re.I,
)
_CORE_ENTITY_RX = re.compile(
    r"\b(?:nvidia|amd|tsmc|sk hynix|kioxia|cxmt|micron|samsung|broadcom|marvell|intel|"
    r"qualcomm|asml|arm|supermicro|coreweave|groq|cerebras|oracle|"
    r"microsoft azure|amazon web services|aws|google cloud)\b",
    re.I,
)
_INFRA_TRANSITIVE_ACTION_RX = re.compile(
    r"\b(?:launch(?:es|ed|ing)?|release[sd]?|unveil(?:s|ed|ing)?|"
    r"open(?:s|ed|ing)?|ship(?:s|ped|ping)?|deploy(?:s|ed|ing)?|"
    r"build(?:s|ing)?|expand(?:s|ed|ing)?|construct(?:s|ed|ing)?|"
    r"breaks? ground|broke ground|"
    r"commission(?:s|ed|ing)?|connect(?:s|ed|ing)?|"
    r"bring(?:s|ing)?\b.{0,24}\bonline|brought\b.{0,24}\bonline|"
    r"start(?:s|ed|ing)?|restart(?:s|ed|ing)?|complet(?:e|es|ed|ing)|"
    r"scrap(?:s|ped|ping)?|cancel(?:s|ed|led|ing)?|idle(?:s|d|ing)?|"
    r"mothball(?:s|ed|ing)?|decommission(?:s|ed|ing)?|"
    r"shelv(?:e|es|ed|ing)|recall(?:s|ed|ing)?|"
    r"acquir(?:e|es|ed|ing)|buy(?:s|ing)?|bought|"
    r"purchas(?:e|es|ed|ing)|sell(?:s|ing)?|sold|"
    r"leas(?:e|es|ed|ing)|procure(?:s|d|ment)|reserv(?:e|es|ed|ing)|"
    r"switch(?:es|ed|ing)?|swap(?:s|ped|ping)?|tap(?:s|ped|ping)?|"
    r"select(?:s|ed|ing)?|choos(?:e|es|ing)|chose|"
    r"invest(?:s|ed|ing)?|financ(?:e|es|ed|ing)|fund(?:s|ed|ing)?|"
    r"spend(?:s|ing)?|sign(?:s|ed|ing)?|partner(?:s|ed|ing)?|"
    r"secur(?:e|es|ed|ing)|wins?|qualif(?:y|ies|ied|ying)|"
    r"block(?:s|ed|ing)?|limit(?:s|ed|ing)?|"
    r"cut(?:s|ting)?|lift(?:s|ed|ing)?|boost(?:s|ed|ing)?|"
    r"double(?:s|d|ing)?)\b",
    re.I,
)
_INFRA_INTRANSITIVE_ACTION_RX = re.compile(
    r"\b(?:opens?|opened|launch(?:es|ed)|debut(?:s|ed)|ships?|shipped|"
    r"comes? online|came online|goes? online|went online|"
    r"starts? (?:production|operations)|started (?:production|operations))\b",
    re.I,
)
_INFRA_INTRANSITIVE_TAIL_RX = re.compile(
    r"^\s*(?:(?:now|today|tomorrow|finally|officially|commercially)|"
    r"(?:in|on|at|outside|near|by|after|before|amid|with|for|following)\b.*|"
    r"(?:next|this|early|late)\b.*|ahead\b.*)?[.!?]?\s*$",
    re.I,
)
_POLICY_SUBSTANCE_RX = re.compile(
    r"\b(?:ai(?:\s+\w+){0,2}\s+act|law|legislation|regulat(?:e|es|ed|ion)|rule[sd]?|"
    r"ban(?:s|ned|ning)?|restrictions?|"
    r"executive order|export controls?|sanctions?|blacklist|procurement (?:ban|guidance)|"
    r"court|lawsuit|copyright(?: suit)?|intellectual property|patents?|"
    r"trade[- ]secrets?|reviews?|competition review|regulatory review|"
    r"antitrust|competition (?:case|regulator|rules?|probe)|consent order|"
    r"probe|inquiry|investigat(?:e|es|ed|ing|ion)|hearing|subpoenas?|"
    r"fine[sd]?|penalt(?:y|ies)|"
    r"oversight|policy framework|regulatory framework|risk label|"
    r"government designation|systemic[- ]risk platform|permits?|moratorium|"
    r"zoning|accord|entity list|injunction|export licenses?|"
    r"registration(?: requirements?)?|disclosure of (?:ai )?model training data|"
    r"mandatory (?:disclosure|reporting)|"
    r"licenses?\b.{0,35}\b(?:ai[- ]chips?|accelerators?|nvidia)?\b.{0,18}exports?|"
    r"binding (?:model[- ]audit )?standards?|model evaluation standards?|"
    r"model[- ]audits?|audit (?:requirements?|deadlines?)|"
    r"ai liability directives?|reporting requirements?|"
    r"appropriat(?:e|es|ed|ing|ion)|"
    r"national ai compute strategy)\b|"
    r"\brequires?\b.{0,45}\breport\b|"
    r"\b(?:ai|artificial[- ]intelligence).{0,30}\b(?:policy|line)\b|"
    r"\b(?:ai|artificial[- ]intelligence).{0,35}\b(?:bill|law|rule|regulation)\b|"
    r"\b(?:bill|law|rule|regulation)\b.{0,35}\b(?:ai|artificial[- ]intelligence)\b",
    re.I,
)
_OFFICIAL_POLICY_ACTOR_RX = re.compile(
    r"\b(?:white house|congress|senate(?: committee)?|house|pentagon|ftc|doj|"
    r"fcc|federal communications commission|ferc|"
    r"federal energy regulatory commission|bis|bureau of industry and security|"
    r"cma|competition and markets authority|european data protection board|edpb|"
    r"courts?|judges?|eu parliament|european parliament|european council|"
    r"governors?|lawmakers?|regulators?|agenc(?:y|ies)|"
    r"commerce department|state department|treasury|federal government|"
    r"united states government|uk government|uk competition regulator|"
    r"california|canada|canadian parliament|china|india|australia|japan|"
    r"japanese regulator|nist|"
    r"european commission|eu|g20|courts?)\b",
    re.I,
)
_UPPER_US_ACTOR_RX = re.compile(r"(?:\bUS\b|\bU\.S\.(?!\w))")
_LEADING_NATIONAL_POLICY_ACTOR_RX = re.compile(
    r"^(?:the\s+)?(?:france|south korea|germany|taiwan|canada|australia|"
    r"india|china|japan|brazil|united kingdom|uk)\b",
    re.I,
)
_POLICY_PROCESS_RX = re.compile(
    r"\b(?:draws?|sets?|changes?|updates?|tightens?|reviews?|assesses?)\b"
    r".{0,45}\b(?:ai )?(?:line|policy|rules?|framework|oversight)\b|"
    r"\b(?:consider(?:s|ed|ing)?|weigh(?:s|ed|ing)?|review(?:s|ed|ing)?|"
    r"propos(?:e|es|ed|ing)|draft(?:s|ed|ing)?)\b"
    r".{0,55}\b(?:export controls?|sanctions?|rules?|regulations?|bills?|"
    r"frameworks?|standards?)\b|"
    r"\b(?:delays?|postpones?)\b.{0,30}\b(?:vote|hearing)\b|"
    r"\bfaces? tighter\b.{0,30}\brules?\b|"
    r"\b(?:strikes?|reaches?|agrees? (?:on|to))\b.{0,45}\b(?:accord|framework)\b",
    re.I,
)
_POLICY_STATUS_RX = re.compile(
    r"\b(?:bans?|blacklists?|restrictions?|designations?|risk labels?|"
    r"sanctions?)\b.{0,28}"
    r"\b(?:is on|are on|stands?|remains?|stays?|in effect)\b|"
    r"\b(?:wins?|loses?|settles?)\b.{0,28}\bcourt challenge\b|"
    r"\bfaces? tighter\b.{0,30}\b(?:rules?|regulation|restrictions?)\b",
    re.I,
)
_SPECULATIVE_POLICY_RX = re.compile(
    r"\b(?:may|might|could|would|expected to|hopes? to|"
    r"float(?:s|ed|ing)?|call(?:s|ed|ing)? (?:for|on)|"
    r"ask(?:s|ed|ing)?|press(?:es|ed|ing)?|plans? to|proposes? to|"
    r"urge(?:s|d|ing)?|"
    r"want(?:s|ed|ing)?|consider(?:s|ed|ing)?|mull(?:s|ed|ing)?|"
    r"warn(?:s|ed|ing)?)\b",
    re.I,
)
_POLICY_ACTION_RX = re.compile(
    r"\b(?:introduc(?:e|es|ed|ing)|unveil(?:s|ed|ing)?|file[sd]?|pass(?:es|ed)?|"
    r"enact(?:s|ed)?|sign(?:s|ed|ing)?|issue[sd]?|publish(?:es|ed|ing)?|"
    r"adopt(?:s|ed)?|approv(?:e|es|ed)|add(?:s|ed|ing)?|require(?:s|d|ing)?|"
    r"advanc(?:e|es|ed|ing)|mandat(?:e|es|ed|ing)|"
    r"designat(?:e|es|ed|ing)|grant(?:s|ed|ing)?|revok(?:e|es|ed|ing)|"
    r"ratif(?:y|ies|ied|ying)|tighten(?:s|ed|ing)?|stays?|stayed|"
    r"amend(?:s|ed|ing)?|suspend(?:s|ed|ing)?|rescind(?:s|ed|ing)?|"
    r"repeal(?:s|ed|ing)?|abolish(?:es|ed|ing)?|"
    r"postpon(?:e|es|ed|ing)|appeal(?:s|ed|ing)?|"
    r"relax(?:es|ed|ing)?|narrow(?:s|ed|ing)?|"
    r"broaden(?:s|ed|ing)?|expand(?:s|ed|ing)?|exempt(?:s|ed|ing)?|"
    r"promulgat(?:e|es|ed|ing)|"
    r"appropriat(?:e|es|ed|ing)|clear(?:s|ed|ing)?|drop(?:s|ped|ping)?|"
    r"reject(?:s|ed|ing)?|certif(?:y|ies|ied|ying)|extend(?:s|ed|ing)?|"
    r"allows?\b.{0,28}\b(?:case|lawsuit|suit)\b.{0,20}\bproceed|"
    # Bare ``ban`` is often only a proposal; an acted verb plus a public actor or
    # legal instrument is required by ``admission_reason`` below.
    r"impose[sd]?|block(?:s|ed|ing)?|bans|banned|banning|sue[sd]?|cracks? down|"
    r"reaffirm(?:s|ed|ing)?|takes? effect|enters? (?:into )?force|uphold(?:s|held)|"
    r"veto(?:es|ed|ing)?|fine[sd]?|subpoena(?:s|ed|ing)?|"
    r"investigat(?:e|es|ed|ing)|"
    r"launch(?:es|ed|ing)?\b.{0,28}\b(?:probe|inquiry|investigation)|"
    r"holds?\b.{0,24}\bhearing|dismiss(?:es|ed|ing)?|settles?|settled|"
    r"strikes? down|strikes?\b.{0,35}\b(?:accord|framework)|"
    r"reaches?\b.{0,35}\b(?:accord|framework)|rules? against|orders?|"
    r"opens?\b.{0,30}\b(?:investigation|probe|inquiry)|"
    r"closes?\b.{0,30}\b(?:investigation|probe|inquiry))\b",
    re.I,
)
_POLICY_DEFINITIVE_ACTION_RX = re.compile(
    r"\b(?:introduces?|introduced|files?|filed|passes|passed|enacts?|enacted|"
    r"signs|signed|issues?|issued|publishes?|published|adopts?|adopted|"
    r"approves?|approved|adds?|added|requires?|required|advances?|advanced|"
    r"mandates?|mandated|designates?|designated|grants?|granted|"
    r"revokes?|revoked|ratifies?|ratified|tightens?|tightened|stays?|stayed|"
    r"amends?|amended|suspends?|suspended|rescinds?|rescinded|"
    r"repeals?|repealed|abolishes?|abolished|postpones?|postponed|"
    r"appeals?|appealed|relaxes?|relaxed|narrows?|narrowed|"
    r"broadens?|broadened|expands?|expanded|exempts?|exempted|"
    r"promulgates?|promulgated|"
    r"appropriates?|appropriated|clears?|cleared|drops?|dropped|"
    r"rejects?|rejected|certifies?|certified|extends?|extended|"
    r"allows?\b.{0,28}\b(?:case|lawsuit|suit)\b.{0,20}\bproceed|"
    r"imposes?|imposed|blocks|blocked|bans|banned|sues|sued|cracks? down|"
    r"reaffirms?|reaffirmed|takes? effect|enters? (?:into )?force|upholds?|upheld|"
    r"vetoes?|vetoed|fines?|fined|subpoenas?|subpoenaed|"
    r"investigates?|investigated|"
    r"launches?\b.{0,28}\b(?:probe|inquiry|investigation)|"
    r"holds?\b.{0,24}\bhearing|dismisses?|dismissed|settles?|settled|"
    r"strikes? down|rules? against|orders?|ordered|"
    r"opens?\b.{0,30}\b(?:investigation|probe|inquiry)|"
    r"opened\b.{0,30}\b(?:investigation|probe|inquiry)|"
    r"closes?\b.{0,30}\b(?:investigation|probe|inquiry)|"
    r"closed\b.{0,30}\b(?:investigation|probe|inquiry))\b",
    re.I,
)
_SECONDARY_MARKET_HARD_RX = re.compile(
    r"\b(?:reit|adrs?|etfs?|dividend|bond yields?|share price|price target|"
    r"market cap|market value|wall street|stock picks?|stocks? to buy|"
    r"favorite stocks?|investment portfolio|stock portfolio|equity portfolio|"
    r"portfolio holdings?|portfolio allocation|portfolio rotation|"
    r"(?:ai )?fund bets?|fund allocation|fund rotation|"
    r"ai trade|nasdaq|dow jones|s&p)\b|"
    r"\b(?:forward|valuation|earnings|revenue) multiples?\b|"
    r"\boptions?\s+(?:bulls?|bears?|traders?)\b|"
    r"\b(?:record closing high|all[- ]time high)\b|"
    r"\b(?:bulls?|bears?)\b.{0,20}\b(?:pile|rush|bet|load)\b|"
    r"\banalysts?\b.{0,22}\b(?:raise|cut|lift|lower|upgrade|downgrade)[sd]?\b",
    re.I,
)
_SHARE_MOVE_RX = re.compile(
    r"\b(?:shares?|stocks?)\b.{0,18}\b(?:are\s+)?(?:up|down|rise|rises|rose|"
    r"soar|soars|surge|surges|jump|jumps|climb|climbs|gain|gains|fall|falls|"
    r"fell|drop|drops|tumble|tumbles|slide|slides|slip|slips|slipped|sink|sinks|"
    r"rally|rallies|pop|pops|popped|plunge|plunges|plunged|slump|slumps|"
    r"slumped|retreat|retreats|retreated|advance|advances|advanced|"
    r"hit|hits|reaches?)\b|"
    r"\b(?:rise|rises|rose|soar|soars|surge|surges|jump|jumps|climb|climbs|"
    r"gain|gains|fall|falls|fell|drop|drops|tumble|tumbles|slide|slides|"
    r"slip|slips|slipped|sink|sinks|pop|pops|popped|plunge|plunges|plunged|"
    r"slump|slumps|slumped|retreat|retreats|retreated|advance|advances|"
    r"advanced)\b"
    r".{0,18}\b(?:shares?|stocks?)\b",
    re.I,
)
_IMPLIED_EQUITY_MOVE_RX = re.compile(
    r"^(?:nvidia|amd|intel|broadcom|marvell|micron|tsmc|sk hynix|samsung|"
    r"asml|arm|qualcomm|supermicro|coreweave|microsoft|meta|google|"
    r"alphabet|amazon|"
    r"oracle)\b.{0,24}"
    r"\b(?:gains?|rises?|jumps?|surges?|soars?|pops?|plunges?|slumps?|"
    r"falls?|fell|drops?|slips?|skids?|leaps?|vaults?|tumbles?|"
    r"retreats?|advances?|rockets?)\b.{0,12}"
    r"(?:\d+(?:\.\d+)?%|\$\d)|"
    r"\b(?:adds?|loses?|sheds?)\b.{0,24}(?:\$[\d.]+|[\d.]+\s*(?:billion|"
    r"million))\b.{0,12}\bin (?:market )?value\b",
    re.I,
)
_PUBLIC_MARKET_CONTEXT_RX = re.compile(
    r"\b(?:price[- ]to[- ]earnings|p/?e ratio|options? traders?|"
    r"short sellers?|trillion[- ]dollar company)\b|"
    r"\b(?:nvidia|amd|intel|broadcom|marvell|micron|tsmc|sk hynix|samsung|"
    r"microsoft|meta|google|alphabet|amazon|oracle)\b.{0,35}"
    r"\b(?:hits?|reaches?|tops?)\b.{0,18}\$[\d.]+\s*(?:trillion|billion)?"
    r"\s+valuation\b",
    re.I,
)
_OPERATING_PERCENT_RX = re.compile(
    r"\b\d+(?:\.\d+)?%(?=\s|$)\s+(?:(?:more|higher|less|lower)\s+)?"
    r"(?:hbm\s+)?(?:capacity|output|production|yield|throughput|shipments?)\b|"
    r"\b(?:capacity|output|production|yield|throughput|shipments?)\b"
    r"\s+(?:rises?|rose|jumps?|surges?|grows?|grew|increases?|increased|"
    r"falls?|fell|drops?|declines?|improves?|improved|reaches?|hits?)"
    r"(?:\s+by|\s+to)?\s+\d+(?:\.\d+)?%(?=\s|$)|"
    r"\b\d+(?:\.\d+)?%(?=\s|$)\s+in\s+(?:\w+[- ]?){0,4}"
    r"(?:capacity|output|production|yield|throughput|shipments?)\b",
    re.I,
)
_INVOICE_BILL_RX = re.compile(
    r"(?:\$[\d.]+\s*(?:million|billion|m|bn)?\s+bill|"
    r"\bbill\b.{0,28}\b(?:invoice|payment|compute charges?|with microsoft))",
    re.I,
)
_INVESTMENT_ADVICE_RX = re.compile(
    r"\b(?:should you buy|how to invest in|best\b.{0,24}\bstocks?|"
    r"stocks? to buy|stock picks?|buy and hold|for your portfolio)\b",
    re.I,
)
_FINANCIAL_RESULTS_RX = re.compile(
    r"\b(?:earnings|quarterly results?|profits?|revenue(?!\s+model)|"
    r"sales (?:forecast|outlook|guidance|estimates?|miss|beat|rise|rises|rose|"
    r"jump|jumps|soar|soars|fall|falls)|"
    r"miss(?:es|ed)?\b.{0,30}\b(?:sales|revenue|earnings)?\s*estimates?)\b",
    re.I,
)
_PRIMARY_CAPITAL_RX = re.compile(
    r"\b(?:funding rounds?|series\s+[a-z]|seed round|venture round|"
    r"credit facilit(?:y|ies)|project debt|debt financing|pre[- ]ipo|"
    r"initial public offering|ipos?|capital raise|stake funding)\b|"
    r"\b(?:rais(?:e|es|ed|ing)|lands?|landed|pulls? in|pulled in|"
    r"closes?|closed|finaliz(?:e|es|ed|ing))\b"
    r".{0,36}(?:\$[\d.]+\s*(?:m|bn|b|million|billion)?|"
    r"[\d.]+\s*(?:million|billion)|funding|series\s+[a-z]|"
    r"credit facilit(?:y|ies)|capital)\b|"
    r"\b(?:(?:to |will )?invest(?:s|ed|ing)?|commit(?:s|ted|ting)?|"
    r"pledge(?:s|d|ing)?)\b"
    r".{0,45}(?:\$[\d.]|"
    r"[\d.]+\s*(?:million|billion)|\bin\b|\binto\b)|"
    r"\b(?:valued at|reaches?\b.{0,24}\bvaluation|valuation\b.{0,32}"
    r"(?:funding round|series\s+[a-z]))\b|"
    r"\b(?:seeks?|secures?|obtains?)\b.{0,38}\b(?:loan|financing|funding)\b|"
    r"\b(?:receiv(?:e|es|ed|ing)|attract(?:s|ed|ing)?|secur(?:e|es|ed|ing))\b"
    r".{0,42}(?:\$[\d.]|[\d.]+\s*(?:million|billion)|strategic (?:backing|"
    r"investment)|sovereign investors?|new backing)\b|"
    r"\bback(?:s|ed|ing)?\b.{0,55}(?:\$[\d.]|[\d.]+\s*(?:million|billion)|"
    r"strategic investment|funding)\b",
    re.I,
)
_TRANSACTION_VERB_RX = re.compile(
    r"\b(?:acquir(?:e|es|ed|ing)|agrees? to buy|buys?|bought|takes? over|"
    r"absorb(?:s|ed|ing)?|carv(?:e|es|ed|ing) out|separat(?:e|es|ed|ing)|"
    r"purchas(?:e|es|ed|ing)|sell(?:s|ing)?|sold|unload(?:s|ed|ing)?|"
    r"divest(?:s|ed|ing)?|merg(?:e|es|ed|ing)|folds? into|teams? up with|"
    r"partners? with|takes?\b.{0,24}\bstake|renegotiat(?:e|es|ed|ing)|"
    r"licens(?:es|ed|ing)|sign(?:s|ed|ing)?|strikes?|struck|striking|"
    r"ink(?:s|ed|ing)?|renew(?:s|ed|ing)?|deepens?|"
    r"wins?|secures?|nears?|spins? (?:out|off)|repric(?:e|es|ed|ing)|"
    r"announc(?:e|es|ed|ing)\b.{0,24}\b(?:deal|pact|agreement|"
    r"partnership|acquisition|merger)|"
    r"ends?|exits?|cancels?|terminat(?:e|es|ed|ing)|loses?|lost)\b",
    re.I,
)
_TRANSACTION_RX = re.compile(
    r"\b(?:acquir(?:e|es|ed|ing)|acquisition|agrees? to buy|buys?|bought|"
    r"absorb(?:s|ed|ing)?|carv(?:e|es|ed|ing) out|separat(?:e|es|ed|ing)|"
    r"purchas(?:e|es|ed|ing)|sell(?:s|ing)?|sold|unload(?:s|ed|ing)?|"
    r"divest(?:s|ed|ing)?|"
    r"merg(?:e|es|ed|ing|er)|takes? over|folds? into|teams? up with|"
    r"partners? with|"
    r"takes?\b.{0,24}\bstake|"
    r"(?:ends?|exits?|cancels?|terminates?|terminated|loses?|lost)\b.{0,30}"
    r"\b(?:a |the )?(?:partnership|alliance|agreement|deal|contract)|"
    r"renegotiat(?:e|es|ed|ing)|renew(?:s|ed|ing)?|licens(?:es|ed|ing)|"
    r"(?:sign(?:s|ed|ing)?|strikes?|struck|striking|ink(?:s|ed|ing)?|"
    r"finaliz(?:e|es|ed|ing)|near(?:s|ed|ing)?)\b.{0,48}"
    r"(?:deals?|pacts?|agreements?|contracts?|partnerships?)|"
    r"(?:wins?|secures?)\b.{0,35}\bcontracts?|"
    r"spins? (?:out|off)\b.{0,35}\b(?:startups?|units?|business(?:es)?)|"
    r"repric(?:e|es|ed|ing)\b.{0,40}\bcontracts?|"
    r"licensing (?:deal|pact|agreement)|distribution agreement|"
    r"deepens?\b.{0,30}\b(?:alliance|partnership)|"
    r"cloud (?:compute )?deal)\b",
    re.I,
)
_PRIVATE_VALUATION_RX = re.compile(
    r"\b(?:tender offer|secondary sale|share sale)\b.{0,55}"
    r"\b(?:values?|valued|valuation)\b.{0,35}(?:\$[\d.]|"
    r"[\d.]+\s*(?:million|billion))|"
    r"\b(?:values?|valued)\b.{0,45}\b(?:company|startup|firm|openai|"
    r"anthropic|xai|mistral|perplexity|cohere)\b.{0,25}(?:\$[\d.]|"
    r"[\d.]+\s*(?:million|billion))|"
    r"\b(?:tender offer|secondary sale|share sale)\b.{0,55}"
    r"(?:\$[\d.]|[\d.]+\s*(?:million|billion)).{0,30}\bvaluation\b",
    re.I,
)
_INVESTMENT_WRITE_OFF_RX = re.compile(
    r"\b(?:write(?:s|ing)? off|wrote off|marks? down|marked down)\b.{0,55}"
    r"\b(?:investment|stake|holding)\b|"
    r"\b(?:investment|stake|holding)\b.{0,55}"
    r"\b(?:write(?:s|ing)? off|wrote off|marks? down|marked down)\b",
    re.I,
)
_COMMERCIAL_CUSTOMER_RX = re.compile(
    r"\b(?:adds?|lands?|signs?|secures?)\b.{0,45}"
    r"\b(?:anchor customer|commercial customer|customer commitment)\b",
    re.I,
)
_CORE_CUSTOMER_CONTRACT_RX = re.compile(
    r"\b(?:wins?|signs?|secures?|lands?)\b.{0,55}\b(?:inference|compute|"
    r"gpu|accelerator|model[- ]hosting|model[- ]serving)\b.{0,24}"
    r"\bcontracts?\b|"
    r"\b(?:inference|compute|gpu|accelerator|model[- ]hosting|"
    r"model[- ]serving)\b.{0,24}\bcontracts?\b",
    re.I,
)
_CORPORATE_TRANSFORMATION_RX = re.compile(
    r"\b(?:convert(?:s|ed|ing)?|reorganiz(?:e|es|ed|ing)|"
    r"restructur(?:e|es|ed|ing)|transition(?:s|ed|ing)?)\b.{0,55}"
    r"\b(?:nonprofit|for[- ]profit|public[- ]benefit corporation|"
    r"corporate structure|ownership structure)\b",
    re.I,
)
_LEADERSHIP_ACTION_RX = re.compile(
    r"\breturns? to lead\b|"
    r"\b(?:resign(?:s|ed|ing)?|steps? down|returns? as|"
    r"takes? over|oust(?:s|ed|ing)?|remov(?:e|es|ed|ing)|"
    r"appoint(?:s|ed|ing)?|names?|named|becomes?)\b.{0,36}"
    r"\b(?:chief executive|ceo|leader)\b|"
    r"\bhands?\b.{0,36}\b(?:chief executive|ceo)\b.{0,18}\brole\b|"
    r"\b(?:chief executive|ceo)\b.{0,36}\b(?:resign(?:s|ed|ing)?|"
    r"steps? down|returns?|oust(?:s|ed|ing)?|remov(?:e|es|ed|ing))\b",
    re.I,
)
_DISTRESS_EVENT_RX = re.compile(
    r"\b(?:files? for|enters?|seeks?)\b.{0,30}\b(?:bankruptcy|"
    r"bankruptcy protection|chapter 11|administration)\b|"
    r"\b(?:goes?|went|falls?) bankrupt\b|\binsolvenc(?:y|ies)\b|"
    r"\bliquidat(?:e|es|ed|ing|ion)\b|"
    r"\b(?:ceases?|ceased|ends?|ended) operations\b|"
    r"\b(?:shuts?|shut|winds?|wound) down\b|"
    r"\bshutter(?:s|ed|ing)?\b|\bfinancing collaps(?:e|es|ed|ing)\b",
    re.I,
)
_UNCONFIRMED_EVENT_RX = re.compile(
    r"\b(?:den(?:y|ies|ied|ying) reports?|rumou?rs?|reportedly|"
    r"deal talks?|talks? intensif(?:y|ies|ied)|valuation worries?|"
    r"no (?:deal|transaction|agreement|funding|action))\b",
    re.I,
)
_BUSINESS_MODEL_RX = re.compile(
    r"\b(?:business model|revenue model|pricing model|usage[- ]based pricing|"
    r"token pricing|api pricing|penny[- ]a[- ]minute|pay[- ]as[- ]you[- ]go|"
    r"per[- ](?:minute|token|request|task)|outcome[- ]based pricing|"
    r"completed agent task|reserved[- ]capacity pricing|tiered enterprise pricing|"
    r"subscription (?:model|plan|tier)|free tier|free api access|"
    r"seat[- ]based pricing|"
    r"commercial terms?|licensing model|marketplace|compute futures?|"
    r"model[- ]licensing terms?|licensing terms?|model access|"
    r"reserved inference capacity|api prices?|token prices?|per query|"
    r"billing model|monetization model|rental model)\b",
    re.I,
)
_BUSINESS_MODEL_ACTION_RX = re.compile(
    r"\b(?:introduc(?:e|es|ed|ing)|launch(?:es|ed|ing)?|change(?:s|d|ing)?|"
    r"adopt(?:s|ed|ing)?|shift(?:s|ed|ing)?|mov(?:e|es|ed|ing)|"
    r"end(?:s|ed|ing)?|"
    r"plan(?:s|ned|ning)?|test(?:s|ed|ing)?|expand(?:s|ed|ing)?|"
    r"cut(?:s|ting)?|lower(?:s|ed|ing)?|rais(?:e|es|ed|ing)|"
    r"offer(?:s|ed|ing)?|price(?:s|d|ing)?|roll(?:s|ed|ing)? out|"
    r"(?:begin|begins|start|starts|started) charging|"
    r"remov(?:e|es|ed|ing)|eliminat(?:e|es|ed|ing)|"
    r"bundl(?:e|es|ed|ing)|"
    r"switch(?:es|ed|ing)?|repric(?:e|es|ed|ing)|emerges? from stealth)\b",
    re.I,
)
_STRATEGIC_SUBSTANCE_RX = re.compile(
    r"\b(?:product roadmap|model(?:[- ]training)? roadmap|research roadmap|"
    r"accelerator roadmap|compute roadmap|chip roadmap|research agenda|"
    r"model development strategy|model[- ]safety strategy|research strategy|"
    r"r&d budget|research budget|investment plan|capex plan|"
    r"roadmap\b.{0,40}\b(?:ai|models?|research|compute|chips?|gpus?)|"
    r"(?:research|model development)\b.{0,30}\btoward|"
    r"gpu procurement|compute fleet|model[- ]licensing terms?|"
    r"supply outlook|production outlook|production target|"
    r"(?:cowos|hbm|fab|accelerator|compute) expansion|"
    r"reorganiz(?:e|es|ed|ing)|restructur(?:e|es|ed|ing)|"
    r"shift(?:s|ed|ing)? resources|post[- ]training strategy)\b",
    re.I,
)
_NON_CORE_CORPORATE_RX = re.compile(
    r"\b(?:headquarters|hq lease|office lease|office building|office space|"
    r"executive hire|hires? (?:an? )?(?:executive|chief)|"
    r"appoints?|names? (?:an? )?(?:executive|chief|ceo)|"
    r"compensation|salary|bonuses?|hiring plans?|team benefits?|layoffs?|"
    r"resigns?|steps down|office[- ]cleaning|"
    r"cleaning contracts?|snacks?|cafeteria|dress[- ]code|workplace rules?|"
    r"employee perks?|ergonomic office chairs?|office furniture|"
    r"branded t[- ]shirts?|sponsorship(?: agreement)?|formula one|f1|"
    r"(?:diversity|community)(?: impact)? reports?|employee shuttle(?:s| buses?)?|"
    r"reassur(?:e|es|ed|ing) employees?|internal memo)\b",
    re.I,
)
_NON_CORE_EVENT_OBJECT_RX = re.compile(
    r"\b(?:wellness|daycare|childcare|insurance|apprenticeship|scholarship|"
    r"employee benefits?|employee gym|fitness program|payroll|catering|"
    r"cafeteria|office security|cleaning|workplace|staff training|"
    r"recruiting|human resources?|hr)\b",
    re.I,
)
_NON_CORE_TRANSACTION_RX = re.compile(
    r"\b(?:catering|meal|food service|insurance|employee wellness|"
    r"wellness program|payroll software|office security|office cleaning|"
    r"workplace benefits?|staff benefits?|recruiting services?|"
    r"human resources?|hr software|daycare|childcare|apprenticeship|"
    r"routine audit)\b",
    re.I,
)
_INFRA_STRUCTURAL_RX = re.compile(
    r"\b(?:shortage|crunch|bottleneck|constraints?|backlash|demand|boom|buildout|"
    r"capacity|production|output|shipments?|supply|supplier networks?|"
    r"orders?|delays?|needs?|"
    r"expansion|grid connection|"
    r"double(?:s|d|ing)?|environmental impact per (?:task|query|token|"
    r"inference|training)|(?:power|water|energy|grid|supply|capacity) impact|"
    r"spending|capex|debt|financ(?:e|es|ed|ing)|funding|investment|valuation|"
    r"funds?\b.{0,30}\b(?:data[- ]centers?|compute|gpus?|infrastructure)|"
    r"permits?|moratorium|(?:us|trade|export) curbs?|power needs?|"
    r"energy needs?|(?:goes?|brings?|brought)\b.{0,35}\bonline)\b",
    re.I,
)
_SUMMARY_INFRA_BRIDGE_RX = re.compile(
    r"\b(?:supply|orders?|shortage|crunch|bottleneck|constraints?|contract|"
    r"deals?|partnership|procurement|capacity|production|output|shipments?|"
    r"buildout|construction|expand(?:s|ed|ing)?|invest(?:s|ed|ing|ment)?|"
    r"spend(?:s|ing)?|capex|financ(?:e|es|ed|ing)|acquir(?:e|es|ed|ing)|"
    r"buy(?:s|ing)?|bought|sell(?:s|ing)?|sold|sign(?:s|ed|ing)?)\b",
    re.I,
)
_NATIONAL_AI_ACTOR_RX = re.compile(
    r"\b(?:uae|united arab emirates|saudi arabia|china|japan|south korea|"
    r"united states|european union|eu|india|france|germany|uk|canada|"
    r"australia|taiwan|brazil)\b",
    re.I,
)
_NATIONAL_AI_STRATEGY_RX = re.compile(
    r"\b(?:bets? big on ai|big bet on ai|national investment strategy|"
    r"national ai strategy|sovereign ai investment|state[- ]backed ai investment|"
    r"ai(?: and chips?)? gamble)\b",
    re.I,
)
_EXCLUDED_VERTICAL_RX = re.compile(
    r"\b(?:classrooms?|schools?|colleges?|students?|homework|teachers?|"
    r"doctors?|patients?|medical|medicine|diagnostic|healthcare|hospitals?|"
    r"clinical trials?|"
    r"drugs?|cures?|diseases?|cancers?|oncology|hepatitis|viruses?|"
    r"therap(?:y|ies|eutic)|protein[- ]discovery|biology|bioscience|"
    r"brain implants?|biotech|pharmaceutical|boehringer|owkin|sanofi|"
    r"astrazeneca|pfizer|moderna|eli lilly|novo nordisk|roche|novartis|merck|"
    r"army|military|weapons?|battlefield|titan trucks?|"
    r"automotive|automobiles?|cars?|vehicles?|legacy industrial|mature[- ]node|"
    r"washing machines?|appliances?|"
    r"digital cameras?|action cameras?|game consoles?|handheld game consoles?|"
    r"cable television|cable tv|satellite (?:television|tv)|cable modems?|"
    r"cash registers?|point[- ]of[- ]sale|office printers?|printer controllers?|"
    r"dating|girlfriend|relationships?|cooking|restaurants?|food service|"
    r"ordering agents?|shopping|retailers?|farmers?|"
    r"agriculture|weather forecasting|weather prediction|municipal parking|"
    r"parking meters?|parking apps?|travel|vacations?|hotels?|resorts?|"
    r"airlines?|passengers?|"
    r"sports?|soccer|nba|nfl|world cup|stadiums?|fitness clubs?|"
    r"video games?|gaming|esports?|casinos?|slot machines?|board games?|"
    r"movies?|music|concert tickets?|concerts?|media industry|"
    r"celebrit(?:y|ies)|toys?|"
    r"cryptocurrenc(?:y|ies)|crypto mining|mining rigs?|oil[- ]exploration|"
    r"home\b.{0,12}\brouters?|perfumes?|fragrances?|"
    r"(?:tourist|visitor) cent(?:er|re)s?|smart speakers?|consumer assistants?|"
    r"advertising|marketing|influencers?|fashion brands?|family (?:life|use)|"
    r"real[- ]estate brokers?|residential real[- ]estate|real[- ]estate agents?|"
    r"home buyers?|home listings?|home agents?|scholarships?|"
    r"family subscription|personal (?:life|home|photos?|productivity)|"
    r"consumer (?:apps?|products?|"
    r"electronics)|smartphones?|phones?|iphone|android phones?|galaxy|"
    r"laptops?|tablets?|pcs?|lawyers?\b.{0,25}\b(?:write|draft|review)\b)\b",
    re.I,
)
_PERSONAL_ASSET_RX = re.compile(
    r"\b(?:mansions?|penthouses?|luxury homes?|luxury watch(?:es)?|artworks?|"
    r"lobby art|personal homes?|"
    r"(?:his|her|their)\b.{0,24}\bhome|private jets?|(?:super)?yachts?|"
    r"private islands?|carry[- ]on luggage|exhibition halls?|sculptures?|"
    r"office cafeterias?|catering deal|make money selling electricity)\b",
    re.I,
)
_PROMOTIONAL_CAMPAIGN_RX = re.compile(
    r"\b(?:ad blitz|advertising campaign|promotional campaign|publicity campaign|"
    r"talent contests?|sponsors?\b.{0,35}\bcontests?)\b",
    re.I,
)
_WORKFORCE_APPLICATION_RX = re.compile(
    r"\b(?:ai workforce|workforce push|union workers?\b.{0,35}\bai protections?|"
    r"reassur(?:e|es|ed|ing) employees?)\b",
    re.I,
)
_PRIVATE_RULE_RX = re.compile(
    r"\b(?:reddit|forum|community|moderators?)\b.{0,45}\b(?:ban|bans|rules?)\b|"
    r"\b(?:ban|bans|rules?)\b.{0,45}\b(?:reddit|forum|community|moderators?)\b|"
    r"\b(?:openai|anthropic|deepmind|xai|mistral|meta|google|microsoft|amazon|"
    r"companies?|firms?)\b.{0,60}\b(?:internal|employee|workplace|partner|"
    r"developer|community)\b.{0,24}\b(?:ban|bans|rules?|restrictions?)\b|"
    r"\b(?:openai|anthropic|deepmind|xai|mistral|meta|google|microsoft|amazon)\b"
    r".{0,45}\b(?:issues?|adopts?|changes?|tightens?)\b.{0,24}\brules?\b",
    re.I,
)
_CORPORATE_RULE_RX = re.compile(
    r"\b(?:startups?|companies|firms?|openai|anthropic|deepmind|xai|mistral|"
    r"meta|google|microsoft|amazon)\b.{0,55}"
    r"\b(?:adopts?|issues?|publishes?|introduces?|changes?|tightens?)\b"
    r".{0,45}\b(?:rules?|restrictions?)\b.{0,40}"
    r"\b(?:its own|products?|customers?|users?|developers?|partners?|"
    r"employees?|contractors?|agencies)\b|"
    r"\brule[- ]management products?\b",
    re.I,
)
_NON_MODEL_HOMONYM_RX = re.compile(
    r"\b(?:role[- ]models?|model employees?|model[- ]airplanes?|"
    r"server[- ]rack furniture|ai chips away|gemini court)\b",
    re.I,
)
_CHARITABLE_EVENT_RX = re.compile(
    r"\b(?:charit(?:y|ies|able)|donations?|disaster relief|fundrais(?:e|es|ing)|"
    r"crowdfunding|philanthrop(?:y|ic)|public[- ]librar(?:y|ies)|museums?|"
    r"urban trees?|professional soccer clubs?)\b",
    re.I,
)
_PERIPHERAL_AI_APPLICATION_RX = re.compile(
    r"\b(?:ai|generative ai|genai)\b.{0,35}\b(?:art|design tools?|"
    r"sales assistants?|customer[- ]service chatbots?|ordering agents?|"
    r"consumer apps?|home agents?)\b|"
    r"\b(?:art|design|sales|customer[- ]service|ordering|consumer|home)\b"
    r".{0,24}\b(?:ai agents?|ai assistants?|ai apps?|ai tools?|chatbots?)\b|"
    r"\b(?:ai )?chatbots?\b.{0,30}\b(?:for )?customer[- ]service\b",
    re.I,
)
_FOOD_CHIP_RX = re.compile(
    r"\b(?:potato|snack|tortilla|corn|chocolate) chips?\b|"
    r"\bchips?\b.{0,18}\b(?:snacks?|grocery|food)\b",
    re.I,
)
_SOCIAL_NOISE_RX = re.compile(
    r"\b(?:optimism|pessimism|public opinion|poll(?:s|ing)?|attitudes?|"
    r"legacy hinges|human history|what people think|young adults?|gen z|"
    r"class divide|safety[- ]net|economic warning|economists?|musical chairs|"
    r"epstein|comebacks?|"
    r"science fiction.{0,30}fear|don['’]t fall for|taylor swift|"
    r"open letters?|^open questions?|\b(?:demand|growth|ai) forever\b|"
    r"we(?:'re| are) waiting for ai|ai hype)\b",
    re.I,
)
_SOFT_GENRE_RX = re.compile(
    r"^(?:how|why|what|who|where|when|can|could|should|would)\b|\?$|"
    r"\b(?:what to know|everything you need to know|explains?|the big questions?)\b",
    re.I,
)
_MEDIA_TYPE_RX = re.compile(
    r"^(?:video|watch|livestream|clip|stream|replay|photos?|footage|webcast|"
    r"audio|gallery|transcript)\s*:|"
    r"\b(?:podcasts?|webinars?|axios events?|axios live|live events?|"
    r"watch now|listen now|newsletters?|sponsored|partner content)\b|"
    # 搜索标题常写成 “video with new AI show”，不是相邻的 “video show”。
    r"\bvideo\b.{0,80}\bshow\b|\bshow\b.{0,80}\bvideo\b",
    re.I,
)
_MEDIA_CARD_RX = re.compile(
    r"\b(?:video|podcasts?|webinars?|axios events?|live event|newsletters?|"
    r"sponsored|partner content)\b",
    re.I,
)
_LOCAL_CARD_RX = re.compile(r"\b(?:axios local|local news|local)\b", re.I)
_LISTING_BLOCK_RX = re.compile(
    r"(?:just a moment|verify you are human|are you a robot|access denied|"
    r"enable javascript and cookies to continue)",
    re.I,
)
_CARD_HINT_RX = re.compile(r"(?:search|result|story|article|card)", re.I)

_MODEL_APPLICATION_TARGET_RX = re.compile(
    r"\b(?:models?|agents?|assistants?|tools?)\b.{0,24}\b(?:for|in|across)\b"
    r".{0,30}\b(?:hospitals?|patients?|doctors?|schools?|classrooms?|students?|"
    r"army|military|battlefield|shopping|retail|smartphones?|phones?|pcs?)\b",
    re.I,
)
_GENERAL_CORPORATE_FINANCE_RX = re.compile(
    r"\b(?:bonds?|debt)\b.{0,45}\bgeneral corporate purposes\b|"
    r"\bgeneral corporate purposes\b",
    re.I,
)
_STRATEGY_ACTION_RX = re.compile(
    r"\b(?:detail(?:s|ed|ing)?|outline(?:s|d|ing)?|map(?:s|ped|ping)? out|"
    r"set(?:s|ting)?|commit(?:s|ted|ting)?|pledge(?:s|d|ing)?|"
    r"pivot(?:s|ed|ing)?|shift(?:s|ed|ing)?|revis(?:e|es|ed|ing)|"
    r"announc(?:e|es|ed|ing)|"
    r"publish(?:es|ed|ing)?|unveil(?:s|ed|ing)?|reorganiz(?:e|es|ed|ing)|"
    r"restructur(?:e|es|ed|ing)|extend(?:s|ed|ing)?|"
    r"forecast(?:s|ed|ing)?|plan(?:s|ned|ning)?)\b",
    re.I,
)
_INDUSTRY_LEAD_ACTION_RX = re.compile(
    r"\b(?:launch(?:es|ed|ing)?|release[sd]?|ship(?:s|ped|ping)?|"
    r"open(?:s|ed|ing)?|build(?:s|ing)?|expand(?:s|ed|ing)?|"
    r"invest(?:s|ed|ing)?|rais(?:e|es|ed|ing)|acquir(?:e|es|ed|ing)|"
    r"buy(?:s|ing)?|bought|sign(?:s|ed|ing)?|cut(?:s|ting)?|"
    r"increase(?:s|d|ing)?|boost(?:s|ed|ing)?|double(?:s|d|ing)?)\b",
    re.I,
)
_FORMAL_LEGAL_INSTRUMENT_RX = re.compile(
    r"\b(?:ai(?:\s+\w+){0,2}\s+act|(?:ai|artificial[- ]intelligence) laws?|"
    r"bills?|legislation|"
    r"executive order|"
    r"court|lawsuits?|"
    r"copyright suit|competition case|consent order|export controls?|"
    r"sanctions?|probe|inquiry|investigation|hearing|subpoenas?|"
    r"procurement (?:ban|guidance)|accord|directives?|risk label|blacklist|"
    r"entity list)\b",
    re.I,
)
_AI_VENTURE_SUBJECT_RX = re.compile(
    r"\b(?:ai|foundation[- ]model|frontier[- ]model|model[- ]training|"
    r"inference|data[- ]center|gpu|semiconductor)\b.{0,22}"
    r"\b(?:startups?|companies|firms?|labs?|developers?|providers?)\b|"
    r"\b(?:startups?|companies|firms?|labs?|developers?|providers?)\b.{0,22}"
    r"\b(?:ai|foundation[- ]models?|frontier[- ]models?|model[- ]training|"
    r"inference|data[- ]centers?|gpus?|semiconductors?)\b",
    re.I,
)
_CORE_TRANSACTION_TARGET_RX = re.compile(
    r"\b(?:ai|openai|anthropic|xai|mistral|perplexity|cohere|deepmind|"
    r"foundation[- ]models?|frontier[- ]models?|reasoning models?|"
    r"claude|gemini|gemma|llama|qwen|grok|kimi|"
    r"enterprise models?|gpt[- ]?\d+|model[- ]monitoring|model[- ]evaluation|"
    r"model[- ]distribution|"
    r"model[- ]licensing|model access|"
    r"cloud|inference|compute|gpus?|accelerators?|hbm|semiconductors?|"
    r"data[- ]centers?|interconnects?|safety[- ]tools?|enterprise ai|"
    r"copyright licensing|cursor|lambda(?: labs?)?|hugging ?face|cerebras|groq|"
    r"coreweave|nvidia|amd|microsoft|amazon web services|aws|google|oracle|"
    r"spacex)\b",
    re.I,
)
_LITIGATION_ACTION_RX = re.compile(
    r"\b(?:sue(?:s|d|ing)?|court\b.{0,22}\brules?|rules? against|"
    r"dismiss(?:es|ed|ing)?|settles?|settled|uphold(?:s|held)|strikes? down|"
    r"wins?|loses?|reject(?:s|ed|ing)?|certif(?:y|ies|ied|ying)|"
    r"drops?|dropped|closes?|closed|clears?|cleared|appeals?|appealed)\b",
    re.I,
)

_POLICY_CLAUSE_SPLIT_RX = re.compile(
    r"\s+(?:while|whereas|but|yet|even as)\s+|[;—]|"
    r"\s+(?:after|before|amid|despite)\s+(?=(?:an?\s+|the\s+)?"
    r"(?:proposed\s+)?(?:ai\s+)?(?:bill|law|rules?|regulation|"
    r"restrictions?|probe|investigation)\b)|"
    r"\s+as\s+(?=(?:critics?|experts?|companies?|officials?|lawmakers?|"
    r"opponents?|supporters?|proposed\b))|"
    r"\s+and\s+(?=(?:the\s+)?(?:eu|u\.s\.|us|court|judge|congress|"
    r"senate|house|white house|ftc|doj|fcc|bis|california|china|india|"
    r"japan|south korea|france|germany|canada|australia|brazil)\b)",
    re.I,
)
_BACKGROUND_POLICY_CONTEXT_RX = re.compile(
    r"\b(?:alongside\s+(?:a\s+)?debate(?:\s+over)?|"
    r"following\s+(?:a\s+)?review(?:\s+of)?|"
    r"after\s+(?:lawmakers?|officials?|regulators?)\s+delay(?:s|ed|ing)?|"
    r"amid\s+(?:a\s+)?controversy(?:\s+over)?|"
    r"while\b.{0,55}\b(?:remain(?:s|ed)?|stay(?:s|ed)?|is|are)\s+"
    r"under review)\b",
    re.I,
)
_POLICY_DEPENDENT_ACTION_RX = re.compile(
    r"\b(?:while|and)\s+(?:also\s+)?(?:setting|tightening|imposing|"
    r"requiring|mandating|restricting|banning|adopting|enacting|"
    r"establishing|expanding|narrowing|amending|abolishing)\b",
    re.I,
)
_POLICY_DEPENDENT_TARGET_RX = re.compile(
    r"\b(?:limits?|restrictions?|rules?|regulations?|audits?|standards?|"
    r"requirements?|controls?|bans?|oversight|registration)\b",
    re.I,
)
_EVENT_HARD_BOUNDARY_RX = re.compile(
    r"\b(?:while|whereas|but|yet|even as)\b|[;—]", re.I
)


def article_id(url: str) -> str:
    parts = urlsplit(url)
    if (parts.hostname or "").lower() not in {"axios.com", "www.axios.com"}:
        return ""
    match = _ARTICLE_RX.fullmatch(parts.path)
    if not match:
        return ""
    year, month, day, raw_slug = match.groups()
    slug = re.sub(r"[^a-z0-9._~-]+", "-", unquote(raw_slug).lower()).strip("-")
    return f"{year}-{month}-{day}-{slug}" if slug else ""


def search_url(keyword: str, page: int = 1) -> str:
    raise RuntimeError("Axios 未配任意关键词搜索：只走固定 artificial intelligence Latest")


def hub_url(slug: str, page: int = 1) -> str:
    # 动态分页在同一个 DOM 中由 Show 10 more results 完成；page 不能伪造成一个
    # 站方并不存在的查询参数。
    return LATEST_AI_URL


def _official_listing(url: str) -> bool:
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    return (
        (parts.hostname or "").lower() in {"axios.com", "www.axios.com"}
        and parts.path.rstrip("/") == "/results"
        and query.get("q") == ["artificial intelligence"]
        and query.get("sort") == ["2"]
    )


def _secondary_market_led(title: str, *, industry_anchor: bool) -> bool:
    """Reject market-led headlines while allowing an incidental trailing move."""
    if (
        _SECONDARY_MARKET_HARD_RX.search(title)
        or _PUBLIC_MARKET_CONTEXT_RX.search(title)
    ):
        return True
    if _IMPLIED_EQUITY_MOVE_RX.search(
        title
    ) and not _OPERATING_PERCENT_RX.search(title):
        return True
    move = _SHARE_MOVE_RX.search(title)
    if move is None:
        return False
    action = _INDUSTRY_LEAD_ACTION_RX.search(title)
    return not bool(industry_anchor and action and action.start() < move.start())


def _signals_near(
    left: re.Pattern[str],
    right: re.Pattern[str],
    text: str,
    *,
    max_gap: int = 18,
) -> bool:
    """Return whether two title signals describe the same compact event."""
    left_matches = tuple(left.finditer(text))
    right_matches = tuple(right.finditer(text))
    left_index = right_index = 0
    while left_index < len(left_matches) and right_index < len(right_matches):
        a = left_matches[left_index]
        b = right_matches[right_index]
        gap = max(0, max(a.start(), b.start()) - min(a.end(), b.end()))
        if gap <= max_gap:
            return True
        if a.end() < b.start():
            left_index += 1
        else:
            right_index += 1
    return False


def _action_targets(
    action: re.Pattern[str],
    target: re.Pattern[str],
    text: str,
    *,
    max_gap: int = 42,
) -> bool:
    """Return whether an active headline verb points at a relevant object."""
    targets = tuple(target.finditer(text))
    for verb in action.finditer(text):
        for obj in targets:
            if obj.start() < verb.end():
                continue
            gap = obj.start() - verb.end()
            if gap > max_gap:
                break
            bridge = text[verb.end() : obj.start()]
            if (
                not _EVENT_HARD_BOUNDARY_RX.search(bridge)
                and not _NON_CORE_EVENT_OBJECT_RX.search(bridge)
            ):
                return True
    return False


def _infra_subject_intransitive_event(title: str) -> bool:
    """Recognize ``GPU launches`` without treating a facility as a location."""
    actions = tuple(_INFRA_INTRANSITIVE_ACTION_RX.finditer(title))
    for subject in _INTRINSIC_INFRA_RX.finditer(title):
        for action in actions:
            if action.start() < subject.end():
                continue
            bridge = title[subject.end() : action.start()]
            if len(bridge) > 28:
                break
            if (
                _EVENT_HARD_BOUNDARY_RX.search(bridge)
                or _NON_CORE_EVENT_OBJECT_RX.search(bridge)
            ):
                continue
            tail = title[action.end() :]
            if (
                not _NON_CORE_EVENT_OBJECT_RX.search(tail)
                and _INFRA_INTRANSITIVE_TAIL_RX.fullmatch(tail)
            ):
                return True
    return False


def _policy_clauses(title: str) -> tuple[str, ...]:
    return tuple(
        clause.strip(" ,:-")
        for clause in _POLICY_CLAUSE_SPLIT_RX.split(title)
        if clause.strip(" ,:-")
    )


def _formal_policy_event(title: str, *, scope: bool) -> bool:
    """Recognize enacted policy and formal proceedings, not private rules or asks."""
    if not scope:
        return False

    background = _BACKGROUND_POLICY_CONTEXT_RX.search(title)
    if background:
        prefix = title[: background.start()]
        prefix_scope = bool(
            _AI_RX.search(prefix)
            or _AI_NATIVE_ENTITY_RX.search(prefix)
            or _MODEL_OBJECT_RX.search(prefix)
            or _CORE_ENTITY_RX.search(prefix)
            or _INTRINSIC_INFRA_RX.search(prefix)
            or _CONTEXTUAL_INFRA_RX.search(prefix)
        )
        if not prefix_scope:
            return False

    dependent = _POLICY_DEPENDENT_ACTION_RX.search(title)
    if dependent:
        prefix = title[: dependent.start()]
        clause = title[dependent.start() :]
        inherited_official = bool(
            _OFFICIAL_POLICY_ACTOR_RX.search(prefix)
            or _UPPER_US_ACTOR_RX.search(prefix)
            or _LEADING_NATIONAL_POLICY_ACTOR_RX.search(prefix)
        )
        dependent_scope = bool(
            _AI_RX.search(clause)
            or _MODEL_OBJECT_RX.search(clause)
            or _INTRINSIC_INFRA_RX.search(clause)
        )
        if (
            inherited_official
            and dependent_scope
            and _POLICY_DEPENDENT_TARGET_RX.search(clause)
        ):
            return True

    for clause in _policy_clauses(title):
        clause_scope = bool(
            _AI_RX.search(clause)
            or _AI_NATIVE_ENTITY_RX.search(clause)
            or _MODEL_OBJECT_RX.search(clause)
            or _CORE_ENTITY_RX.search(clause)
            or _INTRINSIC_INFRA_RX.search(clause)
            or _CONTEXTUAL_INFRA_RX.search(clause)
        )
        if not clause_scope or not _POLICY_SUBSTANCE_RX.search(clause):
            continue

        official = bool(
            _OFFICIAL_POLICY_ACTOR_RX.search(clause)
            or _UPPER_US_ACTOR_RX.search(clause)
            or _LEADING_NATIONAL_POLICY_ACTOR_RX.search(clause)
        )
        if _INVOICE_BILL_RX.search(clause) and not official:
            continue
        if _PRIVATE_RULE_RX.search(clause) and not official:
            continue
        formal_instrument = bool(_FORMAL_LEGAL_INSTRUMENT_RX.search(clause))
        action = bool(_POLICY_ACTION_RX.search(clause))
        definitive_match = _POLICY_DEFINITIVE_ACTION_RX.search(clause)
        process = bool(official and _POLICY_PROCESS_RX.search(clause))
        status = bool(_POLICY_STATUS_RX.search(clause))
        speculative_match = _SPECULATIVE_POLICY_RX.search(clause)
        direct_consideration = bool(
            process
            and speculative_match
            and re.fullmatch(
                r"consider(?:s|ed|ing)?",
                speculative_match.group(0),
                re.I,
            )
        )
        speculative = bool(
            speculative_match
            and not direct_consideration
            and (
                definitive_match is None
                or speculative_match.start() < definitive_match.start()
            )
        )
        if speculative:
            continue
        litigation = bool(
            _LITIGATION_ACTION_RX.search(clause)
            and re.search(
                r"\b(?:court|lawsuit|suit|copyright|intellectual property|"
                r"patent|trade[- ]secret|case|challenge|motion|class)\b",
                clause,
                re.I,
            )
        )

        if litigation or (status and (official or formal_instrument)) or process:
            return True
        if definitive_match and (official or formal_instrument):
            return True
        if action and (official or formal_instrument):
            return True
    return False


def _core_infrastructure_event(
    title: str,
    evidence: str,
    *,
    title_ai: bool,
    title_entity: bool,
    title_native: bool,
    business_model: bool,
    strategy: bool,
) -> bool:
    """Separate intrinsic AI infrastructure from generic grid/server homonyms."""
    title_intrinsic = bool(_INTRINSIC_INFRA_RX.search(title))
    any_intrinsic = bool(_INTRINSIC_INFRA_RX.search(evidence))
    title_contextual = bool(_CONTEXTUAL_INFRA_RX.search(title))
    any_contextual = bool(_CONTEXTUAL_INFRA_RX.search(evidence))
    structural = bool(
        _INFRA_STRUCTURAL_RX.search(title)
        or _OPERATING_PERCENT_RX.search(title)
    )
    capital = bool(_PRIMARY_CAPITAL_RX.search(title))
    intrinsic_action = _action_targets(
        _INFRA_TRANSITIVE_ACTION_RX, _INTRINSIC_INFRA_RX, title
    )
    contextual_action = _action_targets(
        _INFRA_TRANSITIVE_ACTION_RX, _CONTEXTUAL_INFRA_RX, title
    )
    subject_intransitive = _infra_subject_intransitive_event(title)
    if title_intrinsic and (
        structural
        or capital
        or business_model
        or strategy
        or intrinsic_action
        or subject_intransitive
    ):
        return True
    if (
        title_entity
        and any_intrinsic
        and (
            _SUMMARY_INFRA_BRIDGE_RX.search(title)
            or capital
            or business_model
            or strategy
        )
    ):
        return True
    if (
        title_contextual
        and (
            structural
            or capital
            or business_model
            or strategy
            or contextual_action
        )
        and (title_ai or title_entity or title_native)
    ):
        return True
    return bool(
        title_ai
        and any_contextual
        and _INFRA_STRUCTURAL_RX.search(title)
    )


def _foundation_model_event(title: str) -> bool:
    model_object = bool(_MODEL_OBJECT_RX.search(title)) or bool(
        (_AI_LAB_RX.search(title) or _STRATEGIC_MODEL_ENTITY_RX.search(title))
        and _GENERIC_MODEL_RX.search(title)
        and not _NON_TECH_MODEL_RX.search(title)
    )
    if not model_object:
        return False
    lifecycle = bool(_MODEL_LIFECYCLE_ACTION_RX.search(title))
    substance = bool(_MODEL_SUBSTANCE_RX.search(title))
    if lifecycle:
        direct_model_object = _signals_near(
            _MODEL_LIFECYCLE_ACTION_RX,
            _MODEL_EVENT_OBJECT_RX,
            title,
            max_gap=30,
        )
        # Long release names are common, so substantive architecture,
        # capability or training evidence can bridge the distance.  Without
        # that evidence, only a nearby model object is accepted and document /
        # workplace deliverables remain out of scope.
        non_model_deliverable = bool(_NON_MODEL_DELIVERABLE_RX.search(title))
        strong_substance = bool(_MODEL_STRONG_SUBSTANCE_RX.search(title))
        if (substance and (not non_model_deliverable or strong_substance)) or (
            direct_model_object and not non_model_deliverable
        ):
            return True
    if (
        _MODEL_CHANGE_ACTION_RX.search(title)
        and substance
    ):
        return True
    return bool(
        not _SOFT_GENRE_RX.search(title)
        and _MODEL_RESULT_ASSERTION_RX.search(title)
        and (
            _MODEL_ARTIFACT_RX.search(title)
            or _MODEL_SUBSTANCE_RX.search(title)
        )
    )


def _business_events(
    title: str,
    evidence: str,
    *,
    title_ai: bool,
    title_entity: bool,
    title_native: bool,
    model_object: bool,
    title_intrinsic: bool,
) -> tuple[bool, bool, bool, bool]:
    """Return capital, transaction, business-model and strategy signals."""
    if _UNCONFIRMED_EVENT_RX.search(title):
        return False, False, False, False

    venture_subject = bool(_AI_VENTURE_SUBJECT_RX.search(title))
    intrinsic_context = bool(
        title_intrinsic
        or (title_entity and _INTRINSIC_INFRA_RX.search(evidence))
    )
    capital_context = bool(
        title_native
        or model_object
        or intrinsic_context
        or venture_subject
        or (
            title_ai
            and re.search(
                r"(?:\$[\d.]|[\d.]+\s*(?:million|billion)|funding|"
                r"valuation|series\s+[a-z]|capital)",
                title,
                re.I,
            )
        )
    )
    targeted_transaction = _action_targets(
        _TRANSACTION_VERB_RX,
        _CORE_TRANSACTION_TARGET_RX,
        title,
        max_gap=72,
    )
    transaction_context = bool(
        venture_subject
        or targeted_transaction
    )
    business_model_context = bool(
        title_ai or title_native or model_object or intrinsic_context
    )

    capital = bool(
        capital_context
        and _PRIMARY_CAPITAL_RX.search(title)
        and not _GENERAL_CORPORATE_FINANCE_RX.search(title)
    )
    transaction = bool(
        (
            transaction_context
            and _TRANSACTION_RX.search(title)
            and not _NON_CORE_TRANSACTION_RX.search(evidence)
        )
        or (title_native and _INVESTMENT_WRITE_OFF_RX.search(title))
    )
    business_model = bool(
        business_model_context
        and _BUSINESS_MODEL_RX.search(title)
        and _BUSINESS_MODEL_ACTION_RX.search(title)
    )
    strategy = bool(
        _STRATEGIC_SUBSTANCE_RX.search(title)
        and _STRATEGY_ACTION_RX.search(title)
        and (
            title_ai
            or title_native
            or model_object
            or title_intrinsic
            or _CONTEXTUAL_INFRA_RX.search(title)
        )
        and (
            _STRATEGIC_ENTITY_RX.search(title)
            or _KEY_LEADER_RX.search(title)
        )
    )
    return capital, transaction, business_model, strategy


def admission_reason(item: dict[str, Any]) -> str:
    """Return the Bloomberg-style industry reason, or ``""`` before body fetch."""
    title = clean_text(
        item.get("title_en") or item.get("headline") or item.get("title")
    )
    summary = clean_text(item.get("summary") or item.get("description"))
    url = canonical_url(str(item.get("url") or ""), HOME)
    content_type = clean_text(
        item.get("content_type") or item.get("type") or item.get("section")
    )
    if len(title) < 12 or len(title) > 500 or not article_id(url):
        return ""

    path = urlsplit(url).path.lower()
    if (
        "/local/" in path
        or _LOCAL_CARD_RX.search(content_type)
        or _MEDIA_TYPE_RX.search(title)
        or _MEDIA_CARD_RX.search(content_type)
    ):
        return ""

    background = _BACKGROUND_POLICY_CONTEXT_RX.search(title)
    if background:
        prefix = title[: background.start()]
        if not (
            _AI_RX.search(prefix)
            or _AI_NATIVE_ENTITY_RX.search(prefix)
            or _MODEL_OBJECT_RX.search(prefix)
            or _CORE_ENTITY_RX.search(prefix)
            or _INTRINSIC_INFRA_RX.search(prefix)
            or _CONTEXTUAL_INFRA_RX.search(prefix)
        ):
            return ""

    key_leadership_event = bool(
        _LEADERSHIP_ACTION_RX.search(title)
        and _STRATEGIC_ENTITY_RX.search(title)
        and (
            _KEY_LEADER_RX.search(title)
            or re.search(r"\b(?:chief executive|ceo)\b", title, re.I)
        )
    )

    # These describe the primary article, not incidental impacts in a summary.
    # University model research, fab labour constraints and household grid costs
    # therefore survive; medical/consumer applications and personal assets do not.
    if (
        _EXCLUDED_VERTICAL_RX.search(title)
        or _MODEL_APPLICATION_TARGET_RX.search(title)
        or _PERIPHERAL_AI_APPLICATION_RX.search(title)
        or _PERSONAL_ASSET_RX.search(title)
        or _PROMOTIONAL_CAMPAIGN_RX.search(title)
        or _WORKFORCE_APPLICATION_RX.search(title)
        or (
            _NON_CORE_CORPORATE_RX.search(title)
            and not key_leadership_event
        )
        or _SOCIAL_NOISE_RX.search(title)
        or _FOOD_CHIP_RX.search(title)
        or _NON_MODEL_HOMONYM_RX.search(title)
        or _CHARITABLE_EVENT_RX.search(title)
        or _CORPORATE_RULE_RX.search(title)
        or _INVESTMENT_ADVICE_RX.search(title)
        or _UNCONFIRMED_EVENT_RX.search(title)
    ):
        return ""

    summary_excluded = bool(
        _EXCLUDED_VERTICAL_RX.search(summary)
        or _MODEL_APPLICATION_TARGET_RX.search(summary)
        or _PERIPHERAL_AI_APPLICATION_RX.search(summary)
        or _PERSONAL_ASSET_RX.search(summary)
    )

    evidence = f"{title} {summary}"
    title_ai = bool(_AI_RX.search(title))
    title_entity = bool(_CORE_ENTITY_RX.search(title))
    title_native = bool(_AI_NATIVE_ENTITY_RX.search(title))
    title_intrinsic = bool(_INTRINSIC_INFRA_RX.search(title))
    model_object = bool(_MODEL_OBJECT_RX.search(title))
    model_event = _foundation_model_event(title)

    national_strategy = bool(
        title_ai
        and (
            _NATIONAL_AI_ACTOR_RX.search(evidence)
            or _UPPER_US_ACTOR_RX.search(evidence)
        )
        and _NATIONAL_AI_STRATEGY_RX.search(evidence)
    )
    capital, transaction, business_model, strategy = _business_events(
        title,
        evidence,
        title_ai=title_ai,
        title_entity=title_entity,
        title_native=title_native,
        model_object=model_object,
        title_intrinsic=title_intrinsic,
    )
    operational_ai = bool(
        _AI_OPERATIONAL_EVENT_RX.search(title)
        and (
            model_object
            or title_native
            or title_entity
            or title_intrinsic
            or re.search(
                r"\b(?:model providers?|frontier labs?|ai labs?|"
                r"data[- ]centers?|gpus?|accelerators?)\b",
                summary,
                re.I,
            )
        )
    )
    infra_event = _core_infrastructure_event(
        title,
        evidence,
        title_ai=title_ai,
        title_entity=title_entity,
        title_native=title_native,
        business_model=business_model,
        strategy=strategy,
    )
    policy_scope = bool(
        title_ai
        or title_entity
        or title_native
        or model_object
        or title_intrinsic
        or _CONTEXTUAL_INFRA_RX.search(title)
    )
    policy_event = _formal_policy_event(title, scope=policy_scope)

    business_scope = bool(
        title_ai
        or title_native
        or model_object
        or title_intrinsic
        or _AI_VENTURE_SUBJECT_RX.search(title)
    )
    private_valuation = bool(
        title_native and _PRIVATE_VALUATION_RX.search(title)
    )
    corporate_transformation = bool(
        business_scope and _CORPORATE_TRANSFORMATION_RX.search(title)
    )
    commercial_customer = bool(
        business_scope
        and (
            _COMMERCIAL_CUSTOMER_RX.search(title)
            or _CORE_CUSTOMER_CONTRACT_RX.search(title)
        )
    )
    distress = bool(business_scope and _DISTRESS_EVENT_RX.search(title))

    # A stock clause after an actual HBM/fab investment is incidental. A headline
    # led by shares, an ETF/REIT or analyst targets remains secondary-market copy.
    if _secondary_market_led(
        title,
        industry_anchor=bool(infra_event or model_event or strategy),
    ):
        return ""

    # Earnings only matter when they reveal a physical capacity/supply fact.
    if _FINANCIAL_RESULTS_RX.search(title) and not infra_event:
        return ""

    business_event = bool(
        capital
        or transaction
        or business_model
        or strategy
        or national_strategy
        or private_valuation
        or corporate_transformation
        or commercial_customer
        or key_leadership_event
        or distress
    )

    title_only_capital, title_only_transaction, title_only_model, title_only_strategy = (
        _business_events(
            title,
            title,
            title_ai=title_ai,
            title_entity=title_entity,
            title_native=title_native,
            model_object=model_object,
            title_intrinsic=title_intrinsic,
        )
    )
    title_only_infra = _core_infrastructure_event(
        title,
        title,
        title_ai=title_ai,
        title_entity=title_entity,
        title_native=title_native,
        business_model=title_only_model,
        strategy=title_only_strategy,
    )
    strong_model_title = bool(
        model_event
        and (
            _GENERIC_MODEL_RX.search(title)
            or _MODEL_STRONG_SUBSTANCE_RX.search(title)
            or _MODEL_ARTIFACT_RX.search(title)
            or _VERSIONED_MODEL_ID_RX.search(title)
        )
    )
    strong_title_business = bool(
        (title_only_capital and title_native)
        or (
            title_only_transaction
            and (
                model_object
                or title_intrinsic
                or re.search(
                    r"\b(?:compute|inference|model[- ](?:monitoring|evaluation|"
                    r"distribution|licensing)|enterprise ai|copyright licensing|"
                    r"safety tools?)\b",
                    title,
                    re.I,
                )
            )
        )
        or title_only_model
        or title_only_strategy
        or key_leadership_event
        or corporate_transformation
        or distress
    )
    if summary_excluded and not (
        policy_event
        or title_only_infra
        or strong_model_title
        or strong_title_business
    ):
        return ""

    # Deliberate precedence: formal policy; physical/compute infrastructure;
    # capital/commercial strategy; finally model R&D. This keeps API pricing out
    # of model releases and HBM capex out of generic investment.
    if policy_event:
        return "ai_policy"
    if (
        capital
        and _AI_VENTURE_SUBJECT_RX.search(title)
        and not _INFRA_STRUCTURAL_RX.search(title)
    ):
        return "ai_business"
    if (
        transaction
        and re.search(r"\bdivest(?:s|ed|ing)?\b", title, re.I)
        and not _INFRA_STRUCTURAL_RX.search(title)
    ):
        return "ai_business"
    if commercial_customer:
        return "ai_business"
    if infra_event:
        return "core_infrastructure"
    if business_event:
        return "ai_business"
    if model_event or operational_ai:
        return "ai_model"
    return ""


def _card_for(link: Tag, root: Tag) -> Tag:
    fallback: Tag = link
    for depth, parent in enumerate(link.parents, start=1):
        if (
            not isinstance(parent, Tag)
            or parent is root
            or parent.name in {"body", "html"}
        ):
            break
        fallback = parent
        marker = " ".join(
            [
                parent.name,
                str(parent.get("data-testid") or ""),
                str(parent.get("data-cy") or ""),
                str(parent.get("data-vars-page-type") or ""),
                str(parent.get("role") or ""),
                " ".join(parent.get("class") or []),
            ]
        )
        if parent.name in {"article", "li"} or _CARD_HINT_RX.search(marker):
            return parent
        # 不向上吞掉整块结果区；标题周围的三四层足够覆盖常见卡片结构。
        if depth >= 5:
            break
    return fallback


_CTA_SUFFIX_RX = re.compile(
    r"\s+(?:go deeper|read more)(?:\s*\([^)]*\))?\s*(?:→|->)?\s*$",
    re.I,
)


def _headline_from_card(card: Tag, link: Tag) -> str:
    """Read Axios' semantic headline, never the CTA bundled into its anchor."""
    structured = card if card.get("data-vars-headline") else card.select_one(
        "[data-vars-headline]"
    )
    if structured is not None:
        title = clean_text(str(structured.get("data-vars-headline") or ""))
        if title:
            return title

    for selector in (
        "[data-cy^='story-headline-']",
        "a[data-cy='story-promo-headline'] h1",
        "a[data-cy='story-promo-headline'] h2",
        "a[data-cy='story-promo-headline'] h3",
        "a[data-cy='story-promo-headline'] h4",
        "h1",
        "h2",
        "h3",
        "h4",
    ):
        node = card.select_one(selector)
        if node is not None:
            title = clean_text(node.get_text(" ", strip=True))
            if title:
                return title

    # Compatibility fallback for a future markup change. Strip only a terminal CTA;
    # do not use broad replacements that could alter a real headline.
    return clean_text(_CTA_SUFFIX_RX.sub("", link.get_text(" ", strip=True)))


def _summary_from_card(card: Tag, title: str) -> str:
    candidates: list[str] = []
    for node in card.select("p"):
        text = clean_text(node.get_text(" ", strip=True))
        lowered = text.lower()
        if (
            len(text) < 25
            or text == title
            or lowered.startswith("go deeper")
            or lowered.startswith("by ")
        ):
            continue
        candidates.append(text)
    return max(candidates, key=len, default="")[:800]


def _first_text(card: Tag, selectors: str) -> str:
    node = card.select_one(selectors)
    return clean_text(node.get_text(" ", strip=True)) if node else ""


def _content_type(card: Tag, section: str) -> str:
    markers = [
        section,
        str(card.get("data-type") or ""),
        str(card.get("data-testid") or ""),
        str(card.get("data-cy") or ""),
        " ".join(card.get("class") or []),
    ]
    badge = card.select_one(
        "[data-testid*='format'], [data-cy*='format'], [class*='format'], "
        "[class*='content-type'], [aria-label*='podcast' i], "
        "[aria-label*='video' i], [aria-label*='sponsored' i]"
    )
    if badge is not None:
        markers.append(clean_text(badge.get_text(" ", strip=True)))
    return clean_text(" ".join(markers))


def parse_search_results(
    html: str,
    keyword: str,
    page_url: str = "",
) -> list[dict[str, Any]]:
    listing_url = page_url or LATEST_AI_URL
    if not _official_listing(listing_url):
        raise RuntimeError(f"Axios 列表解析器只接受固定 Latest 搜索页:{listing_url}")

    soup = BeautifulSoup(html, "html.parser")
    page_text = clean_text(
        f"{soup.title.get_text(' ', strip=True) if soup.title else ''} "
        f"{soup.get_text(' ', strip=True)[:1500]}"
    )
    if _LISTING_BLOCK_RX.search(page_text):
        raise RuntimeError("Axios Latest 搜索页被验证页拦截，不能把它当成空结果")

    root = soup.select_one("main") or soup
    candidates: list[tuple[Tag, str, str]] = []
    for link in root.select("a[href]"):
        url = canonical_url(str(link.get("href") or ""), HOME)
        identifier = article_id(url)
        if identifier:
            candidates.append((link, url, identifier))
    if not candidates:
        raise RuntimeError("Axios Latest 搜索页没有可识别的结果链接，DOM 可能已改版")

    rows: dict[str, dict[str, Any]] = {}
    strengths: dict[str, tuple[int, int]] = {}
    recognized_titles = 0
    for link, url, identifier in candidates:
        card = _card_for(link, root)
        title = _headline_from_card(card, link)
        if len(title) < 12:
            continue
        recognized_titles += 1
        summary = _summary_from_card(card, title)
        section = _first_text(
            card,
            "[data-cy='rubric'], [data-testid*='category'], [data-cy*='category'], "
            "[class*='eyebrow'], [class*='category'], [class*='section']",
        )
        content_type = _content_type(card, section)
        reason = admission_reason(
            {
                "title": title,
                "summary": summary,
                "url": url,
                "section": section,
                "content_type": content_type,
            }
        )
        if not reason:
            continue

        time_node = card.select_one("time")
        published = clean_text(
            (time_node.get("datetime") if time_node else "")
            or (time_node.get_text(" ", strip=True) if time_node else "")
        )
        if not parse_datetime(published):
            published = identifier[:10]
        row = {
            "article_id": identifier,
            "title_en": title,
            # 搜索卡摘要可补足标题里的基础设施语境；保留它，确保首次准入与
            # ledger/archive 重画时使用的是同一份可复核证据。
            "description": summary,
            "url": url,
            "published_at": published,
            "section": section,
            "keywords": [keyword],
            "admission_reason": reason,
        }
        strength = (len(title), len(summary))
        if identifier not in rows or strength > strengths[identifier]:
            rows[identifier] = row
            strengths[identifier] = strength
    if not recognized_titles:
        raise RuntimeError("Axios Latest 结果链接存在但标题 DOM 无法识别，页面可能已改版")
    return list(rows.values())


def admitted_rows(
    rows: dict[str, dict[str, Any]] | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    values = list(rows.values()) if isinstance(rows, dict) else list(rows)
    return [row for row in values if admission_reason(row)]


def barrier_before_body(text: str, title: str) -> bool:
    return _shared.barrier_before_body(text, title, BARRIER_RX)


def drop_padding(
    rows: dict[str, dict[str, Any]], searched: list[str]
) -> set[str]:
    return set()


merge = _shared.merge
newest_first = _shared.newest_first
oldest_first = _shared.oldest_first


def floor_for(since: str) -> str:
    return _shared.floor_for(since, EARLIEST)


def within_window(row: dict[str, Any], since: str) -> bool:
    return _shared.within_window(row, since, EARLIEST)
