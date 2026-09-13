#!/usr/bin/env python3
"""Authenticated HTTP adapter for shared business commands and declared static URLs.

Local binding defaults to loopback. Non-loopback deployment enables login unless
HUB_AUTH explicitly overrides it; authorization and input parsing live here,
while data mutation rules live in workflow.commands.
"""

from inresearch.paths import project_root
from inresearch.interfaces.static import source_path
from inresearch.interfaces import pages
import os
import json
from inresearch.interfaces import auth as auth
from inresearch.materials import inbox as material_intake
import hmac
from inresearch.workflow import commands as commands
from inresearch.knowledge import registry as research
from inresearch.delivery import report as report_model
import posixpath
import subprocess as subprocess
import sys
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer as ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = project_root()
PY = sys.executable

TASKS = {
    "collect":    ("兼容历史简报", ["manage.py", "historical-brief", "--offline"], 600),
    "news":       ("inews 采集状态", ["manage.py", "acquisition-status", "inews"], 30),
    "sec":        ("SEC 采集状态", ["manage.py", "acquisition-status", "sec"], 30),
    "gpu":        ("GPU 采集状态", ["manage.py", "acquisition-status", "gpu"], 30),
    "indicators": ("指标回填", ["manage.py", "indicators"], 30),
    "verify":     ("生成核验队列", ["manage.py", "verify"], 30),
    "validate":   ("数据校验", ["manage.py", "validate"], 30),
    "export":     ("导出全量报告（md+docx）", ["manage.py", "export", "--docx"], 120),
    "map":        ("Top10 地图（html+pdf）", ["manage.py", "map"], 90),
    "inbox":      ("扫描收件箱（docs/inbox）", ["manage.py", "scan-candidates"], 30),
    "reader":     ("Spark 常驻阅读状态", ["manage.py", "reader-status"], 30),
    "queue":      ("生成精读队列", ["manage.py", "reading-queue"], 30),
    "workorder":  ("生成工单队列", ["manage.py", "workorders"], 60),
    "blindspot":  ("盲区体检", ["manage.py", "coverage"], 60),
    "intake":     ("成员投递机检与分流", ["manage.py", "submissions"], 60),
    "facts":      ("事实层校验与可比性", ["manage.py", "facts"], 30),
}
RUNNING = set()
LOCK = threading.Lock()


def log_run(task, output):
    d = ROOT / "logs"
    d.mkdir(exist_ok=True)
    (d / f"task_{task}.log").write_text(
        f"[{datetime.now().isoformat(timespec='seconds')}]\n{output}\n", encoding="utf-8")


