"""一轮同步里每篇正文实际走了哪条浏览器通道 —— 进程内的一本流水账。

**为什么需要它。** 站长 2026-08-08 拍板「先全进静默栏,靠数据挪」。那句话要
成立,得先有数据:面板现在只看得见「正文失败 21 篇」,而 21 篇失败背后可能是
「无头拿不到正文」(该把这个站挪进手动栏),也可能是「站点的墙或容器规则变了」
(该改声明)—— 这两件事该做的处置完全不同,靠失败数分不出来。

**为什么是进程内计数,不落库。** 它回答的是「这一轮」的问题,寿命就是一轮同步:
Mac 上抓完即打印进成果行,经 worker 回传服务器(与成果行、入库明细同一条路)。
落库等于给一个一次性数字建一张表,而真正要长期看的是面板上那一列。

词表封闭:未登记的通道名当场抛错,不静默记进一个没人看的键 —— 通道只有两条,
第三条出现时应该有人来决定它算什么,而不是让它悄悄多出一列。
"""
from __future__ import annotations

HEADLESS = "headless"
DAILY = "daily"
CHANNELS = (HEADLESS, DAILY)

METRICS = ("attempted", "succeeded", "failed")

_LEDGER: dict[str, dict[str, int]] = {}


class UnknownChannel(ValueError):
    """记了一笔词表外的通道 —— 让它当场响,不要静默多出一列。"""


def _record(channel: str, metric: str) -> None:
    bucket = _LEDGER.setdefault(channel, dict.fromkeys(METRICS, 0))
    bucket[metric] += 1


def through(channel: str, operation):
    """先记尝试，再执行并分别记录成功或失败。

    ``operation`` 在生产调用点传零参数函数。必须由这里负责调用,不能先在调用点
    求值再把结果传进来:后者一旦抛错,控制流永远到不了记账函数,于是 144 次无头
    失败会被面板报成「无头 0 次」。为兼容少量直接穿透值的测试/调用,非 callable
    仍原样返回并按一次成功计。
    """
    if channel not in CHANNELS:
        raise UnknownChannel(f"未登记的浏览器通道:{channel!r}")
    _record(channel, "attempted")
    try:
        value = operation() if callable(operation) else operation
    except BaseException:
        _record(channel, "failed")
        raise
    _record(channel, "succeeded")
    return value


def snapshot() -> dict[str, int]:
    """本轮通道尝试/成功/失败;没记过的值是 0(不是缺失)。"""
    return {
        f"{channel}_{metric}": _LEDGER.get(channel, {}).get(metric, 0)
        for channel in CHANNELS
        for metric in METRICS
    }


def reset() -> None:
    """开始新的一轮。Mac 上一个进程只跑一个站的一轮,主要供测试与复用进程。"""
    _LEDGER.clear()
