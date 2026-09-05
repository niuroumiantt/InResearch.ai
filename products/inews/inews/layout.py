"""产出目录的形状:哪些是给人看的页面,哪些是抓取的内部状态。

    out/FT.COM/
      index.html  stats.html  dashboard.html  site.css   ← 页面
      p/2026-08/<uuid>.html                              ← 每篇一页,按年月分层
      data/articles/<uuid>.json                          ← 正文正本
      data/ledger.json  data/runs.json                   ← 台账与跑批记录

**文件名保持 uuid**:那是站方发的唯一身份,标题会被编辑改、会带上「Updated」。
文件夹按年月分,只是为了几千篇之后 Finder 里还翻得动 —— 分层是给人看的,
身份仍然只由 uuid 决定。

读不到时间的归到 ``undated/``:不拿抓取时间凑一个月份出来,那种假时间会一路
流进目录名,而且从此看不出来。
"""
from __future__ import annotations

import os
from pathlib import Path

from inews.textutil import parse_datetime

PAGES_DIR = "p"
DATA_DIR = "data"
UNDATED = "undated"
# 正文页在 ``p/<年月>/`` 里,离站点根两层 —— 样式表和回链都按这个前缀写。
PAGE_PREFIX = "../../"


def page_folder(published_at: str) -> str:
    parsed = parse_datetime(published_at)
    return parsed.strftime("%Y-%m") if parsed else UNDATED


def page_relpath(article_id: str, published_at: str) -> str:
    return f"{PAGES_DIR}/{page_folder(published_at)}/{article_id}.html"


def data_dir(out_dir: Path) -> Path:
    return out_dir / DATA_DIR


def adopt(out_dir: Path, name: str) -> Path:
    """返回 ``data/<name>`` 的路径;老布局把它放在根上的话,先搬过来。

    **不能就地留下孤儿。** 台账留在旧位置而程序读新位置,等于把爬过的几百篇
    一次忘光,下一轮全部重爬 —— 一个静默的、要花几小时才看得出来的故障。
    搬用 ``os.replace``(同一个文件系统内原子),搬不动就退回旧位置继续用。
    """
    current = data_dir(out_dir) / name
    legacy = out_dir / name
    if current.exists() or not legacy.exists():
        return current
    try:
        current.parent.mkdir(parents=True, exist_ok=True)
        os.replace(legacy, current)
    except OSError:
        return legacy
    return current
