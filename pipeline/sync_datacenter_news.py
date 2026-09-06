#!/usr/bin/env python3
"""Hourly, bounded public article projection into Spark's permanent acquisition ledger."""
import json
import os
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from acquisition import Collector, NoRedirect, data_root, now, import_news

URL='https://inews.today/api/feeds/datacenter'

def projection():
    articles=[]; seen=set(); cursors=set(); cursor=None
    for _ in range(100):
        params={'hours':168,'limit':100}
        if cursor: params['cursor']=cursor
        with build_opener(NoRedirect).open(Request(URL+'?'+urlencode(params), headers={'User-Agent':'inresearch.ai-news-sync/1.0','Accept':'application/json'}),timeout=40) as response:
            body=response.read(4*1024*1024+1)
        if len(body)>4*1024*1024: raise ValueError('news_response_too_large')
        page=json.loads(body)
        if page.get('schema_version')!=1 or not isinstance(page.get('items'),list) or len(page['items'])>100: raise ValueError('invalid_news_feed')
        for item in page['items']:
            if not isinstance(item,dict) or not isinstance(item.get('id'),(int,str)) or not isinstance(item.get('title'),str) or not isinstance(item.get('url'),str): raise ValueError('invalid_news_item')
            guid=str(item['id'])
            if guid in seen: continue
            seen.add(guid)
            row={k:item.get(k) for k in ('id','title','title_zh','title_zh_profile','url','domain','publisher','published_at','cluster_id')}
            # Same article ID identity as historical export when GUID is unavailable.
            row['guid']=item.get('guid') or 'inews:'+guid
            articles.append(row)
        cursor=page.get('next_cursor')
        if not cursor: break
        if not isinstance(cursor,str) or len(cursor)>4096 or cursor in cursors: raise ValueError('invalid_news_cursor')
        cursors.add(cursor)
    return {'schema':'inews-research-signals-v1','exported_at':now(),'window_days':7,'truncated':bool(cursor),'articles':articles}

def main():
    os.umask(0o077)
    c=Collector(data_root())
    try:
        count=c.run('inews',lambda:import_news(c,projection()))
        print(json.dumps({'status':'success','items':count}))
    finally:c.close()

if __name__=='__main__':main()
