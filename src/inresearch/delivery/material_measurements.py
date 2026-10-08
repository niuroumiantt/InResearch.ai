"""Small read-only measurements; directory scans are cached outside authority DBs."""
import json
import re
import sqlite3
import subprocess
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from inresearch.materials.artifacts import atomic_json

DIRECTORIES = ('raw-materials','originals','incoming','fulltext_ocr','offload',
               'extracted','fulltext','artifacts','pdf-text','backups')
DATABASES = {'reader':'catalog/catalog.sqlite','acquisition':'acquisition/catalog.sqlite',
             'review':'material-reviews/research-verification/queue.sqlite'}

def stamp():
    return datetime.now(timezone.utc).isoformat()

def database_sizes(path):
    if not path.is_file() or path.is_symlink():
        return {'state':'unavailable'}
    out={'state':'observed'}
    for key,suffix in [('file_bytes',''),('wal_bytes','-wal'),('shm_bytes','-shm')]:
        f=Path(str(path)+suffix);out[key]=f.stat().st_size if f.exists() else 0
    try:
        with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
            out['index_bytes']=db.execute("SELECT COALESCE(SUM(pgsize),0) FROM dbstat WHERE name IN(SELECT name FROM sqlite_master WHERE type='index')").fetchone()[0]
    except sqlite3.Error:
        out['index_bytes']=None
    return out

def directory_sizes(data, cache_root=None, *, now=None):
    now=time.time() if now is None else now
    cache=Path(cache_root)/'material-directory-measurements.json' if cache_root else None
    old={}
    if cache and cache.is_file() and not cache.is_symlink():
        try:
            old=json.loads(cache.read_text())
            if not isinstance(old,dict):old={}
            if old.get('root')==str(data.resolve()) and 0<=now-old['sample_epoch']<3600:
                return {k:v for k,v in old.items() if k not in ('root','sample_epoch')}
        except (ValueError,KeyError,TypeError,OSError):
            pass
    try:
        result=subprocess.run(['du','-B1','--max-depth=1',str(data)],capture_output=True,
                              text=True,check=True,timeout=15)
        rows={}
        for line in result.stdout.splitlines():
            size,name=line.split('\t',1);path=Path(name)
            key='.' if path==data else path.relative_to(data).as_posix()
            rows[key]=int(size)
        out={'state':'observed','measured_at':stamp(),'allocated_bytes':rows['.'],
             'directories':{k:rows[k] for k in DIRECTORIES if k in rows},
             'other_bytes':rows['.']-sum(rows.get(k,0) for k in DIRECTORIES)}
        if out['other_bytes']<0:
            raise ValueError('inconsistent_directory_allocation')
        if cache:
            try:atomic_json(cache,{**out,'root':str(data.resolve()),'sample_epoch':now})
            except OSError:pass
        return out
    except (OSError,ValueError,KeyError,TypeError,AttributeError,subprocess.SubprocessError):
        # Keep an explicitly stale last measurement; failure never becomes zero.
        if old.get('root')==str(data.resolve()) and old.get('state')=='observed':
            return {**{k:v for k,v in old.items() if k not in ('root','sample_epoch')},
                    'state':'stale','error':'directory_measurement_failed'}
        return {'state':'unavailable','error':'directory_measurement_failed'}

def spark_snapshot(conn,data,cache_root=None):
    result={'schema_version':1,'measured_at':stamp()}
    row=conn.execute('SELECT COUNT(*),COUNT(DISTINCT sha256),SUM(size_bytes) FROM documents').fetchone()
    result['catalog']={'files':row[0],'content_identities':row[1],'size_bytes':row[2] or 0,
        'types':[{'suffix':r[0],'files':r[1],'size_bytes':r[2]} for r in conn.execute('SELECT suffix,COUNT(*),SUM(size_bytes) FROM documents GROUP BY suffix ORDER BY COUNT(*) DESC')],
        'states':{r[0]:r[1] for r in conn.execute('SELECT state,COUNT(*) FROM current_readings GROUP BY state')}}
    result['archive']=directory_sizes(Path(data),cache_root)
    result['databases']={}
    for k,v in DATABASES.items():
        try:result['databases'][k]=database_sizes(Path(data)/v)
        except OSError:result['databases'][k]={'state':'unavailable'}
    return result

