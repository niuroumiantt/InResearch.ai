#!/usr/bin/env python3
"""在新 Terminal 窗口启动本地精读会话（macOS）。

ops.html 管理后台"🚀 启动精读"按钮 → serve.py → 本脚本 → osascript 打开
Terminal.app 运行 docs/local_reader/start.sh（git pull → 建工作目录 → 启动
claude 并自动喂入 KICKOFF_PROMPT）。零依赖。

云端/非 macOS 环境下只打印手动命令，不报错。
"""
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SH = ROOT / "docs" / "local_reader" / "start.sh"


def main():
    if platform.system() != "Darwin":
        print(f"当前不是 macOS，无法自动开 Terminal。请在本机手动运行：\n  bash {SH}")
        return 0
    script = f'''
tell application "Terminal"
  activate
  do script "bash {SH}"
end tell'''
    subprocess.run(["osascript", "-e", script], check=True)
    print("已在新 Terminal 窗口启动精读会话（claude 会自动读取 KICKOFF_PROMPT 开工）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
