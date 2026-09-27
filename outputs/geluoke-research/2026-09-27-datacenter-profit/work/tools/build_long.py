#!/usr/bin/env python3
"""Assemble the long-form WeChat HTML (and full HTML) from article.json. usage: build_long.py article.json out.html [--qr path]"""
import json, sys, base64, os, html as H, re
spec=json.load(open(sys.argv[1])); base=os.path.dirname(os.path.abspath(sys.argv[1]))
def data_uri(path):
    p=path if os.path.isabs(path) else os.path.join(base,path)
    ext=os.path.splitext(p)[1].lower(); mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'}[ext]
    return 'data:%s;base64,%s'%(mime,base64.b64encode(open(p,'rb').read()).decode())
SANS='Arial, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", "WenQuanYi Zen Hei", sans-serif'
FANG='FangSong, STFangsong, "FangSong_GB2312", "仿宋", "Songti SC", "AR PL UMing CN", serif'
INK='#1F2A37'; MUTED='#5A6B7F'; H1C='#0068B5'; H2C='#08577C'; ACC='#1E66B3'
def esc(t): return H.escape(t, quote=False)
def rich(t):
    t=esc(t)
    t=re.sub(r'\*\*(.+?)\*\*', r'<strong style="color:%s;">\1</strong>'%H2C, t)
    return re.sub(r'\[(\d+(?:[,，、–-]\s*\d+)*)\]', r'<span style="color:%s;font-size:0.85em;">[\1]</span>'%ACC, t)
def p(t, size=17, color=INK, extra=''):
    return '<p style="margin:0 0 16px;font-size:%dpx;line-height:1.8;color:%s;font-family:%s;text-align:justify;letter-spacing:0.2px;%s">%s</p>'%(size,color,SANS,extra,rich(t))
def img(path, alt, w='100%'):
    return '<img src="%s" alt="%s" style="display:block;width:%s;max-width:100%%;height:auto;margin:0 auto;">'%(data_uri(path),esc(alt),w)
def caption(t):
    return '<p style="margin:6px 0 20px;font-size:12px;line-height:1.6;color:%s;font-family:%s;text-align:justify;">%s</p>'%(MUTED,SANS,esc(t))
out=['<section style="background:#EEF3F8;padding:14px 0 18px;margin:0;">','<section style="background:#FFFFFF;margin:0;padding:0;">']
out.append(img(spec['cover']['file'], spec['title']))
out.append('<p style="margin:14px 0 6px;font-size:14px;line-height:1.6;color:%s;font-family:%s;letter-spacing:1px;">格洛可数据中心专题</p>'%(ACC,SANS))
out.append('<h1 style="margin:0 0 8px;font-size:26px;line-height:1.45;font-weight:700;color:%s;font-family:%s;">%s</h1>'%(H1C,SANS,esc(spec['title'])))
out.append('<p style="margin:0 0 18px;font-size:14px;line-height:1.6;color:%s;font-family:%s;">%s</p>'%(MUTED,SANS,esc(spec['date_display'])))
for t in spec['lead']: out.append(p(t))
out.append('<p style="margin:0 0 22px;font-size:14px;line-height:1.7;color:%s;font-family:%s;">%s</p>'%(MUTED,SANS,esc(spec['coverage'])))
for ch in spec['chapters']:
    out.append('<h2 style="margin:30px 0 12px;font-size:22px;line-height:1.4;font-weight:700;color:%s;font-family:%s;">%s　%s</h2>'%(H2C,SANS,esc(ch['no']),esc(ch['title'])))
    for i,t in enumerate(ch['paras']):
        out.append(p(t))
        fig=ch.get('figure')
        if fig and fig.get('after_para')==i and fig.get('file'):
            out.append(img(fig['file'], fig.get('alt','图'))); out.append(caption(fig['caption']))
    fig=ch.get('figure')
    if fig and fig.get('file') and fig.get('after_para',0)>=len(ch['paras']):
        out.append(img(fig['file'], fig.get('alt','图'))); out.append(caption(fig['caption']))
out.append('<h2 style="margin:30px 0 10px;font-size:22px;line-height:1.4;font-weight:700;color:%s;font-family:%s;">格洛可点评</h2>'%(H2C,SANS))
for t in spec['commentary']:
    out.append('<p style="margin:0 0 16px;font-size:17px;line-height:1.85;color:%s;font-family:%s;text-align:justify;">%s</p>'%(INK,FANG,rich(t)))
src='来源：'+'；'.join('[%d] %s'%(s['n'],s['org']) for s in spec['sources'])+'。'
out.append('<p style="margin:26px 0 8px;font-size:11px;line-height:1.7;color:%s;font-family:%s;text-align:justify;">%s</p>'%(MUTED,SANS,esc(src)))
out.append('<p style="margin:0 0 22px;font-size:11px;line-height:1.7;color:%s;font-family:%s;text-align:justify;">%s</p>'%(MUTED,SANS,esc('备注：'+re.sub(r'^备注[：:]\s*','',spec['notes']))))
if spec.get('qr'):
    out.append('<section style="text-align:center;margin:8px 0 10px;">'+img(spec['qr'],'官方二维码','200px')+'</section>')
out.append('<p style="margin:10px 0 0;font-size:14px;line-height:1.6;color:%s;font-family:%s;text-align:center;">%s</p>'%(MUTED,SANS,esc(spec['signature'])))
out.append('</section></section>')
body='\n'.join(out)
FULL='--full' in sys.argv
if FULL:
    body='<div style="max-width:720px;margin:0 auto;padding:24px 16px 40px;">'+body+'</div>'
doc='<!DOCTYPE html>\n<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>%s</title></head>\n<body style="margin:0;padding:0;background:#EEF3F8;">\n%s\n</body></html>\n'%(esc(spec['title']),body)
open(sys.argv[2],'w',encoding='utf-8').write(doc); print('wrote',sys.argv[2],os.path.getsize(sys.argv[2]),'bytes')
