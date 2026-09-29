"""Local Apple Vision OCR used on macOS when no configured vision model exists."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading

from inresearch.materials.reader_contracts import Blocked


_BUILD_LOCK = threading.Lock()
_SOURCE = Path(__file__).with_suffix(".swift")


def available() -> bool:
    return sys.platform == "darwin" and shutil.which("swiftc") is not None


def _binary(state_root: Path) -> Path:
    if not available():
        raise Blocked("macos_vision_ocr_unavailable")
    folder = state_root.expanduser().resolve() / "vision-ocr"
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(folder, 0o700)
    binary = folder / "vision-ocr"
    if binary.is_symlink():
        raise Blocked("macos_vision_ocr_binary_unsafe")
    stale = (not binary.is_file() or binary.stat().st_mtime_ns < _SOURCE.stat().st_mtime_ns)
    if stale:
        with _BUILD_LOCK:
            stale = (not binary.is_file() or binary.stat().st_mtime_ns < _SOURCE.stat().st_mtime_ns)
            if stale:
                fd, temporary = tempfile.mkstemp(prefix=".vision-ocr-", dir=folder)
                os.close(fd)
                try:
                    result = subprocess.run(
                        ["swiftc", "-O", "-framework", "Vision", "-framework", "AppKit",
                         str(_SOURCE), "-o", temporary],
                        capture_output=True, text=True, timeout=180, check=False)
                    if result.returncode:
                        raise Blocked("macos_vision_ocr_build_failed")
                    os.chmod(temporary, 0o700)
                    os.replace(temporary, binary)
                except (OSError, subprocess.TimeoutExpired):
                    raise Blocked("macos_vision_ocr_build_failed") from None
                finally:
                    if os.path.exists(temporary):
                        os.unlink(temporary)
    return binary


def recognize(image_path: Path, state_root: Path, pass_index: int) -> dict:
    """Run two deliberately distinct Vision passes; caller checks numeric agreement."""
    if pass_index not in (0, 1):
        raise ValueError("pass_index must be 0 or 1")
    binary = _binary(Path(state_root))
    try:
        result = subprocess.run([str(binary), str(Path(image_path).resolve()), str(pass_index)],
                                 capture_output=True, text=True, timeout=120, check=False)
        value = json.loads(result.stdout) if result.stdout else {}
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
        raise Blocked("macos_vision_ocr_failed") from None
    if result.returncode or not isinstance(value, dict) or "error" in value:
        raise Blocked("macos_vision_ocr_failed")
    text = value.get("text")
    blank, unreadable = value.get("blank"), value.get("unreadable")
    if (not isinstance(text, str) or not isinstance(blank, bool) or not isinstance(unreadable, bool)
            or not isinstance(value.get("model"), str)):
        raise Blocked("macos_vision_ocr_output_invalid")
    return {"text": text, "blank": blank, "unreadable": unreadable,
            "_model": {"actual": value["model"], "provider": "macOS Vision"}}
