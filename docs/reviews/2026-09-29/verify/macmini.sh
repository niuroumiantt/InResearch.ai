#!/usr/bin/env bash
# 在 Mac mini 上跑（ssh hermes@macmini）。只读。核对 fetchspec 与 inews 原文库采集实际在哪台机器、跑不跑。
set -u
OUT="$HOME/inresearch-verify-macmini-$(date +%F).txt"
{
echo "==== 0 主机"; hostname; date -Is
echo; echo "==== 1 fetchspec：实际执行机与最近运行"
ls -d ~/.local/share/fetchspec 2>/dev/null && du -sh ~/.local/share/fetchspec 2>/dev/null
ls -t ~/.local/share/fetchspec/ledger/runs 2>/dev/null | head -3
launchctl list 2>/dev/null | grep -iE 'fetchspec|inews|inresearch' || echo "(无相关 launchd 任务)"
echo; echo "==== 2 inews 原文库采集（Python 链路）"
ls ~/code/inews.today/out 2>/dev/null | head -25
echo; echo "==== 3 磁盘"
df -h / | tail -1
echo; echo "==== 完成，结果已写到 $OUT"
} 2>&1 | tee "$OUT"
