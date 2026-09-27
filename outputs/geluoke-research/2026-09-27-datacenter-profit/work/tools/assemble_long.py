#!/usr/bin/env python3
"""Assemble article.json (for build_long.py), sources.json and article.md from chapters_final.json + lead.json + figure map.
usage: assemble_long.py workdir  (expects workdir/chapters_final.json, workdir/lead.json, workdir/figmap.json)"""
import json, sys, os, re
wd=sys.argv[1]
ch=json.load(open(os.path.join(wd,'chapters_final.json')))
lead=json.load(open(os.path.join(wd,'lead.json')))
figmap=json.load(open(os.path.join(wd,'figmap.json')))   # {fig_id: {file, alt}}
date_display=lead.get('date_display','2026年9月27日')
# --- sources: number by first appearance across chapters
CANON=json.load(open(os.path.join(wd,'canon.json'))) if os.path.exists(os.path.join(wd,'canon.json')) else {}
def canon(org):
    base=re.sub(r'[（(][^()（）]*[)）]','',org).strip()
    for k,v in CANON.items():
        if k in base: return v
    return base or org
srcs=[]; key2n={}
def add_source(s):
    org=canon(s['org']); url=s.get('url','')
    for i,x in enumerate(srcs):
        if x['org']==org:
            if url and url not in [d['url'] for d in x['details']]: x['details'].append({'org_raw':s['org'],'url':url,'title':s.get('title',''),'date':s.get('date',''),'kind':s.get('kind','')})
            return i+1
    srcs.append({'org':org,'url':url,'details':[{'org_raw':s['org'],'url':url,'title':s.get('title',''),'date':s.get('date',''),'kind':s.get('kind','')}]}); return len(srcs)
chapters_out=[]
for c in ch['chapters']:
    keymap={s['key']:s for s in c.get('sources_used',[])}
    paras=[]
    for p in c['paras']:
        ns=[]
        for k in p.get('cites',[]):
            if k in keymap:
                n=add_source(keymap[k])
                if n not in ns: ns.append(n)
        txt=p['text'].rstrip()
        if ns: txt+='['+','.join(str(n) for n in sorted(ns))+']'
        paras.append(txt)
    fig=c.get('figure') or {}
    fm=figmap.get(fig.get('id'),{})
    figure={'after_para':fig.get('after_para',len(paras)-1),'caption':fig.get('caption',''),'file':fm.get('file'),'alt':fm.get('alt',fig.get('title',''))} if fm.get('file') else None
    chapters_out.append({'no':c['no'],'title':c['title'],'paras':paras,'figure':figure})
for s in lead.get('sources_added',[]): add_source(s)
art={'title':lead['title'],'date_display':date_display,'cover':{'file':figmap['cover']['file']},'lead':[lead['lead1'],lead['lead2']],'coverage':lead['coverage_line'],
     'chapters':chapters_out,'commentary':lead['commentary'],'sources':[{'n':i+1,'org':s['org']} for i,s in enumerate(srcs)],'notes':lead['notes'],'signature':lead.get('signature','格洛可数据中心研究'),'qr':figmap.get('qr',{}).get('file')}
json.dump(art,open(os.path.join(wd,'article.json'),'w'),ensure_ascii=False,indent=1)
json.dump([{'n':i+1,'org':s['org'],'items':s['details']} for i,s in enumerate(srcs)],open(os.path.join(wd,'sources.json'),'w'),ensure_ascii=False,indent=1)
# editable markdown
md=[f"# {art['title']}",'',f"格洛可数据中心专题 · {date_display}",'']+[l+'\n' for l in art['lead']]+[art['coverage'],'']
for c in chapters_out:
    md+= [f"## {c['no']}　{c['title']}",'']
    for i,p in enumerate(c['paras']):
        md.append(p+'\n')
        if c['figure'] and c['figure']['after_para']==i: md.append(f"![{c['figure']['alt']}]({os.path.basename(c['figure']['file'])})\n\n*{c['figure']['caption']}*\n")
md+=['## 格洛可点评','']+[t+'\n' for t in art['commentary']]
md+=['','来源：'+'；'.join(f"[{s['n']}] {s['org']}" for s in art['sources'])+'。','','备注：'+art['notes'],'',art['signature']]
open(os.path.join(wd,'article.md'),'w').write('\n'.join(md))
print('sources',len(srcs),'| chapters',len(chapters_out),'| paras',sum(len(c['paras']) for c in chapters_out))
