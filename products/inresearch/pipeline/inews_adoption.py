#!/usr/bin/env python3
"""采用 inews 的内容包 —— 两个平行产品之间唯一允许的通路。

契约见 `products/inews/CONTENT_INTERFACE.md`。这里实现采用方那一半:
校验内容包、拒绝任何夹带身份的包、按固定版本记录采用。

为什么要有这一层, 而不是让 inresearch 直接读 inews 的库:
手册第 3 节要求两个产品的账号、会员与授权各自管理, 不按邮箱自动关联身份。
一旦 inresearch 能读到 inews 的用户表, 「独立」就只剩文档上的说法。
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
VERSION_RE = re.compile(r"^[0-9a-f]{32}$")
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

# 这些键在任何嵌套层级出现都拒绝整个包。身份不得顺着内容流进研究侧。
IDENTITY_KEYS = frozenset({
    "user", "user_id", "users", "account", "account_id", "email",
    "member", "member_id", "membership", "subscriber", "subscription",
    "session", "session_id", "token", "password", "auth",
    "credential", "credentials", "api_key",
})

REQUIRED_ITEM_FIELDS = ("item_id", "title", "published_at", "origin_url")


class AdoptionError(ValueError):
    """内容包不可采用。宁可这一轮不采用, 也不要把脏数据写进研究记录。"""


def compute_version(items) -> str:
    """版本由内容算出: 同样的内容得到同样的版本, 内容变了版本一定变。

    这样研究成果引用的「某个版本」是可重放的 —— 不是「当时碰巧的最新」。
    """
    canonical = json.dumps(items, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def find_identity_key(value, _path=""):
    """递归找身份字段。嵌在 topics 或任何自定义结构深处也要找出来。"""
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).strip().lower() in IDENTITY_KEYS:
                return f"{_path}.{key}" if _path else str(key)
            found = find_identity_key(item, f"{_path}.{key}" if _path else str(key))
            if found:
                return found
    elif isinstance(value, list):
        for i, item in enumerate(value):
            found = find_identity_key(item, f"{_path}[{i}]")
            if found:
                return found
    return None


def validate_package(payload) -> dict:
    if not isinstance(payload, dict):
        raise AdoptionError("内容包根节点必须是对象")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise AdoptionError(f"不支持的 schema_version: {payload.get('schema_version')!r}")
    if payload.get("source") != "inews.today":
        raise AdoptionError(f"内容包来源不是 inews.today: {payload.get('source')!r}")

    # 身份检查放在最前面: 一个夹带身份的包, 其余字段合不合法都不重要。
    leaked = find_identity_key(payload)
    if leaked:
        raise AdoptionError(f"内容包夹带身份字段 {leaked!r} —— 两个产品的账号必须各自独立")

    items = payload.get("items")
    if not isinstance(items, list):
        raise AdoptionError("items 必须是数组")

    seen = set()
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise AdoptionError(f"items[{i}] 必须是对象")
        missing = [f for f in REQUIRED_ITEM_FIELDS if not item.get(f)]
        if missing:
            raise AdoptionError(f"items[{i}] 缺少字段 {missing}")
        if item["item_id"] in seen:
            raise AdoptionError(f"items[{i}] item_id 重复: {item['item_id']}")
        seen.add(item["item_id"])
        if not RFC3339.match(str(item["published_at"])):
            raise AdoptionError(f"items[{i}] published_at 不是 RFC3339")
        url = str(item["origin_url"])
        if not url.startswith(("http://", "https://")):
            raise AdoptionError(f"items[{i}] origin_url 必须是 http(s)")

    version = payload.get("package_version")
    if not isinstance(version, str) or not VERSION_RE.match(version):
        raise AdoptionError("package_version 必须是 32 位十六进制")
    expected = compute_version(items)
    if version != expected:
        # 版本对不上说明内容在产出后被改过 —— 那么「引用固定版本」就失效了。
        raise AdoptionError(f"package_version 与内容不符: 声明 {version}, 实算 {expected}")
    return payload


def load_package(path) -> dict:
    p = Path(path)
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AdoptionError(f"内容包读不出来: {exc}") from exc
    return validate_package(payload)


def adopt(package, *, adopted_item_ids=None, now=None):
    """产出一条采用记录。研究成果引用新闻时引用这条记录, 不引用「当前的 inews」。"""
    package = validate_package(package)
    available = {item["item_id"] for item in package["items"]}
    if adopted_item_ids is None:
        adopted = sorted(available)
    else:
        adopted = sorted(set(adopted_item_ids))
        unknown = [i for i in adopted if i not in available]
        if unknown:
            raise AdoptionError(f"采用了内容包里不存在的条目: {unknown}")
    stamp = now or datetime.now(timezone.utc).isoformat()
    return {
        "source": "inews.today",
        "package_version": package["package_version"],
        "adopted_at": stamp,
        "adopted_item_ids": adopted,
        "item_count": len(adopted),
    }
