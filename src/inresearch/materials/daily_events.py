"""Non-executing, section-level daily evidence ledger. Never an adopted GW sum."""
import hashlib
import json
import re
from pathlib import Path
from inresearch.adapters.html_document import _Document
from inresearch.knowledge import news_observations as observe
from inresearch.storage.files import locked, write_json

COUNTRIES = {'中国':'CN','澳大利亚':'AU','芬兰':'FI','英国':'GB','美国':'US','印度':'IN','菲律宾':'PH',
             '泰国':'TH','马来西亚':'MY','新加坡':'SG','瑞典':'SE','挪威':'NO','日本':'JP','韩国':'KR',
             '德国':'DE','法国':'FR','加拿大':'CA','巴西':'BR','墨西哥':'MX','阿联酋':'AE','沙特':'SA',
             '爱尔兰':'IE','荷兰':'NL','丹麦':'DK','台湾':'TW'}


class Sections(_Document):
    def __init__(self):
        super().__init__(); self.headings=[]; self.heading_start=None; self.heading_level=None

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag in ('h2','h3') and not self.omit_stack:
            self.heading_start=len(self.parts);self.heading_level=tag

    def handle_endtag(self, tag):
        if tag == self.heading_level and self.heading_start is not None:
            start=self.heading_start
            self.headings.append({'start':start,'end':len(self.parts),'level':tag,'title':' '.join(''.join(self.parts[start:]).split())})
            self.heading_start=None
        super().handle_endtag(tag)


