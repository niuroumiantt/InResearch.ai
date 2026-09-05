#!/bin/bash
# 本地 ⇄ GitHub 自动同步（com.inresearch.sync 每 30 分钟跑一次；手动跑也安全）
#
# 用法：bash docs/local_setup/sync.sh          # 只拉取：保证本地有最新远端内容
#       bash docs/local_setup/sync.sh --push   # 拉取 + 推送：本机改动过校验才入账上站
#
# 链路：本机改动 → validate.py --strict 闸门 → commit → push
#       → 服务器 autopull（≤2 分钟）→ inresearch.ai 更新
# 校验不过：改动原样留在本地、只记日志，绝不硬推——铁律是闸门不是摆设。
# 与远端冲突：中止并留言，自动同步不裁决冲突，由人工处理。
set -u
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
mkdir -p logs
LOG="logs/sync.log"
say() { echo "[$(date '+%F %T')] $*" >> "$LOG"; echo "$*"; }

BRANCH="$(git rev-parse --abbrev-ref HEAD)"
if [ "$BRANCH" != "main" ]; then
  say "⚠️ 当前在 $BRANCH 不是 main，自动同步只动主分支，本次跳过"
  exit 0
fi

# 1) --push 模式：本机有改动先过闸再入账。
#    生成物（brief/队列/工单）与手工改动一视同仁——网站要吃的就是这些文件，
#    launchd 每日重新生成后靠这里推上去，服务器才有当天的简报。
if [ "${1:-}" = "--push" ] && [ -n "$(git status --porcelain)" ]; then
  if python3 pipeline/validate.py --strict >> "$LOG" 2>&1; then
    git add -A
    n="$(git diff --cached --name-only | wc -l | tr -d ' ')"
    if [ "$n" -gt 0 ]; then
      git commit -q -m "本地自动同步：$(date '+%m-%d %H:%M') 本机改动 ${n} 个文件入账"
      say "已提交本机改动 ${n} 个文件"
    fi
  else
    say "⚠️ validate.py --strict 未过，本机改动暂不推送（本机跑 python3 pipeline/validate.py 看原因）"
  fi
fi

# 2) 拉取远端（rebase + autostash：未提交/未过闸的改动自动暂存再放回，不会丢）
if ! git pull --rebase --autostash origin main >> "$LOG" 2>&1; then
  git rebase --abort 2>/dev/null || true
  say "❌ 与远端冲突，自动同步不裁决——请人工在 $REPO 跑 git pull 处理后再等下轮"
  exit 1
fi

# 3) 本地领先则推送（网络失败按 2/4/8/16 秒退避重试）
if [ "${1:-}" = "--push" ]; then
  ahead="$(git rev-list --count origin/main..HEAD 2>/dev/null || echo 0)"
  if [ "$ahead" -gt 0 ]; then
    pushed=0
    for i in 0 2 4 8 16; do
      [ "$i" -gt 0 ] && sleep "$i"
      if git push -u origin main >> "$LOG" 2>&1; then pushed=1; break; fi
      say "push 失败，${i}s 退避后再试"
    done
    if [ "$pushed" = 1 ]; then
      say "已推送 ${ahead} 个提交 → 服务器 2 分钟内自动上线"
    else
      say "❌ push 连续失败，改动已提交在本地，下轮同步会再试"
      exit 1
    fi
  fi
fi
say "同步完成（$(git rev-parse --short HEAD)）"
