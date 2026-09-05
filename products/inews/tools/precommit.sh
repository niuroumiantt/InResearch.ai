#!/usr/bin/env bash
# 一条命令跑完全部检查。存在的唯一理由:让「只跑一部分」这个选项不存在。
#
# 两条硬性质(从 yidian 项目带过来的做法):
#   1. 不 fail-fast —— 全部跑完再汇总。fail-fast 会训练出「修一条、重跑」的
#      循环,人只看得见最前面那个问题。
#   2. **被跳过的测试不计入全绿。** 一条 importorskip 就能让某个保证从未
#      真正执行过,而摘要照样是绿的。需要「这条暂时通不过」就用
#      xfail(strict=True):它在被修好的那一刻变红,逼人来摘标记。
set -uo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

PY=${PY:-}
if [ -z "$PY" ]; then
  if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY=python3; fi
fi

FAILED=(); PASSED=()
step() {
  local name=$1; shift
  printf '\n\033[1m── %s\033[0m\n' "$name"
  if "$@"; then PASSED+=("$name"); else FAILED+=("$name"); fi
}

step "独立性守卫" "$PY" tools/guard_standalone.py

run_tests() {
  local out; out=$(mktemp)
  "$PY" -m pytest -q -rs 2>&1 | tee "$out"
  local code=${PIPESTATUS[0]}
  if grep -qE '[0-9]+ skipped' "$out"; then
    printf '\n\033[31m被跳过的测试不计入全绿(见上方 SKIPPED 行)\033[0m\n' >&2
    code=1
  fi
  rm -f "$out"; return "$code"
}
step "测试(skip 视为失败)" run_tests

printf '\n\033[1m════════ 汇总 ════════\033[0m\n'
for n in "${PASSED[@]}"; do printf '  \033[32m通过\033[0m  %s\n' "$n"; done
if [ ${#FAILED[@]} -gt 0 ]; then
  for n in "${FAILED[@]}"; do printf '  \033[31m失败\033[0m  %s\n' "$n"; done
  printf '\n%d 项失败。\n' "${#FAILED[@]}"; exit 1
fi
printf '\n全部 %d 项通过。\n' "${#PASSED[@]}"
