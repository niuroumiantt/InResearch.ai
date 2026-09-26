#!/usr/bin/env python3
import json, sys, os, html
out=sys.argv[1]
c=json.load(open(os.path.join(out,'work','content.json'))); cv=json.load(open(os.path.join(out,'work','cover.json')))
MS_OLD=['摩根士丹利称通知将令数据中心贷款与租约文件受审视','彭博引摩根士丹利称贷款与租约文件将受审视','摩根士丹利称该通知将令数据中心贷款与租约文件受到审视']
MS_NEW='彭博称摩根士丹利认为该通知将拖累数据中心债务'
def fix(t):
    for o in MS_OLD: t=t.replace(o,MS_NEW)
    t=t.replace('彭博援引彭博称','彭博称').replace('彭博援引'+MS_NEW,MS_NEW).replace('德州','得州')
    return t
c['lead']=[fix(t) for t in c['lead']]; c['commentary']=[fix(t) for t in c['commentary']]
for e in c['events']:
    e['paras']=[fix(t) for t in e['paras']]; e['title']=fix(e['title'])
def un(t): return html.unescape(t) if '&lt;' in t or '&gt;' in t else t
cv['title_html']=un(cv['title_html'])
for m in cv['modules']: m['fact_html']=un(m['fact_html'])
for m in cv['modules']:
    if m['name'].startswith('网络'):
        m['fact_html']='微软印度中南部区域启用（三可用区）；特伦甘纳邦全邦已运营约<b>300MW</b>、在建约<b>2GW</b>'
        m['sub']='微软海得拉巴区域'
c['notes']=c['notes'].lstrip('备注：').rstrip('。')+'。首图“中国”栏引用阿里云9月22日云栖大会提出的2032年运营规模超20GW目标，属背景。'
json.dump(c,open(os.path.join(out,'work','content.json'),'w'),ensure_ascii=False,indent=1)
json.dump(cv,open(os.path.join(out,'work','cover.json'),'w'),ensure_ascii=False,indent=1)
print('postedit ok')
