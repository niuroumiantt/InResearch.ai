#!/usr/bin/env python3
"""Datacenter Hub 本地服务器：静态站点 + 管理后台 API。零依赖，仅监听 127.0.0.1。

    python3 pipeline/serve.py [端口]     # 默认 8000；launchd 常驻运行

API（供 ops.html 管理后台调用）：
  POST /api/run        {"task": "<名>"}         运行白名单内的管线脚本，返回输出
  POST /api/add-price  {价格记录字段}            人工录入价格/事件 → prices.json（先校验后落盘）
  POST /api/assign     {workorder_id, assignee, status, due?, note?}
                                                派工/改状态 → assignments.json（team.html 调用）
  GET  /api/status                              各任务上次运行时间（logs/ 时间戳）

安全：仅本机回环地址；任务白名单；录入走 validate.py 把关，失败自动回滚。
"""
import os
import json
import auth
import subprocess
import sys
import threading
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable

TASKS = {
    "collect":    ("每日流水线（采集+简报+标记）", ["pipeline/collect.py"], 600),
    "news":       ("news 信号桥接", ["pipeline/fetch_news_signals.py"], 120),
    "sec":        ("SEC EDGAR 采集", ["pipeline/fetch_sec.py"], 300),
    "gpu":        ("GPU 租价采集（vast.ai）", ["pipeline/fetch_gpu_prices.py"], 90),
    "indicators": ("指标回填", ["pipeline/refresh_indicators.py"], 30),
    "verify":     ("生成核验队列", ["pipeline/verify.py"], 30),
    "validate":   ("数据校验", ["pipeline/validate.py"], 30),
    "export":     ("导出全量报告（md+docx）", ["pipeline/export.py", "--docx"], 120),
    "map":        ("Top10 地图（html+pdf）", ["pipeline/output_map.py"], 90),
    "inbox":      ("扫描收件箱（docs/inbox）", ["pipeline/scan_inbox.py"], 30),
    "reader":     ("启动本地精读会话（新 Terminal）", ["pipeline/launch_reader.py"], 30),
    "queue":      ("生成精读队列", ["pipeline/reading_queue.py"], 30),
    "workorder":  ("生成工单队列", ["pipeline/workorder.py"], 60),
    "blindspot":  ("盲区体检", ["pipeline/blindspot.py"], 60),
    "intake":     ("成员投递机检与分流", ["pipeline/intake.py"], 60),
    "facts":      ("事实层校验与可比性", ["pipeline/facts.py"], 30),
}
ASSIGN_STATUSES = {"已派", "进行中", "已交付", "已合并", "已放弃"}
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

    def log_message(self, *a):
        pass

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

    # ── 认证闸门 ─────────────────────────────────────────
    # 返回 None 表示本请求已被闸门处理完（重定向/拒绝），调用方应直接 return；
    # 返回用户名或 "" 表示放行。**除 /login 与 /api/login 外一切路径都过闸**，
    # 包括静态文件——账本、事实层、打分表全在静态目录里，漏一条路径等于没锁门。
    def _gate(self):
        if not AUTH_ON:
            return ""
        # 密钥与用户表即使登录后也永远不可经 HTTP 取到（纵深防御）
        if "/.hub_secret" in self.path or "/users.json" in self.path:
            self._json(404, {"ok": False, "error": "not found"})
            return None
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
        username = (payload.get("username") or "").strip()
        password = payload.get("password") or ""
        if not auth.load_users():
            return self._json(503, {"ok": False, "error":
                "尚未创建任何用户——在服务器上运行 "
                "`docker compose exec dchub python3 pipeline/users.py add <用户名>`"})
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

    def do_HEAD(self):
        # SimpleHTTPRequestHandler 自带 HEAD 支持——不过闸的话可以用 HEAD 探文件存在与大小
        if self._gate() is None:
            return
        return super().do_HEAD()

    def do_GET(self):
        user = self._gate()
        if user is None:
            return
        if user and auth.user_role(user) == "intern":
            path = self.path.split("?")[0]
            if path in ("/", "/index.html"):
                return self._redirect("/team.html")     # 实习生的首页就是工单板
            if not any(path == a or (a.endswith("/") and path.startswith(a))
                       for a in auth.INTERN_GET_ALLOW):
                return self._html(403, auth.FORBIDDEN_PAGE)
        if self.path == "/login":
            if user:                       # 已登录还访问登录页 → 回首页
                return self._redirect("/")
            return self._html(200, auth.LOGIN_PAGE)
        if self.path == "/logout":
            return self._redirect("/login", [("Set-Cookie", auth.clear_cookie())])
        if self.path == "/account":
            if not user:                   # 本地模式没有身份，改密无从谈起
                return self._redirect("/")
            return self._html(200, auth.PASSWD_PAGE)
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
        if self.path == "/api/status":
            st = {}
            for t in TASKS:
                f = ROOT / "logs" / f"task_{t}.log"
                st[t] = {"last": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="minutes")
                         if f.exists() else None, "running": t in RUNNING}
            return self._json(200, st)
        return super().do_GET()

    def do_POST(self):
        user = self._gate()
        if user is None:
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n).decode() or "{}")
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

    def api_passwd(self, payload, user):
        """登录用户自助改密。必须验旧密码——cookie 被顺走 ≠ 知道密码，
        没有这道验证，捡到会话的人可以改掉密码把真主人锁在门外。"""
        if not user:
            return self._json(400, {"ok": False, "error": "本地模式无需密码"})
        old_pw = payload.get("old_password") or ""
        new_pw = payload.get("new_password") or ""
        if len(new_pw) < 8:
            return self._json(400, {"ok": False, "error": "新密码至少 8 位"})
        if not auth.verify_password(user, old_pw):
            auth.record_fail(auth.client_ip(self))   # 猜旧密码与猜登录同罪，计入限速
            return self._json(401, {"ok": False, "error": "当前密码不对"})
        auth.set_password(user, new_pw)
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
        required = ["series_id", "as_of", "value", "unit", "grade", "source_url", "category", "module"]
        missing = [k for k in required if rec.get(k) in (None, "")]
        if missing:
            return self._json(400, {"ok": False, "error": "缺少字段: " + ", ".join(missing)})
        try:
            rec["value"] = float(rec["value"])
        except (TypeError, ValueError):
            return self._json(400, {"ok": False, "error": "value 必须是数字"})
        if rec["grade"] == "estimate" and not rec.get("assumptions"):
            return self._json(400, {"ok": False, "error": "estimate 级必须填写 assumptions（推导链条）"})
        rec.setdefault("region", None)
        rec.setdefault("assumptions", None)
        rec.setdefault("note", "管理后台人工录入")

        p = ROOT / "data" / "prices.json"
        backup = p.read_text(encoding="utf-8")
        doc = json.loads(backup)
        if any(r["series_id"] == rec["series_id"] and r["as_of"] == rec["as_of"] for r in doc["records"]):
            return self._json(409, {"ok": False, "error": "该序列在此时点已有记录（series_id + as_of 唯一）"})
        doc["records"].append(rec)
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        chk = subprocess.run([PY, "pipeline/validate.py"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        if chk.returncode != 0:
            p.write_text(backup, encoding="utf-8")  # 回滚
            return self._json(400, {"ok": False, "error": "校验未通过，已回滚：\n" + chk.stdout[-800:]})
        subprocess.run([PY, "pipeline/refresh_indicators.py"], cwd=ROOT, capture_output=True, timeout=30)
        return self._json(200, {"ok": True, "msg": f"已入库 {rec['series_id']}@{rec['as_of']} = {rec['value']} {rec['unit']}，指标已回填"})


    def api_assign(self, rec, by=""):
        """派工/改状态。工单号必须真实存在于当前队列——否则就是派了一件不存在的活。"""
        wid = (rec.get("workorder_id") or "").strip()
        status = (rec.get("status") or "").strip()
        if not wid:
            return self._json(400, {"ok": False, "error": "缺 workorder_id"})
        if status and status not in ASSIGN_STATUSES:
            return self._json(400, {"ok": False, "error": f"状态非法（合法：{'、'.join(sorted(ASSIGN_STATUSES))}）"})

        wof = ROOT / "reports" / "workorders.json"
        if not wof.exists():
            return self._json(400, {"ok": False, "error": "工单队列尚未生成，先跑 workorder 任务"})
        live = {o["wid"] for o in json.loads(wof.read_text(encoding="utf-8"))["orders"]}
        if wid not in live:
            return self._json(400, {"ok": False,
                                    "error": f"{wid} 不在当前工单队列里——可能该缺口已被填上，工单自动消失了"})

        p = ROOT / "data" / "assignments.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        row = next((r for r in doc["records"] if r["workorder_id"] == wid), None)
        if row is None:
            row = {"workorder_id": wid}
            doc["records"].append(row)
        for k in ("assignee", "status", "due", "note"):
            if rec.get(k) is not None:
                row[k] = rec[k]
        row.setdefault("status", "已派")
        row["updated"] = datetime.now().date().isoformat()
        if by:
            row["by"] = by          # 谁派的工——登录后自动带上，审计用
        if not row.get("assigned"):
            row["assigned"] = row["updated"]
        if row.get("status") == "已放弃" and not row.get("note"):
            return self._json(400, {"ok": False, "error": "标为已放弃必须写 note 说明原因——不写原因，下次还会重派同一件事"})
        doc["updated"] = row["updated"]
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return self._json(200, {"ok": True, "msg": f"{wid} → {row.get('assignee') or '未指定'}（{row['status']}）"})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    # 默认仍只监听 127.0.0.1——**本脚本没有任何认证**，绑到 0.0.0.0 等于把含
    # 招标控制价与业主商业信息的后台裸奔。容器化部署时用 HUB_HOST=0.0.0.0，
    # 但那必须配合前置反代与身份验证（见 deploy/README.md），
    # **不要只为了「能访问」就改这个变量**。
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
        print("⚠️  认证已开但还没有用户——先跑 `python3 pipeline/users.py add <用户名>`")
    if host != "127.0.0.1" and not AUTH_ON:
        print("⚠️  绑定了非本机地址且认证被显式关闭——确认前面有反代级认证再这么跑")
    srv.serve_forever()


if __name__ == "__main__":
    main()
