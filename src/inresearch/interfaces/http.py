#!/usr/bin/env python3
"""Authenticated HTTP adapter for shared business commands and declared static URLs.

Local binding defaults to loopback. Non-loopback deployment enables login unless
HUB_AUTH explicitly overrides it; authorization and input parsing live here,
while data mutation rules live in workflow.commands.
"""

from inresearch.paths import project_root
from inresearch.storage.layout import initialize_runtime, workspace_path
from inresearch.storage.files import CommitUncertain
from inresearch.interfaces.static import source_path
from inresearch.interfaces import pages
from inresearch.interfaces import repository_pages
import os
import json
import re
from inresearch.interfaces import auth as auth
from inresearch.interfaces import public
from inresearch.materials import inbox as material_intake
from inresearch.materials import model_assets
import hmac
from inresearch.workflow import operations
from inresearch.workflow import commands as commands
from inresearch.workflow import supply
from inresearch.workflow import news_marks
from inresearch.workflow import dispatch
from inresearch.workflow import pilot_progress
from inresearch.workflow import product_catalog
from inresearch.workflow import company_window
from inresearch.adapters import company_quotes
from inresearch.workflow import product_coverage
from inresearch.adapters import acquisition
from inresearch.knowledge import registry as research
from inresearch.knowledge import graph as graph_mod
from inresearch.delivery import report as report_model
import posixpath
import sqlite3
import subprocess as subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer as BaseThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlencode, urlsplit


class ThreadingHTTPServer(BaseThreadingHTTPServer):
    # Caddy fans a cold page's HTTP/2 assets out into concurrent HTTP/1 requests.
    # The stdlib default backlog of five drops this burst before handlers start.
    request_queue_size = 128


ROOT = project_root()
PY = sys.executable

