#!/usr/bin/env bash
# 在 Spark 上跑。先 ssh spark@dgx，然后整段粘贴。只读。结果写到 ~/inresearch-verify-spark-<日期>.txt。
set -u
OUT="$HOME/inresearch-verify-spark-$(date +%F).txt"
{
echo "==== 0 主机"; hostname; date -Is
if [ "$(hostname)" != dgx ]; then echo "不是 Spark（期望 dgx），停止"; exit 1; fi
echo; echo "==== 1 源码版本与 release 标签"
git -C ~/code/inresearch.ai log --oneline -1 2>/dev/null; git -C ~/code/inresearch.ai status --porcelain 2>/dev/null | head -5
grep -E '^READER_RELEASE=' ~/.config/inresearch.ai/reader.env 2>/dev/null || echo "(reader.env 无 READER_RELEASE)"
echo; echo "==== 2 定时器与服务"
systemctl --user list-timers --all --no-pager | grep inresearch || echo "(无 inresearch timer)"
systemctl --user is-active inresearch-reader.service inresearch-reader-publish.timer inresearch-news.timer inresearch-material-intake.timer 2>&1
echo; echo "==== 3 发布器与新闻同步最近状态"
cat ~/.local/state/inresearch.ai/publish-status.json 2>/dev/null; echo
cat ~/.local/share/inresearch.ai/acquisition/news-window.json 2>/dev/null; echo
journalctl --user -u inresearch-news.service -n 5 --no-pager 2>/dev/null
journalctl --user -u inresearch-reader-publish.service -n 3 --no-pager 2>/dev/null
echo; echo "==== 4 凭证权限（只看权限）"
stat -c '%U %a %y %n' ~/.local/state/inresearch.ai/reader-sync.token 2>&1
echo; echo "==== 5 磁盘与温度"
df -h ~ | tail -1; du -sh ~/.local/share/inresearch.ai 2>/dev/null
nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used --format=csv 2>/dev/null || echo "(无 nvidia-smi)"
echo; echo "==== 完成，结果已写到 $OUT"
} 2>&1 | tee "$OUT"
