#!/usr/bin/env python3
"""Bounded collection into a permanent candidate ledger, never core facts or the reader inbox.

Run on Spark: --data-root ~/.local/share/inresearch.ai <command>.
The separate ledger owns discovery/acquisition; catalog/catalog.sqlite owns reading.
"""

from inresearch.paths import project_root
import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
import os as os
from pathlib import Path
import sqlite3
import statistics
import shutil
import tempfile
import time as time
from urllib.parse import quote, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError

ROOT = project_root()
SOURCES = ('inews', 'sec', 'gpu', 'fetchspec')
from inresearch.knowledge.news_policy import INEWS_DATACENTER_URL, build_terms, AMBIGUOUS, ENTITY_CONTEXT, classify
_DIRECT_FEED_PROOF = object()


@dataclass(frozen=True)
class VerifiedNewsProjection:
    """In-process result of the fixed HTTPS feed fetch, never a JSON authority flag."""
    payload_json: bytes
    proof: object = field(repr=False)


SCHEMA = '''
CREATE TABLE IF NOT EXISTS items (
 id TEXT PRIMARY KEY, source TEXT NOT NULL, source_key TEXT NOT NULL, kind TEXT NOT NULL,
 state TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL, metadata TEXT NOT NULL,
 created TEXT NOT NULL, updated TEXT NOT NULL, UNIQUE(source,source_key));
CREATE TABLE IF NOT EXISTS observations (
 id INTEGER PRIMARY KEY, item_id TEXT NOT NULL, sha256 TEXT NOT NULL, relative_path TEXT NOT NULL,
 observed_at TEXT NOT NULL, request_json TEXT NOT NULL, UNIQUE(item_id,sha256));
CREATE TABLE IF NOT EXISTS links (
 item_id TEXT NOT NULL, question_id TEXT NOT NULL, direction TEXT NOT NULL,
 PRIMARY KEY(item_id,question_id,direction));
CREATE TABLE IF NOT EXISTS runs (
 id INTEGER PRIMARY KEY, source TEXT NOT NULL, started TEXT NOT NULL, finished TEXT,
 status TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0, error_code TEXT);
CREATE TABLE IF NOT EXISTS product_documents (
 id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL, source_item_id TEXT NOT NULL,
 company_id TEXT NOT NULL, first_category TEXT NOT NULL, categories_json TEXT NOT NULL,
 format TEXT NOT NULL, language TEXT NOT NULL, question_id TEXT NOT NULL, object_ids_json TEXT NOT NULL,
 task_id TEXT, source_url TEXT NOT NULL, original_filename TEXT, version_relation_json TEXT NOT NULL,
 title TEXT NOT NULL, received_at TEXT NOT NULL, UNIQUE(sha256,source_item_id,question_id));
CREATE INDEX IF NOT EXISTS product_documents_company_category ON product_documents(company_id,first_category,format,language);
CREATE INDEX IF NOT EXISTS product_documents_question ON product_documents(question_id,company_id,first_category);
'''
def now(): return datetime.now(timezone.utc).isoformat()
def encoded(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def hash_file(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def data_root(): return Path(os.environ.get('READER_DATA_ROOT', Path.home()/'.local/share/inresearch.ai'))
def error_code(e):
    return ('http_'+str(e.code)) if isinstance(e,HTTPError) else str(e)[:100] if isinstance(e,ValueError) and str(e).replace('_','').isalnum() else type(e).__name__

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None

class Collector:
    def __init__(self, root):
        self.root=Path(root); self.home=self.root/'acquisition'; self.home.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.home/'catalog.sqlite',timeout=30)
        self.db.row_factory=sqlite3.Row
        self.db.executescript(SCHEMA)
    def close(self): self.db.close()
    def item(self, source, key, kind, url, title, metadata, state='discovered', question=None):
        if source not in SOURCES: raise ValueError('unknown_source')
        if question and question not in {q['id'] for q in json.loads((ROOT/'framework/research_questions.json').read_text())['records']}: raise ValueError('unknown_question')
        ident=hashlib.sha256(encoded([source,str(key)])).hexdigest()
        stamp=now()
        with self.db:
            self.db.execute('INSERT INTO items VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,metadata=excluded.metadata,url=excluded.url,updated=excluded.updated',
                (ident,source,str(key),kind,state,url,title,encoded(metadata).decode(),stamp,stamp))
            if question: self.db.execute('INSERT OR IGNORE INTO links VALUES(?,?,?)',(ident,question,'top_down'))
        return ident
    def archive(self, ident, body, suffix, request):
        sha=hashlib.sha256(body).hexdigest(); rel='acquisition/blobs/'+sha[:2]+'/'+sha+suffix
        dest=self.root/rel; dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():
            if hashlib.sha256(dest.read_bytes()).hexdigest()!=sha: raise ValueError('archive_integrity')
        else:
            fd,tmp=tempfile.mkstemp(prefix='.partial-',dir=dest.parent)
            try:
                with os.fdopen(fd,'wb') as f: f.write(body);f.flush();os.fsync(f.fileno())
                os.replace(tmp,dest)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO observations(item_id,sha256,relative_path,observed_at,request_json) VALUES(?,?,?,?,?)',(ident,sha,rel,now(),encoded(request).decode()))
            self.db.execute('UPDATE items SET state=?,updated=? WHERE id=?',('archived',now(),ident))
        return sha
    def archive_file(self, ident, source, suffix, request):
        """Stream an already-verified supplier file into the shared SHA blob store."""
        source = Path(source)
        sha = hashlib.sha256()
        with source.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(block)
        hexdigest = sha.hexdigest()
        rel = 'acquisition/blobs/' + hexdigest[:2] + '/' + hexdigest + suffix
        dest = self.root / rel
        dest.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if dest.exists():
            if hash_file(dest) != hexdigest:
                raise ValueError('archive_integrity')
        else:
            fd, tmp = tempfile.mkstemp(prefix='.partial-', dir=dest.parent)
            try:
                with os.fdopen(fd, 'wb') as output, source.open('rb') as incoming:
                    shutil.copyfileobj(incoming, output, 1024 * 1024)
                    output.flush(); os.fsync(output.fileno())
                if hash_file(Path(tmp)) != hexdigest:
                    raise ValueError('archive_integrity')
                os.replace(tmp, dest)
                os.chmod(dest, 0o400)
            finally:
                if os.path.exists(tmp): os.unlink(tmp)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO observations(item_id,sha256,relative_path,observed_at,request_json) VALUES(?,?,?,?,?)',
                (ident, hexdigest, rel, now(), encoded(request).decode()))
            self.db.execute('UPDATE items SET state=?,updated=? WHERE id=?', ('archived', now(), ident))
        return hexdigest
    def run(self,source,fn):
        with self.db: rid=self.db.execute('INSERT INTO runs(source,started,status) VALUES(?,?,?)',(source,now(),'running')).lastrowid
        try:
            count=fn()
        except Exception as e:
            code=error_code(e)
            with self.db:self.db.execute('UPDATE runs SET finished=?,status=?,error_code=? WHERE id=?',(now(),'failed',code[:100],rid))
            raise
        with self.db:self.db.execute('UPDATE runs SET finished=?,status=?,count=? WHERE id=?',(now(),'success',count,rid))
        return count

