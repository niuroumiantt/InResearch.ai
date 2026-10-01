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
from inresearch.knowledge.news_policy import EVENT_TYPES, RESEARCH_ANGLES, FEED_V2_FIELDS, OBJECT_ID, TARGET_ID, skeleton_ids, target_ids
from inresearch.paths import project_root

URL=INEWS_DATACENTER_URL
CHANGES_URL=INEWS_DATACENTER_URL+'/changes'
# 增量为主，每 6 小时整窗重拉一次校正（漏掉的变更、窗口边界、members 文件丢失都由整窗兜底）。
FULL_EVERY_MS=6*3600*1000
STATE='news-sync-state.json'
WEEK_MS=7*86400000
# 单页读超时（2026-09-29 由 40 秒放到 120 秒）：Spark 实测 7 天窗口首页 2.6–7.2 秒且波动大，深分页更慢，40 秒偶发撞上。
# 整次同步仍受 systemd TimeoutStartSec=1800 约束；深分页本身的快慢是 inews 侧的事。
READ_TIMEOUT=int(os.environ.get('INRESEARCH_NEWS_READ_TIMEOUT','120'))


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


def validate_page(page, expected_window, known_ids=None, known_targets=None):
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
        validate_item(item, window, known_ids, known_targets)
    return window


def validate_item(item, window, known_ids=None, known_targets=None):
    """One readable feed item; shared by the full window and the incremental changes."""
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
    validate_v2_fields(item, known_ids, known_targets)


def validate_v2_fields(item, known_ids=None, known_targets=None):
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
    targets=item.get('target_ids')
    if targets is not None:
        if (not isinstance(targets,list) or len(targets)>32 or any(not isinstance(t,str) or not TARGET_ID.fullmatch(t) for t in targets)
                or len(set(targets))!=len(targets)):
            raise ValueError('invalid_news_target_ids')
        if known_targets is not None:
            item['target_ids']=[t for t in targets if t in known_targets]

def fetch_page(base, params):
    request_url=base+'?'+urlencode(params)
    with build_opener(NoRedirect).open(Request(request_url, headers={'User-Agent':'inresearch.ai-news-sync/1.0','Accept':'application/json'}),timeout=READ_TIMEOUT) as response:
        if response.status!=200 or response.geturl()!=request_url:raise ValueError('unverified_news_origin')
        body=response.read(4*1024*1024+1)
    if len(body)>4*1024*1024: raise ValueError('news_response_too_large')
    return json.loads(body)


def next_cursor(page, cursors):
    cursor=page.get('next_cursor')
    if cursor is None: return None
    if not isinstance(cursor,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,4096}',cursor) or cursor in cursors: raise ValueError('invalid_news_cursor')
    cursors.add(cursor)
    return cursor


def collect(item, articles, seen, guids):
    ident=str(item['id'])
    guid=item.get('guid') or 'inews:'+ident
    if guid in guids and guids[guid]!=ident:raise ValueError('conflicting_news_guid')
    guids[guid]=ident
    if ident in seen: return
    seen.add(ident)
    row={k:item.get(k) for k in ('id','title','title_zh','title_zh_profile','url','domain','publisher','published_at','cluster_id','topics')+FEED_V2_FIELDS}
    # Same article ID identity as historical export when GUID is unavailable.
    row['guid']=guid
    articles.append(row)


def verified(articles, window):
    payload={'schema':'inews-research-signals-v1','exported_at':now(),'window_days':7,
             'upstream_window':window,'truncated':False,'articles':articles}
    return VerifiedNewsProjection(encoded(payload),_DIRECT_FEED_PROOF)


def projection():
    articles=[]; seen=set(); cursors=set(); cursor=None; window=None; guids={}
    known_ids=skeleton_ids(project_root()); known_targets=target_ids(project_root())
    for _ in range(100):
        params={'hours':168,'limit':100}
        if cursor: params['cursor']=cursor
        page=fetch_page(URL,params)
        window=validate_page(page,window,known_ids,known_targets)
        for item in page['items']: collect(item,articles,seen,guids)
        cursor=next_cursor(page,cursors)
        if cursor is None: break
    if cursor is not None:raise ValueError('news_window_truncated')
    return verified(articles,window)


