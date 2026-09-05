"""持久 JSON 的一套读写纪律。

台账和跑批记录不能把「JSON 损坏」解释成「从未运行」：下一次保存会用一份空状态
覆盖事故现场。关键状态保留上一版 ``.bak``，主文件损坏或原子切换中断时自动回读；
两份都不可读才明确失败。正文存档同样复用原子写，但不为每篇复制备份。
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator


class CorruptStateError(RuntimeError):
    """关键状态存在，但主文件和备份都无法读取。"""


def _decode(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_json(path: Path, default: Any, *, recover: bool = True) -> Any:
    """读取 JSON；关键状态优先主文件，失败后回退到上一版。"""
    backup = path.with_suffix(path.suffix + ".bak")
    errors: list[str] = []
    for candidate in (path, backup) if recover else (path,):
        try:
            return _decode(candidate)
        except FileNotFoundError:
            continue
        except (OSError, ValueError) as error:
            errors.append(f"{candidate.name}: {error}")
    if errors and recover:
        raise CorruptStateError(f"状态文件损坏，拒绝按空状态继续:{'; '.join(errors)}")
    return default


def write_json_atomic(path: Path, payload: Any, *, backup: bool = True) -> None:
    """同目录写临时文件后切换；关键状态在切换前保留上一版。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    if backup and path.exists():
        os.replace(path, path.with_suffix(path.suffix + ".bak"))
    os.replace(temp, path)


def write_text_atomic(path: Path, text: str, *, mode: int = 0o644) -> None:
    """并发生成共享 HTML 时只暴露完整旧版或完整新版，不暴露半截文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        # mkstemp 故意创建 0600；静态 HTML/CSS 由 rsync -a 发布，必须在原子切换
        # 前恢复成可由 Web 进程读取的权限，否则服务器会把安全默认值原样带过去。
        os.chmod(name, mode)
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def interprocess_lock(path: Path) -> Iterator[None]:
    """用 Python 自带的 ``flock`` 串行一小段共享文件生成。

    shell 层刻意不用系统 ``flock`` 命令（macOS 没有 util-linux）；Python 的
    ``fcntl.flock`` 是 Darwin/POSIX 自带接口，适合保护短暂的 Dashboard 快照。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
