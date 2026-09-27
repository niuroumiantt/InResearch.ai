#!/bin/bash
set -e
S=/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad/longform
D=2026-09-27
OUT=/home/user/InResearch.ai/outputs/geluoke-research/$D-datacenter-profit
mkdir -p $OUT/work $OUT/checks
python3 $S/postedit_long.py
python3 $S/export_figs.py $OUT $D
python3 $S/make_cover_long.py $OUT $D
cp $S/chapters_final.json $S/work/chapters_final.json
cp $S/work/canon.json $S/work/canon.json 2>/dev/null || true
python3 $S/assemble_long.py $S/work
cp $S/work/article.json $OUT/work/article.json
cp $S/work/figmap.json $OUT/work/figmap.json
cp $S/work/sources.json $OUT/$D-sources.json
cp $S/work/article.md $OUT/$D-article.md
cp $S/work/lead.json $OUT/work/lead.json
cp $S/chapters_final.json $OUT/work/chapters_final.json
python3 $S/build_long.py $OUT/work/article.json $OUT/$D-datacenter-profit-wechat.html
python3 $S/build_long.py $OUT/work/article.json $OUT/$D-datacenter-profit-full.html --full
python3 $S/../tools/validate.py $OUT/$D-datacenter-profit-wechat.html $OUT/checks