def changes(since):
    """增量（2026-10-01）：since 之后可见状态变了的卡。可读的照全量同样校验；tombstone 只收文章号；
    发布时间已出 7 天窗的跳过（全量窗本来也不含它们）。返回 (projection, 撤下的文章号, 下次的 since)。"""
    articles=[]; seen=set(); cursors=set(); cursor=None; guids={}; withdrawn=set(); fixed=None
    known_ids=skeleton_ids(project_root()); known_targets=target_ids(project_root())
    for _ in range(100):
        params={'since':since,'limit':100}
        if cursor: params['cursor']=cursor
        page=fetch_page(CHANGES_URL,params)
        if (not isinstance(page,dict) or page.get('schema_version')!=1 or not isinstance(page.get('items'),list) or len(page['items'])>100
                or type(page.get('since')) is not int or type(page.get('until')) is not int or page['since']!=since
                or not since<page['until']<=time.time()*1000+300000 or fixed is not None and page['until']!=fixed):
            raise ValueError('invalid_news_changes')
        fixed=page['until']
        window={'since':int(time.time()*1000)-WEEK_MS,'until':fixed+300000}
        for item in page['items']:
            if isinstance(item,dict) and item.get('withdrawn') is True:
                if not article_id(item.get('id')): raise ValueError('invalid_news_tombstone')
                withdrawn.add(str(item['id'])); continue
            if isinstance(item,dict) and type(item.get('published_at')) is int and item['published_at']<window['since']: continue
            validate_item(item,window,known_ids,known_targets)
            withdrawn.discard(str(item['id']))
            collect(item,articles,seen,guids)
        cursor=next_cursor(page,cursors)
        if cursor is None: break
    if cursor is not None:raise ValueError('news_changes_truncated')
    nxt=page.get('next_since')
    if type(nxt) is not int or nxt!=fixed: raise ValueError('invalid_news_next_since')
    return verified(articles,{'since':since,'until':fixed}), withdrawn, nxt

def sync(c, clock=None):
    """一次同步：状态新鲜就拉增量并合并进现行窗口，否则整窗重拉。返回 (模式, 条数)。"""
    from inresearch.storage.files import write_json as atomic_json
    at=int(clock if clock is not None else time.time()*1000)
    state_path=c.home/STATE; window_path=c.home/'news-window.json'
    try: state=json.loads(state_path.read_text())
    except (OSError,ValueError): state=None
    fresh=(isinstance(state,dict) and type(state.get('next_since')) is int and type(state.get('full_at')) is int
           and at-state['full_at']<FULL_EVERY_MS and at-state['next_since']<23*3600*1000 and window_path.exists())
    if fresh:
        try:
            projection_, withdrawn, nxt = changes(state['next_since'])
            count=c.run('inews',lambda:import_news(c,projection_,merge={'withdrawn':withdrawn,'now':at}))
        except (ValueError,OSError):
            # 增量不成（上游拒收 since、窗口文件缺 members、网络中断）就本轮整窗重拉，不卡在坏状态上。
            pass
        else:
            atomic_json(state_path,{'next_since':nxt,'full_at':state['full_at']})
            return 'changes',count
    projection_=projection()
    count=c.run('inews',lambda:import_news(c,projection_))
    until=json.loads(projection_.payload_json)['upstream_window']['until']
    atomic_json(state_path,{'next_since':until,'full_at':at})
    return 'full',count

def main():
    os.umask(0o077)
    c=Collector(data_root())
    try:
        mode,count=sync(c)
        print(json.dumps({'status':'success','mode':mode,'items':count}))
    finally:c.close()

if __name__=='__main__':main()
