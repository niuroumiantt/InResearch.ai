#!/usr/bin/env bash
# 把**正本**打个包留一份:正文存档 + 台账。
#
# 正文只存在于一台机器上的一个目录里,而发布用的 rsync 带 --delete ——
# 2026-08-21 一条 `rm -rf out/FT.COM` 就把二十篇稿子从本机和服务器同时抹掉了。
# 渲染出来的 HTML 不备份:它随时能从存档重画(`--render-only`)。
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

OUT=${RAW_OUT:-$ROOT/out/FT.COM}
DIR=${INEWS_BACKUP_DIR:-$ROOT/out/backups}
KEEP=${INEWS_BACKUP_KEEP:-14}

[ -d "$OUT/data/articles" ] || { echo "还没有正文存档,不用备份:$OUT/data/articles" >&2; exit 0; }

mkdir -p "$DIR"
STAMP=$(date +%Y%m%d-%H%M%S)
LIBRARY=$(basename "$OUT" | tr '[:upper:]' '[:lower:]')
tar -czf "$DIR/inews-$LIBRARY-$STAMP.tar.gz" -C "$OUT" data/articles data/ledger.json 2>/dev/null \
  || tar -czf "$DIR/inews-$LIBRARY-$STAMP.tar.gz" -C "$OUT" data/articles

# 只留最近 KEEP 份。备份把磁盘塞满,下一轮抓取就写不进去了 ——
# 那会让备份这件事本身变成故障源。
ls -1t "$DIR"/inews-"$LIBRARY"-*.tar.gz 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f

echo "已备份 → $DIR/inews-$LIBRARY-$STAMP.tar.gz"
