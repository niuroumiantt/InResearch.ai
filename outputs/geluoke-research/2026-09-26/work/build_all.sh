#!/bin/bash
# End-to-end build: cover -> figures -> HTML -> validation. usage: build_all.sh <outdir>
set -e
S=/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad
OUT=$1; mkdir -p "$OUT/work" "$OUT/checks"
D=2026-09-26
python3 $S/tools/assemble.py "$OUT/work"
python3 $S/tools/postedit.py "$OUT"
# cover
python3 $S/cover/fill_cover.py "$OUT/work/cover.json" $S/cover/cover_template.html "$OUT/work/cover.html"
python3 $S/tools/render.py "$OUT/work/cover.html" "$OUT/$D-article-summary.png" --width 1200 --height 1800 --dpr 2
python3 $S/tools/tojpeg.py "$OUT/$D-article-summary.png" "$OUT/$D-article-summary-wechat.jpg" 1280
# figures: quantized PNG copies for embedding (256 colours, no dither), originals kept in work/
python3 - "$OUT" <<'PY'
import sys, os, shutil
from PIL import Image
S='/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/figs'
out=sys.argv[1]
names={'fig_jupiter.png':'2026-09-26-fig1-jupiter-power-chain.png','fig_us_power.png':'2026-09-26-fig2-us-power-cost.png','fig_funding.png':'2026-09-26-fig3-funding-stages.png','fig_asia.png':'2026-09-26-fig4-asia-conditions.png'}
for src,dst in names.items():
    im=Image.open(os.path.join(S,src)).convert('RGB')
    q=im.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.NONE)
    q.save(os.path.join(out,dst), optimize=True)
    shutil.copy(os.path.join(S,src), os.path.join(out,'work',src))
    shutil.copy(os.path.join(S,src.replace('.png','.svg')), os.path.join(out,'work',src.replace('.png','.svg')))
    print(dst, os.path.getsize(os.path.join(out,dst)))
PY
# patch content.json figure filenames to the published names
python3 - "$OUT" <<'PY'
import json, sys, os
out=sys.argv[1]; c=json.load(open(os.path.join(out,'work','content.json')))
names={'fig_jupiter.png':'2026-09-26-fig1-jupiter-power-chain.png','fig_us_power.png':'2026-09-26-fig2-us-power-cost.png','fig_funding.png':'2026-09-26-fig3-funding-stages.png','fig_asia.png':'2026-09-26-fig4-asia-conditions.png'}
for e in c['events']:
    if e.get('figure'): e['figure']['file']='../'+names[e['figure']['file']]
c['cover']['file']='../2026-09-26-article-summary-wechat.jpg'
json.dump(c,open(os.path.join(out,'work','content.json'),'w'),ensure_ascii=False,indent=1)
PY
python3 $S/tools/build_html.py "$OUT/work/content.json" "$OUT/$D-daily-wechat.html"
python3 $S/tools/validate.py "$OUT/$D-daily-wechat.html" "$OUT/checks"
cp "$OUT/checks/validation.json" "$OUT/validation.json"
echo BUILD DONE
