#!/usr/bin/env python3
"""PNG -> JPEG quality 94, 4:4:4 chroma (subsampling=0). usage: tojpeg.py in.png out.jpg [max_width]"""
import sys
from PIL import Image
im=Image.open(sys.argv[1]).convert('RGB')
if len(sys.argv)>3:
    mw=int(sys.argv[3])
    if im.width>mw: im=im.resize((mw, round(im.height*mw/im.width)), Image.LANCZOS)
q=int(sys.argv[4]) if len(sys.argv)>4 else 94
im.save(sys.argv[2], 'JPEG', quality=q, subsampling=0, optimize=True)
import os; print(sys.argv[2], im.size, os.path.getsize(sys.argv[2]), 'bytes')
