"""Bounded public news observations. No observation becomes an adopted GW total."""
import json
import hashlib
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from inresearch.knowledge.industry import public_url, number, project
from inresearch.knowledge import news_observations as observe
from inresearch.knowledge.site_timeline import current, adoptions

BEIJING = timezone(timedelta(hours=8))
COUNTRY_NAMES = {'CN':'China','US':'United States of America','AU':'Australia','FI':'Finland','GB':'United Kingdom','IN':'India','PH':'Philippines','TH':'Thailand','MY':'Malaysia','SG':'Singapore','SE':'Sweden','NO':'Norway','JP':'Japan','KR':'South Korea','DE':'Germany','FR':'France','CA':'Canada','BR':'Brazil','MX':'Mexico','AE':'United Arab Emirates','SA':'Saudi Arabia','IE':'Ireland','NL':'Netherlands','DK':'Denmark','TW':'Taiwan','CL':'Chile','ES':'Spain','IT':'Italy','BE':'Belgium','ID':'Indonesia','HK':'Hong Kong','VN':'Vietnam','KH':'Cambodia','BN':'Brunei','LA':'Laos'}
REGIONS = {**dict.fromkeys(('US','CA','MX'),'north-america'), **dict.fromkeys(('GB','FI','SE','NO','DE','FR','IE','NL','DK','ES','IT','BE'),'europe'), **dict.fromkeys(('AU','PH','TH','MY','SG','JP','KR','TW','ID','HK','VN','KH','BN','LA'),'apac'), **dict.fromkeys(('AE','SA'),'mena'), 'CN':'china','IN':'india','BR':'latam','CL':'latam'}


def _compile_term(alias):
    """Compile observe.contains semantics once; callers normalize each text once."""
    term=observe.normalized(alias)
    return term, None if re.search(r'[\u3400-\u9fff]',term) else re.compile(r'(?<!\w)'+re.escape(term)+r'(?!\w)')


def _contains_normalized(text, compiled):
    term,pattern=compiled
    return bool(term and (term in text if pattern is None else pattern.search(text)))


def _company_terms(companies, aliases=None):
    aliases=aliases or {}
    return [(company['company_id'],[_compile_term(term) for term in
             [company.get('name_cn') or '',*(company.get('name') or '').split(' / '),*aliases.get(company['company_id'],[])]
             if len(term)>=3]) for company in companies]


def _company_mentions(text, terms):
    return {ident for ident,compiled in terms if any(_contains_normalized(text,term) for term in compiled)}


def short(value, limit=200):
    return value[:limit] if isinstance(value, str) else ''


def capacities(rows):
    """Public quantities only: private original quotes/locators never leave this view."""
    result = []
    for row in (rows if isinstance(rows, list) else [])[:30]:
        if not isinstance(row, dict): continue
        value = row.get('mw')
        if value is None and number(row.get('value')) and row.get('unit') in ('MW','GW'):
            value = row['value'] * (1000 if row['unit']=='GW' else 1)
        if not number(value): continue
        basis = row.get('basis')
        if basis in ('facility','grid','generation'): basis='facility_or_grid'
        if basis not in ('it','facility_or_grid','lease','unknown'): basis='unknown'
        quoted = short(row.get('quoted_value'), 80) or (str(row['value'])+' '+row['unit'] if 'value' in row and row.get('unit') in ('MW','GW') else str(value)+' MW')
        item = dict(quoted_value=quoted, mw=value, basis=basis, acceptance='candidate')
        for key in ('scope','phase','nature'):
            if row.get(key): item[key] = short(row[key],80)
        if item not in result: result.append(item)
    return result


def countries(rows):
    result=[]
    for row in (rows if isinstance(rows,list) else [])[:10]:
        if not isinstance(row,dict): continue
        code=row.get('code')
        if isinstance(code,str) and re.fullmatch('[A-Z]{2}',code):
            item={'code':code,'name':short(row.get('name'),80) or COUNTRY_NAMES.get(code,code)}
            if item not in result: result.append(item)
    return result


def date_string(value):
    if not isinstance(value,str): return None
    try: return datetime.strptime(value,'%Y-%m-%d').date().isoformat()
    except ValueError: return None


