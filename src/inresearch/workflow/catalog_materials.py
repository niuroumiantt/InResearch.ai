"""Public original links, indexed by legacy ledger content identity.

PDF/Office bytes are not admitted or extracted by this index. Parent-page links
carry verified HTML receipts; unassigned official documents stay searchable.
"""
import json
from pathlib import Path
import re
import sqlite3
from urllib.parse import unquote, urlsplit


def validate_materials(items, company, source_keys):
    from .product_catalog import official
    if not isinstance(items,list) or len(items)>20000:
        raise ValueError('invalid material index')
    seen = set()
    for d in items:
        if not isinstance(d,dict) or not re.fullmatch('[0-9a-f]{64}',d.get('id','')) or d['id'] in seen:
            raise ValueError('invalid/repeated material identity')
        seen.add(d['id'])
        if d.get('format') not in {'pdf','doc','docx','docm','xls','xlsx','xlsm','xlsb','ppt','pptx','pptm'}:
            raise ValueError('invalid material format')
        if not isinstance(d.get('urls'),list) or not d['urls'] or len(d['urls'])>1000 or any(not official(u,company) for u in d['urls']):
            raise ValueError('material must name official original links')
        if not isinstance(d.get('links'),list) or len(d['links'])>10000:
            raise ValueError('invalid material parent links')
        for link in d['links']:
            if not isinstance(link,dict) or link.get('url') not in d['urls'] or not isinstance(link.get('label'),str) or len(link['label'])>500:
                raise ValueError('invalid material relationship')
            if (link.get('source_sha256'),link.get('source_url')) not in source_keys:
                raise ValueError('material parent HTML receipt missing')
            if not isinstance(link.get('product_id'),str):
                raise ValueError('material product identity missing')


def check_material_products(items, ids):
    if any(link['product_id'] not in ids for d in items for link in d['links']):
        raise ValueError('material refers to an unknown current product')


def store_materials(db, items):
    for d in items:
        old = db.execute('SELECT payload FROM materials WHERE id=?',(d['id'],)).fetchone()
        merged = json.loads(old[0]) if old else {'id':d['id'],'format':d['format'],'urls':[],'links':[]}
        if merged['format'] != d['format']:
            raise ValueError('material format conflicts for one content identity')
        merged['urls'] = sorted(set(merged['urls'] + d['urls']))
        merged['links'] += [l for l in d['links'] if l not in merged['links']]
        merged['basis'] = 'source_link_index_not_document_extraction'
        db.execute('INSERT OR REPLACE INTO materials VALUES(?,?)',(d['id'],json.dumps(merged,ensure_ascii=False)))


def query(root, company, q='', offset=0, limit=50):
    from .product_catalog import database, company_config
    company_config(company)
    path = database(root,company)
    empty = {'available':False,'company_id':company,'total':0,'matched':0,'items':[],
             'basis':'source_link_index_not_document_extraction'}
    if not Path(path).is_file():
        return empty
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='materials'").fetchone():
            return empty
        offset,limit = max(0,int(offset)),min(100,max(1,int(limit)))
        records = []
        for row in db.execute('SELECT payload FROM materials ORDER BY id'):
            d = json.loads(row[0])
            d['name'] = unquote(urlsplit(d['urls'][0]).path.rsplit('/',1)[-1]) or d['id'][:12]
            records.append(d)
        from .catalog_ownership import conflict
        names, excluded_ids = {}, set()
        for pid,name,url,product_url,owner in db.execute("""SELECT id,json_extract(payload,'$.name'),
                json_extract(payload,'$.source_url'),json_extract(payload,'$.product_url'),
                json_extract(payload,'$.company_id') FROM products
                WHERE run_id=(SELECT id FROM runs ORDER BY generated DESC LIMIT 1)"""):
            if not conflict({'source_url':url,'product_url':product_url,'company_id':owner}, company):
                names[pid] = name
            else:
                excluded_ids.add(pid)
        for d in records:
            d['links'] = [l for l in d['links'] if l['product_id'] not in excluded_ids]
        matched = [d for d in records if not q or q.casefold() in json.dumps(d,ensure_ascii=False).casefold()
                   or any(q.casefold() in names.get(l['product_id'],'').casefold() for l in d['links'])]
        page = []
        for d in matched[offset:offset+limit]:
            links = list({l['product_id']:l for l in d['links']}.values())
            page.append({**d,'urls':d['urls'][:4],'link_count':len(links),
                         'links':[{**l,'product_name':names.get(l['product_id'],''),'current_product':l['product_id'] in names} for l in links[:4]]})
        return {**empty,'available':True,'total':len(records),'matched':len(matched),
                'unassigned':sum(not d['links'] for d in records),'offset':offset,'limit':limit,'items':page}
    finally:
        db.close()
