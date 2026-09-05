"""逐站知识:一个站一个文件。

这里只有一张注册表。编排层(run/cli/fetch/render)通过它拿站点模块,
之后只说站点词汇表里的词(HUBS、LABEL、EARLIEST……)—— **一旦编排层
想写 `if 站名`,说明词汇表缺了一个词**,该补词,不该写分支。
"""
from __future__ import annotations

from inews.sites import axios, bloomberg, cnbc, ft, reuters, wsj
from inews.sites.protocol import SiteAdapter, validate

_ADAPTERS = (ft, bloomberg, cnbc, wsj, reuters, axios)
for _adapter in _ADAPTERS:
    validate(_adapter)

REGISTRY: dict[str, SiteAdapter] = {site.KEY: site for site in _ADAPTERS}

# 各站专题线的标签。它们不是搜索词 —— 「仅提及」这类按词计票的判定要把
# 它们整体排除,而判定代码不该点任何一个站的名。
TOPIC_LABELS = frozenset(
    label
    for site in REGISTRY.values()
    for label in (site.TOPIC_LABEL, *site.HUB_LABELS.values())
)


def get(key: str) -> SiteAdapter:
    """按键取站点模块;不认识的键把可选名单说全 —— 让打错字的人一眼看到答案。"""
    try:
        return REGISTRY[key]
    except KeyError:
        raise KeyError(
            f"没有这个站:{key};可选 {', '.join(sorted(REGISTRY))}"
        ) from None
