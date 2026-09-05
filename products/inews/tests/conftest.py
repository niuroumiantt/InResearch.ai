"""用例的公共前置。"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    """用例里不限速。

    限速是给**真实站点**的礼貌,不是被测的行为。留着它的话,几个走 cli 的用例
    每轮要空等一分多钟 —— 而那一分多钟什么也没验证。真实取数的限速由
    `run.PACE_SECONDS` 决定,这里只是把它在用例进程里关掉。
    """
    monkeypatch.setenv("INEWS_PACE_SECONDS", "0")