def sanitize(value):
    try:return _sanitize(value)
    except (AttributeError,ValueError,TypeError,KeyError,OverflowError):
        return {'state':'unavailable'}

def _sanitize(value):
    """The receiver admits aggregate counts, fixed directory names and dates only."""
    if not isinstance(value,dict) or value.get('schema_version')!=1:
        return {'state':'unavailable'}
    def number(v):
        return type(v) is int and 0<=v<2**63
    def dated(v):
        try:return datetime.fromisoformat(v.replace('Z','+00:00')).tzinfo is not None
        except (ValueError,TypeError,AttributeError):return False
    if not dated(value.get('measured_at')):return {'state':'unavailable'}
    out={'schema_version':1,'measured_at':value['measured_at']}
    catalog=value.get('catalog',{})
    if all(number(catalog.get(k)) for k in ('files','content_identities','size_bytes')):
        out['catalog']={k:catalog[k] for k in ('files','content_identities','size_bytes')}
        out['catalog']['states']={k:v for k,v in catalog.get('states',{}).items() if k in ('complete','queued','running','blocked','failed','rejected','ready') and number(v)}
        out['catalog']['types']=[{k:r[k] for k in ('suffix','files','size_bytes')} for r in catalog.get('types',[])[:100] if isinstance(r,dict) and isinstance(r.get('suffix'),str) and re.fullmatch(r'\.[a-z0-9]{1,20}|',r['suffix']) and number(r.get('files')) and number(r.get('size_bytes'))]
    archive=value.get('archive',{})
    if archive.get('state') in ('observed','stale') and dated(archive.get('measured_at')) and number(archive.get('allocated_bytes')):
        out['archive']={k:archive[k] for k in ('state','measured_at','allocated_bytes')}
        out['archive']['directories']={k:v for k,v in archive.get('directories',{}).items() if k in DIRECTORIES and number(v)}
        if number(archive.get('other_bytes')):out['archive']['other_bytes']=archive['other_bytes']
    else:out['archive']={'state':'unavailable'}
    out['databases']={}
    for key,v in value.get('databases',{}).items():
        if key not in DATABASES or not isinstance(v,dict):continue
        out['databases'][key]={'state':'observed' if v.get('state')=='observed' else 'unavailable',**{k:v[k] for k in ('file_bytes','wal_bytes','shm_bytes','index_bytes') if number(v.get(k))}}
    totals=value.get('candidates')
    if isinstance(totals,dict) and all(number(totals.get(k)) for k in ('documents','statements','evidence')):
        out['candidates']={k:totals[k] for k in ('documents','statements','evidence')}
        if totals.get('scope') in ('current_batch','export_selection','delivered_documents'):
            out['candidates']['scope']=totals['scope']
    return out

def sanitize_scope(value):
    """No executor configuration, original paths or model credentials in this view."""
    if not isinstance(value,dict):return None
    def number(v):return type(v) is int and 0<=v<2**63
    out={k:v for k,v in value.items() if k in ('documents','chunks_total','chunks_read',
        'complete_with_gaps','unread_gap_pages','skipped_image_pages','text_layer_empty_pages') and number(v)}
    for key,allowed in [('counts',('complete','queued','running','blocked','failed','ready','summarized')),
                        ('types',('.pdf','.html','.txt','.md','.docx'))]:
        rows=value.get(key)
        if isinstance(rows,dict):out[key]={k:v for k,v in rows.items() if k in allowed and number(v)}
    return out
