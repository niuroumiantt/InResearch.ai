#!/bin/bash
# Synchronize committed work only. Never commit, stash or overwrite an active checkout.
set -eu
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"
[ "$(git branch --show-current)" = main ] || exit 0
if [ -n "$(git status --porcelain --untracked-files=all)" ]; then
  echo "工作区有未提交内容，本轮跳过；请在独立任务中审核并提交后同步。" >&2
  exit 1
fi
git fetch origin main
git merge --ff-only origin/main
if [ "${1:-}" = --push ]; then
  python3 pipeline/governance.py --check
  python3 pipeline/validate.py --strict
  python3 pipeline/research.py
  git push origin main
fi
