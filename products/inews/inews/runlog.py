"""跑批记录:每轮留一条,让「链路什么时候断的」有地方可查。

每小时一轮跑在后台,没人盯着终端。**「新增 0」是常态,「连着三轮失败」不是** ——
这两件事从产出页面上长得一模一样(都是页面没变),只有把每轮的结果记下来
才分得开。dashboard 上那块健康指示就读这份文件。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from inews import layout
from inews.storage import read_json, write_json_atomic

FILENAME = "runs.json"
KEEP = 200  # 每小时一轮 ≈ 八天;再往前的诊断价值迅速归零


def path_for(out_dir: Path) -> Path:
    return layout.adopt(out_dir, FILENAME)


def load(path: Path) -> list[dict[str, Any]]:
    payload = read_json(path, {})
    entries = payload.get("runs") if isinstance(payload, dict) else None
    return entries if isinstance(entries, list) else []


def record(path: Path, entry: dict[str, Any]) -> list[dict[str, Any]]:
    entries = [*load(path), entry][-KEEP:]
    write_json_atomic(path, {"runs": entries})
    return entries


def consecutive_failures(entries: list[dict[str, Any]]) -> int:
    """从最近一轮往回数,连着几轮不 ok。"""
    count = 0
    for entry in reversed(entries):
        if entry.get("ok"):
            break
        count += 1
    return count


def last_error(entries: list[dict[str, Any]]) -> str:
    """最近一次失败的原话;没有失败就返回空串。**不造措辞**。"""
    for entry in reversed(entries):
        if not entry.get("ok"):
            return str(entry.get("error") or "")
    return ""