def fetch(url, data=None, token=None):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.hostname not in {'data.sec.gov','www.sec.gov','console.vast.ai'} or parsed.username or parsed.password: raise ValueError('source_not_allowed')
    headers={'User-Agent':os.environ.get('SEC_USER_AGENT','InResearch research niuroumiantt@gmail.com'),'Accept':'application/json,text/html'}
    if token:headers['Authorization']='Bearer '+token
    if data is not None:headers['Content-Type']='application/json'
    # No automatic redirection, cookie jar, or credential-bearing URL.
    with build_opener(NoRedirect).open(Request(url,data=encoded(data) if data is not None else None,headers=headers),timeout=40) as response:
        body=response.read(32*1024*1024+1)
        if len(body)>32*1024*1024:raise ValueError('response_too_large')
        return body

def export_news(db_path,days=7,limit=2000):
    """Project public article fields only. Never export the shared identity/session tables."""
    path=Path(db_path).resolve()
    con=sqlite3.connect(path.as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    try:
        cutoff=int((time.time()-days*86400)*1000)
        rows=con.execute('''SELECT id,guid,url,title,title_zh,title_zh_profile,domain,publisher,published_at,first_seen_at,lang,cluster_id,relevance,genre FROM articles
        WHERE relevant=1 AND hidden_at IS NULL AND (published_at>=? OR first_seen_at>=?)
        ORDER BY first_seen_at DESC,id DESC LIMIT ?''',(cutoff,cutoff,limit+1)).fetchall()
        return {'schema':'inews-research-signals-v1','exported_at':now(),'window_days':days,'truncated':len(rows)>limit,
                'scope':'bounded recent relevant, non-hidden article metadata; not full text or full history',
                'articles':[dict(row) for row in rows[:limit]]}
    finally:con.close()

def import_news(c,payload,question=None):
    verified = isinstance(payload, VerifiedNewsProjection)
    if verified:
        if payload.proof is not _DIRECT_FEED_PROOF:
            raise ValueError('unverified_news_projection')
        payload = json.loads(payload.payload_json)
    if payload.get('schema')!='inews-research-signals-v1' or not isinstance(payload.get('articles'),list):raise ValueError('invalid_news_export')
    if len(payload['articles'])>10000:raise ValueError('news_batch_too_large')
    terms=build_terms(ROOT);count=0
    for row in payload['articles']:
        title=row.get('title',''); text=title+' '+(row.get('title_zh') or '')
        if not isinstance(title,str) or not row.get('guid') or not row.get('url'):raise ValueError('invalid_news_row')
        matches=sorted({eid for eid,_,term,pat in terms if pat.search(text) and (term.lower() not in AMBIGUOUS or ENTITY_CONTEXT.search(text))})
        # Industry keywords also retain supply-chain leads without a known company match.
        if not verified and not matches and not ENTITY_CONTEXT.search(text) and not classify(row):continue
        allowed={key:row.get(key) for key in ('id','guid','url','title','title_zh','title_zh_profile','domain','publisher','published_at','first_seen_at','lang','cluster_id','relevance','genre')}
        if verified:
            allowed['topics'] = row['topics']
        meta={**allowed,'matched_entity_ids':matches,'match_status':'candidate','content_scope':'headline_only','exported_at':payload.get('exported_at'),'export_truncated':payload.get('truncated',False)}
        if verified:
            meta['upstream_selection'] = {
                'url': INEWS_DATACENTER_URL, 'schema_version': 1,
                'verification': 'direct_https_feed_v1',
                'window': payload['upstream_window'],
                'verified_at': payload['exported_at'],
            }
        ident=c.item('inews',row['guid'],'news_lead',row['url'],title,meta,question=question)
        request={'method':'inews_metadata_export','schema':payload['schema']}
        if verified:request['upstream_selection']=meta['upstream_selection']
        c.archive(ident,encoded(allowed),'.json',request);count+=1
    # Commit the current bounded visibility window only after the whole import succeeds.
    from inresearch.storage.files import write_json as atomic_json
    atomic_json(c.home/'news-window.json', {'exported_at':payload.get('exported_at'),
        'truncated':payload.get('truncated',False), 'guids':[r['guid'] for r in payload['articles']]})
    return count

def sec(c,company,limit=1,question=None):
    companies=json.loads((ROOT/'data/companies.json').read_text())['records']
    target=next((x for x in companies if x['company_id']==company and x.get('cik')),None)
    if not target:raise ValueError('company_cik_missing')
    cik=str(int(target['cik'])).zfill(10);url='https://data.sec.gov/submissions/CIK'+cik+'.json'
    body=fetch(url);data=json.loads(body)
    if str(int(data['cik'])).zfill(10)!=cik:raise ValueError('cik_mismatch')
    ident=c.item('sec',cik+':submissions','filing_index',url,target['name'],{'company_id':company,'cik':cik},question=question)
    c.archive(ident,body,'.json',{'url':url,'method':'GET'})
    recent=data.get('filings',{}).get('recent',{});count=0
    for form,accession,doc,date in zip(recent.get('form',[]),recent.get('accessionNumber',[]),recent.get('primaryDocument',[]),recent.get('filingDate',[])):
        if form not in {'10-K','10-Q','8-K','20-F','6-K','10-K/A','10-Q/A','8-K/A','20-F/A','6-K/A'}:continue
        link=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-", "")}/{quote(doc,safe="")}'
        fid=c.item('sec',cik+':'+accession+':'+doc,'filing_document',link,company+' '+form+' '+date,
            {'company_id':company,'cik':cik,'accession':accession,'primary_document':doc,'form':form,'filing_date':date,'scope':'primary_document_only; exhibits and historical pages not yet fetched'},question=question)
        if count<limit:
            # An accession/document is immutable in this phase; amendments have distinct IDs.
            seen=c.db.execute('SELECT 1 FROM observations WHERE item_id=?',(fid,)).fetchone()
            if not seen:
                time.sleep(.6)
                raw=fetch(link)
                if not raw.strip():raise ValueError('empty_filing')
                suffix=Path(doc).suffix.lower()
                suffix='.html' if suffix in {'.htm','.html'} else suffix if suffix in {'.pdf','.txt','.xml'} else '.bin'
                c.archive(fid,raw,suffix,{'url':link,'method':'GET'})
            count+=1
    return count

def summarize_offers(offers,gpu):
    accepted=[];seen=set();rejected=0
    for row in offers:
        value=row.get('dph_total');key=row.get('id',row.get('ask_contract_id'))
        if key is None or key in seen or row.get('gpu_name')!=gpu or row.get('num_gpus')!=1 or row.get('rentable') is not True or row.get('rented') is not False or row.get('is_bid') is True or isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0:
            rejected+=1;continue
        seen.add(key);accepted.append(value)
    return {'sample_n':len(accepted),'rejected_n':rejected,'median':statistics.median(accepted) if accepted else None,
            'unit':'USD/offer-hour','rental_type':'on-demand','gpu_count':1,'gpu_name':gpu,
            'scope':'lowest-price bounded offers; not a market-wide index, transaction price, or interruptible price',
            'price_field':'dph_total','cost_boundary':'listed offer hourly total; preserve raw storage/bandwidth charges separately','acceptance':'candidate'}

def gpu(c,gpu_name,question=None):
    token=os.environ.get('VAST_API_KEY','').strip()
    if not token:raise ValueError('vast_api_key_missing')
    query={'gpu_name':{'eq':gpu_name},'num_gpus':{'eq':1},'rentable':{'eq':True},'rented':{'eq':False},'type':'on-demand','order':[['dph_total','asc']],'limit':20}
    url='https://console.vast.ai/api/v0/bundles';body=fetch(url,query,token);rows=json.loads(body).get('offers')
    if not isinstance(rows,list):raise ValueError('unexpected_offer_schema')
    summary=summarize_offers(rows,gpu_name)
    stamp=now();ident=c.item('gpu',gpu_name+':'+stamp,'quote_snapshot',url,gpu_name+' 按需报价',summary,question=question)
    c.archive(ident,body,'.json',{'url':url,'method':'POST','query':query,'recipe':'vast-ondemand-single-low20-v1'})
    if not summary['sample_n']:raise ValueError('no_valid_offers')
    return summary['sample_n']

def summary(root):
    path=Path(root)/'acquisition/catalog.sqlite'
    if not path.exists():return {'status':'not_initialized','sources':{}}
    con=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    try:
        sources={}
        for source in SOURCES:
            row=con.execute('SELECT started,finished,status,count,error_code FROM runs WHERE source=? ORDER BY id DESC LIMIT 1',(source,)).fetchone()
            sources[source]={'items':con.execute('SELECT count(*) FROM items WHERE source=?',(source,)).fetchone()[0],
                'last_run':dict(row) if row else None}
        from inresearch.adapters.news_projection import feed
        return {'status':'candidate_acquisition','sources':sources,'news_feed':feed(root),'note':'新闻标题线索；全文翻译、SEC/GPU 周期采集与自动采用尚未开启。'}
    finally:con.close()

def product_documents(root, *, company_id=None, category=None, question_id=None,
                      format=None, language=None, limit=50, offset=0):
    """Indexed cross-company/product/research-question view of Fetchspec candidates."""
    if type(limit) is not int or not 1 <= limit <= 200 or type(offset) is not int or not 0 <= offset <= 1000000:
        raise ValueError('invalid_product_document_page')
    path=Path(root)/'acquisition/catalog.sqlite'
    if not path.is_file():return {'status':'not_initialized','total':0,'records':[],'acceptance':'candidate'}
    clauses=[];params=[]
    for column,value in (('company_id',company_id),('first_category',category),('question_id',question_id),('format',format),('language',language)):
        if value:
            if not isinstance(value,str) or len(value)>160:raise ValueError('invalid_product_document_filter')
            clauses.append(column+'=?');params.append(value)
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    con=sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=3);con.row_factory=sqlite3.Row
    try:
        try:
            total=con.execute('SELECT COUNT(*) FROM product_documents'+where,params).fetchone()[0]
            rows=con.execute('''SELECT sha256,source_item_id,company_id,first_category,categories_json,format,language,
            question_id,object_ids_json,task_id,source_url,original_filename,version_relation_json,title,received_at
            FROM product_documents'''+where+' ORDER BY received_at DESC,sha256 LIMIT ? OFFSET ?',
            (*params,limit,offset)).fetchall()
        except sqlite3.OperationalError:
            return {'status':'not_initialized','total':0,'records':[],'acceptance':'candidate'}
        return {'status':'available','total':total,'limit':limit,'offset':offset,
            'filters':{'company_id':company_id,'category':category,'question_id':question_id,'format':format,'language':language},
            'records':[{'sha256':r['sha256'],'source_item_id':r['source_item_id'],'company_id':r['company_id'],
                'first_category':r['first_category'],'categories':json.loads(r['categories_json']),
                'format':r['format'],'language':r['language'],'question_id':r['question_id'] or None,
                'object_ids':json.loads(r['object_ids_json']),'task_id':r['task_id'],'source_url':r['source_url'],
                'original_filename':r['original_filename'],'version_relation':json.loads(r['version_relation_json']),
                'title':r['title'],'received_at':r['received_at'],'acceptance':'candidate'} for r in rows]}
    finally:con.close()