def parse(path, root, original_name=None):
    path=Path(path); raw=path.read_bytes(); sha=hashlib.sha256(raw).hexdigest()
    parser=Sections();parser.feed(raw.decode('utf-8-sig'))
    all_text=''.join(parser.parts)
    if not re.search(r'日报|DAILY', ''.join(parser.title)+all_text[:1500], re.I): return []
    name=original_name or path.name
    date_match=re.search(r'20\d{2}-\d{2}-\d{2}',name)
    if not date_match:date_match=re.search(r'20\d{2}-\d{2}-\d{2}', ''.join(parser.title))
    report_date=date_match.group() if date_match else None
    if not report_date:
        date_match=re.search(r'(20\d{2})[年./](\d{1,2})[月./](\d{1,2})', ''.join(parser.title))
        if date_match:report_date='%s-%02d-%02d'%(date_match[1],int(date_match[2]),int(date_match[3]))
    companies=json.loads((Path(root)/'data/companies.json').read_text())['records']
    sites=json.loads((Path(root)/'data/projects.json').read_text())['records']
    if sum(h.get('level')=='h3' for h in parser.headings)>=2:
        parser.headings=[h for h in parser.headings if h.get('level')=='h3' or re.search(r'来源|参考|Sources',h['title'],re.I)]
    if not parser.headings:
        # WeChat exports use styled paragraphs rather than heading tags.
        parser.parts=list(all_text)
        for m in re.finditer(r'(?m)^\s*(?:(?:0?[1-9]|1[0-9])[.、/]\s*|(?:0[1-9]|1[0-9])\s+)([^\n]+)\s*$',all_text):
            parser.headings.append({'start':m.start(),'end':m.end(),'title':m.group(1).strip()})
        tail=re.search(r'(?m)^\s*(?:主要来源|来源\s*[/／]|参考来源)[^\n]*',all_text)
        if tail:parser.headings.append({'start':tail.start(),'end':tail.end(),'title':'来源'})
    source_heading=next((h for h in reversed(parser.headings) if re.search(r'来源|参考|Sources',h['title'],re.I)),None)
    source_text=''.join(parser.parts[source_heading['end']:]) if source_heading else all_text[all_text.rfind('来源'):]
    refs={}
    markers=list(re.finditer(r'\[(\d+)\]|【(\d+)】',source_text))
    for i,m in enumerate(markers):
        segment=source_text[m.end():markers[i+1].start() if i+1<len(markers) else len(source_text)]
        refs[m.group(1) or m.group(2)]={'label':' '.join(segment.split())[:1200],
                                      'urls':list(dict.fromkeys(re.findall(r'https?://[^\s<>\]]+',segment)))}
    events=[]
    for index,heading in enumerate(parser.headings):
        if re.search(r'点评|跨市场|来源|参考|Sources|本期|目录',heading['title'],re.I): break
        end=parser.headings[index+1]['start'] if index+1<len(parser.headings) else len(parser.parts)
        body=''.join(parser.parts[heading['end']:end]).strip()
        before=''.join(parser.parts[:heading['start']]).strip().split('\n')[-3:]
        following=[line.strip() for line in body.split('\n') if line.strip()]
        kicker=next((line for line in reversed(before) if re.search(r'^\d{2}\s*[/／]',line)),None)
        place_quote=kicker or (following[0] if following and '·' in following[0] else '')
        # A preceding label belongs to the next story, not this story's facts.
        body=re.sub(r'\n\s*\d{2}\s*[/／][^\n]*\s*$', '',body).strip()
        # Some exports keep the source list inside the last section. Publisher
        # names there must not become project/location identity evidence.
        body=re.split(r'(?:^|\n)\s*(?:主要来源|参考来源|来源|Sources)\s*[:：]',body,maxsplit=1,flags=re.I)[0].strip()
        title=heading['title']; text=title+'\n'+place_quote+'\n'+body
        if not body: continue
        country=[{'name':name,'code':code,'quote':place_quote} for name,code in COUNTRIES.items() if name in place_quote]
        actors=[{'company_id':c['company_id'],'name':c['name'],'quote':text[:1000]} for c in companies
                if any(observe.contains(text,c.get(k) or '') for k in ('name','name_cn'))]
        identity=observe.identity({'title':text,'object_ids':['actor:'+a['company_id'] for a in actors]},sites,companies)
        stage='unknown'
        for key,pattern in [('planning',r'未获批|没有获得.*许可|拟建|计划建设|拟建设'),
                            ('operating',r'已投运|投入运营|已通电|已运营'),
                            ('construction',r'已开工|正在施工|开工建设|建设中'),
                            ('approved',r'获批|批准|建设许可已经取得')]:
            if re.search(pattern,text): stage=key;break
        ids=list(dict.fromkeys(re.findall(r'\[(\d+)\]|【(\d+)】',text)))
        citations=[refs.get(a or b,{'label':'来源编号 '+(a or b)+'；原链接待补','urls':[]}) for a,b in ids]
        semantic=hashlib.sha256((' '.join(text.split())).encode()).hexdigest()
        events.append({'id':'daily-event-'+semantic,'title':title,'body':body,'place_quote':place_quote,
                       'project_quotes':[sentence.strip() for sentence in re.split(r'[。\n]',body)
                                         if re.search(r'项目|园区|位于|数据中心',sentence)][:6],
                       'country_mentions':country,'actors':actors,'reported_stage':stage,
                       'capacity_observations':observe.power(text,'section:'+str(index+1)),
                       'constraints':observe.constraints(text),'sources':citations,
                       'document_refs':[{'sha256':sha,'filename':name,'report_date':report_date,'section':index+1}],
                       'reported_dates':re.findall(r'\d{1,2}月\d{1,2}日[^。\n]{0,60}',text),
                       'identity_review':'pending','capacity_review':'pending','acceptance':'candidate',**identity})
    return events


