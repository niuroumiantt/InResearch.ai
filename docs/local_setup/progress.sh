#!/bin/sh
# 在 Mac 上看 Spark 阅读进度：每 60 秒从 Spark 取一次进度页，首次自动用浏览器打开。
# 用法：sh ~/code/inresearch.ai/docs/local_setup/progress.sh   （Ctrl-C 结束）
OUT="${1:-$HOME/inresearch-progress.html}"
REMOTE="${INRESEARCH_SPARK:-spark}"
opened=""
while :; do
  if ssh -o BatchMode=yes -o ConnectTimeout=15 "$REMOTE" \
      'cd ~/code/inresearch.ai && set -a && . ~/.config/inresearch.ai/reader.env && set +a && python3 manage.py reader-progress' \
      > "$OUT.partial" 2>/dev/null && [ -s "$OUT.partial" ]; then
    mv "$OUT.partial" "$OUT"
    [ -z "$opened" ] && open "$OUT" && opened=1
    echo "$(date '+%H:%M:%S') 已更新 $OUT"
  else
    rm -f "$OUT.partial"
    echo "$(date '+%H:%M:%S') 连不上 Spark 或生成失败，60 秒后重试"
  fi
  sleep 60
done