def main():
    os.umask(0o077)
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data-root',type=Path,default=data_root());sub=p.add_subparsers(dest='command',required=True)
    n=sub.add_parser('export-news');n.add_argument('--db',required=True);n.add_argument('--days',type=int,default=7);n.add_argument('--limit',type=int,default=2000)
    n=sub.add_parser('news');n.add_argument('--input',type=Path,required=True);n.add_argument('--question')
    s=sub.add_parser('sec');s.add_argument('--company',required=True);s.add_argument('--limit',type=int,default=1);s.add_argument('--question')
    g=sub.add_parser('gpu');g.add_argument('--gpu',default='H100 SXM');g.add_argument('--question')
    d=sub.add_parser('product-documents',help='search received Fetchspec documents by company/product/research scope')
    d.add_argument('--company-id');d.add_argument('--category');d.add_argument('--question-id');d.add_argument('--format');d.add_argument('--language')
    d.add_argument('--limit',type=int,default=50);d.add_argument('--offset',type=int,default=0)
    sub.add_parser('status');a=p.parse_args()
    if a.command=='export-news':
        if not 1<=a.days<=90 or not 1<=a.limit<=10000:p.error('bounded days/limit required')
        print(encoded(export_news(a.db,a.days,a.limit)).decode());return 0
    if a.command=='status':print(encoded(summary(a.data_root)).decode());return 0
    if a.command=='product-documents':
        print(encoded(product_documents(a.data_root,company_id=a.company_id,category=a.category,
            question_id=a.question_id,format=a.format,language=a.language,limit=a.limit,offset=a.offset)).decode());return 0
    if a.command=='sec' and not 0<=a.limit<=10:p.error('SEC primary document limit must be 0..10')
    c=Collector(a.data_root)
    try:
        if a.command=='news':count=c.run('inews',lambda:import_news(c,json.loads(a.input.read_text()),a.question))
        elif a.command=='sec':count=c.run('sec',lambda:sec(c,a.company,a.limit,a.question))
        else:count=c.run('gpu',lambda:gpu(c,a.gpu,a.question))
        print(json.dumps({'status':'success','source':a.command,'processed':count,'acceptance':'candidate'}));return 0
    except Exception as e:
        print(json.dumps({'status':'failed','source':a.command,'error_code':error_code(e),'detail':'See acquisition ledger; no core facts written.'}));return 1
    finally:c.close()
if __name__=='__main__':raise SystemExit(main())