TASKS = {
    "collect":    ("兼容历史简报", ["manage.py", "historical-brief"], 600),
    "news":       ("inews 采集状态", ["manage.py", "acquisition-status", "inews"], 30),
    "indicators": ("指标回填", ["manage.py", "indicators"], 30),
    "verify":     ("生成核验队列", ["manage.py", "verify"], 30),
    "validate":   ("数据校验", ["manage.py", "validate"], 30),
    "export":     ("导出成果快照（Markdown + JSON）", ["manage.py", "export"], 120),
    "map":        ("Top10 地图（HTML；PDF 取决于渲染环境）", ["manage.py", "map"], 90),
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
    d = workspace_path("logs", ROOT)
    d.mkdir(exist_ok=True)
    (d / f"task_{task}.log").write_text(
        f"[{datetime.now().isoformat(timespec='seconds')}]\n{output}\n", encoding="utf-8")


AUTH_ON = False   # main() 按绑定地址决定；127.0.0.1 本地用法永远不要求登录


class Handler(SimpleHTTPRequestHandler):
    # MIME 由代码决定，不依赖运行镜像的系统 mime 表（slim 镜像没有 .woff2）。
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.woff2': 'font/woff2'}

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(ROOT), **kw)

    def translate_path(self, path):
        normalized = posixpath.normpath(unquote(urlsplit(path).path).replace('\\', '/'))
        if normalized == '/product-catalog.html':
            query = parse_qs(urlsplit(path).query)
            detail = query.get('view') in (['products'], ['categories'], ['materials'], ['research']) or any(k in query for k in
                ('q', 'group', 'family', 'category', 'product_id', 'series', 'kind', 'with_specs', 'line', 'scope'))
            if not detail:
                return str(ROOT / 'web/pages/company-home.html')
            if query.get('c') == ['supermicro'] and query.get('view') not in (['materials'], ['research']):
                return str(ROOT / 'web/pages/company-products.html')
        return str(source_path(normalized, ROOT))

    def list_directory(self, path):
        self.send_error(404, 'not found')
        return None

    def log_message(self, *a):
        pass

    def end_headers(self):
        if repository_pages.protected(self._norm_path()) or self._norm_path().lower() == '/admin/company.html':
            self.send_header('Cache-Control', 'private, no-store')
            self.send_header('Vary', 'Cookie')
            self.send_header('X-Frame-Options', 'SAMEORIGIN')
        super().end_headers()

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            # Navigation may cancel an in-flight response; the request is over.
            self.close_connection = True

    def _json(self, code, obj, compressed=False):
        body = json.dumps(obj, ensure_ascii=False, separators=(',', ':')).encode()
        gzip_ok = any(part.split(';')[0].strip() == 'gzip' and
                      not any(re.fullmatch(r'q\s*=\s*0(?:\.0*)?', p.strip()) for p in part.split(';')[1:])
                      for part in self.headers.get('Accept-Encoding', '').split(','))
        if compressed and gzip_ok:
            import gzip
            body = gzip.compress(body, compresslevel=5, mtime=0)
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        if compressed:
            self.send_header('Cache-Control', 'private, no-store')
            self.send_header('Vary', 'Accept-Encoding')
            if gzip_ok:
                self.send_header('Content-Encoding', 'gzip')
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
        # Infrastructure diagrams contain private host/network information.
        # These pages require a real admin session even in local development.
        if repository_pages.protected(self._norm_path()) or self._norm_path().lower() == '/admin/company.html':
            user = auth.session_user(self.headers.get('Cookie'))
            if not user:
                self._redirect('/login')
                return None
            if auth.user_role(user) != 'admin':
                self._html(403, pages.FORBIDDEN_PAGE)
                return None
            return user
        if not AUTH_ON:
            return ""
        # 密钥与用户表即使登录后也永远不可经 HTTP 取到（纵深防御）。
        # 路径已解码归一并转小写：大小写不敏感的文件系统上 /DATA/USERS.JSON 一样能取到文件。
        if "/.hub_secret" in low or "/users.json" in low:
            self._json(404, {"ok": False, "error": "not found"})
            return None
        # 登录前只公开外观 CSS/JS 与字体包(含许可证); 字体包目录整体公开, 里面只有 infra 同步来的字体文件。
        if self._norm_path() in {"/assets/site-skin.js", "/assets/theme-state.js", "/assets/auth-form.js", "/assets/auth.css", "/assets/site-skin.css"} or self._norm_path().startswith("/assets/fonts/"):
            return ""
        user = auth.session_user(self.headers.get("Cookie"))
        if user:
            return user
        # 公开只读（reader）：目录三项、账本与它们读的数据，只对 GET/HEAD 匿名放行（白名单见 public.py）；
        # 写接口永远不放行，模型文件按角色过滤后再给（见 do_GET）。
        if self.command in ("GET", "HEAD") and public.allowed(self._norm_path()):
            return ""
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
                "系统尚未初始化账号，请联系管理员（服务器上运行 `python3 manage.py users add <用户名>`）"})
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
        # 实习生白名单 + 公开只读的内容：reader 不登录能看的，登录的实习生当然能看（账本给的是同一份公开视图）。
        return public.allowed(path) or any(path == a or (a.endswith("/") and path.startswith(a))
                                           for a in auth.INTERN_GET_ALLOW)

    def _role(self, user):
        """本地模式（不要求登录）视同 admin；要求登录而未登录的是公开只读 reader。"""
        return auth.user_role(user) if user else ("reader" if AUTH_ON else "admin")

    def do_HEAD(self):
        # SimpleHTTPRequestHandler 自带 HEAD 支持——不过闸的话可以用 HEAD 探文件存在与大小
        user = self._gate()
        if user is None:
            return
        if self._norm_path() in repository_pages.ALIASES:
            return self._redirect(repository_pages.ALIASES[self._norm_path()])
        # 实习生白名单对 HEAD 同样生效——不然可用 HEAD 探封锁文件的存在与大小
        if user and auth.user_role(user) == "intern" \
                and not self._intern_allowed(self._norm_path()):
            return self._html(403, pages.FORBIDDEN_PAGE)
        if self._norm_path() == '/company.html':
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            query.setdefault('c', ['microsoft'])
            return self._redirect('/product-catalog.html?' + urlencode(query, doseq=True))
        return super().do_HEAD()

    def intake_worker(self):
        token_path = Path(os.environ.get('INRESEARCH_READER_TOKEN_FILE', workspace_path('data/.reader_sync_token', ROOT)))
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
        if self._norm_path() in repository_pages.ALIASES:
            return self._redirect(repository_pages.ALIASES[self._norm_path()])
        merged = {'/team.html': '#tasks', '/materials.html': '#inbox', '/nvidia-pilot.html': '#pilot'}
        if self._norm_path() in merged:  # 三页并入采集页（2026-09-28）
            return self._redirect('/supply.html' + merged[self._norm_path()])
        if user and auth.user_role(user) == "intern":
            path = self._norm_path()
            if path in ("/", "/index.html"):
                return self._redirect("/supply.html#targets")     # 实习生的首页就是采集页的目标表（自己的行）
            if not self._intern_allowed(path):
                return self._html(403, pages.FORBIDDEN_PAGE)
        if self._norm_path() == '/company.html':
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            query.setdefault('c', ['microsoft'])
            return self._redirect('/product-catalog.html?' + urlencode(query, doseq=True))
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
        if self._norm_path() == "/healthz":
            # 健康探针（2026-09-29）：只证明进程在、能路由、能序列化；不 stat 日志、不读运行文件、不看登录态。
            # 容器编排、Dockerfile 与 infra hosts/apps.json 都探这里，不再探登录页或首页。
            return self._json(200, {"ok": True, "service": "inresearch", "auth_required": bool(AUTH_ON)})
        if self.path == "/api/whoami":
            role = self._role(user)
            return self._json(200, {"ok": True, "user": user or (None if role == "reader" else "(本地模式)"), "role": role})
        if self._norm_path() == "/data/datacenter_model.json" and self._role(user) in ("reader", "intern"):
            # 账本的公开视图：基准预设与校准锚，地区与情景预设登录后才有。过滤在服务端，页面照着渲染。
            try:
                spec = json.loads(Path(self.translate_path(self.path)).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return self._json(404, {"ok": False, "error": "not found"})
            return self._json(200, public.public_model(spec))
        if urlsplit(self.path).path == '/api/targets':
            # 目标表 + 派工状态，服务端按角色过滤：实习生只见分配给自己的行；公开只读没有这个接口（闸门已 401）
            params = {k: v[0] for k, v in parse_qs(urlsplit(self.path).query).items()}
            try:
                return self._json(200, dispatch.targets_view(ROOT, user or None, self._role(user), params))
            except (OSError, ValueError, KeyError, TypeError):
                return self._json(503, {'ok': False, 'error': '目标表暂不可读取'})
        if urlsplit(self.path).path == '/api/admin/product-coverage':
            # 登记覆盖页：产品线型号标签按规格库（Fetchspec 交付）名称匹配；仅管理员。
            if self._role(user) != "admin":
                return self._json(403, {"ok": False, "error": "登记覆盖仅限 admin"})
            try:
                return self._json(200, product_coverage.coverage(ROOT))
            except (OSError, ValueError, KeyError, sqlite3.Error):
                return self._json(503, {"ok": False, "error": "登记覆盖暂不可读取"})
        if self.path == "/api/users":
            if self._role(user) != "admin":
                return self._json(403, {"ok": False, "error": "用户管理仅限 admin"})
            users = auth.load_users()
            return self._json(200, {"ok": True, "users": [
                {"name": n, "role": u.get("role", "member"), "created": u.get("created", "?")}
                for n, u in sorted(users.items())]})
        if urlsplit(self.path).path.startswith('/api/product-catalog/'):
            # 规格库按公司分库（2026-10-01）：/api/product-catalog/<company>，公司须在 COMPANIES 登记。
            company = urlsplit(self.path).path.removeprefix('/api/product-catalog/')
            if company not in product_catalog.COMPANIES:
                return self._json(404, {'ok': False, 'error': 'unknown catalog company'})
            query = parse_qs(urlsplit(self.path).query)
            if query.get('view') == ['browse']:
                from inresearch.workflow.catalog_browse import query as browse_query
                try:
                    return self._json(200, browse_query(ROOT, company,
                        category=query.get('category',[''])[0], line=query.get('line',[''])[0],
                        q=query.get('q',[''])[0], kind=query.get('kind',[''])[0],
                        with_specs=query.get('with_specs',[''])[0]=='1', offset=query.get('offset',['0'])[0]))
                except ValueError as exc:
                    return self._json(400, {'error':str(exc)})
                except sqlite3.Error:
                    return self._json(503, {'error':'product browsing temporarily unavailable'})
            if query.get('view') == ['materials']:
                from inresearch.workflow.catalog_materials import query as material_query
                try:
                    return self._json(200, material_query(ROOT,company,query.get('q',[''])[0],query.get('offset',['0'])[0]))
                except (ValueError, sqlite3.Error):
                    return self._json(400, {'error':'invalid material query'})
            export = query.get('export', [''])[0]
            if export:
                value = product_catalog.snapshot(ROOT, company)
                try:
                    body = product_catalog.csv_export(value, export, query.get('q', [''])[0], query.get('kind', [''])[0], query.get('with_specs', [''])[0] == '1', query.get('group', [''])[0], query.get('family', [''])[0], query.get('scope', ['all'])[0], company=company, line=query.get('line', [''])[0], category=query.get('category',[''])[0]).encode('utf-8')
                except ValueError as exc:
                    return self._json(400, {'error': str(exc)})
                self.send_response(200)
                self.send_header('Content-Type', 'text/csv; charset=utf-8')
                self.send_header('Content-Disposition', 'attachment; filename="' + company + '-' + export + '.csv"')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                return self.wfile.write(body)
            product_id = query.get('product_id', [''])[0]
            if product_id:
                try:
                    value = product_catalog.product_snapshot(ROOT, product_id, company)
                except ValueError as exc:
                    return self._json(400, {'error': str(exc)})
                if value['product'] is None:
                    return self._json(404, {'error': 'product not found'})
                return self._json(200, value)
            series_id = query.get('series_id', [''])[0]
            if series_id:  # one vendor series: its parts pivoted into a comparison table
                try:
                    value = product_catalog.series_snapshot(ROOT, series_id, company)
                except ValueError as exc:
                    return self._json(400, {'error': str(exc)})
                if value['available'] and value['series'] is None:
                    return self._json(404, {'error': 'series not found'})
                return self._json(200, value)
            view = query.get('view', ['full'])[0]
            if view == 'index':
                return self._json(200, product_catalog.index_snapshot(ROOT, company))
            if view == 'summary':  # the company page: coverage, vendor groups and demand alignment, no product list
                return self._json(200, product_catalog.summary_snapshot(ROOT, company))
            if view == 'full':
                return self._json(200, product_catalog.snapshot(ROOT, company))
            return self._json(400, {'error': 'unknown catalog view'})
        if urlsplit(self.path).path == '/api/pilot-progress/nvidia':
            try:
                return self._json(200, pilot_progress.public_snapshot(ROOT))
            except (ValueError, TypeError, KeyError, OSError):
                return self._json(503, {'ok': False, 'error': 'pilot progress unavailable'})
        if self.path == "/api/supply":
            try:
                return self._json(200, supply.snapshot(ROOT))
            except (ValueError, OSError, KeyError, TypeError):
                return self._json(503, {"ok": False, "error": "供应台账不可用，请重试或修复"})
        if urlsplit(self.path).path == "/api/product-documents":
            query=parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            allowed={'company_id','category','question_id','format','language','limit','offset'}
            if set(query)-allowed or any(len(v)!=1 for v in query.values()):
                return self._json(400, {'ok':False,'error':'invalid_product_document_query'})
            try:
                page={'limit':int(query.get('limit',['50'])[0]),'offset':int(query.get('offset',['0'])[0])}
                filters={key:query[key][0] for key in allowed-{'limit','offset'} if key in query}
                data_root=Path(os.environ.get('READER_DATA_ROOT',Path.home()/'.local/share/inresearch.ai')).expanduser()
                return self._json(200,acquisition.product_documents(data_root,**filters,**page))
            except (ValueError,TypeError):
                return self._json(400, {'ok':False,'error':'invalid_product_document_filter'})
        if self.path == "/api/materials":
            return self._json(200, {"items": material_intake.records()[:200]})
        if urlsplit(self.path).path in ('/api/ops', '/api/ops/log'):
            if self._role(user) != 'admin':
                return self._json(403, {'ok': False, 'error': '仅管理员可查看运行诊断与日志'})
            if urlsplit(self.path).path == '/api/ops':
                with LOCK:
                    running = set(RUNNING)
                return self._json(200, operations.snapshot(ROOT, TASKS, running), compressed=True)
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            if set(query) != {'id'} or len(query['id']) != 1:
                return self._json(400, {'ok': False, 'error': 'invalid log query'})
            try:
                output = operations.log_content(ROOT, query['id'][0]).encode('utf-8')
            except ValueError:
                return self._json(400, {'ok': False, 'error': 'invalid run identity'})
            except OSError:
                return self._json(404, {'ok': False, 'error': 'run log not found'})
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Disposition', 'attachment; filename="run-' + query['id'][0] + '.log"')
            self.send_header('Content-Length', str(len(output)))
            self.end_headers()
            return self.wfile.write(output)
        if self.path == "/api/status":
            with LOCK:
                running = set(RUNNING)
            return self._json(200, operations.task_state(ROOT, TASKS, running))
        if urlsplit(self.path).path == '/api/model-assets':
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            page = query.get('page', [None])
            if set(query) - {'page'} or len(page) != 1 or (page[0] is not None and page[0] not in model_assets.PAGES):
                return self._json(400, {'ok': False, 'error': '无效场景'})
            try:
                return self._json(200, model_assets.snapshot(ROOT, page[0]))
            except (ValueError, TypeError, KeyError, OSError):
                return self._json(503, {'ok': False, 'error': '模型登记暂不可用，请重试'})
        if urlsplit(self.path).path == '/api/targets/backflow':
            query = parse_qs(urlsplit(self.path).query)
            team = query.get('team', ['fetchspec'])
            if set(query) - {'team'} or len(team) != 1:
                return self._json(400, {'ok': False, 'error': '只接受一个 team 参数'})
            try:
                return self._json(200, research.build_backflow(ROOT, team[0]))
            except KeyError:
                return self._json(400, {'ok': False, 'error': '未登记的采集队'})
            except (ValueError, TypeError, OSError):
                return self._json(503, {'ok': False, 'error': '回流暂不可用，请稍后重试'})
        if urlsplit(self.path).path == '/api/news/marks':
            # 研究员自己的「有用 / 没用」标记(2026-10-01);只给内部成员,公开的只有 /api/news 里的按目标行计数。
            if self._role(user) not in ('member', 'admin'):
                return self._json(403, {'ok': False, 'error': '需要内部成员登录'})
            try:
                return self._json(200, {'ok': True, 'marks': news_marks.mark_map(ROOT)})
            except (ValueError, TypeError, KeyError, OSError):
                return self._json(503, {'ok': False, 'error': '标记暂不可用，请重试'})
        if urlsplit(self.path).path == '/api/industry':
            from inresearch.knowledge.industry import snapshot
            try:
                query = parse_qs(urlsplit(self.path).query)
                if any(len(v) != 1 for v in query.values()): raise ValueError('duplicate filter')
                return self._json(200, snapshot(ROOT, {k: v[0] for k, v in query.items()}))
            except LookupError as error:
                return self._json(404, {'error': str(error)})
            except ValueError as error:
                return self._json(400, {'error': str(error)})
            except (OSError, TypeError, KeyError):
                return self._json(503, {'error': '行业数据暂不可用'})
        if urlsplit(self.path).path in ('/api/company-window', '/api/company-quote'):
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            if set(query) != {'c'} or len(query['c']) != 1:
                return self._json(400, {'error': 'invalid company filter'})
            try:
                cid = query['c'][0]
                profile = company_window.company(ROOT, cid)
                value = (company_quotes.snapshot(ROOT, profile) if urlsplit(self.path).path == '/api/company-quote'
                         else company_window.snapshot(ROOT, cid))
                return self._json(200, value)
            except KeyError:
                return self._json(404, {'error': 'unknown company'})
            except (OSError, ValueError, TypeError, sqlite3.Error):
                return self._json(503, {'error': 'company data unavailable'})
        if urlsplit(self.path).path == '/api/news':
            query = parse_qs(urlsplit(self.path).query, keep_blank_values=True)
            if set(query) - {'company', 'limit'} or any(len(v) != 1 for v in query.values()):
                return self._json(400, {'error': 'invalid news filter'})
            cid = query.get('company', [None])[0]
            try:
                limit = int(query.get('limit', ['6' if cid else '80'])[0])
                if not 1 <= limit <= (20 if cid else 80): raise ValueError('invalid limit')
                if cid is not None: company_window.company(ROOT, cid)
            except KeyError:
                return self._json(404, {'error': 'unknown company'})
            except (ValueError, TypeError):
                return self._json(400, {'error': 'invalid news filter'})
            try:
                return self._json(200, research.build_news(ROOT, company_id=cid, limit=limit))
            except (ValueError, TypeError, KeyError, OSError):
                return self._json(503, {'ok': False, 'error': '新闻暂不可用，请稍后重试'})
        if self._norm_path() == '/research.html':
            # 研究页退役（2026-09-28）：问题、候选证据、陈述与一跳关系并入节点页第一问；旧 ID 折算到骨架节点
            wanted = parse_qs(urlsplit(self.path).query).get('node', [''])[0]
            try:
                node = graph_mod.node_for(wanted, json.loads((ROOT / 'framework/bom.json').read_text(encoding='utf-8'))) if wanted else None
            except (OSError, ValueError):
                node = None
            return self._redirect('/node.html' + ('?' + urlencode({'id': node}) if node and node != 'root' else ''))
        if urlsplit(self.path).path == '/api/research-summary':
            try:
                node = parse_qs(urlsplit(self.path).query).get('node', [''])[0]
                return self._json(200, research.summary_for_node(research.build_research_summary(ROOT), node))
            except (ValueError, TypeError, KeyError, OSError):
                return self._json(503, {'ok': False, 'error': '研究摘要暂不可用，请稍后重试'})
        if urlsplit(self.path).path == '/api/research-adopted':
            try:
                nodes = parse_qs(urlsplit(self.path).query).get('node', ['root'])
                if len(nodes) != 1:
                    return self._json(400, {'error': 'one node required'})
                return self._json(200, research.adopted_for_node(ROOT, nodes[0]))
            except (ValueError, TypeError, KeyError, OSError):
                return self._json(503, {'ok': False, 'error': '采用详情暂不可用，请稍后重试'})
        if urlsplit(self.path).path == "/api/research":
            try:
                return self._json(200, research.build_snapshot(ROOT))
            except (ValueError, TypeError, KeyError, OSError) as e:
                return self._json(503, {"ok": False, "error": "研究索引暂不可用", "detail": str(e)[:300]})
        if urlsplit(self.path).path == '/api/report':
            try:
                legacy = parse_qs(urlsplit(self.path).query).get('legacy', [''])[0] == '1'
                return self._json(200, report_model.build_report(ROOT) if legacy else report_model.build_snapshot_report(ROOT))
            except (ValueError, TypeError, KeyError, OSError):
                return self._json(503, {'ok': False, 'error': '报告暂不可用，请稍后重试'})
        if urlsplit(self.path).path == '/api/tasks':
            try:
                return self._json(200, research.task_board(ROOT))
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
        if self.path.startswith('/api/product-catalog/'):
            company = self.path.removeprefix('/api/product-catalog/')
            if company not in product_catalog.COMPANIES:
                return self._json(404, {'ok': False, 'error': 'unknown catalog company'})
            return self.api_nvidia_pilot_progress(
                receiver=lambda root, payload: product_catalog.receive(root, payload, company))
        if self.path == '/api/pilot-progress/nvidia':
            return self.api_nvidia_pilot_progress()
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
        if self.path == "/api/supply":
            if role != "admin" or self.headers.get("X-Requested-With") != "supply-center":
                return self._json(403, {"ok": False, "error": "仅管理员可管理供应需求"})
            try:
                return self._json(200, supply.mutate(ROOT, payload, user or "local"))
            except supply.Conflict as exc:
                return self._json(409, {"ok": False, "error": str(exc)})
            except CommitUncertain:
                return self._json(503, {"ok": False, "error": "提交结果需核对，请刷新；重试将复用同一操作身份"})
            except ValueError as exc:
                return self._json(400, {"ok": False, "error": str(exc)})
            except OSError:
                return self._json(503, {"ok": False, "error": "供应台账暂不可写，请重试"})
        if self.path == "/api/news/mark":
            # 线索评价，不是 C3 采用：内部成员(member/admin)可点；自定义请求头挡跨站表单。
            if role not in ("member", "admin") or self.headers.get("X-Requested-With") != "news-mark":
                return self._json(403, {"ok": False, "error": "需要内部成员登录"})
            try:
                return self._json(200, news_marks.mark(ROOT, payload, user or "local", research.news_leads(ROOT)))
            except CommitUncertain:
                return self._json(503, {"ok": False, "error": "提交结果需核对，请刷新"})
            except ValueError as exc:
                return self._json(400, {"ok": False, "error": str(exc)[:200]})
            except OSError:
                return self._json(503, {"ok": False, "error": "标记暂不可写，请重试"})
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
        if self.path == "/api/deliver":
            try:
                return self._json(200, dispatch.register_delivery(ROOT, payload, by=user, role=role))
            except CommitUncertain as error:
                return self._json(503, {'ok': False, 'error': str(error), 'commit_state': 'visible_durability_unconfirmed'})
            except dispatch.Rejected as exc:
                return self._json(exc.status, {'ok': False, 'error': str(exc)})
        return self._json(404, {"ok": False, "error": "未知接口"})

    def api_reader_snapshot(self):
        token_path = Path(os.environ.get('INRESEARCH_READER_TOKEN_FILE', workspace_path('data/.reader_sync_token', ROOT)))
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
            if size <= 0 or size > commands.SNAPSHOT_WIRE_MAX_BYTES:
                return self._json(413, {"ok": False, "error": "snapshot must be 1 byte to 64 MiB"})
            try:
                body = commands.inflate_snapshot(self.rfile.read(size), self.headers.get('Content-Encoding'))
            except commands.SnapshotTooLarge as e:
                return self._json(413, {"ok": False, "error": str(e)})
            payload = json.loads(body)
            reply = commands.receive_snapshot(ROOT, payload)
        except CommitUncertain as error:
            return self._json(503, {'ok': False, 'error': str(error),
                                    'commit_state': 'visible_durability_unconfirmed'})
        except commands.Rejected as e:
            return self._json(e.status, {"ok": False, "error": str(e)})
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            return self._json(400, {"ok": False, "error": str(e)[:500]})
        return self._json(200, reply)

    def api_nvidia_pilot_progress(self, receiver=None):
        token_path = pilot_progress.token_path(ROOT)
        try:
            token = token_path.read_text().strip()
        except OSError:
            return self._json(503, {'ok': False, 'error': 'pilot receiver is not configured'})
        authorization = self.headers.get('Authorization', '')
        supplied = authorization.removeprefix('Bearer ')
        if (not authorization.startswith('Bearer ') or len(token) < 32
                or not hmac.compare_digest(token.encode(), supplied.encode())):
            return self._json(401, {'ok': False, 'error': 'invalid pilot credential'})
        try:
            size = int(self.headers.get('Content-Length', 0))
            if size <= 0 or size > 16 * 1024 * 1024:
                return self._json(413, {'ok': False, 'error': 'progress payload must be 1 byte to 16 MiB'})
            payload = json.loads(self.rfile.read(size))
            return self._json(200, (receiver or pilot_progress.receive)(ROOT, payload))
        except (ValueError, TypeError, KeyError, OSError) as exc:
            return self._json(400, {'ok': False, 'error': str(exc)[:300]})

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
        started, clock = time.time(), time.monotonic()
        name, args, timeout = TASKS[task]
        try:
            r = subprocess.run([PY] + args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
            out = ((r.stdout or "") + (r.stderr or "")).strip()
            record = operations.record_task(ROOT, task, name, out, started=started,
                returncode=r.returncode, duration=time.monotonic() - clock)
            # Preserve the beginning (where summaries live) and the end; full log is downloadable.
            preview = out if len(out) <= 12000 else out[:9000] + "\n… 中段已折叠，请下载完整日志 …\n" + out[-3000:]
            return self._json(200, {"ok": r.returncode == 0, "task": task, "name": name,
                "output": preview, "truncated": len(out) > 12000, "run": record,
                "log_url": '/api/ops/log?id=' + record['id']})
        except (subprocess.TimeoutExpired, OSError) as exc:
            out = '任务超时' if isinstance(exc, subprocess.TimeoutExpired) else '任务无法启动：' + type(exc).__name__
            for part in (getattr(exc, 'stdout', None), getattr(exc, 'stderr', None)):
                if part:
                    out += '\n' + (part.decode('utf-8', 'replace') if isinstance(part, bytes) else part)
            record = operations.record_task(ROOT, task, name, out, started=started,
                outcome='timeout' if isinstance(exc, subprocess.TimeoutExpired) else 'failed',
                duration=time.monotonic() - clock)
            return self._json(200, {"ok": False, "error": out[:12000], "run": record,
                "log_url": '/api/ops/log?id=' + record['id']})
        finally:
            with LOCK:
                RUNNING.discard(task)

    def api_add_price(self, rec):
        try:
            reply = commands.add_price(ROOT, rec)
        except CommitUncertain as error:
            return self._json(503, {'ok': False, 'error': str(error),
                                    'commit_state': 'visible_durability_unconfirmed'})
        except commands.Rejected as exc:
            return self._json(exc.status, {"ok": False, "error": str(exc)})
        return self._json(200, reply)


    def api_assign(self, rec, by=""):
        try:
            reply = commands.assign(ROOT, rec, by=by, role=auth.user_role(by) if by else 'admin')
        except CommitUncertain as error:
            return self._json(503, {'ok': False, 'error': str(error),
                                    'commit_state': 'visible_durability_unconfirmed'})
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
    if os.environ.get('INRESEARCH_RUNTIME_ROOT'):
        initialize_runtime(ROOT)
        from inresearch.knowledge.indicators import refresh
        refresh(ROOT)
    if AUTH_ON:
        # 部署声明的管理员（HUB_ADMIN_USERNAME / HUB_ADMIN_PASSWORD，见 auth.py 模块说明）：
        # 启动即对齐账号表，声明为空则什么都不做。只记结果，永远不记密码。
        try:
            outcome = auth.apply_declared_admin()
        except ValueError as error:
            sys.exit(f"部署声明的管理员无效：{error}")
        if outcome and outcome != "unchanged":
            declared = auth.declared_admin()[0]
            print(f"部署声明的管理员 {declared}：{outcome}")
            log_run("auth", f"部署声明的管理员 {declared}：{outcome}")
    srv = ThreadingHTTPServer((host, port), Handler)
    where = "http://localhost:%d" % port if host == "127.0.0.1" else f"{host}:{port}"
    print(f"inresearch.ai 服务运行于 {where}（静态 + 管理 API）"
          f"｜登录认证 {'开' if AUTH_ON else '关'}")
    if AUTH_ON and not auth.load_users():
        print("⚠️  认证已开但还没有用户——先跑 `python3 manage.py users add <用户名>`")
    if host != "127.0.0.1" and not AUTH_ON:
        print("⚠️  绑定了非本机地址且认证被显式关闭——确认前面有反代级认证再这么跑")
    srv.serve_forever()


if __name__ == "__main__":
    main()
