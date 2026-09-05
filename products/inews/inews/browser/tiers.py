"""获取档位:一个站的正文**怎么取到**,以及会不会弹到你脸上。

这是一份**纯数据契约**,只随代码审阅变动 —— 不读环境变量、不读运行时 JSON。
理由很实在:档位蕴含「会不会打开一个你没点过的浏览器窗口」,那种承诺不该
由一个配置文件说改就改。

封闭词汇表(从 yidian 的 ADR-0029 带过来,连同它的教训):

  bpc     有墙,已登录 Chrome + BPC 扩展能过。**无头静默**,可以自动跑。
  headless 公开页。普通 HTTPS 失败后只用空白的无头 Chromium，不读日常 Cookie/扩展。
  manual  统一的本机有头通道。可见窗口；只允许人工触发或站长明确授权的本机
          错峰任务使用，绝不作为无头来源失败后的偷偷回落。

原项目还有 direct/archive 两档,这里没有成员就不立 —— 一个零成员的词只会
诱使后来人把站往里塞。第一个真需要它的站出现时再加,那时它有证据。
"""
from __future__ import annotations

BPC_TIER = "bpc"
HEADLESS_TIER = "headless"
MANUAL_TIER = "manual"
TIERS = (BPC_TIER, HEADLESS_TIER, MANUAL_TIER)
INTERACTIVE_TIERS = frozenset((MANUAL_TIER,))

# 逐站声明。站点键与 browser.contract.SITE_DOMAINS 对齐。
TIER_OF: dict[str, str] = {
    # FT:2026-08 实测无头产出过低,走本机有头；定时运行须由 schedule 明确授权。
    "ft": MANUAL_TIER,
    # Bloomberg(9-02 站长指定加站):反爬比 FT 更凶,直接按人工有头登记 ——
    # 无头档要靠实测证据才升,和 FT 当初同一条路。
    "bloomberg": MANUAL_TIER,
    # WSJ 列表会拦普通 HTTP，请求正文又有订阅预览；与 Bloomberg 一样使用
    # 日常 Chrome/BPC。定时任务必须进专用窗口并与其他有头来源串行。
    "wsj": MANUAL_TIER,
    # CNBC 正文公开可直抓；偶发页面不完整时只允许无头兜底，不能让每小时任务
    # 因一个公开页面突然弹出可见 Chrome。
    "cnbc": HEADLESS_TIER,
    # Reuters 的专题与正文直抓当前会遇到 DataDome；只使用站长已经验证可打开的
    # 可见浏览器通道，不调用内部分页接口，也不把一次挑战误当成公开无头可用。
    "reuters": MANUAL_TIER,
    # Axios 搜索页在隔离浏览器实测触发 Cloudflare verification，而站长日常
    # Chrome 能正常打开。发现页因此使用明确授权的专用可见窗口；正文仍先直抓。
    "axios": MANUAL_TIER,
}


def tier_of(site: str) -> str:
    return TIER_OF.get(site, "")


def is_headless_site(site: str) -> bool:
    """未登记的站按**人工**处理。

    漏登一个站时,宁可它不自动跑,也不能让它悄悄拿到「静默」的承诺却照样弹窗。
    """
    return tier_of(site) in {BPC_TIER, HEADLESS_TIER}


def requires_visible_browser(site: str) -> bool:
    return tier_of(site) in INTERACTIVE_TIERS
