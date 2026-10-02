"""Durable sales leads. News expiry never deletes a lead or adopts its capacity."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from inresearch.storage.files import locked, write_json
from inresearch.knowledge.industry import public_url

STATES = ('lead', 'reviewing', 'paused', 'cancelled', 'linked')


def read(home):
    path = Path(home)/'project-pipeline.json'
    if not path.exists(): return {'version': 1, 'records': {}}
    value = json.loads(path.read_text())
    if value.get('version') != 1 or not isinstance(value.get('records'), dict): raise ValueError('invalid pipeline')
    return value


def signals(item, sites):
    """Low-threshold observations, never an adopted capacity or construction fact."""
    title = ' '.join(str(item.get(k) or '') for k in ('title_zh', 'title'))
    text = title.casefold()
    relevant = item.get('event_type') in ('project_milestone', 'lease_contract') or (
        re.search(r'数据中心|算力中心|智算中心|data[ -]?cent(?:er|re)|campus', text) and
        re.search(r'拟|计划|建设|扩建|筹建|选址|消息|暂停|取消|审批|投运|plan|build|expand|report|construct|cancel|pause|review', text))
    if not relevant: return None
    stage = 'reported'
    for key, pattern in [('cancelled', r'取消|撤回|cancel|scrap'), ('paused', r'暂停|搁置|pause|halt|suspend'),
                         ('reviewing', r'重新评审|重新审查|重新评估|reconsider|under review'),
                         ('reported', r'消息称|据悉|传闻|据报|reportedly|rumou?r|could|may build'),
                         ('operating', r'已投运|投入运营|已通电|opened|operational'),
                         ('construction', r'已开工|开工建设|动工|broke ground|breaks ground|under construction'),
                         ('announced', r'宣布|官宣|announce')]:
        if re.search(pattern, text): stage = key; break
    # Original units are kept as a quoted observation; power basis and scope may be unknown.
    capacity = list(dict.fromkeys(m.group(0) for m in re.finditer(r'(?<![\d.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:GW|MW|吉瓦|兆瓦)(?![A-Za-z/])', title, re.I)))
    actors = {x[6:] for x in item.get('object_ids') or [] if x.startswith('actor:')}
    normalized = re.sub(r'[^\w]', '', text)
    matches = []
    for site in sites:
        name = re.sub(r'[^\w]', '', site.get('name', '').casefold())
        if len(name) >= 4 and name in normalized and actors.intersection(site.get('developer', []) + site.get('tenant', [])):
            matches.append(site['site_id'])
    return {'reported_stage': stage, 'reported_capacity': ' / '.join(capacity) or None,
            'matched_site_id': matches[0] if len(matches) == 1 else None}


def receive(home, articles, at, withdrawn=(), root=None):
    """Only direct-feed validated rows; cluster dedup is not project identity."""
    if root is None:
        from inresearch.paths import project_root
        root = project_root()
    sites = json.loads((Path(root)/'data/projects.json').read_text())['records']
    path = Path(home)/'project-pipeline.json'
    with locked(path):
        value = read(home)
        records = value['records']
        for item in articles:
            signal = signals(item, sites)
            if signal is None: continue
            if not public_url(item.get('url')): continue
            key = 'cluster:'+str(item['cluster_id']) if item.get('cluster_id') else 'article:'+str(item['id'])
            ident = next((r['id'] for r in records.values() if any(str(e['id']) == str(item['id']) for e in r['events'])), None)
            if ident is None and signal['matched_site_id']:
                ident = next((r['id'] for r in records.values() if r.get('site_id') == signal['matched_site_id'] or any(e.get('matched_site_id') == signal['matched_site_id'] for e in r['events'])), None)
            ident = ident or 'lead-'+hashlib.sha256(key.encode()).hexdigest()[:20]
            row = records.setdefault(ident, {'id': ident, 'state': 'lead', 'first_seen': at, 'events': [], 'company_ids': [], 'site_id': None})
            event = {k: item.get(k) for k in ('id', 'title_zh', 'title', 'url', 'published_at', 'editorial_pick', 'event_type')}
            event.update(signal)
            event['withdrawn'] = False
            events = {str(e['id']): e for e in row['events']}; events[str(item['id'])] = event
            row['events'] = sorted(events.values(), key=lambda e: e.get('published_at') or 0)
            row['title'] = row['events'][-1].get('title_zh') or row['events'][-1].get('title')
            row['last_seen'] = at
            row['company_ids'] = sorted(set(row['company_ids']) | {i[6:] for i in item.get('object_ids') or [] if i.startswith('actor:')})
        removed = {str(i) for i in withdrawn}
        for row in records.values():
            for event in row['events']:
                if str(event['id']) in removed: event['withdrawn'] = True
        write_json(path, value)


def projection(home):
    records = []
    for row in read(home)['records'].values():
        events = [{k: e.get(k) for k in ('title_zh', 'title', 'url', 'published_at', 'event_type', 'reported_stage', 'reported_capacity', 'matched_site_id')} for e in row['events'] if not e.get('withdrawn') and public_url(e.get('url'))]
        if not events: continue
        latest = events[-1]
        item = {k: row.get(k) for k in ('id', 'state', 'first_seen', 'last_seen', 'company_ids', 'site_id', 'review_note')}
        matched = {e['matched_site_id'] for e in events if e.get('matched_site_id')}
        if not row.get('reviews'):
            item['site_id'] = next(iter(matched)) if len(matched) == 1 else None
            item['state'] = latest.get('reported_stage') if latest.get('reported_stage') in ('paused', 'cancelled', 'reviewing') else 'lead'
        item.update(title=latest.get('title_zh') or latest.get('title'), events=events,
                    reported_stage=latest.get('reported_stage') or 'reported', reported_capacity=latest.get('reported_capacity'),
                    match_method='reviewed' if row.get('reviews') else 'name_and_actor' if item['site_id'] else None)
        records.append(item)
    records.sort(key=lambda r: r.get('last_seen') or '', reverse=True)
    return {'records': records[:500], 'total': len(records), 'truncated': len(records) > 500,
            'scope': '持久项目线索；未核实容量，不参加 GW 合计。关联项目后仍保留消息历史。'}


def review(home, ident, state, note, site_id=None, root=None):
    if state not in STATES or not note.strip(): raise ValueError('review needs valid state and note')
    if state == 'linked' and not site_id: raise ValueError('linked requires site')
    if site_id:
        sites = json.loads((Path(root)/'data/projects.json').read_text())['records']
        if site_id not in {p['site_id'] for p in sites}: raise ValueError('unknown site')
    path = Path(home)/'project-pipeline.json'
    with locked(path):
        value = read(home)
        if ident not in value['records']: raise ValueError('unknown lead')
        row = value['records'][ident]
        row.setdefault('reviews', []).append({'state': state, 'note': note, 'site_id': site_id, 'reviewed_at': datetime.now(timezone.utc).isoformat()})
        row.update(state=state, review_note=note, site_id=site_id)
        write_json(path, value)


def main():
    from inresearch.paths import project_root
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', type=Path, required=True, help='Reader data root (parent of acquisition)')
    parser.add_argument('--id'); parser.add_argument('--state', choices=STATES)
    parser.add_argument('--note'); parser.add_argument('--site')
    args = parser.parse_args(); home = args.data_root/'acquisition'
    if args.id:
        review(home, args.id, args.state, args.note or '', args.site, project_root())
    print(json.dumps(projection(home), ensure_ascii=False))
    return 0
