#!/usr/bin/env python3
"""Hourly, bounded public article projection into Spark's permanent acquisition ledger."""
import json
import math
import os
import re
import time
from datetime import datetime
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener
from inresearch.adapters.acquisition import Collector, NoRedirect, data_root, now, import_news, INEWS_DATACENTER_URL, VerifiedNewsProjection, _DIRECT_FEED_PROOF, encoded
from inresearch.knowledge.news_policy import EVENT_TYPES, RESEARCH_ANGLES, FEED_V2_FIELDS, OBJECT_ID, skeleton_ids
from inresearch.paths import project_root

URL=INEWS_DATACENTER_URL
WEEK_MS=7*86400000


def article_id(value):
    return (type(value) is int and 0 < value <= 9007199254740991
            or isinstance(value,str) and bool(re.fullmatch(r'[1-9][0-9]{0,15}',value))
            and int(value) <= 9007199254740991)


def public_url(value):
    if not isinstance(value,str) or len(value)>8192 or re.search(r'[\x00-\x20]',value): return False
    try:
        url=urlsplit(value)
        return url.scheme in {'https','http'} and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        return False


def validate_page(page, expected_window, known_ids=None):
    if not isinstance(page,dict) or type(page.get('schema_version')) is not int or page['schema_version']!=1 or not isinstance(page.get('items'),list) or len(page['items'])>100:
        raise ValueError('invalid_news_feed')
    window=page.get('window')
    if (not isinstance(window,dict) or any(type(window.get(k)) is not int for k in ('since','until'))
            or not 0 < window['since'] < window['until']
            or window['until']-window['since']>WEEK_MS
            or not time.time()*1000-86400000 <= window['until'] <= time.time()*1000+300000
            or expected_window is not None and window!=expected_window):
        raise ValueError('invalid_news_window')
    try:
        stamp=datetime.fromisoformat(page['generated_at'].replace('Z','+00:00'))
        if stamp.tzinfo is None or not math.isfinite(stamp.timestamp()): raise ValueError()
    except (KeyError,AttributeError,ValueError,TypeError,OverflowError):
        raise ValueError('invalid_news_timestamp') from None
    for item in page['items']:
        if (not isinstance(item,dict) or not article_id(item.get('id'))
                or not isinstance(item.get('title'),str) or not item['title'].strip() or len(item['title'])>20000
                or not public_url(item.get('url'))
                or type(item.get('published_at')) is not int
                or not window['since'] <= item['published_at'] <= window['until']):
            raise ValueError('invalid_news_item')
        for key in ('guid','title_zh','title_zh_profile','domain','publisher'):
            value=item.get(key)
            if value is not None and (not isinstance(value,str) or len(value)>20000 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]',value)):
                raise ValueError('invalid_news_item')
        if item.get('guid') is not None and (not item['guid'].strip() or len(item['guid'])>512):raise ValueError('invalid_news_guid')
        if item.get('cluster_id') is not None and not article_id(item['cluster_id']):raise ValueError('invalid_news_item')
        topics=item.get('topics')
        if (not isinstance(topics,list) or not 1<=len(topics)<=32
                or any(not isinstance(t,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}',t) for t in topics)):
            raise ValueError('invalid_news_topics')
        validate_v2_fields(item, known_ids)
    return window


def validate_v2_fields(item, known_ids=None):
    """Optional additive fields; absent or null is fine, a wrong shape rejects the page.
    object_ids: shape errors reject; IDs outside the current skeleton are dropped one by one (known_ids given), never adopted."""
    event_type=item.get('event_type')
    if event_type is not None and event_type not in EVENT_TYPES: raise ValueError('invalid_news_event_type')
    angle=item.get('research_angle')
    if angle is not None and angle not in RESEARCH_ANGLES: raise ValueError('invalid_news_research_angle')
    layers=item.get('layer_tags')
    if layers is not None and (not isinstance(layers,list) or len(layers)>5
            or any(type(l) is not int or not 1<=l<=5 for l in layers) or len(set(layers))!=len(layers)):
        raise ValueError('invalid_news_layer_tags')
    pointer=item.get('origin_pointer')
    if pointer is not None and not public_url(pointer): raise ValueError('invalid_news_origin_pointer')
    pick=item.get('editorial_pick')
    if pick is not None and type(pick) is not bool: raise ValueError('invalid_news_editorial_pick')
    ids=item.get('object_ids')
    if ids is not None:
        if (not isinstance(ids,list) or len(ids)>32 or any(not isinstance(i,str) or not OBJECT_ID.fullmatch(i) for i in ids)
                or len(set(ids))!=len(ids)):
            raise ValueError('invalid_news_object_ids')
        if known_ids is not None:
            item['object_ids']=[i for i in ids if i in known_ids]

def projection():
    articles=[]; seen=set(); cursors=set(); cursor=None; window=None; guids={}
    known_ids=skeleton_ids(project_root())
    for _ in range(100):
        params={'hours':168,'limit':100}
        if cursor: params['cursor']=cursor
        request_url=URL+'?'+urlencode(params)
        with build_opener(NoRedirect).open(Request(request_url, headers={'User-Agent':'inresearch.ai-news-sync/1.0','Accept':'application/json'}),timeout=40) as response:
            if response.status!=200 or response.geturl()!=request_url:raise ValueError('unverified_news_origin')
            body=response.read(4*1024*1024+1)
        if len(body)>4*1024*1024: raise ValueError('news_response_too_large')
        page=json.loads(body)
        window=validate_page(page,window,known_ids)
        for item in page['items']:
            ident=str(item['id'])
            guid=item.get('guid') or 'inews:'+ident
            if guid in guids and guids[guid]!=ident:raise ValueError('conflicting_news_guid')
            guids[guid]=ident
            if ident in seen: continue
            seen.add(ident)
            row={k:item.get(k) for k in ('id','title','title_zh','title_zh_profile','url','domain','publisher','published_at','cluster_id','topics')+FEED_V2_FIELDS}
            # Same article ID identity as historical export when GUID is unavailable.
            row['guid']=guid
            articles.append(row)
        cursor=page.get('next_cursor')
        if cursor is None: break
        if not isinstance(cursor,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,4096}',cursor) or cursor in cursors: raise ValueError('invalid_news_cursor')
        cursors.add(cursor)
    if cursor is not None:raise ValueError('news_window_truncated')
    payload={'schema':'inews-research-signals-v1','exported_at':now(),'window_days':7,
             'upstream_window':window,'truncated':False,'articles':articles}
    return VerifiedNewsProjection(encoded(payload),_DIRECT_FEED_PROOF)

def main():
    os.umask(0o077)
    c=Collector(data_root())
    try:
        count=c.run('inews',lambda:import_news(c,projection()))
        print(json.dumps({'status':'success','items':count}))
    finally:c.close()

if __name__=='__main__':main()
