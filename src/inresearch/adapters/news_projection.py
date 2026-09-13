"""Conservative headline projection. A news lead is not adopted research evidence."""
import json
import sqlite3
import time
from pathlib import Path

from inresearch.knowledge.news_policy import POLICY, classify, trusted_news_selection

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
        rows=[]
        keys=list(ids)
        for offset in range(0,len(keys),500):
            batch=keys[offset:offset+500]
            rows.extend(con.execute("SELECT id,url,title,metadata FROM items WHERE source='inews' AND source_key IN ("+','.join('?' for _ in batch)+")",batch).fetchall())
        for row in rows:
            meta = json.loads(row['metadata'])
            if meta.get('guid') not in ids: continue
            # Only our fixed-origin fetch can create this ledger provenance.
            # File imports discard provenance flags and retain the legacy filter.
            trusted = trusted_news_selection(meta)
            category = '数据中心产业新闻' if trusted else classify(meta)
            if not category: continue
            stamp = meta.get('published_at') or meta.get('first_seen_at') or 0
            if not isinstance(stamp,(int,float)) or not time.time()*1000-7*86400000 <= stamp <= time.time()*1000+300000: continue
            selected.append({'id':row['id'], 'url':row['url'], 'title':row['title'],
                'title_zh':meta.get('title_zh'), 'translation_profile':meta.get('title_zh_profile'),
                'domain':meta.get('domain'), 'publisher':meta.get('publisher') or meta.get('domain'), 'published_at':stamp,
                'category':category, 'cluster_id':meta.get('cluster_id'),
                'topics':meta.get('topics', []) if trusted else []})
        seen = set()
        for item in sorted(selected,key=lambda r:r['published_at'],reverse=True):
            key = item['cluster_id'] or item['url']
            if key in seen: continue
            seen.add(key); result['items'].append(item)
            if len(result['items']) >= limit: break
        return result
    finally: con.close()
