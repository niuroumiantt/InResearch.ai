"""登录态:从文件或环境变量读某个域名的 cookie。

支持两种格式,都是浏览器插件常见的导出:Netscape ``cookies.txt`` 与 JSON 数组。

**过期的 cookie 直接丢掉。** 带着过期条目发请求,站方返回的是未登录页,而错误
信息会说「正文太短」—— 那会把一次「该重新导出 cookie 了」伪装成解析问题。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _active(pairs: list[tuple[str, str, int]]) -> list[tuple[str, str]]:
    now = time.time()
    return [(name, value) for name, value, expires in pairs if not expires or expires > now]


def parse(text: str, domain: str) -> list[tuple[str, str, int]]:
    """返回 ``(名, 值, 过期时间戳)``;认不出格式就返回空表。"""
    stripped = text.strip()
    if stripped.startswith("["):
        try:
            payload = json.loads(stripped)
        except ValueError:
            return []
        return [
            (
                str(item.get("name", "")),
                str(item.get("value", "")),
                int(float(item.get("expirationDate") or item.get("expires") or 0)),
            )
            for item in payload
            if isinstance(item, dict)
            and domain in str(item.get("domain", ""))
            and item.get("name")
        ]
    pairs: list[tuple[str, str, int]] = []
    for line in stripped.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) >= 7 and domain in fields[0]:
            try:
                expires = int(float(fields[4]))
            except ValueError:
                expires = 0
            pairs.append((fields[5], fields[6], expires))
    return pairs


class Cookie:
    """某个域名的登录态来源:环境变量优先,然后按顺序找文件。"""

    def __init__(self, domain: str, env: str, filename: str, required: tuple[str, ...] = ()):
        self.domain = domain
        self.env = env
        self.filename = filename
        self.required = required

    def candidate_paths(self) -> list[Path]:
        custom = os.environ.get(f"{self.env}_FILE", "").strip()
        paths = [Path(custom)] if custom else []
        paths.append(Path.cwd() / "secrets" / self.filename)
        paths.append(Path.home() / ".inews" / self.filename)
        return paths

    def _load(self) -> tuple[str, str]:
        inline = os.environ.get(self.env, "").strip()
        if inline:
            return inline, f"环境变量 {self.env}"
        for path in self.candidate_paths():
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            pairs = parse(text, self.domain)
            if pairs:
                header = "; ".join(f"{n}={v}" for n, v in _active(pairs))
                return header, str(path)
        return "", ""

    def header(self) -> str:
        return self._load()[0]

    def status(self) -> dict[str, object]:
        """**说清楚缺什么。** 「没登录」和「登录过期」要能分开,不然每次都得猜。"""
        header, origin = self._load()
        if not header:
            where = " 或 ".join(str(p) for p in self.candidate_paths())
            return {
                "ok": False,
                "note": f"未配置 {self.domain} 登录态:把浏览器导出的 cookie 存到 {where}"
                        f"(或设环境变量 {self.env})",
            }
        names = {part.split("=", 1)[0].strip() for part in header.split(";")}
        missing = [name for name in self.required if name not in names]
        if missing:
            return {
                "ok": False,
                "note": f"{origin} 里缺少 {', '.join(missing)} —— 多半是登录态已过期,请重新导出",
            }
        return {"ok": True, "note": f"登录态来自 {origin}"}


FT = Cookie(domain="ft.com", env="FT_COOKIE", filename="ft.cookies")
BLOOMBERG = Cookie(
    domain="bloomberg.com", env="BLOOMBERG_COOKIE", filename="bloomberg.cookies"
)
WSJ = Cookie(domain="wsj.com", env="WSJ_COOKIE", filename="wsj.cookies")

# 按站点键取登录态。键与 browser.contract.SITE_DOMAINS 对齐 —— fetch 层只说
# 站点词汇表里的词,不点名任何一个 Cookie 对象。
STORES = {"ft": FT, "bloomberg": BLOOMBERG, "wsj": WSJ}


def store_for(site_key: str) -> Cookie:
    try:
        return STORES[site_key]
    except KeyError:
        raise KeyError(
            f"没有这个站的登录态声明:{site_key};可选 {', '.join(sorted(STORES))}"
        ) from None
