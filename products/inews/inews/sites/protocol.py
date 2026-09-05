"""采集站点的唯一接口。

过去 ``run``、``fetch``、``render`` 各自凭记忆读取模块属性；漏一个字段只会在某条
很晚才走到的路径上报 ``AttributeError``。Protocol 让编辑器能检查，``validate`` 让
第三方站点在注册时就失败。站点仍可保持一个小模块，不需要继承框架基类。
"""
from __future__ import annotations

from typing import Any, Callable, Protocol


class SiteAdapter(Protocol):
    KEY: str
    NAME: str
    HOME: str
    LABEL: str
    TAGLINE: str
    OUT_DIR: str
    SEARCHABLE: bool
    # ``None`` = 走通用渲染浏览器；公开结构化栏目可以声明自己的只读抓取器。
    LISTING_FETCHER: Callable[[str], tuple[str, str]] | None
    TOPIC_LABEL: str
    LISTING_SCROLLS: bool
    LOAD_MORE_TEXT: str
    RULES: tuple[str, ...]
    LINK_PATTERN: str
    HUBS: tuple[str, ...]
    HUB_LABELS: dict[str, str]
    HUB_TIERS: dict[str, str]
    BODY_SELECTORS: tuple[str, ...]
    BODY_PARAGRAPH_SELECTORS: tuple[str, ...]
    # 某些付费站把墙做成无可见文字的 DOM 标记。表达式匹配整页原始 HTML；
    # 命中后启用共享的严格恢复率门槛，而非一票否决。空组表示该站不启用。
    RAW_HTML_REJECT_PATTERNS: tuple[str, ...]
    # 精确正文容器失效后是否允许通用正文猜测。公开站若把付费正文藏在 DOM 中，
    # 必须关掉这一档，不能让通用提取器把 CSS 隐藏内容当成可读正文。
    ALLOW_TRAFILATURA: bool
    MIN_BODY_CHARS: int
    # 英文付费站可能给一段很长的免费导语；字符数够不代表全文。两道门都由
    # 站点声明，0 表示该站不额外要求。
    MIN_BODY_WORDS: int
    # 若页面声明了全文词数，实际提取词数至少要达到这个比例；0 表示不检查。
    MIN_BODY_COVERAGE: float
    REQUIRES_AUTH: bool
    EARLIEST: str

    def article_id(self, url: str) -> str: ...
    def search_url(self, keyword: str, page: int = 1) -> str: ...
    def hub_url(self, slug: str, page: int = 1) -> str: ...
    def parse_search_results(
        self, html: str, keyword: str, page_url: str = ""
    ) -> list[dict[str, Any]]: ...
    def merge(
        self, rows: dict[str, dict[str, Any]], found: list[dict[str, Any]], *, source: str
    ) -> int: ...
    def admitted_rows(
        self, rows: dict[str, dict[str, Any]] | list[dict[str, Any]]
    ) -> list[dict[str, Any]]: ...
    def newest_first(self, rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]: ...
    def oldest_first(self, rows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]: ...
    def drop_padding(
        self, rows: dict[str, dict[str, Any]], searched: list[str]
    ) -> set[str]: ...
    def floor_for(self, since: str) -> str: ...
    def within_window(self, row: dict[str, Any], since: str) -> bool: ...
    def barrier_before_body(self, text: str, title: str) -> bool: ...


_VALUES = tuple(SiteAdapter.__annotations__)
_CALLABLES = tuple(
    name for name, value in SiteAdapter.__dict__.items()
    if callable(value) and not name.startswith("_")
)


def validate(site: object) -> None:
    """注册时一次报全缺口，而不是运行半小时后逐个撞 ``AttributeError``。"""
    missing = [name for name in (*_VALUES, *_CALLABLES) if not hasattr(site, name)]
    invalid = [
        name for name in _CALLABLES
        if hasattr(site, name) and not callable(getattr(site, name))
    ]
    if missing or invalid:
        label = getattr(site, "KEY", repr(site))
        details = []
        if missing:
            details.append(f"缺少 {', '.join(missing)}")
        if invalid:
            details.append(f"不可调用 {', '.join(invalid)}")
        raise TypeError(f"站点适配器 {label} 不完整:" + ";".join(details))
