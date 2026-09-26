#!/usr/bin/env python3
"""Merge writer/lead outputs + figures into content.json and cover.json. usage: assemble.py outdir"""
import json, os, sys, re, glob
S='/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/scratchpad'
T='/tmp/claude-0/-home-user/84d17af6-4887-559a-8d6e-523be1e3e039/tasks'
outdir=os.path.abspath(sys.argv[1]); os.makedirs(outdir,exist_ok=True)
def load_task(tid):
    d=json.load(open(os.path.join(T,tid+'.output')))
    return d['result'] if 'result' in d else d
events={}
for tid in ['ws2qt2kd3','wetehv6da','wt82pn8tx']:
    r=load_task(tid)
    drafts={d['no']:d for d in r['drafts']}
    for c in r['checked']:
        no=c['no']; d=drafts.get(no,{})
        ev=dict(d); ev.update(c['corrected']); ev['check_pass']=c['pass']; ev['check_problems']=c['problems']
        events[no]=ev
lead=load_task('wip3ct4kv')['checked']['corrected']
plan=json.load(open(os.path.join(S,'event_plan.json')))
# figures
FIG={'01':('fig_jupiter.png','图1 甲骨文木星园区供电链条的时间点。阶段与日期来自Bloomberg、Reuters、Albuquerque Journal及新墨西哥州政府文件；不可抗力通知条款为匿名信源转述，摩根士丹利观点仅取彭博标题。'),
     '04':('fig_us_power.png','图2 美国六项供电成本与许可安排的对照。得州、TVA与埃尔帕索为本期事件，俄勒冈与加州分别为9月16日、9月21日的背景决定；容量承诺费数值来自区域媒体转述，TVA正式费率表未公开。'),
     '07':('fig_funding.png','图3 当日披露的四笔数据中心资金，单位为十亿美元。蓝色为客户合同承诺（Akamai–Anthropic 116亿、Cipher Digital 90亿以上），橙色为已交割融资（Nscale 33.6亿中23.6亿已到账，CleanSpark 22.76亿）；数字来自各公司8-K与公告。'),
     '13':('fig_asia.png','图4 南亚与东南亚六地同一天的土地、许可、电力与水条件对照；数字均为各地政府或公司披露口径，非本刊测算。')}
# source numbering
CANON=[('Bloomberg','Bloomberg'),('Reuters','Reuters'),('24/7 Wall St','24/7 Wall St.'),('Texas Attorney General','Texas Attorney General'),('Office of the Texas Governor','Office of the Texas Governor'),('ERCOT','ERCOT'),('美国能源部','美国能源部'),('U.S. Department of Energy','美国能源部'),('rocketcitynow','WZDX'),('WAFF','WAFF'),('256 Today','256 Today'),('American Public Power','American Public Power Association'),('Inside Climate News','Inside Climate News'),('KTSM','KTSM'),('Cipher Digital','Cipher Digital（SEC 8-K）'),('Cipher Mining','Cipher Digital（SEC 8-K）'),('GlobeNewswire','GlobeNewswire'),('Investing.com','Investing.com'),('CleanSpark','CleanSpark（SEC 8-K／PR Newswire）'),('Nscale','Nscale'),('BeBeez','BeBeez International'),('Unite.AI','Unite.AI'),('金融庁','日本金融厅'),('金融厅','日本金融厅'),('Japan Times','The Japan Times'),('Nikkei Asia','Nikkei Asia'),('Elon Musk','Elon Musk（X）'),('WATN','WATN'),('localmemphis','WATN'),('Business Standard','Business Standard'),('UNI India','UNI India'),('OdishaBytes','OdishaBytes'),('Indian Infrastructure','Indian Infrastructure'),('Telangana Today','Telangana Today'),('Microsoft','Microsoft'),('ThePrint','ThePrint'),('Kaohoon','Kaohoon'),('Khaosod','Khaosod English'),('The Nation','The Nation Thailand'),('Data Center Dynamics','Data Center Dynamics'),('Eco World','Eco World Development Group（Bursa公告）'),('The Star','The Star'),('星洲','星洲日报'),('Antara','Antara'),('Jakarta Post','The Jakarta Post'),('detik','detik'),('Newsom','Office of Governor Gavin Newsom'),('Public Utility Commission of Oregon','Public Utility Commission of Oregon'),('Hindu BusinessLine','The Hindu BusinessLine'),('Dân trí','Dân trí'),('IT之家','IT之家'),('Utility Dive','Utility Dive'),('The Register','The Register'),('FirstAlert7','FirstAlert7'),('SEC EDGAR - CleanSpark','CleanSpark（SEC 8-K／PR Newswire）')]
def canon_org(org):
    for k,v in CANON:
        if k.lower() in org.lower(): return v
    return re.sub(r'[（(].*?[)）]','',org).strip()
