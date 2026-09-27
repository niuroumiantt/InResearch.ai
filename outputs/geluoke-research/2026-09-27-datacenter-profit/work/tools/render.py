#!/usr/bin/env python3
"""Render an HTML or SVG file to PNG with headless Chromium.
usage: render.py <input.html|svg> <out.png> [--width W] [--height H] [--dpr D] [--full]
"""
import asyncio, sys, os, argparse
from playwright.async_api import async_playwright
CHROME='/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
async def main(a):
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CHROME if os.path.exists(CHROME) else None, args=['--no-sandbox','--font-render-hinting=none'])
        pg=await b.new_page(viewport={'width':a.width,'height':a.height},device_scale_factor=a.dpr)
        url='file://'+os.path.abspath(a.input)
        await pg.goto(url)
        await pg.wait_for_timeout(400)
        await pg.evaluate("document.fonts && document.fonts.ready")
        await pg.wait_for_timeout(200)
        await pg.screenshot(path=a.out, full_page=a.full)
        await b.close()
ap=argparse.ArgumentParser(); ap.add_argument('input'); ap.add_argument('out')
ap.add_argument('--width',type=int,default=1200); ap.add_argument('--height',type=int,default=1800)
ap.add_argument('--dpr',type=float,default=2); ap.add_argument('--full',action='store_true')
a=ap.parse_args(); asyncio.run(main(a)); print('wrote',a.out)
