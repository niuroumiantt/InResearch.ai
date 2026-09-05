"""Chrome 中 BPC 状态的发现与最小化安全镜像。

镜像只包含 Bypass Paywalls Clean 的本地存储，以及**需要登录/BPC 的放行域**
(见 ``_cookie_scope``)的 Cookie；公开 headless 站不在其中。密码、自动填充、历史、
书签、其它扩展和其它站点 Cookie 都不会复制。
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sqlite3
from pathlib import Path

from inews.browser.contract import SITE_DOMAINS, BrowserBypassError
from inews.browser.tiers import HEADLESS_TIER, tier_of

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOCAL_EXTENSION_RELATIVE = Path(
    "code/ft.com/bypass-paywalls-chrome-clean-master-magnolia-1234-main"
)
BPC_EXTENSION_ID = "lkbebcjgcmobigpeffafkodonchffocl"
_COOKIE_DB_RELATIVES = (Path("Network/Cookies"), Path("Cookies"))


def _installed_extension_path() -> Path | None:
    """日常 Chrome 里**已装**的那份 BPC —— Chrome 装扩展时本来就是解压存放的。

    2026-08-07 站长实测暴露的缺口:此前只找环境变量指定的目录和管理员手动解压的
    那一份副本,于是「站长的 Chrome 里明明装着 BPC」和「隔离通道说找不到扩展」
    同时成立 —— 无头通道因此永远用不起来,只能退回弹窗。

    取版本目录里最新的一个:Chrome 升级扩展时会并存新旧版本,旧的迟早被清掉。
    """
    root = chrome_user_data_root()
    profile = chrome_profile_path()
    if profile is None or root is None:
        return None
    versions = profile / "Extensions" / BPC_EXTENSION_ID
    if not versions.is_dir():
        return None
    installed = [
        version
        for version in sorted(versions.iterdir(), reverse=True)
        if version.is_dir() and (version / "manifest.json").is_file()
    ]
    return installed[0].resolve() if installed else None


def lookup_report() -> list[str]:
    """逐条说明「找过哪里、看到了什么」—— 探测失败时唯一有信息的东西。

    2026-08-08 站长实况:Chrome 的 ``Extensions/<BPC>/`` 目录在,但里面是空的
    (.crx 装过又卸了,只剩空壳),而工具只说「没找到扩展」。**「没找到」与
    「找到了但那里是空的」对人的下一步完全不同** —— 前者去装扩展,后者去找
    真正那一份在哪。站长为此查了三轮。
    """
    lines = []
    for name in ("INEWS_BYPASS_EXTENSION_PATH", "FT_BYPASS_EXTENSION_PATH"):
        value = os.getenv(name, "").strip()
        if value:
            ok = (Path(value).expanduser() / "manifest.json").is_file()
            lines.append(f"环境变量 {name}={value}:{'可用' if ok else '里面没有 manifest.json'}")
        else:
            lines.append(f"环境变量 {name}:未设置")
    for label, candidate in (
        ("仓库 vendor 目录", PROJECT_ROOT / "vendor" / "bypass-paywalls-chrome-clean"),
        ("手工副本", Path.home() / LOCAL_EXTENSION_RELATIVE),
    ):
        lines.append(
            f"{label} {candidate}:"
            + ("可用" if (candidate / "manifest.json").is_file() else "不存在")
        )
    profile = chrome_profile_path()
    if profile is None:
        lines.append("Chrome profile:没找到装过 BPC 的 profile")
        return lines
    versions = profile / "Extensions" / BPC_EXTENSION_ID
    if not versions.is_dir():
        lines.append(f"Chrome {profile.name} 的 Extensions/<BPC>:目录不存在")
    else:
        usable = [
            item.name
            for item in versions.iterdir()
            if item.is_dir() and (item / "manifest.json").is_file()
        ]
        lines.append(
            f"Chrome {profile.name} 的 Extensions/<BPC>:"
            + (f"可用版本 {usable}" if usable else "目录在,但里面没有任何版本(空壳)")
        )
    return lines


def extension_path() -> Path | None:
    """找到已解压的 BPC 扩展；生产优先显式配置，本机兼容现有目录."""
    configured = (
        os.getenv("INEWS_BYPASS_EXTENSION_PATH", "").strip()
        or os.getenv("FT_BYPASS_EXTENSION_PATH", "").strip()
    )
    candidates = [
        Path(configured).expanduser() if configured else None,
        PROJECT_ROOT / "vendor" / "bypass-paywalls-chrome-clean",
        Path.home() / LOCAL_EXTENSION_RELATIVE,
    ]
    for candidate in candidates:
        if candidate and candidate.is_dir() and (candidate / "manifest.json").is_file():
            return candidate.resolve()
    # 显式配置与手动副本都没有时,回到日常 Chrome 已装的那份。放在最后是因为
    # 前两者是「我要用这一份」的明确表态,这一条只是兜底。
    return _installed_extension_path()


def chrome_user_data_root() -> Path | None:
    configured = (
        os.getenv("INEWS_BYPASS_CHROME_USER_DATA_DIR", "").strip()
        or os.getenv("FT_BYPASS_CHROME_USER_DATA_DIR", "").strip()
    )
    if configured:
        root = Path(configured).expanduser()
    elif platform.system() == "Darwin":
        root = Path.home() / "Library/Application Support/Google/Chrome"
    elif platform.system() == "Windows":
        local_app_data = os.getenv("LOCALAPPDATA", "").strip()
        root = (
            Path(local_app_data) / "Google/Chrome/User Data"
            if local_app_data
            else None
        )
    else:
        root = Path.home() / ".config/google-chrome"
    return root.resolve() if root and root.is_dir() else None


def _profile_order(local_state: dict) -> list[str]:
    profile_state = local_state.get("profile", {})
    info_cache = profile_state.get("info_cache", {})
    wanted_email = (
        os.getenv("INEWS_BYPASS_CHROME_PROFILE_EMAIL", "").strip()
        or os.getenv("FT_BYPASS_CHROME_PROFILE_EMAIL", "").strip()
    ).lower()
    ordered: list[str] = []
    if wanted_email:
        ordered.extend(
            name
            for name, value in info_cache.items()
            if str(value.get("user_name") or "").strip().lower() == wanted_email
        )
    last_used = str(profile_state.get("last_used") or "").strip()
    if last_used:
        ordered.append(last_used)
    ordered.extend(info_cache)
    return list(dict.fromkeys(ordered))


def chrome_profile_path() -> Path | None:
    """定位装有 BPC 的日常 Chrome profile，但不直接拿它启动浏览器."""
    root = chrome_user_data_root()
    if root is None:
        return None
    configured_dir = (
        os.getenv("INEWS_BYPASS_CHROME_PROFILE_DIR", "").strip()
        or os.getenv("FT_BYPASS_CHROME_PROFILE_DIR", "").strip()
    )
    if configured_dir:
        candidate = Path(configured_dir).expanduser()
        candidate = candidate if candidate.is_absolute() else root / candidate
        return candidate.resolve() if candidate.is_dir() else None
    try:
        local_state = json.loads((root / "Local State").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        local_state = {}
    ordered = [(root / name).resolve() for name in _profile_order(local_state)]
    installed = [
        candidate
        for candidate in ordered
        if candidate.is_dir()
        and (candidate / "Local Extension Settings" / BPC_EXTENSION_ID).is_dir()
    ]
    # **两样都要有**:少了扩展过不了墙,少了 Cookie 库连站方的基础会话都没有。
    # 2026-08-09 站长机器上挑中的 `Profile 1` 装着 BPC(扩展设置读到 5 个文件),
    # 却连 `Network/` 目录都没有 —— 一个装过扩展、从没用来上过网的空壳,而它正好
    # 排在 last_used。于是镜像每轮都在认真地拷一个空的 Cookie 库,他真正在用的那个
    # profile 从来没被看过一眼。判据只问了「装没装 BPC」,漏了另一半。
    with_cookies = [
        candidate
        for candidate in installed
        if cookie_source_state(candidate)[0] == "ok"
    ]
    # 退回只看扩展:Cookie 库**读不到**(macOS 权限)时全部都不满足上一条,
    # 这时候必须保住原来的行为 —— 挑不出来会把「少带了 Cookie」升级成
    # 「连扩展都用不上」,比原来更差。
    return next(iter(with_cookies or installed), None)


# archive.ph 的镜像域:同一个服务在多个后缀之间轮换,``SITE_DOMAINS`` 只登记
# 当前主用的那一个(打开哪个由 ``archive_newest_url`` 决定)。Cookie 范围要覆盖
# 全部镜像 —— 打开 archive.ph 却只认 archive.ph 的 Cookie,轮到 .today 那天就是
# 一次没人看得懂的失败。这不是「多放几家」,是同一家的几个门牌。
_ARCHIVE_MIRRORS = frozenset({
    "archive.today", "archive.fo", "archive.is",
    "archive.li", "archive.md", "archive.ph", "archive.vn",
})


def _cookie_scope() -> frozenset[str]:
    """镜像哪些站的 Cookie —— 只含需要登录/BPC 的放行域。

    两端都是硬边界:少一个域,那个站原样撞 401 而症状看不出是 Cookie;多一个域,
    就是站长的邮箱/银行登录态多躺进一个无人值守的浏览器一次。所以它不该是手工
    名单 —— 曾经写死成 ft.com + bloomberg.com,后面十一家转正时没人回头改它。
    公开 ``headless`` 档只用空白 context，不能因为允许打开 CNBC 就顺手镜像它的
    日常 Cookie。
    """
    return frozenset(
        domain
        for site, domain in SITE_DOMAINS.items()
        if tier_of(site) != HEADLESS_TIER
    ) | _ARCHIVE_MIRRORS


def _is_scoped_cookie_host(host: str) -> bool:
    # 按域后缀匹配,不是精确相等:会话 Cookie 普遍挂在子域上(``.wsj.com``、
    # ``www.nytimes.com``、``account.economist.com``),而站点表里写的是裸域。
    normalized = host.strip().lower().lstrip(".")
    return any(
        normalized == domain or normalized.endswith("." + domain)
        for domain in _cookie_scope()
    )


def _cookie_source(profile: Path) -> tuple[Path | None, str, str]:
    """兼容 Chrome 新旧 Cookie 布局，并返回实际可镜像的数据库路径。"""
    unreadable = []
    for relative in _COOKIE_DB_RELATIVES:
        path = profile / relative
        try:
            with path.open("rb"):
                return path, "ok", ""
        except FileNotFoundError:
            continue
        except OSError as exc:
            unreadable.append(f"{path} 读不到:{exc}")
    if unreadable:
        return None, "unreadable", "；".join(unreadable)
    checked = "、".join(str(profile / relative) for relative in _COOKIE_DB_RELATIVES)
    return None, "missing", f"{checked} 均不存在(这个 profile 可能从没用来浏览过)"


def cookie_source_state(profile: Path) -> tuple[str, str]:
    """Cookie 库是「没有」还是「读不到」—— **这两件事必须分开**。

    ``Path.is_file()`` 没有读权限时也返回 False,于是一次「终端缺完全磁盘访问
    权限」被静默记成「这个 profile 没有 Cookie」,而两者的下一步完全相反:
    前者去系统设置授权,后者去看是不是挑错了 profile。
    """
    _path, state, note = _cookie_source(profile)
    return state, note


def _snapshot_cookie_db(source: Path, target: Path) -> int:
    """SQLite 在线备份后仅留私站/archive Cookie，并擦除其它站点残页."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    source_uri = f"{source.resolve().as_uri()}?mode=ro"
    with (
        sqlite3.connect(source_uri, uri=True) as source_db,
        sqlite3.connect(target) as target_db,
    ):
        source_db.backup(target_db)
        hosts = [
            row[0]
            for row in target_db.execute(
                "SELECT DISTINCT host_key FROM cookies"
            ).fetchall()
        ]
        allowed = [host for host in hosts if _is_scoped_cookie_host(str(host))]
        target_db.execute("PRAGMA secure_delete=ON")
        if allowed:
            placeholders = ",".join("?" for _ in allowed)
            target_db.execute(
                f"DELETE FROM cookies WHERE host_key NOT IN ({placeholders})",
                allowed,
            )
        else:
            target_db.execute("DELETE FROM cookies")
        count = int(
            target_db.execute("SELECT COUNT(*) FROM cookies").fetchone()[0]
        )
        target_db.commit()
        target_db.execute("VACUUM")
    target.chmod(0o600)
    return count