srcs=[]; idx={}
def num(org,url=''):
    key=canon_org(org)
    if key not in idx:
        idx[key]=len(srcs)+1; srcs.append({'n':len(srcs)+1,'org':key,'urls':[]})
    if url and url not in srcs[idx[key]-1]['urls']: srcs[idx[key]-1]['urls'].append(url)
    return idx[key]
out_events=[]
for pe in plan['events']:
    no=pe['no']; ev=events[no]
    ns=[]
    for s in ev.get('sources_used',[])[:4]:
        ns.append(num(s['org'],s.get('url','')))
    ns=sorted(set(ns))
    marker=''.join('[%d]'%n for n in ns)
    p1=ev['para1'].rstrip()
    p1=p1+marker
    item={'no':no,'title':ev['title'],'info':ev['info_line'],'paras':[p1,ev['para2']],'card':pe.get('card'),'check_pass':ev['check_pass'],'check_problems':ev['check_problems']}
    if no in FIG: item['figure']={'file':FIG[no][0],'caption':FIG[no][1],'alt':FIG[no][1][:20]}
    out_events.append(item)
# commentary named cases -> sources
comm=list(lead['commentary'])
cm=[]
for c in lead.get('named_cases_used',[]):
    cm.append(num(c['org'],c.get('url','')))
cm=sorted(set(cm))
if cm: comm[1]=comm[1].rstrip()+''.join('[%d]'%n for n in cm)
content={'date':'2026-09-26','date_display':'2026年9月26日','title':lead['title'],'lead':[lead['lead1'],lead['lead2']],'coverage':lead['coverage_line'],'events':out_events,'commentary':comm,'sources':[{'n':s['n'],'org':s['org']} for s in srcs],'notes':lead['notes'],'qr':None,'signature':'格洛可数据中心日报 · 2026年9月26日','cover':{'file':'2026-09-26-article-summary-wechat.jpg'}}
json.dump(content,open(os.path.join(outdir,'content.json'),'w'),ensure_ascii=False,indent=1)
json.dump({'sources':srcs,'events':[{'no':e['no'],'card':e['card'],'check_pass':e['check_pass'],'problems':e['check_problems']} for e in out_events],'lead_named_cases':lead.get('named_cases_used',[])},open(os.path.join(outdir,'sources_ledger.json'),'w'),ensure_ascii=False,indent=1)
cover=lead['cover']
cover_spec={'date':'2026年9月26日','edition':cover['edition_tag'],'title_html':cover['title_html'],'subtitle':cover['subtitle'],'claim':cover['claim'],'band_tag':'AI 数据中心 工程剖视 · 电力—机房—冷却—网络','xsec':'file://'+S+'/xsec_final.svg','modules':[{'name':m['name'],'sub':m['sub'],'fact_html':m['fact_html']} for m in cover['modules']],'regions':cover['regions'],'conclusion':cover['conclusion'],'signature':'格洛可数据中心日报 · 2026-09-26','qr':None,'maps':[m['maps_to_no'] for m in cover['modules']]}
json.dump(cover_spec,open(os.path.join(outdir,'cover.json'),'w'),ensure_ascii=False,indent=1)
print('events',len(out_events),'sources',len(srcs),'check_fail',[e['no'] for e in out_events if not e['check_pass']])
print('TITLE:',content['title'])
