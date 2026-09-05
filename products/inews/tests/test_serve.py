"""本机监听的用例:清单页上的按钮按下去,**这台机器上真的要跑起来一轮**。

这是这个项目里唯一一处「网页能触发本机动作」的口子,所以它的边界要钉死:
只绑回环、只认一条路径、只认放行的来源。任何一条松了,都是把本机的登录态
和浏览器暴露给任意网页。
"""
from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from inews import serve


@pytest.fixture
def server(tmp_path: Path):
    marker = tmp_path / "ran"
    script = tmp_path / "round.sh"
    # 睡一下:并发那条用例要的是「上一轮确实还在跑」,不能靠抢时间。
    script.write_text(
        f'#!/usr/bin/env bash\necho 跑了 >> "{marker}"\nsleep 3\n', encoding="utf-8"
    )
    script.chmod(0o755)
    httpd = serve.build(port=0, command=["bash", str(script)])
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd, marker
    httpd.shutdown()
    httpd.server_close()


def _post(httpd, path: str = "/run", origin: str = "https://inews.today"):
    url = f"http://127.0.0.1:{httpd.server_address[1]}{path}"
    request = urllib.request.Request(url, data=b"", method="POST")
    if origin:
        request.add_header("Origin", origin)
    return urllib.request.urlopen(request, timeout=5)


def test_it_only_listens_on_loopback(server):
    """绑 0.0.0.0 就等于把「跑一轮」这个动作开放给同一个网里的任何人。"""
    httpd, _marker = server
    assert httpd.server_address[0] == "127.0.0.1"


def test_a_post_actually_starts_a_round(server):
    """按钮的全部意义就在这一条:它得**真的跑**,不是回一句「已收到」。"""
    httpd, marker = server
    response = _post(httpd)
    assert response.status == 200
    assert json.loads(response.read())["started"] is True
    for _ in range(50):
        if marker.exists():
            break
        __import__("time").sleep(0.1)
    assert marker.exists(), "POST /run 之后那一轮没有真的启动"


def test_it_refuses_a_second_round_while_one_is_running(server):
    """一轮还没跑完就再按一次,两个实例会互相盖台账。**如实回绝,不排队。**"""
    httpd, _marker = server
    assert json.loads(_post(httpd).read())["started"] is True
    payload = json.loads(_post(httpd).read())
    assert payload["started"] is False, "上一轮还在跑,不该再起一个"
    assert "上一轮" in payload["reason"], "要说清楚为什么没跑,不能只回个 false"


def test_unknown_paths_are_not_served(server):
    """只认一条路径。多开一条就是多一个要防的口子。"""
    httpd, _marker = server
    with pytest.raises(urllib.error.HTTPError) as caught:
        _post(httpd, path="/anything")
    assert caught.value.code == 404


def test_a_page_from_another_site_cannot_press_the_button(server):
    """浏览器会把任意网页的请求也送到 127.0.0.1 —— 来源不在放行表里就拒绝。"""
    httpd, _marker = server
    with pytest.raises(urllib.error.HTTPError) as caught:
        _post(httpd, origin="https://evil.example")
    assert caught.value.code == 403


def test_the_preflight_answers_what_chrome_needs(server):
    """https 页面去连 127.0.0.1,Chrome 会先发预检,还要求私有网络那个头。

    少一个头,按钮在浏览器里就是「点了没反应」,而服务端日志里什么都看不到。
    """
    httpd, _marker = server
    url = f"http://127.0.0.1:{httpd.server_address[1]}/run"
    request = urllib.request.Request(url, method="OPTIONS")
    request.add_header("Origin", "https://inews.today")
    request.add_header("Access-Control-Request-Method", "POST")
    request.add_header("Access-Control-Request-Private-Network", "true")
    response = urllib.request.urlopen(request, timeout=5)
    headers = {k.lower(): v for k, v in response.headers.items()}
    assert headers["access-control-allow-origin"] == "https://inews.today"
    assert "POST" in headers["access-control-allow-methods"]
    assert headers["access-control-allow-private-network"] == "true"
