#!/usr/bin/env python3
"""Hub 登录认证——纯标准库，无注册入口，用户由管理员在服务器后台添加。

设计（2026-08-18 用户拍板：「设计登录用户名密码这个环节，不需要给予注册的机会，
让我在后台添加使用者即可」）：

- **密码**：PBKDF2-HMAC-SHA256，200,000 轮，每用户独立盐。存 `data/users.json`
  ——**该文件不进 git**（.gitignore 已排除），只存在于服务器挂载卷；里面是哈希不是明文，
  但哈希也不该公开。加用户用 `pipeline/users.py`（见该文件）。
- **会话**：HMAC-SHA256 签名的 cookie（`用户名:过期时间:签名`），密钥首次运行自动生成到
  `data/.hub_secret`（同样不进 git）。无服务端会话表——重启不踢人，签名自足验证。
  有效期 7 天；改密码不会使已发会话失效（要踢人就删用户或换 `.hub_secret`）。
- **限速**：同一 IP 在 5 分钟内失败 5 次即拒绝 5 分钟。IP 取 X-Forwarded-For 首项
  （本服务只应躲在 Caddy 后面，该头由 Caddy 设置）。内存态，重启清零——够用，
  这是内部工具不是银行。
- **何时启用**：绑 127.0.0.1（本地单人用法）不启用，行为与从前完全一样；
  绑其它地址（容器里 HUB_HOST=0.0.0.0）强制启用。可用 HUB_AUTH=on/off 显式覆盖。

零依赖。
"""
# macOS 系统 /usr/bin/python3 是 3.9：`str | None` 标注在 3.10 前不能求值，
# 本机 launchd 常驻就靠系统 Python 跑，这行让标注延迟求值以兼容
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from http.cookies import SimpleCookie
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
    except (json.JSONDecodeError, OSError):
        return {}


