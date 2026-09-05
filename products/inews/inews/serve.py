"""本机监听:让清单页上的「抓一轮」按钮真的能在这台 Mac 上跑起来。

产出是静态 HTML,服务器上没有服务端 —— 而抓取必须在站长本机开一个带登录态的
可见 Chrome(FT 是 manual 档)。所以按钮要真的能按,只有一条路:**本机常驻一个
监听进程**,页面按钮去敲它。这个模块就是那个进程。

它是这个项目里唯一一处「网页能触发本机动作」的口子,所以边界写在这里,钉死:

- **只绑回环。** 绑 0.0.0.0 等于把「跑一轮」开放给同一个网里的任何人。
- **只认放行表里的来源。** 浏览器会把任意网页发起的请求也送到 127.0.0.1;
  来源不对就 403。
- **只认一张写死的动作表**(``ACTIONS``)。9-03 加第二个站与「修复未抓取」时,
  做法是把表列长,不是给 ``/run`` 加参数 —— 参数能被拼出来,表不能。
- **不接受任何参数。** 跑什么、跑几页、发不发布,全由那个脚本决定 ——
  网页那边一个字都改不了这一轮的行为。

它**不做**的事:不抓、不解析、不写台账。只是把表里那条命令启动起来,
然后如实回答「起没起来」。
"""
from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

# 谁可以按这个按钮。**这是安全边界,不是配置** —— 想让别的地址也能按,
# 得改这里并且想清楚为什么。
ALLOWED_ORIGINS = (
    "https://inews.today",
    "http://localhost:8000",  # 本地预览产出时用
    "null",                   # 双击本地 index.html 时,file:// 页面的 Origin 就是 null
)
DEFAULT_PORT = 8787
PATH = "/run"


def _script(name: str, *args: str) -> list[str]:
    base = Path(__file__).resolve().parents[1]
    return ["bash", str(base / "tools" / name), *args]


# 页面能触发的**全部**动作。9-03 加第二个站和「修复未抓取」时,做法不是给
# /run 加参数,而是把表列长 —— 参数是可以被拼出来的,表不是。页面只能从这份
# 写死的名单里挑一个键;不在表里的路径一律 404(见 do_POST)。
#
# 每个值是「无参可传的一条具体命令」:跑什么、发不发布仍然由那个脚本决定,
# 网页那边一个字都改不了这一轮的行为 —— 模块开头那条边界没有松动。
ACTIONS: dict[str, object] = {
    "/run": lambda: _script("hourly.sh"),
    "/run/bloomberg": lambda: _script("hourly.sh", "bloomberg"),
    "/run/cnbc": lambda: _script("hourly.sh", "cnbc"),
    "/run/wsj": lambda: _script("hourly.sh", "wsj"),
    "/run/reuters": lambda: _script("hourly.sh", "reuters"),
    "/run/axios": lambda: _script("hourly.sh", "axios"),
    "/repair": lambda: _script("repair.sh", "ft"),
    "/repair/bloomberg": lambda: _script("repair.sh", "bloomberg"),
    "/repair/cnbc": lambda: _script("repair.sh", "cnbc"),
    "/repair/wsj": lambda: _script("repair.sh", "wsj"),
    "/repair/reuters": lambda: _script("repair.sh", "reuters"),
    "/repair/axios": lambda: _script("repair.sh", "axios"),
}


def round_command(root: Path | None = None) -> list[str]:
    """默认动作(FT 那一轮)。保留这个名字:用例和 build() 都拿它当缺省。"""
    base = root or Path(__file__).resolve().parents[1]
    return ["bash", str(base / "tools" / "hourly.sh")]


class _Round:
    """当前这一轮。同时只允许一个 —— 两个实例会互相盖台账。

    `hourly.sh` 自己也有一把锁,这里再挡一次是为了**能当场回话**:锁那边的
    「跳过」只写进日志,按按钮的人在页面上什么也看不到。
    """

    def __init__(self, command: list[str] | None = None) -> None:
        # 用例会塞一条假命令进来;真跑时是 None,由动作表决定这一次执行什么。
        self.command_override = command
        self._process: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()

    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self, command: list[str]) -> tuple[bool, str]:
        with self._lock:
            if self.running():
                return False, "上一轮还在跑,这次不重复启动"
            # 不等它跑完:一轮要几分钟,而按钮那边等不了那么久。
            self._process = subprocess.Popen(command)
            return True, "已经开始跑了；需要可见浏览器的来源会打开专用 Chrome 窗口"


class _Handler(BaseHTTPRequestHandler):
    round: _Round  # 由 build() 绑上

    def do_OPTIONS(self) -> None:  # noqa: N802 BaseHTTPRequestHandler 的命名
        """预检。

        https 页面去连 http://127.0.0.1 时 Chrome 会先发预检,并且要求
        `Access-Control-Allow-Private-Network`。少一个头,按钮在浏览器里就是
        「点了没反应」—— 而服务端这边连一条请求记录都看不到。
        """
        origin = self.headers.get("Origin", "")
        if origin not in ALLOWED_ORIGINS:
            self._json(403, {"started": False, "reason": f"来源不在放行表里:{origin}"})
            return
        self.send_response(204)
        self._cors(origin)
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 同上
        action = self.path.split("?")[0]
        if action not in ACTIONS:
            self._json(404, {
                "started": False,
                "reason": f"不认识的动作:{action};只认 {'、'.join(ACTIONS)}",
            })
            return
        origin = self.headers.get("Origin", "")
        if origin not in ALLOWED_ORIGINS:
            self._json(403, {"started": False, "reason": f"来源不在放行表里:{origin}"})
            return
        # 同时只允许一轮:抓取和修复都会写同一份台账,两个一起跑会互相盖。
        # 用例给的 command 优先(它要能挑一条假命令),否则按动作表取。
        command = self.round.command_override or ACTIONS[action]()
        started, reason = self.round.start(command)
        self._json(200, {"started": started, "reason": reason}, origin=origin)

    def do_GET(self) -> None:  # noqa: N802 同上
        """`/status`:页面加载时问一句「本机监听开着吗、这会儿在跑吗」。"""
        origin = self.headers.get("Origin", "")
        if self.path.split("?")[0] != "/status":
            self._json(404, {"reason": "只认 POST /run 和 GET /status"})
            return
        self._json(200, {"running": self.round.running()}, origin=origin)

    def _cors(self, origin: str) -> None:
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _json(self, code: int, payload: dict[str, object], origin: str = "") -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self._cors(origin or self.headers.get("Origin", ""))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        # 每一次按钮都留一行。这个口子上发生过什么,要能查。
        print(f"[inews serve] {fmt % args}", flush=True)


def build(*, port: int = DEFAULT_PORT, command: list[str] | None = None) -> ThreadingHTTPServer:
    """造好监听但**不启动** —— 用例要能自己挑端口、自己收摊。"""
    handler = type("_BoundHandler", (_Handler,), {"round": _Round(command)})
    # 127.0.0.1 写死在这里,不给参数:它是这个模块的安全前提,不是可调项。
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main(port: int | None = None) -> int:
    resolved = port or int(os.getenv("INEWS_SERVE_PORT", str(DEFAULT_PORT)))
    httpd = build(port=resolved)
    host, bound = httpd.server_address[0], httpd.server_address[1]
    print(f"本机监听已开:http://{host}:{bound}{PATH}(只认这台机器上的请求)")
    print("清单页上的「抓一轮」按钮现在按下去会真的跑。Ctrl-C 停。")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n停了。")
    finally:
        httpd.server_close()
    return 0
