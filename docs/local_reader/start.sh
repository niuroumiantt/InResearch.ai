#!/bin/bash
# 一键启动本地精读会话（datacenter-reader）。
# 用法：bash /Users/yidian/code/datacenter/docs/local_reader/start.sh
# 或在管理后台（ops.html）点"🚀 启动精读"按钮（经 launch_reader.py 在新 Terminal 打开）。
set -e

REPO="$(cd "$(dirname "$0")/../.." && pwd)"

echo "── 更新主仓库 ──"
git -C "$REPO" pull --ff-only || echo "（pull 失败或有本地改动，继续用当前版本）"

READER="$HOME/code/datacenter-reader"
mkdir -p "$READER"
cd "$READER"

echo "── 在 $READER 启动 Claude Code ──"
exec claude "请读取 $REPO/docs/local_reader/KICKOFF_PROMPT.md，按里面的指令开工。若 $REPO/docs/inbox/scored_batches/ 已有批次文件，先接着上次进度继续，不要重复打分已处理的文件。第一次运行时：先跑通 5 份 SemiAnalysis 材料的完整链路给我确认格式，确认后再放量。"
