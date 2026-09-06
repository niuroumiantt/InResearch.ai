"""Conservative headline projection. A news lead is not adopted research evidence."""
import json
import re
import sqlite3
import time
from pathlib import Path

POLICY = 'datacenter-headline-v1'
DIRECT = re.compile(r"data[ -]?cent(?:er|re)s?|colocation|hyperscal(?:e|er)|数据中心|资料中心|數據中心|智算中心|算力中心|机房|機房", re.I)
INFRA = re.compile(r"enterprise ssd|server (?:cpu|gpu|rack|memory)|gpu cluster|ai server|hbm[0-9e]*|infiniband|nvlink|cpo|co-packaged optics|800g|1\.6t|coolant distribution unit|direct.to.chip|液冷|冷板|企业级.?ssd|伺服器|服务器|光模块|算力租赁|算力基建|供配电", re.I)
CONTEXT = re.compile(r"server|gpu|compute|rack|hyperscal|data[ -]?cent|ai infrastructure|服务器|机柜|算力|数据中心|智算", re.I)
SUPPLY = re.compile(r"nand|dram|ssd|controller|power|grid|substation|cooling|ppa|transformer|电网|变电|供电|储能|冷却|控制器|存储", re.I)
NOISE = re.compile(r"gaming|geforce|playstation|xbox|smartphone|游戏|手机|笔记本|stocks to buy|price target|股价|目标价", re.I)

def classify(row):
    text = str(row.get('title') or '') + ' ' + str(row.get('title_zh') or '')
    if DIRECT.search(text): return '数据中心建设与运营'
    if NOISE.search(text): return None
    if INFRA.search(text): return '数据中心硬件与基础设施'
    if SUPPLY.search(text) and CONTEXT.search(text): return '数据中心供应链'
    return None

def feed(root, limit=80):
    path = Path(root)/'acquisition/catalog.sqlite'
    result = {'policy': POLICY, 'scope': 'headline_only', 'items': [], 'last_sync': None, 'status': 'not_initialized'}
    if not path.exists(): return result
    con = sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    try:
        run = con.execute("SELECT finished,status,error_code FROM runs WHERE source='inews' ORDER BY id DESC LIMIT 1").fetchone()
        if run: result.update(last_sync=run['finished'], status=run['status'], error_code=run['error_code'])
        # Only members of the latest successful source window are displayable;
        # disappearing/hidden upstream items stay archived but leave the live feed.
        window = Path(root)/'acquisition/news-window.json'
        if not window.exists():
            result['status'] = 'awaiting_sync'
            return result
        current = json.loads(window.read_text())
        ids = set(current['guids'])
        result.update(exported_at=current['exported_at'], truncated=current.get('truncated',False))
        selected = []
        for row in con.execute("SELECT id,url,title,metadata FROM items WHERE source='inews'"):
            meta = json.loads(row['metadata'])
            if meta.get('guid') not in ids: continue
            category = classify(meta)
            if not category: continue
            stamp = meta.get('published_at') or meta.get('first_seen_at') or 0
            if not isinstance(stamp,(int,float)) or not time.time()*1000-7*86400000 <= stamp <= time.time()*1000+300000: continue
            selected.append({'id':row['id'], 'url':row['url'], 'title':row['title'],
                'title_zh':meta.get('title_zh'), 'translation_profile':meta.get('title_zh_profile'),
                'publisher':meta.get('publisher') or meta.get('domain'), 'published_at':stamp,
                'category':category, 'cluster_id':meta.get('cluster_id')})
        seen = set()
        for item in sorted(selected,key=lambda r:r['published_at'],reverse=True):
            key = item['cluster_id'] or item['url']
            if key in seen: continue
            seen.add(key); result['items'].append(item)
            if len(result['items']) >= limit: break
        return result
    finally: con.close()
