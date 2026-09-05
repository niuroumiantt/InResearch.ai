"""正文存档:每篇一份 JSON,**正文文本**和元数据一起留下来。

为什么不能只留渲染好的 HTML:HTML 是产物,不是原料。只有它的时候,
「换个版式」和「做一次分析」都只能倒着从标签里抠文本 —— 或者干脆重爬一遍。
2026-08-21 站长为了看新版式,把二十篇稿子重爬了一次,就是这个缺口的成本。

存档是这个项目里**正文的唯一正本**:清单页、正文页、分析页、dashboard 全部
从它重画;`--render-only` 一个请求都不用发。台账仍然只管「爬过没有」。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from inews import layout
from inews.storage import read_json, write_json_atomic

DIRNAME = "articles"

# 存档里留什么:能重画一页正文、能做分析所需要的一切,别的不留。
# 尤其**不留 HTML** —— 那是产物,存两遍就会有两份互相打架的真相。
FIELDS = (
    "article_id",
    "url",
    "title_en",
    # 部分站点用栏目卡摘要补足标题的 AI/基础设施语境；重画也要复用同一证据。
    "description",
    # 译文和正文同一份正本:重画时不该丢,更不该为了重画再翻一遍。
    "title_zh",
    "published_at",
    "section",
    "keywords",
    "found_via",
    "origins",
    "body",
    "body_error",
    "extractor",
)


def dir_for(out_dir: Path) -> Path:
    """存档在 ``data/articles/``;老布局那份(根上的 ``articles/``)搬过来。"""
    return layout.adopt(out_dir, DIRNAME)


def path_for(out_dir: Path, article_id: str) -> Path:
    return dir_for(out_dir) / f"{article_id}.json"


def save(out_dir: Path, rows: list[dict[str, Any]]) -> int:
    """把本轮抓到的存下来,返回写了几篇。

    **只存有正文的**:抓失败的那些已经在台账里记了状态,再存一份空正文,
    以后重画时会分不清「取失败了」和「取到的是一片空白」。
    """
    directory = dir_for(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written = 0
    for row in rows:
        if not row.get("body"):
            continue
        payload = {key: row.get(key) for key in FIELDS if row.get(key) is not None}
        # 存档只会写有正文的稿子,``body_error`` 因此只可能是从
        # 上一次失败漏下来的旧状态。在持久化边界再守一次这个不变式。
        payload.pop("body_error", None)
        target = path_for(out_dir, row["article_id"])
        # 原子写:半截的存档比没有存档更坏。整库另有备份，不再逐篇复制 .bak。
        write_json_atomic(target, payload, backup=False)
        written += 1
    return written


def stored_ids(out_dir: Path) -> set[str]:
    """存档里有正文的那些 id。**这是「本地有没有这一页」的唯一依据** ——
    页面从存档重画,存档没有的,页面也画不出来。"""
    directory = dir_for(out_dir)
    if not directory.is_dir():
        return set()
    return {path.stem for path in directory.glob("*.json")}


def load(out_dir: Path) -> list[dict[str, Any]]:
    """读回全部存档(不排序 —— 排序是调用方的档次)。

    坏掉的单个文件跳过并**继续**:一份读不出来的存档不该让整站没法重画。
    """
    directory = dir_for(out_dir)
    if not directory.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.json")):
        payload = read_json(path, {}, recover=False)
        if isinstance(payload, dict) and payload.get("article_id"):
            # 兼容旧版重试写出的「有正文 + 旧 body_error」存档。
            # 读时归一化,一次 --render-only 会再把干净版写回盘上。
            if payload.get("body"):
                payload.pop("body_error", None)
            rows.append(payload)
    return rows


def total_chars(out_dir: Path) -> int:
    """存档里正文一共多少字。

    从**正本**数,不从台账数:台账不存正文(那会让它变成第二数据库),而清单页
    顶上那个「正文字数」要的是真的字数,不是「取到过几篇」乘一个平均值。
    """
    return sum(len(str(row.get("body") or "")) for row in load(out_dir))