def published_ms(value):
    if type(value) not in (float,int) or not number(value) or value<=0: return 0
    try: datetime.fromtimestamp(value/1000,timezone.utc)
    except (ValueError, OverflowError, OSError): return 0
    return value


def local_date(value):
    try:
        if type(value) in (float,int):
            return datetime.fromtimestamp(value/1000, BEIJING).date().isoformat() if value>0 else None
        if not isinstance(value,str): return None
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return d.astimezone(BEIJING).date().isoformat() if d.tzinfo else date_string(value)
    except (ValueError,OverflowError,OSError): return None


def country_points(root):
    """Schematic country centroids from the same registered atlas land geometry."""
    path=Path(root)/'web/assets/world.geo.json'
    if not path.is_file(): return {}
    geometries={f.get('properties',{}).get('name'):f.get('geometry',{}) for f in json.loads(path.read_text()).get('features',[])}
    result={}
    for code,name in COUNTRY_NAMES.items():
        g=geometries.get(name,{})
        rings=([g.get('coordinates',[])] if g.get('type')=='Polygon' else g.get('coordinates',[]) if g.get('type')=='MultiPolygon' else [])
        choices=[]
        for polygon in rings:
            ring=polygon[0] if polygon else []
            area=cx=cy=0
            for a,b in zip(ring,ring[1:]):
                cross=a[0]*b[1]-b[0]*a[1];area+=cross;cx+=(a[0]+b[0])*cross;cy+=(a[1]+b[1])*cross
            if area and max(p[0] for p in ring)-min(p[0] for p in ring)<180:
                choices.append((abs(area),[round(cy/(3*area),3),round(cx/(3*area),3)]))
        if choices: result[code]=max(choices)[1]
    return result


def enrichment(event):
    """Metadata from a received daily section; no raw text or private file identity."""
    authored=event.get('editorial_event') or {}; p=authored.get('project') or {}
    observations=event.get('capacity_observations') or []
    if event.get('structured_evidence_status')=='quotes_verified' and authored.get('capacities'):
        observations=authored['capacities']
    return dict(company_ids=[r['company_id'] for r in event.get('actors',[]) if isinstance(r,dict) and isinstance(r.get('company_id'),str)][:30],
                country_mentions=countries(event.get('country_mentions')),
                location=', '.join(short(p.get(k)) for k in ('city','province','country') if p.get(k)),
                capacity_observations=capacities(observations),
                published_date=date_string(authored.get('reported_date')),
                event_date=date_string(authored.get('event_date')),
                matched_site_id=event.get('matched_site_id'))


