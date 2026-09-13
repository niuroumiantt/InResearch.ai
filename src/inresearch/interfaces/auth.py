#!/usr/bin/env python3
"""Hub 登录认证——纯标准库，无注册入口，用户由管理员在服务器后台添加。

设计（2026-08-18 用户拍板：「设计登录用户名密码这个环节，不需要给予注册的机会，
让我在后台添加使用者即可」）：

- **密码**：PBKDF2-HMAC-SHA256，200,000 轮，每用户独立盐。存 `data/users.json`
  ——**该文件不进 git**（.gitignore 已排除），只存在于服务器挂载卷；里面是哈希不是明文，
  但哈希也不该公开。加用户用 `src/inresearch/interfaces/users.py`（见该文件）。
- **会话**：HMAC-SHA256 签名的 cookie（`用户名:过期时间:签名`），密钥首次运行自动生成到
  `data/.hub_secret`（同样不进 git）。无服务端会话表——重启不踢人，签名自足验证。
  有效期 7 天；改密码不会使已发会话失效（要踢人就删用户或换 `.hub_secret`）。
- **限速**：同一 IP 在 5 分钟内失败 5 次即拒绝 5 分钟。IP 取 X-Forwarded-For **末项**
  ——首项是客户端可以随便填的，末项才是最近一跳可信反代（Caddy）看到的真实来源；
  Caddyfile 里同时把该头重写为 CF-Connecting-IP，双保险。表有上界防内存耗尽。
  内存态，重启清零——够用，这是内部工具不是银行。
- **何时启用**：绑 127.0.0.1（本地单人用法）不启用，行为与从前完全一样；
  绑其它地址（容器里 HUB_HOST=0.0.0.0）强制启用。可用 HUB_AUTH=on/off 显式覆盖。

零依赖。
"""
# macOS 系统 /usr/bin/python3 是 3.9：`str | None` 标注在 3.10 前不能求值，
# 本机 launchd 常驻就靠系统 Python 跑，这行让标注延迟求值以兼容
from __future__ import annotations

from inresearch.paths import project_root

import base64
import fcntl
import threading
from functools import wraps
import hashlib
import hmac
import json
import os as os
import secrets
import time
from http.cookies import SimpleCookie
from inresearch.storage.jsonl import atomic_write

ROOT = project_root()
USERS_FILE = ROOT / "data" / "users.json"
SECRET_FILE = ROOT / "data" / ".hub_secret"

PBKDF2_ITERS = 200_000
SESSION_TTL = 7 * 24 * 3600          # 7 天
COOKIE_NAME = "hub_session"
FAIL_WINDOW = 300                    # 秒
FAIL_LIMIT = 5

_fails: dict[str, list[float]] = {}  # ip -> [失败时间戳]


# ── 用户与密码 ──────────────────────────────────────────────

def load_users() -> dict:
    if not USERS_FILE.exists():
        return {}
    try:
        return json.loads(USERS_FILE.read_text(encoding="utf-8")).get("users", {})
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("user_store_unavailable") from exc


_user_lock = threading.RLock()


