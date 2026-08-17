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
import json
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

    def do_GET(self):
        if self.path == "/api/status":
            st = {}
            for t in TASKS:
                f = ROOT / "logs" / f"task_{t}.log"
                st[t] = {"last": datetime.fromtimestamp(f.stat().st_mtime).isoformat(timespec="minutes")
                         if f.exists() else None, "running": t in RUNNING}
            return self._json(200, st)
        return super().do_GET()

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(n).decode() or "{}")
        except (ValueError, json.JSONDecodeError):
            return self._json(400, {"ok": False, "error": "请求体不是合法 JSON"})
        if self.path == "/api/run":
            return self.api_run(payload)
        if self.path == "/api/add-price":
            return self.api_add_price(payload)
        if self.path == "/api/assign":
            return self.api_assign(payload)
        return self._json(404, {"ok": False, "error": "未知接口"})

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


    def api_assign(self, rec):
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
        if not row.get("assigned"):
            row["assigned"] = row["updated"]
        if row.get("status") == "已放弃" and not row.get("note"):
            return self._json(400, {"ok": False, "error": "标为已放弃必须写 note 说明原因——不写原因，下次还会重派同一件事"})
        doc["updated"] = row["updated"]
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return self._json(200, {"ok": True, "msg": f"{wid} → {row.get('assignee') or '未指定'}（{row['status']}）"})


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Datacenter Hub 服务运行于 http://localhost:{port}（静态 + 管理 API）")
    srv.serve_forever()


if __name__ == "__main__":
    main()
