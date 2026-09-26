#!/usr/bin/env python3
"""Acceptance checks for the WeChat HTML. usage: validate.py page.html outdir"""
import asyncio, os, sys, json, re, base64
from playwright.async_api import async_playwright
CHROME='/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
html_path=os.path.abspath(sys.argv[1]); outdir=os.path.abspath(sys.argv[2]); os.makedirs(outdir,exist_ok=True)
raw=open(html_path,'rb').read()
res={'html_file':os.path.basename(html_path),'html_bytes':len(raw)}
srcs=re.findall(rb'<img src="data:(image/[a-z]+);base64,([A-Za-z0-9+/=]+)"', raw)
res['img_count']=len(srcs)
res['images']=[{'index':i,'mime':m.decode(),'base64_len':len(b)} for i,(m,b) in enumerate(srcs)]
res['cover_embed_mime']=srcs[0][0].decode() if srcs else None
res['cover_base64_len']=len(srcs[0][1]) if srcs else None
async def main():
    async with async_playwright() as p:
        b=await p.chromium.launch(executable_path=CHROME,args=['--no-sandbox'])
        for name,w in (('desktop',1000),('mobile390',390)):
            ctx=await b.new_context(viewport={'width':w,'height':900},device_scale_factor=2,permissions=['clipboard-read','clipboard-write'])
            pg=await ctx.new_page(); await pg.goto('file://'+html_path); await pg.wait_for_timeout(800)
            loaded=await pg.evaluate("Array.from(document.images).map(i=>({ok:i.complete&&i.naturalWidth>0,w:i.naturalWidth,h:i.naturalHeight}))")
            sw=await pg.evaluate("document.documentElement.scrollWidth"); cw=await pg.evaluate("document.documentElement.clientWidth")
            res[name]={'viewport':w,'images_loaded':all(x['ok'] for x in loaded),'images':loaded,'scrollWidth':sw,'clientWidth':cw,'horizontal_overflow':sw>cw}
            await pg.screenshot(path=os.path.join(outdir,'render-%s.png'%name),full_page=True)
            if name=='desktop':
                # copy round trip: select the article, Ctrl+C, paste into a blank contenteditable
                await pg.evaluate("""()=>{const d=document.createElement('div');d.id='__paste';d.contentEditable='true';d.style.minHeight='40px';document.body.appendChild(d);const r=document.createRange();r.selectNodeContents(document.body.firstElementChild);const s=getSelection();s.removeAllRanges();s.addRange(r);}""")
                await pg.keyboard.press('Control+C'); await pg.wait_for_timeout(400)
                await pg.click('#__paste'); await pg.keyboard.press('Control+V'); await pg.wait_for_timeout(1200)
                n=await pg.evaluate("document.querySelectorAll('#__paste img').length")
                ok=await pg.evaluate("Array.from(document.querySelectorAll('#__paste img')).every(i=>i.src.startsWith('data:'))")
                res['copy_roundtrip']={'images_before':len(srcs),'images_after_paste':n,'all_data_uri':ok,'pass':n==len(srcs) and ok}
            await ctx.close()
        await b.close()
asyncio.run(main())
res['wechat_paste']='公众号待验证'
res['limits']={'html_under_3_8MB':res['html_bytes']<3.8*1024*1024,'html_under_2_0MB':res['html_bytes']<2.0*1024*1024}
json.dump(res,open(os.path.join(outdir,'validation.json'),'w'),ensure_ascii=False,indent=1)
print(json.dumps({k:v for k,v in res.items() if k not in('images',)},ensure_ascii=False,indent=1))
