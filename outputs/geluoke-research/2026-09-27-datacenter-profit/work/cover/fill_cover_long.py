import json, sys, html
spec=json.load(open(sys.argv[1])); tpl=open(sys.argv[2],encoding='utf-8').read()
e=lambda s: html.escape(s, quote=False)
paths=''.join('<div class="path"><div class="n">%s</div><div class="v">%s</div></div>'%(e(p['name']),e(p['roic'])) for p in spec['paths'])
layers=''.join('<div class="layer"><div class="h">%s</div><div class="t">%s</div></div>'%(e(l['name']),e(l['unit'])) for l in spec['layers'])
mods=''.join('<div class="mod"><div class="n">%d</div><div class="k">%s</div><div class="v">%s</div></div>'%(i+1,e(m['name']),m['fact_html']) for i,m in enumerate(spec['modules']))
qr='<img src="%s">'%spec['qr'] if spec.get('qr') else ''
out=tpl
for k,v in {'DATE':e(spec['date']),'EDITION':e(spec['edition']),'TITLE':spec['title_html'],'SUBTITLE':e(spec['subtitle']),'CLAIM':e(spec['claim']),'BAND_TAG':e(spec['band_tag']),'XSEC':spec['xsec'],'PATHS':paths,'PNOTE':e(spec.get('pnote','')),'LAYERS':layers,'MODULES':mods,'CONCLUSION':e(spec['conclusion']),'SIGNATURE':e(spec['signature']),'QR':qr}.items():
    out=out.replace('{{%s}}'%k,v)
open(sys.argv[3],'w',encoding='utf-8').write(out); print('wrote',sys.argv[3])