def save_users(users: dict):
    USERS_FILE.write_text(
        json.dumps({"_note": "Hub 登录用户表。哈希非明文，但本文件仍不进 git、不外发。",
                    "users": users}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    os.chmod(USERS_FILE, 0o600)


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

def _secret() -> bytes:
    if not SECRET_FILE.exists():
        SECRET_FILE.write_bytes(secrets.token_bytes(32))
        os.chmod(SECRET_FILE, 0o600)
    return SECRET_FILE.read_bytes()


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


def set_password(username: str, new_password: str) -> bool:
    """改指定用户的密码；用户不存在返回 False。CLI 与自助改密共用此入口。"""
    import secrets as _s
    users = load_users()
    if username not in users:
        return False
    salt = _s.token_bytes(16).hex()
    users[username].update(salt=salt, hash=hash_password(new_password, salt))
    save_users(users)
    return True


ROLES = ("admin", "member", "intern")

# 实习生白名单（默认拒绝）。为什么不是黑名单：打分表的 summary 里就有招标控制价
# 数字——敏感的不只是标了 sensitive 的事实记录，账本本身就是。逐条拉黑必漏，
# **漏一条路径等于没锁门**；白名单只放行工单系统，其余一概 403。
INTERN_GET_ALLOW = ("/team.html", "/reports/workorders.json", "/data/assignments.json",
                    "/api/status", "/api/whoami", "/account", "/login", "/logout",
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
    if name not in load_users():
        return False, f"用户不存在：{name}", None
    pw = password or _s.token_urlsafe(12)
    set_password(name, pw)
    return True, f"已重置 {name} 的密码", pw


# ── 登录限速 ────────────────────────────────────────────────

def client_ip(handler) -> str:
    xff = handler.headers.get("X-Forwarded-For", "")
    return (xff.split(",")[0].strip() or handler.client_address[0])


def throttled(ip: str) -> bool:
    now = time.time()
    _fails[ip] = [t for t in _fails.get(ip, []) if now - t < FAIL_WINDOW]
    return len(_fails[ip]) >= FAIL_LIMIT


def record_fail(ip: str):
    _fails.setdefault(ip, []).append(time.time())


# ── 登录页 ──────────────────────────────────────────────────

LOGIN_PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inresearch Hub · 登录</title><style>
  :root{color-scheme:light dark}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
       background:#0f1419;color:#e6e6e6}
  form{background:#1a2129;border:1px solid #2c3844;border-radius:12px;
       padding:36px 40px;width:300px}
  h1{font-size:17px;margin:0 0 4px;font-weight:600}
  p.sub{margin:0 0 22px;color:#8a97a5;font-size:12.5px}
  label{display:block;font-size:12.5px;color:#8a97a5;margin:14px 0 4px}
  input{width:100%;box-sizing:border-box;padding:9px 11px;border-radius:8px;
        border:1px solid #2c3844;background:#0f1419;color:#e6e6e6;font-size:14px}
  input:focus{outline:none;border-color:#4a90d9}
  button{width:100%;margin-top:22px;padding:10px;border:0;border-radius:8px;
         background:#2f6db8;color:#fff;font-size:14px;cursor:pointer}
  button:hover{background:#3a7cc9}
  .err{margin-top:14px;color:#e07b7b;font-size:12.5px;min-height:1.2em}
  .note{margin-top:18px;color:#5c6a78;font-size:11.5px;text-align:center}
</style></head><body>
<form onsubmit="return go(event)">
  <h1>Inresearch Hub</h1>
  <p class="sub">数据中心研究 · 内部系统</p>
  <label>用户名</label><input id="u" autocomplete="username" autofocus>
  <label>密码</label><input id="p" type="password" autocomplete="current-password">
  <button>登录</button>
  <div class="err" id="err"></div>
  <div class="note">账号由管理员分配，本系统不提供注册</div>
</form>
<script>
async function go(e){e.preventDefault();
  const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:document.getElementById('u').value.trim(),
                         password:document.getElementById('p').value})});
  const d=await r.json();
  if(d.ok){location.href='/';}
  else{document.getElementById('err').textContent=d.error||'登录失败';}
  return false;}
</script></body></html>"""


PASSWD_PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>修改密码 · Inresearch Hub</title><style>
  :root{color-scheme:light dark}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
       background:#0f1419;color:#e6e6e6}
  form{background:#1a2129;border:1px solid #2c3844;border-radius:12px;
       padding:36px 40px;width:300px}
  h1{font-size:17px;margin:0 0 22px;font-weight:600}
  label{display:block;font-size:12.5px;color:#8a97a5;margin:14px 0 4px}
  input{width:100%;box-sizing:border-box;padding:9px 11px;border-radius:8px;
        border:1px solid #2c3844;background:#0f1419;color:#e6e6e6;font-size:14px}
  input:focus{outline:none;border-color:#4a90d9}
  button{width:100%;margin-top:22px;padding:10px;border:0;border-radius:8px;
         background:#2f6db8;color:#fff;font-size:14px;cursor:pointer}
  .msg{margin-top:14px;font-size:12.5px;min-height:1.2em}
  .msg.err{color:#e07b7b}.msg.ok{color:#7bc98a}
  a{color:#6aa3d8;font-size:12px;display:block;text-align:center;margin-top:16px}
</style></head><body>
<form onsubmit="return go(event)">
  <h1>修改密码</h1>
  <label>当前密码</label><input id="old" type="password" autocomplete="current-password" autofocus>
  <label>新密码（至少 8 位）</label><input id="n1" type="password" autocomplete="new-password">
  <label>再输一遍</label><input id="n2" type="password" autocomplete="new-password">
  <button>确认修改</button>
  <div class="msg" id="msg"></div>
  <a href="/">← 返回首页</a>
</form>
<script>
async function go(e){e.preventDefault();
  const m=document.getElementById('msg');
  const n1=document.getElementById('n1').value,n2=document.getElementById('n2').value;
  if(n1!==n2){m.className='msg err';m.textContent='两次输入的新密码不一致';return false;}
  const r=await fetch('/api/passwd',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({old_password:document.getElementById('old').value,new_password:n1})});
  const d=await r.json();
  m.className='msg '+(d.ok?'ok':'err');
  m.textContent=d.ok?'已修改。下次登录用新密码。':(d.error||'失败');
  return false;}
</script></body></html>"""


FORBIDDEN_PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>无权访问 · Inresearch Hub</title><style>
  :root{color-scheme:light dark}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       font:15px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;
       background:#0f1419;color:#e6e6e6}
  div{background:#1a2129;border:1px solid #2c3844;border-radius:12px;
      padding:36px 40px;width:320px;text-align:center}
  h1{font-size:16px;margin:0 0 10px}
  p{color:#8a97a5;font-size:13px;margin:0 0 20px}
  a{color:#6aa3d8;font-size:13px}
</style></head><body><div>
<h1>这一页不在你的权限里</h1>
<p>你的账号是实习生角色，可访问工单系统。<br>如需更多权限，请联系管理员。</p>
<a href="/team.html">→ 去工单板</a>
</div></body></html>"""
