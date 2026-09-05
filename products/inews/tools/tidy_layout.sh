#!/usr/bin/env bash
# 把老布局(一堆 <uuid>.html 平铺在根上、台账和存档也在根上)整理成现在的形状:
#
#   p/<年月>/<uuid>.html   页面      data/articles/  data/ledger.json  data/runs.json
#
# 跑一次就够。顺序是**先重画、再删**:新页面从存档里画出来之后,根上那些老页面
# 才是真正的孤儿。反过来先删,中间任何一步出错都会留下一个空站点。
#
# 台账/存档/跑批记录的搬迁由程序自己做(inews/layout.py 的 adopt),
# 这里只负责收拾**产物**。
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT"

OUT=${RAW_OUT:-$ROOT/out/FT.COM}
PY=${PY:-$ROOT/.venv/bin/inews}

[ -d "$OUT" ] || { echo "没有这个目录:$OUT" >&2; exit 1; }

echo "== 先从存档重画一遍(不出网)"
"$PY" --render-only --out "$OUT"

echo "== 再清掉根目录下的老页面"
# 只删长得像 <uuid>.html 的那些 —— index/stats/dashboard 和 site.css 不在此列。
# 写死这个形状而不是「删掉所有 .html」:哪天根上多了一个手写的页面,
# 一个宽口径的删除会把它一起带走。
#
# **存档里没有对应正本的,一律不删。** 2026-08-22 这一步删掉了 23 篇的页面:
# 那批是存档机制上线之前爬的,正文只存在于那些 HTML 里,重画画不出来 ——
# 「产物随时能重画」这句话只在有正本的时候成立。留下来,让 --refill 去补。
count=0
kept=0
while IFS= read -r page; do
  id=$(basename "$page" .html)
  if [ ! -f "$OUT/data/articles/$id.json" ]; then
    echo "   留 $id.html(存档里没有这篇的正文,删了就没了)"
    kept=$((kept + 1))
    continue
  fi
  echo "   删 $id.html"
  rm -f "$page"
  count=$((count + 1))
done < <(find "$OUT" -maxdepth 1 -type f \
  -name '????????-????-????-????-????????????.html' -print)

echo "== 完成:清掉 $count 个老页面"
if [ "$kept" -gt 0 ]; then
  echo "   留下 $kept 个没有正本的页面 —— 跑一次补正本:"
  echo "     cd $ROOT && .venv/bin/inews --refill --limit 0"
fi
echo "   页面在 $OUT/p/,抓取状态在 $OUT/data/"
echo "   服务器上那份等下次 publish 时由 rsync --delete 跟着收拾"