def build(root, feed, leads, *, received_at=None, available=False, truncated=False, now=None):
    root=Path(root)
    site_path=root/'data/projects.json';company_path=root/'data/companies.json'
    sites={r['site_id']:current(r) for r in json.loads(site_path.read_text())['records']} if site_path.exists() else {}
    companies=json.loads(company_path.read_text())['records'] if company_path.exists() else []; company_ids={r['company_id'] for r in companies}
    from inresearch.materials.daily_events import COUNTRIES
    company_terms=_company_terms(companies)
    research_terms=_company_terms(companies,{'amazon':['AWS','Amazon Web Services','亚马逊'],
        'alphabet-google':['Google','谷歌'],'microsoft':['Microsoft','微软'],'meta':['Meta','Facebook'],
        'alibaba':['Alibaba','阿里云','阿里巴巴'],'bytedance':['ByteDance','TikTok','字节跳动','抖音']})
    country_terms=[(code,name,_compile_term(name)) for name,code in COUNTRIES.items()]
    english_country_terms=[(code,name,_compile_term(name)) for code,name in COUNTRY_NAMES.items()]
    points=country_points(root); records={}
    input_truncated=len(leads)>1000 or len((feed or {}).get('items',[]))>80
    def make(event,row=None):
        row=row or {}; url=public_url(event.get('url'))
        if not url: return None
        title=short(event.get('title_zh') or event.get('title') or row.get('title'),400)
        if not title: return None
        ids={i for i in (row.get('company_ids') or []) if i in company_ids}
        ids.update(i[6:] for i in event.get('object_ids',[]) if isinstance(i,str) and i.startswith('actor:') and i[6:] in company_ids)
        normalized_title=observe.normalized(title)
        ids.update(_company_mentions(normalized_title,company_terms))
        mentions=countries(event.get('country_mentions') or row.get('country_mentions'))
        if not mentions:
            mentions=[{'code':code,'name':name} for code,name,term in country_terms if _contains_normalized(normalized_title,term)]
            for code,name,term in english_country_terms:
                if _contains_normalized(normalized_title,term) and not any(c['code']==code for c in mentions): mentions.append({'code':code,'name':name})
        ident=row.get('site_id') or event.get('matched_site_id'); site=sites.get(ident)
        observations=capacities(event.get('capacity_observations') or row.get('capacity_observations'))
        if not observations: observations=capacities(observe.power(title))
        stamp=published_ms(event.get('published_at'))
        published=local_date(stamp) or date_string(event.get('published_date') or row.get('published_date'))
        received=event.get('received_at') or (row.get('first_seen') if row.get('origin')=='daily_html' or len(row.get('events',[]))==1 else None)
        item=dict(id=short(row.get('id') or 'news',120)+'-'+hashlib.sha256(url.encode()).hexdigest()[:16],lead_id=short(row.get('id'),160) or None,title=title,url=url,
                  published_at=stamp,published_date=published,report_date=date_string(row.get('report_date')),
                  received_at=short(received,50) or None,received_date=local_date(received),
                  company_ids=sorted(ids),country_mentions=mentions[:10],site_id=site['site_id'] if site else None,
                  location=short(event.get('location') or row.get('location')),
                  coordinates=None,location_precision='unknown',region=None,
                  capacity_observations=observations,reported_stage=short(event.get('reported_stage') or row.get('reported_stage'),40) or 'reported',
                  verification_status='project_adopted' if site and adoptions(site) else 'raw',capacity_adopted=False,
                  origin=row.get('origin') or 'news_feed')
        if site:
            item.update(coordinates=project(site)['coordinates'], location=site.get('location'),region=site.get('region'))
            if item['coordinates']: item['location_precision']='site'
            if site.get('country') and not mentions: item['country_mentions']=countries([{'code':site['country']}])
        if not item['coordinates'] and len(item['country_mentions'])==1:
            code=item['country_mentions'][0]['code'];item['coordinates']=points.get(code)
            item['region']=REGIONS.get(code)
            if item['coordinates']: item['location_precision']='country'
        return item
    # A daily section with several source URLs is one event, not several capacity additions.
    for row in leads[:1000]:
        if not isinstance(row,dict): continue
        events=[e for e in row.get('events',[]) if isinstance(e,dict)]
        if row.get('origin')=='daily_html': events=events[:1]
        elif len(events)>100: input_truncated=True
        for event in events[:100]:
            item=make(event,row)
            if item:
                key=('daily:'+str(row.get('id'))) if row.get('origin')=='daily_html' else item['url']
                if key not in records or item['published_at']>records[key]['published_at']: records[key]=item
    for event in (feed or {}).get('items',[])[:80]:
        if not isinstance(event,dict): continue
        item=make(event)
        if item:
            existing=next((r for r in records.values() if r['url']==item['url']),None)
            if existing is None: records[item['url']]=item
            else:
                # The direct feed can supply a true publication timestamp for a daily source link.
                if item['published_at']>existing['published_at']:
                    existing['published_at']=item['published_at'];existing['published_date']=item['published_date']
                existing['company_ids']=sorted(set(existing['company_ids'])|set(item['company_ids']))
                if not existing['capacity_observations']:existing['capacity_observations']=item['capacity_observations']
    ledger_path=root/'docs/research/2026-10-11/data-centers/project-ledger.json'
    research_total=0
    if ledger_path.is_file():
        ledger=json.loads(ledger_path.read_text())
        if ledger.get('schema')=='source-reported-project-ledger-v1' and ledger.get('formal_database_ingested') is False:
            publication=date_string(ledger.get('publication_date'))
            for row in ledger.get('records',[])[:500]:
                if not isinstance(row,dict): continue
                sources=[u for u in row.get('sources',[]) if public_url(u)][:10]
                if not sources: continue
                roles={k:short(v,600) for k,v in (row.get('roles') or {}).items() if k in ('developer_or_builder','operator','disclosed_user')}
                ids=_company_mentions(observe.normalized(' '.join(roles.values())),research_terms)
                code=row.get('country_code'); mentions=countries([{'code':code,'name':row.get('country_label')}])
                item=dict(id=short(row.get('id'),160),title=short(row.get('name'),400),name=short(row.get('name'),400),
                          url=sources[0],sources=sources,published_at=0,published_date=None,report_date=None,
                          publication_date=publication,received_at=None,received_date=None,
                          company_ids=sorted(ids),company_match='source_mention_unverified',country_mentions=mentions,country_code=code,
                          site_id=None,canonical_site_id=None,coordinates=points.get(code),location_precision='country' if mentions else 'unknown',
                          location=short(row.get('public_location'),600),public_location=short(row.get('public_location'),600),
                          region=REGIONS.get(code),roles=roles,capacity_text=short((row.get('capacity') or {}).get('quoted_text'),1000),
                          capacity_observations=[],capacity_adopted=False,reported_stage='reported',
                          stage_and_date=short(row.get('stage_and_date'),800),evidence_date_text=short(row.get('evidence_date_text'),1000),
                          boundary=short(row.get('boundary'),800),verification_status='raw',origin='research_publication')
                records['research:'+item['id']]=item;research_total+=1
    values=sorted(records.values(),key=lambda r:(r['published_date'] or r['report_date'] or r.get('publication_date') or '',r['published_at'],r['received_at'] or ''),reverse=True)
    today=(now or datetime.now(timezone.utc)).astimezone(BEIJING).date().isoformat()
    fresh=[r for r in values if r['published_date']==today]
    adopted=[s for s in sites.values() if adoptions(s)]
    updates=sum(any(local_date(a.get('review',{}).get('at') or a.get('reviewed_at'))==today
                    for a in adoptions(s)) for s in adopted)
    groups=[]
    for code in sorted({r['country_code'] for r in values if r.get('origin')=='research_publication' and r.get('country_code')}):
        subset=[r for r in values if r.get('origin')=='research_publication' and r.get('country_code')==code]
        groups.append(dict(country_code=code,country_name=subset[0]['country_mentions'][0]['name'],coordinates=points.get(code),
                           count=len(subset),company_ids=sorted({c for r in subset for c in r['company_ids']}),
                           location_precision='country',kind='source_records'))
    research=[r for r in values if r.get('origin')=='research_publication']
    news=[r for r in values if r.get('origin')!='research_publication']
    shown=research+news[:max(0,400-len(research))]
    news_truncated=bool(truncated or input_truncated or len(shown)<len(values))
    receipt_complete=all(r.get('received_date') for r in news)
    daily=dict(today=today,news_available=bool(available),receipt_dates_complete=receipt_complete, published_events=len(fresh) if available else None,
               received_events=sum(r['received_date']==today for r in values) if available and receipt_complete else None,
               report_events=sum(r['report_date']==today for r in values) if available else None,
               research_published_records=sum(r.get('publication_date')==today for r in values),
               capacity_observations=sum(bool(r['capacity_observations']) for r in fresh) if available else None,
               capacity_values=sum(len(r['capacity_observations']) for r in fresh) if available else None,
               located_events=sum(bool(r['coordinates']) for r in fresh) if available else None,
               adopted_project_updates=updates if adopted else None,
               adopted_fields_projects=len(adopted),latest_project_registration=max((p.get('verified_date') or '' for p in sites.values()),default='') or None)
    return dict(country_groups=groups,records=shown,total=len(values),located_total=sum(bool(r['coordinates']) for r in values),
                unlocated_total=sum(not r['coordinates'] for r in values),truncated=news_truncated,available=bool(available or research_total),research_total=research_total,
                latest_published_at=max((r['published_at'] for r in values),default=0) or None,
                latest_received_at=max((r['received_at'] for r in values if r['received_at']),default=None),
                daily=daily,news_available=bool(available),news_total=len(news),news_truncated=news_truncated,research_truncated=False,
                scope='有界来源观察；国家落点仅为区域示意，报道 MW 不汇总为正式 GW。',
                received_at=received_at,counts_complete=bool(available and not news_truncated),counts_scope='本次有界来源快照，非全球事件总数。')