def _copy_extension_settings(source_profile: Path, target_profile: Path) -> int:
    source = source_profile / "Local Extension Settings" / BPC_EXTENSION_ID
    target = target_profile / "Local Extension Settings" / BPC_EXTENSION_ID
    if target.exists():
        shutil.rmtree(target)
    if not source.is_dir():
        return 0
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("LOCK", "*.tmp"),
    )
    return sum(path.is_file() for path in target.rglob("*"))


def snapshot_chrome_profile(
    source_profile: Path, target_user_data: Path
) -> dict[str, int]:
    """制作只含 BPC 状态与受限 Cookie 的 Playwright 专用镜像."""
    source_profile = source_profile.resolve()
    target_user_data = target_user_data.resolve()
    source_root = source_profile.parent
    if (
        target_user_data in {source_profile, source_root}
        or source_root in target_user_data.parents
    ):
        raise BrowserBypassError(
            "FT_BYPASS_PROFILE_DIR 不得指向日常 Chrome User Data/Profile"
        )
    target_profile = target_user_data / "Default"
    target_profile.mkdir(parents=True, exist_ok=True)
    settings_files = _copy_extension_settings(source_profile, target_profile)
    source_cookie, state, note = _cookie_source(source_profile)
    cookie_count = (
        _snapshot_cookie_db(
            source_cookie,
            target_profile / source_cookie.relative_to(source_profile),
        )
        if source_cookie is not None
        else 0
    )
    return {
        "settings_files": settings_files,
        "cookie_count": cookie_count,
        "cookie_state": state,
        # 0 条必须带得出原因:一个不会说话的 0,让人对着 HTTP 401 猜了两轮。
        "cookie_note": note,
    }