AUTH_ON = False   # main() 按绑定地址决定；127.0.0.1 本地用法永远不要求登录


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def translate_path(self, path):
        normalized = posixpath.normpath(unquote(urlsplit(path).path).replace('\\', '/'))
        return str(source_path(normalized, ROOT))

    def list_directory(self, path):
        self.send_error(404, 'not found')
        return None

    def log_message(self, *a):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            # Navigation may cancel an in-flight response; the request is over.
            self.close_connection = True

    def _json(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, code, html, extra_headers=()):
        body = html.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in extra_headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self, to, extra_headers=()):
        self.send_response(302)
        self.send_header("Location", to)
        for k, v in extra_headers:
            self.send_header(k, v)
        self.end_headers()

    # ── 路径归一化 ───────────────────────────────────────
    # 静态文件服务（translate_path）会先 unquote 路径再找文件；闸门若拿原始
    # 字符串做子串/前缀判断，/data/users%2Ejson、/assets/%2E%2E/data/… 这类
    # 编码或穿越变体就能穿过封锁。一切基于路径的允许/拒绝判断都必须用这里
    # 解码 + 反斜杠归一 + normpath 之后的路径。
    def _norm_path(self):
        return posixpath.normpath(
            unquote(urlsplit(self.path).path).replace("\\", "/"))

    # ── 认证闸门 ─────────────────────────────────────────
    # 返回 None 表示本请求已被闸门处理完（重定向/拒绝），调用方应直接 return；
    # 返回用户名或 "" 表示放行。仅登录入口与两份纯外观资源公开，
    # 包括静态文件——账本、事实层、打分表全在静态目录里，漏一条路径等于没锁门。
    def _gate(self):
        low = self._norm_path().lower()
        if any(p.startswith('.') for p in low.split('/') if p) or low.endswith('/users.json') or low == '/data/research_runtime.json':
            self._json(404, {"ok": False, "error": "not found"})
            return None
        if not AUTH_ON:
            return ""
        # 密钥与用户表即使登录后也永远不可经 HTTP 取到（纵深防御）。
        # 判解码归一化后的路径（见 _norm_path），并转小写——本机 launchd 部署跑在
        # macOS 上，文件系统大小写不敏感，/DATA/USERS.JSON 一样能取到文件。
        low = self._norm_path().lower()
        if "/.hub_secret" in low or "/users.json" in low:
            self._json(404, {"ok": False, "error": "not found"})
            return None
        if self._norm_path() in {"/assets/site-skin.js", "/assets/theme-state.js", "/assets/auth-form.js", "/assets/auth.css", "/assets/site-skin.css", "/assets/InterVariable.woff2", "/assets/Inter-LICENSE.txt"}:
            return ""
        user = auth.session_user(self.headers.get("Cookie"))
        if user:
            return user
        if self.path == "/login" or self.path == "/api/login":
            return ""
        if self.path.startswith("/api/"):
            self._json(401, {"ok": False, "error": "未登录"})
        else:
            self._redirect("/login")
        return None

    def api_login(self, payload):
        ip = auth.client_ip(self)
        if auth.throttled(ip):
            return self._json(429, {"ok": False, "error": "尝试过于频繁，5 分钟后再试"})
        if not isinstance(payload.get('username'), str) or not isinstance(payload.get('password'), str):
            return self._json(400, {"ok": False, "error": "用户名和密码必须是文本"})
        username = payload['username'].strip()
        password = payload.get("password") or ""
        if not auth.load_users():
            return self._json(503, {"ok": False, "error":
                "尚未创建任何用户——在服务器上运行 "
                "`docker compose exec dchub python3 manage.py users add <用户名>`"})
        if auth.verify_password(username, password):
            log_run("auth", f"登录成功 {username} @ {ip}")
            return self._login_ok(username)
        auth.record_fail(ip)
        log_run("auth", f"登录失败 {username or '(空)'} @ {ip}")
        return self._json(401, {"ok": False, "error": "用户名或密码不对"})

    def _login_ok(self, username):
        body = json.dumps({"ok": True, "user": username}, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Set-Cookie", auth.make_cookie(username))
        self.end_headers()
        self.wfile.write(body)

    def _intern_allowed(self, path):
        return any(path == a or (a.endswith("/") and path.startswith(a))
                   for a in auth.INTERN_GET_ALLOW)

    def do_HEAD(self):
        # SimpleHTTPRequestHandler 自带 HEAD 支持——不过闸的话可以用 HEAD 探文件存在与大小
        user = self._gate()
        if user is None:
            return
        # 实习生白名单对 HEAD 同样生效——不然可用 HEAD 探封锁文件的存在与大小
        if user and auth.user_role(user) == "intern" \
                and not self._intern_allowed(self._norm_path()):
            return self._html(403, pages.FORBIDDEN_PAGE)
        return super().do_HEAD()

    def intake_worker(self):
        token_path = Path(os.environ.get('INRESEARCH_READER_TOKEN_FILE', ROOT / 'data/.reader_sync_token'))
        try:
            token = token_path.read_text().strip()
        except OSError:
            token = ''
        supplied = self.headers.get('Authorization', '').removeprefix('Bearer ')
        if len(token) < 32 or not hmac.compare_digest(token.encode(), supplied.encode()):
            self._json(401, {'ok': False, 'error': 'invalid credential'})
            return False
        return True

    def do_GET(self):
        if self.path.startswith('/api/intake-worker/'):
            if not self.intake_worker():
                return
            if self.path == '/api/intake-worker/pending':
                return self._json(200, {'items': [r for r in material_intake.records() if r['status'] == 'queued'][:20]})
            try:
                key = self.path.removeprefix('/api/intake-worker/content/')
                path = material_intake.record_path(key) / 'content'
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', str(path.stat().st_size))
                self.end_headers()
                with path.open('rb') as f:
                    import shutil
                    shutil.copyfileobj(f, self.wfile)
                return
            except (ValueError, OSError):
                return self._json(404, {'ok': False})
        user = self._gate()
        if user is None:
            return
        if user and auth.user_role(user) == "intern":
            path = self._norm_path()
            if path in ("/", "/index.html"):
                return self._redirect("/team.html")     # 实习生的首页就是工单板
            if not self._intern_allowed(path):
                return self._html(403, pages.FORBIDDEN_PAGE)
        if self.path == "/login":
            if user:                       # 已登录还访问登录页 → 回首页
                return self._redirect("/")
            return self._html(200, pages.LOGIN_PAGE)
        if self.path == "/logout":
            return self._redirect("/login", [("Set-Cookie", auth.clear_cookie())])
        if self.path == "/account":
            if not user:                   # 本地模式没有身份，改密无从谈起
                return self._redirect("/")
            return self._html(200, pages.PASSWD_PAGE)
        if self.path == "/api/whoami":
            return self._json(200, {"ok": True, "user": user or "(本地模式)",
                                    "role": auth.user_role(user) if user else "admin"})
        if self.path == "/api/users":
            if user and auth.user_role(user) != "admin":
                return self._json(403, {"ok": False, "error": "用户管理仅限 admin"})
            users = auth.load_users()
            return self._json(200, {"ok": True, "users": [
                {"name": n, "role": u.get("role", "member"), "created": u.get("created", "?")}
                for n, u in sorted(users.items())]})
        if self.path == "/api/materials":
            return self._json(200, {"items": material_intake.records()[:200]})
        if self.path == "/api/status":
            st = {}
            for t in TASKS:
                f = ROOT / "logs" / f"task_{t}.log"
                st[t] = {"last": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="minutes")
                         if f.exists() else None, "running": t in RUNNING}
            return self._json(200, st)
        if urlsplit(self.path).path == "/api/research":
            try:
                return self._json(200, research.build_snapshot(ROOT))
            except (ValueError, TypeError, KeyError, OSError) as e:
                return self._json(503, {"ok": False, "error": "研究索引暂不可用", "detail": str(e)[:300]})
        if urlsplit(self.path).path == '/api/report':
            try:
                return self._json(200, report_model.build_report(ROOT))
            except (ValueError, TypeError, KeyError, OSError):
                return self._json(503, {'ok': False, 'error': '报告暂不可用，请稍后重试'})
        if urlsplit(self.path).path == '/api/tasks':
            try:
                projection = research.read_json(ROOT / 'reports/workorders.json', {})
                return self._json(200, {'orders': research.current_tasks(ROOT),
                                       'module_stats': projection.get('module_stats', {}),
                                       'generated': datetime.now().isoformat(timespec='seconds')})
            except (ValueError, TypeError, KeyError, OSError):
                return self._json(503, {'ok': False, 'error': '任务暂不可用，请稍后重试'})
        return super().do_GET()

    def do_POST(self):
        if self.path == '/api/intake-worker/ack':
            if not self.intake_worker():
                return
            try:
                size = int(self.headers.get('Content-Length', 0))
                if not 0 < size < 4096:
                    raise ValueError('invalid size')
                payload = json.loads(self.rfile.read(size))
                material_intake.acknowledge(payload['id'], payload['sha256'])
                return self._json(200, {'ok': True})
            except (ValueError, KeyError, OSError):
                return self._json(400, {'ok': False})
        if self.path == '/api/materials':
            user = self._gate()
            if user is None:
                return
            if user and auth.user_role(user) == 'intern':
                return self._json(403, {'ok': False, 'error': '需要内部成员权限'})
            if self.headers.get('X-Requested-With') != 'material-intake':
                return self._json(403, {'ok': False, 'error': 'invalid request'})
            try:
                size = int(self.headers.get('Content-Length', 0))
                metadata = json.loads(unquote(self.headers.get('X-Material-Metadata', '{}')))
                if not isinstance(metadata, dict):
                    raise ValueError('invalid metadata')
                result = material_intake.receive(self.rfile, size, metadata, user or 'local')
                return self._json(201, {'ok': True, 'item': result})
            except (ValueError, OSError) as exc:
                return self._json(400, {'ok': False, 'error': str(exc)[:200]})
        if self.path == "/api/reader-snapshot":
            return self.api_reader_snapshot()
        user = self._gate()
        if user is None:
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            if n < 0 or n > 1024 * 1024:
                return self._json(413, {"ok": False, "error": "请求过大"})
            payload = json.loads(self.rfile.read(n).decode() or "{}")
            if not isinstance(payload, dict):
                raise ValueError('object required')
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"ok": False, "error": "请求体不是合法 JSON"})
        role = auth.user_role(user) if user else "admin"   # 本地模式视同 admin
        if self.path == "/api/login":
            return self.api_login(payload)
        if user and role == "intern" and self.path not in auth.INTERN_POST_ALLOW:
            return self._json(403, {"ok": False, "error": "该操作需要内部成员权限"})
        if self.path == "/api/run":
            if role != "admin":
                return self._json(403, {"ok": False, "error": "跑管线任务仅限 admin"})
            return self.api_run(payload)
        if self.path == "/api/add-price":
            if role == "intern":
                return self._json(403, {"ok": False, "error": "录入数据需要内部成员权限"})
            return self.api_add_price(payload)
        if self.path == "/api/users":
            if user and role != "admin":
                return self._json(403, {"ok": False, "error": "用户管理仅限 admin"})
            return self.api_users(payload, by=user)
        if self.path == "/api/passwd":
            return self.api_passwd(payload, user)
        if self.path == "/api/assign":
            return self.api_assign(payload, by=user)
        return self._json(404, {"ok": False, "error": "未知接口"})

    def api_reader_snapshot(self):
        token_path = Path(os.environ.get('INRESEARCH_READER_TOKEN_FILE', ROOT / 'data/.reader_sync_token'))
        try:
            token = token_path.read_text().strip()
        except OSError:
            return self._json(503, {"ok": False, "error": "reader receiver is not configured"})
        authorization = self.headers.get('Authorization', '')
        supplied = authorization.removeprefix('Bearer ')
        if not authorization.startswith('Bearer ') or len(token) < 32 or not hmac.compare_digest(token.encode(), supplied.encode()):
            return self._json(401, {"ok": False, "error": "invalid reader credential"})
        try:
            size = int(self.headers.get('Content-Length', 0))
            if size <= 0 or size > 64 * 1024 * 1024:
                return self._json(413, {"ok": False, "error": "snapshot must be 1 byte to 64 MiB"})
            payload = json.loads(self.rfile.read(size))
            reply = commands.receive_snapshot(ROOT, payload)
        except commands.Rejected as e:
            return self._json(e.status, {"ok": False, "error": str(e)})
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            return self._json(400, {"ok": False, "error": str(e)[:500]})
        return self._json(200, reply)

    def api_passwd(self, payload, user):
        """登录用户自助改密。必须验旧密码——cookie 被顺走 ≠ 知道密码，
        没有这道验证，捡到会话的人可以改掉密码把真主人锁在门外。"""
        if not user:
            return self._json(400, {"ok": False, "error": "本地模式无需密码"})
        old_pw = payload.get("old_password") or ""
        new_pw = payload.get("new_password") or ""
        if not isinstance(old_pw, str) or not isinstance(new_pw, str) or len(new_pw) < 8:
            return self._json(400, {"ok": False, "error": "新密码至少 8 位"})
        if not auth.set_password(user, new_pw, current_password=old_pw):
            auth.record_fail(auth.client_ip(self))   # 猜旧密码与猜登录同罪，计入限速
            return self._json(401, {"ok": False, "error": "当前密码不对"})
        log_run("auth", f"改密成功 {user} @ {auth.client_ip(self)}")
        return self._json(200, {"ok": True})

    def api_users(self, payload, by=""):
        """管理后台的用户管理（仅 admin，路由层已拦）。
        add / reset 会把明文密码返回**这一次**——前端一次性展示，之后只有哈希。"""
        action = payload.get("action")
        name = (payload.get("username") or "").strip()
        if action == "add":
            ok, msg, pw = auth.add_user(name, payload.get("password") or None,
                                        payload.get("role") or None)
            if ok:
                log_run("auth", f"加用户 {name} by {by or '(本地)'}")
            return self._json(200 if ok else 400, {"ok": ok, "msg" if ok else "error": msg,
                                                   **({"password": pw} if ok else {})})
        if action == "remove":
            if name == by:
                return self._json(400, {"ok": False, "error": "不能删除自己——请让另一位 admin 操作"})
            ok, msg = auth.remove_user(name)
            if ok:
                log_run("auth", f"删用户 {name} by {by or '(本地)'}")
            return self._json(200 if ok else 400, {"ok": ok, "msg" if ok else "error": msg})
        if action == "role":
            ok, msg = auth.set_role(name, payload.get("role") or "")
            if ok:
                log_run("auth", f"改角色 {name}→{payload.get('role')} by {by or '(本地)'}")
            return self._json(200 if ok else 400, {"ok": ok, "msg" if ok else "error": msg})
        if action == "rename":
            ok, msg = auth.rename_user(name, (payload.get("new_name") or "").strip())
            if ok:
                log_run("auth", f"改名 {name}→{payload.get('new_name')} by {by or '(本地)'}")
            return self._json(200 if ok else 400, {"ok": ok, "msg" if ok else "error": msg})
        if action == "reset":
            ok, msg, pw = auth.reset_password(name, payload.get("password") or None)
            if ok:
                log_run("auth", f"重置密码 {name} by {by or '(本地)'}")
            return self._json(200 if ok else 400, {"ok": ok, "msg" if ok else "error": msg,
                                                   **({"password": pw} if ok else {})})
        return self._json(400, {"ok": False, "error": f"未知 action：{action}"})

    def api_run(self, payload):
        task = payload.get("task")
        if task not in TASKS:
            return self._json(400, {"ok": False, "error": f"任务不在白名单: {task}"})
        with LOCK:
            if task in RUNNING:
                return self._json(409, {"ok": False, "error": "该任务正在运行中"})
            RUNNING.add(task)
        try:
            name, args, timeout = TASKS[task]
            r = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
            out = ((r.stdout or "") + (r.stderr or "")).strip()[-4000:]
            log_run(task, out)
            return self._json(200, {"ok": r.returncode == 0, "task": task, "name": name, "output": out})
        except subprocess.TimeoutExpired:
            return self._json(200, {"ok": False, "error": "任务超时"})
        finally:
            RUNNING.discard(task)

    def api_add_price(self, rec):
        try:
            reply = commands.add_price(ROOT, rec)
        except commands.Rejected as exc:
            return self._json(exc.status, {"ok": False, "error": str(exc)})
        return self._json(200, reply)


    def api_assign(self, rec, by=""):
        try:
            reply = commands.assign(ROOT, rec, by=by, role=auth.user_role(by) if by else 'admin')
        except commands.Rejected as exc:
            return self._json(exc.status, {"ok": False, "error": str(exc)})
        return self._json(200, reply)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    host = os.environ.get("HUB_HOST", "127.0.0.1")
    # 登录认证：绑非本机地址时强制开启（HUB_AUTH=off 可显式关，仅限调试）；
    # 本地 127.0.0.1 单人用法永远不要求登录，行为与从前一样。
    global AUTH_ON
    AUTH_ON = {"on": True, "off": False}.get(
        os.environ.get("HUB_AUTH", "").lower(), host != "127.0.0.1")
    srv = ThreadingHTTPServer((host, port), Handler)
    where = "http://localhost:%d" % port if host == "127.0.0.1" else f"{host}:{port}"
    print(f"Datacenter Hub 服务运行于 {where}（静态 + 管理 API）"
          f"｜登录认证 {'开' if AUTH_ON else '关'}")
    if AUTH_ON and not auth.load_users():
        print("⚠️  认证已开但还没有用户——先跑 `python3 manage.py users add <用户名>`")
    if host != "127.0.0.1" and not AUTH_ON:
        print("⚠️  绑定了非本机地址且认证被显式关闭——确认前面有反代级认证再这么跑")
    srv.serve_forever()


if __name__ == "__main__":
    main()
