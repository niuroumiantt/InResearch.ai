#!/usr/bin/env python3
"""Paste the original official-account QR bitmap into the cover's reserved bottom-right area.
usage: composite_qr.py cover.png qrcode.jpg out.png [--box x,y,w,h]  (box in cover pixels; default matches the 1200x1800 layout at DPR 2)
The QR is only resized with nearest-neighbour-free LANCZOS on white, never redrawn; a white quiet zone is kept."""
import sys
from PIL import Image
cover=Image.open(sys.argv[1]).convert('RGB'); qr=Image.open(sys.argv[2]).convert('RGB')
box=None
for i,a in enumerate(sys.argv):
    if a=='--box': box=[int(v) for v in sys.argv[i+1].split(',')]
if box is None:
    # default reserved area: 190x190 CSS px at right/bottom of the footer, DPR 2 -> 380x380 px; position read from layout: measured .qr rect at 1200x1800 CSS: x=974,y=1590,w=170,h=170
    box=[1948,3180,340,340]
x,y,w,h=box
pad=int(w*0.06)
tile=Image.new('RGB',(w,h),'white')
inner=qr.resize((w-2*pad,h-2*pad),Image.LANCZOS)
tile.paste(inner,(pad,pad))
cover.paste(tile,(x,y))
cover.save(sys.argv[3]); print('wrote',sys.argv[3],cover.size)