def user_write(fn):
    """Serialize complete read-modify-write operations across HTTP and CLI."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        with _user_lock:
            USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with USERS_FILE.with_name('.users.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                try:
                    return fn(*args, **kwargs)
                finally:
                    fcntl.flock(lock, fcntl.LOCK_UN)
    return wrapped


def save_users(users: dict):
    """Atomic persistence; callers must hold user_write for the full mutation."""
    body = json.dumps({'users': users}, ensure_ascii=False, indent=2) + '\n'
    atomic_write(USERS_FILE, body.encode('utf-8'))


def hash_password(password: str, salt_hex: str) -> str:
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             bytes.fromhex(salt_hex), PBKDF2_ITERS)
    return dk.hex()


def verify_password(username: str, password: str) -> bool:
    u = load_users().get(username)
    if not u:
        # 用户不存在也走一遍哈希，抹平时间差（避免用枚举响应时长探测用户名）
        hash_password(password, "00" * 16)
        return False
    return hmac.compare_digest(hash_password(password, u["salt"]), u["hash"])


# ── 会话 cookie ─────────────────────────────────────────────

@user_write
def _initialize_secret():
    # Recheck after acquiring the same cross-process account-store lock.
    if not SECRET_FILE.exists():
        SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(SECRET_FILE, secrets.token_bytes(32))


def _secret() -> bytes:
    try:
        value = SECRET_FILE.read_bytes()
    except FileNotFoundError:
        _initialize_secret()
        value = SECRET_FILE.read_bytes()
    if len(value) != 32:
        raise RuntimeError('session_key_unavailable')
    return value


def _sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def make_cookie(username: str) -> str:
    exp = int(time.time()) + SESSION_TTL
    payload = f"{username}:{exp}"
    token = base64.urlsafe_b64encode(f"{payload}:{_sign(payload)}".encode()).decode()
    return (f"{COOKIE_NAME}={token}; Path=/; Max-Age={SESSION_TTL}; "
            f"HttpOnly; Secure; SameSite=Lax")


def clear_cookie() -> str:
    return f"{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax"


def session_user(cookie_header: str | None) -> str | None:
    """从 Cookie 头解出已登录用户名；无效/过期/被删用户返回 None。"""
    if not cookie_header:
        return None
    c = SimpleCookie()
    try:
        c.load(cookie_header)
    except Exception:
        return None
    m = c.get(COOKIE_NAME)
    if not m:
        return None
    try:
        payload_sig = base64.urlsafe_b64decode(m.value.encode()).decode()
        username, exp_s, sig = payload_sig.rsplit(":", 2)
        exp = int(exp_s)
    except Exception:
        return None
    if time.time() > exp:
        return None
    if not hmac.compare_digest(_sign(f"{username}:{exp}"), sig):
        return None
    if username not in load_users():      # 删用户即踢人
        return None
    return username


@user_write
def set_password(username: str, new_password: str, *, current_password: str | None = None) -> bool:
    """在同一事务内核对旧密码并修改；管理员重置可省略旧密码。"""
    import secrets as _s
    users = load_users()
    if username not in users:
        return False
    if current_password is not None and not hmac.compare_digest(
            hash_password(current_password, users[username]['salt']), users[username]['hash']):
        return False
    salt = _s.token_bytes(16).hex()
    users[username].update(salt=salt, hash=hash_password(new_password, salt))
    save_users(users)
    return True


ROLES = ("admin", "member", "intern")

# 实习生白名单（默认拒绝）。为什么不是黑名单：打分表的 summary 里就有招标控制价
# 数字——敏感的不只是标了 sensitive 的事实记录，账本本身就是。逐条拉黑必漏，
# **漏一条路径等于没锁门**；白名单只放行工单系统，其余一概 403。
INTERN_GET_ALLOW = ("/assets/site-skin.js", "/assets/site-skin.css", "/assets/InterVariable.woff2", "/assets/Inter-LICENSE.txt", "/team.html", "/reports/workorders.json", "/data/assignments.json",
                    "/api/status", "/api/tasks", "/api/whoami", "/account", "/login", "/logout",
                    "/assets/", "/favicon")
INTERN_POST_ALLOW = ("/api/login", "/api/passwd", "/api/assign")


def user_role(username: str) -> str:
    """缺 role 的老用户按 member 算（内部人，但不给 admin——权限只显式给）。"""
    u = load_users().get(username) or {}
    r = u.get("role", "member")
    return r if r in ROLES else "member"


# ── 用户 CRUD（CLI 与管理后台 API 的共用入口，规则只写一处）──

NAME_RE_STR = r"^[a-z0-9][a-z0-9_.-]{1,30}$"


def _validate_name(name: str):
    import re
    if not re.fullmatch(NAME_RE_STR, name or ""):
        return "用户名须为小写字母/数字开头，2-31 位，可含 _ . -"
    return None


@user_write
def add_user(name: str, password: str | None = None, role: str | None = None):
    """返回 (ok, 提示或错误, 明文密码或 None)。密码只在这一次返回，之后只有哈希。"""
    import secrets as _s
    from datetime import date as _d
    users = load_users()
    if name in users:
        return False, f"用户已存在：{name}", None
    err = _validate_name(name)
    if err:
        return False, err, None
    pw = password or _s.token_urlsafe(12)
    # 首个用户必为 admin（否则系统里永远没有管理员）；其余默认 intern——权限从最小给起
    r = "admin" if not users else (role or "intern")
    if r not in ROLES:
        return False, f"角色须为 {'/'.join(ROLES)}", None
    salt = _s.token_bytes(16).hex()
    users[name] = {"salt": salt, "hash": hash_password(pw, salt),
                   "role": r, "created": _d.today().isoformat()}
    save_users(users)
    return True, f"已添加 {name}（角色：{r}）", pw


@user_write
def remove_user(name: str):
    users = load_users()
    if name not in users:
        return False, f"用户不存在：{name}"
    admins = [n for n, u in users.items() if u.get("role", "member") == "admin"]
    if users[name].get("role") == "admin" and admins == [name]:
        return False, "这是最后一个 admin，删掉会让系统没有管理员"
    del users[name]
    save_users(users)
    return True, f"已删除 {name}（其会话下一次请求即失效）"


@user_write
def set_role(name: str, role: str):
    users = load_users()
    if name not in users:
        return False, f"用户不存在：{name}"
    if role not in ROLES:
        return False, f"角色须为 {'/'.join(ROLES)}"
    admins = [n for n, u in users.items() if u.get("role", "member") == "admin"]
    if users[name].get("role") == "admin" and role != "admin" and admins == [name]:
        return False, "这是最后一个 admin，降级会让系统没有管理员——先给别人升 admin"
    users[name]["role"] = role
    save_users(users)
    return True, f"{name} → {role}（即时生效）"


@user_write
def rename_user(old: str, new: str):
    """改用户名。旧名的会话 cookie 随之失效（cookie 里是名字），需用新名重登。"""
    users = load_users()
    if old not in users:
        return False, f"用户不存在：{old}"
    if new in users:
        return False, f"新用户名已被占用：{new}"
    err = _validate_name(new)
    if err:
        return False, err
    users[new] = users.pop(old)
    save_users(users)
    return True, f"{old} → {new}（旧名会话已失效，需用新名重新登录）"


def reset_password(name: str, password: str | None = None):
    """返回 (ok, 提示, 明文新密码或 None)。"""
    import secrets as _s
    pw = password or _s.token_urlsafe(12)
    if not set_password(name, pw):
        return False, f"用户不存在：{name}", None
    return True, f"已重置 {name} 的密码", pw


# ── 登录限速 ────────────────────────────────────────────────

def client_ip(handler) -> str:
    # 取**末项**不取首项：首项是客户端自己可以伪造的（curl -H 'X-Forwarded-For: 随机'
    # 每次换一个就绕过限速），末项才是最近一跳可信反代追加/重写的真实来源
    xff = handler.headers.get("X-Forwarded-For", "")
    return (xff.split(",")[-1].strip() or handler.client_address[0])


FAIL_TABLE_MAX = 4096   # 限速表条目上界：伪造海量 XFF 时防慢速内存耗尽


def throttled(ip: str) -> bool:
    now = time.time()
    _fails[ip] = [t for t in _fails.get(ip, []) if now - t < FAIL_WINDOW]
    return len(_fails[ip]) >= FAIL_LIMIT


def record_fail(ip: str):
    now = time.time()
    # 表满时先清掉窗口外的过期条目；仍满则丢最旧的一条，保证有界
    if len(_fails) >= FAIL_TABLE_MAX and ip not in _fails:
        for k in [k for k, v in _fails.items() if all(now - t >= FAIL_WINDOW for t in v)]:
            del _fails[k]
        if len(_fails) >= FAIL_TABLE_MAX:
            del _fails[min(_fails, key=lambda k: max(_fails[k]))]
    # 每 IP 只留最近 FAIL_LIMIT 条就够判限速——列表同样不许无界长
    _fails[ip] = (_fails.get(ip, []) + [now])[-FAIL_LIMIT:]


# ── 登录页 ──────────────────────────────────────────────────
