#!/usr/bin/env python3
"""Export figures/cover to the delivery directory with published names. usage: export_figs.py OUTDIR DATE"""
import sys, os, shutil, subprocess
from PIL import Image
S=os.path.dirname(os.path.abspath(__file__)); OUT=sys.argv[1]; D=sys.argv[2]
os.makedirs(OUT,exist_ok=True); os.makedirs(os.path.join(OUT,'work','figs'),exist_ok=True)
names={'fig1':'fig1-1gw-capex-by-chip','fig2':'fig2-three-paths-roic','fig3':'fig3-shell-lease-contracts','fig4':'fig4-capital-stack','fig5':'fig5-roic-sensitivity','fig6':'fig6-china-vs-us'}
for k,n in names.items():
    src=os.path.join(S,'figs',k+'.png'); im=Image.open(src).convert('RGB')
    q=im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    dst=os.path.join(OUT,f'{D}-{n}.png'); q.save(dst,optimize=True)
    shutil.copy(os.path.join(S,'figs',k+'.svg'),os.path.join(OUT,'work','figs',k+'.svg'))
    print(n, im.size, os.path.getsize(dst))