def receive(path, data, root, original_name=None):
    events=parse(path,root,original_name)
    if not events:return []
    target=Path(data)/'acquisition/daily-events.json'
    with locked(target):
        doc=json.loads(target.read_text()) if target.exists() else {'version':2,'records':{},'parses':{}}
        if doc.get('version') not in (1,2) or not isinstance(doc.get('records'),dict):raise ValueError('invalid_daily_event_ledger')
        if 'parses' not in doc:
            doc['parses']={}
            for row in doc['records'].values():
                for ref in row['document_refs']:
                    doc['parses'].setdefault(ref['sha256'],{'revision':'legacy','event_ids':[]})['event_ids'].append(row['id'])
        doc['version']=2
        for event in events:
            old=doc['records'].get(event['id'])
            if old:
                for ref in event['document_refs']:
                    if ref not in old['document_refs']:old['document_refs'].append(ref)
                # Recompute unreviewed interpretation while retaining prior output.
                keys=('actors','country_mentions','site_candidates','matched_site_id','capacity_observations','project_quotes')
                changes={k:event.get(k) for k in keys}
                previous={k:old.get(k) for k in keys}
                if old.get('identity_review')=='pending' and changes!=previous:
                    old.setdefault('interpretation_history',[]).append(previous)
                    old.update(changes)
                for source in event['sources']:
                    if source not in old['sources']:old['sources'].append(source)
            else:doc['records'][event['id']]=event
        sha=events[0]['document_refs'][0]['sha256']
        doc['parses'][sha]={'revision':'daily-section-v3','event_ids':[e['id'] for e in events]}
        write_json(target,doc)
    return events


def projection(data):
    path=Path(data)/'acquisition/daily-events.json'
    if not path.exists():return {'total':0,'records':[],'status':'not_initialized'}
    doc=json.loads(path.read_text())
    active={i for p in doc.get('parses',{}).values() for i in p['event_ids']} if doc.get('parses') else set(doc['records'])
    records=[r for i,r in doc['records'].items() if i in active]
    records.sort(key=lambda r:max((d.get('report_date') or '' for d in r['document_refs']),default=''),reverse=True)
    return {'total':len(records),'historical_parse_records':len(doc['records']),'document_versions':len({d['sha256'] for r in records for d in r['document_refs']}),
            'capacity_observations':sum(len(r['capacity_observations']) for r in records),
            'identity_candidates':sum(bool(r['site_candidates']) for r in records),
            'missing_source_links':sum(not any(s['urls'] for s in r['sources']) for r in records),
            'records':[{**{k:v for k,v in r.items() if k!='interpretation_history'},'body':r['body'][:1600]} for r in records[:1000]],'truncated':len(records)>1000,
            'status':'candidate_event_ledger',
            'scope':'逐事件正文登记；同文幂等、来源版本保留；非全球已投运或在建 GW 合计。'}


def review(data, root, event_id, site_id, reviewer, note):
    """Resolve identity only; never adopt capacity or rewrite Git facts."""
    sites=json.loads((Path(root)/'data/projects.json').read_text())['records']
    if site_id not in {s['site_id'] for s in sites} or not reviewer.strip() or not note.strip():raise ValueError('identity_review_requires_known_site_reviewer_and_note')
    path=Path(data)/'acquisition/daily-events.json'
    with locked(path):
        ledger=json.loads(path.read_text())
        if event_id not in ledger['records']:raise ValueError('unknown_daily_event')
        event=ledger['records'][event_id]
        from inresearch.adapters.acquisition import now
        event.setdefault('identity_reviews',[]).append({'site_id':site_id,'reviewer':reviewer,'note':note,'at':now()})
        event.update(identity_review='resolved',matched_site_id=site_id)
        write_json(path,ledger)


def main():
    import argparse
    from inresearch.adapters.acquisition import data_root
    from inresearch.paths import project_root
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root',type=Path,default=data_root())
    parser.add_argument('--event');parser.add_argument('--site');parser.add_argument('--reviewer');parser.add_argument('--note')
    args=parser.parse_args()
    if args.event:review(args.data_root,project_root(),args.event,args.site,args.reviewer or '',args.note or '')
    print(json.dumps(projection(args.data_root),ensure_ascii=False))
    return 0
