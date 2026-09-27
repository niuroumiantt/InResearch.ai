#!/usr/bin/env python3
"""lead.json -> cover.json -> cover.html -> PNG master (2400x3600) + WeChat JPEG (1280 wide). usage: make_cover_long.py OUTDIR DATE"""
import json, os, sys, subprocess, html
S=os.path.dirname(os.path.abspath(__file__)); OUT=sys.argv[1]; D=sys.argv[2]
L=json.load(open(os.path.join(S,'work','lead.json'))); C=L['cover']
e=lambda s: html.escape(s, quote=False)
# ledger numbers for the cross-section
led={k:C['ledger'][k] for k in ('capex','it_capex','non_it_capex','revenue','opex','tax','nopat','roic')}
import re
num=lambda s: (re.search(r'\d+(?:\.\d+)?%?',str(s)).group(0) if re.search(r'\d',str(s)) else str(s))
led_num={k:num(v) for k,v in led.items()}
json.dump(led_num,open(os.path.join(S,'cover','ledger.json'),'w'),ensure_ascii=False)
subprocess.run(['python3',os.path.join(S,'cover','ledger_xsec.py'),os.path.join(S,'cover','ledger.json'),os.path.join(S,'cover','ledger_xsec.svg')],check=True)
title=L.get('title_short') or L['title']
# emphasise the last clause in gold if a separator exists
th=e(title)
for sep in ('：','，','——'):
    if sep in title:
        a,b=title.split(sep,1); th=e(a)+e(sep)+'<em>'+e(b)+'</em>'; break
paths=[dict(p) for p in C['paths']]
for p_ in paths:
    if 'NOPAT' in p_['roic'] or '利润率' in p_['roic']: p_['roic']=re.search(r'\d+%',p_['roic']).group(0)+'*'; p_['name']=p_['name'].replace('跑模型API','跑API')
spec={'date':L.get('date_display','2026年9月27日'),'edition':'造价 · 回报 · 融资 · 电力 · 中国参照','title_html':th,'subtitle':C['subtitle'],'claim':C['claim'],
 'band_tag':'1GW 账本剖面（摩根士丹利2026年9月估算，示意）','xsec':'ledger_xsec.svg','paths':paths,'pnote':'*第三条为NOPAT利润率（NOPAT÷收入），前两条为ROIC（NOPAT÷总资本开支）','layers':C['layers'],'modules':C['modules'],
 'conclusion':C['conclusion'],'signature':L.get('signature','格洛可数据中心研究')+' · '+L.get('date_display','2026年9月27日'),'qr':''}
json.dump(spec,open(os.path.join(S,'cover','cover.json'),'w'),ensure_ascii=False,indent=1)
subprocess.run(['python3',os.path.join(S,'cover','fill_cover_long.py'),os.path.join(S,'cover','cover.json'),os.path.join(S,'cover','cover_long.html'),os.path.join(S,'cover','cover.html')],check=True)
master=os.path.join(OUT,f'{D}-cover.png')
subprocess.run(['python3',os.path.join(S,'..','tools','render.py'),os.path.join(S,'cover','cover.html'),master,'--width','1200','--height','1800','--dpr','2'],check=True)
subprocess.run(['python3',os.path.join(S,'..','tools','tojpeg.py'),master,os.path.join(OUT,f'{D}-cover-wechat.jpg'),'1080','88'],check=True)
os.makedirs(os.path.join(OUT,'work','cover'),exist_ok=True)
for f in ('cover.html','cover.json','cover_long.html','ledger_xsec.svg','ledger_xsec.py','fill_cover_long.py','ledger.json'):
    subprocess.run(['cp',os.path.join(S,'cover',f),os.path.join(OUT,'work','cover',f)])
print('cover done', os.path.getsize(master), os.path.getsize(os.path.join(OUT,f'{D}-cover-wechat.jpg')))
