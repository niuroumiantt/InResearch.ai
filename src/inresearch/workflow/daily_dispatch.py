"""Independent daily delivery lanes; news publication never adopts capacity."""
import json
import re
from collections import Counter
from pathlib import Path
from inresearch.knowledge.industry import public_url


def receipt_documents(data):
    """Receiver receipts, not supplier-supplied flags, authorize public metadata."""
    accepted = {}
    directory = Path(data)/'material-reviews/daily-deliveries'
    if not directory.is_dir(): return accepted
    for path in directory.glob('*.json'):
        if path.is_symlink() or path.stat().st_size > 1024*1024: continue
        try: receipt = json.loads(path.read_text())
        except (OSError, ValueError): continue
        if receipt.get('producer') != 'inews_geluoke' or receipt.get('status') != 'indexed_candidate': continue
        for doc in receipt.get('documents', []):
            if isinstance(doc, dict) and re.fullmatch('[0-9a-f]{64}', doc.get('sha256') or ''):
                accepted[doc['sha256']] = receipt.get('received_at')
    return accepted


def bound_urls(event, accepted):
    refs = {r['sha256'] for r in event.get('document_refs', []) if r.get('sha256') in accepted}
    if not refs: return []
    urls = []
    for source in event.get('sources', []):
        # Only a validated sidecar explicitly bound to this event is eligible.
        # Inline HTML URLs and same-day/title guesses stay internal candidates.
        if not re.fullmatch('[0-9a-f]{64}', source.get('source_sha256') or '') or not source.get('source_locator'): continue
        if source.get('document_sha256') and source['document_sha256'] not in refs: continue
        if not source.get('document_sha256') and source.get('source_sha256') != (event.get('editorial_event') or {}).get('metadata_sha256'): continue
        for url in source.get('urls', []):
            if public_url(url) and url not in urls: urls.append(url)
    return urls


def project_event(event):
    text = event.get('title', '')+'\n'+event.get('body', '')
    return bool(re.search(r'数据中心|算力中心|智算中心|园区|机房|data[ -]?cent(?:er|re)|campus', text, re.I))


def read_events(data):
    path = Path(data)/'acquisition/daily-events.json'
    if not path.is_file(): return []
    value = json.loads(path.read_text())
    active = {i for p in value.get('parses', {}).values() for i in p['event_ids']} if value.get('parses') else set(value['records'])
    return [r for i, r in value['records'].items() if i in active]


def news_records(data, events=None):
    accepted = receipt_documents(data)
    records = []
    for event in read_events(data) if events is None else events:
        urls = bound_urls(event, accepted)
        if not urls or not project_event(event) or event.get('withdrawn'): continue
        authored = event.get('editorial_event') or {}
        # A reported stage is a news observation, not a project-state change.
        stage = authored.get('stage') or event.get('reported_stage') or 'unknown'
        records.append({'id': event['id'], 'title': event['title'], 'urls': urls,
                        'report_date': max((r.get('report_date') or '' for r in event['document_refs']), default=''),
                        'reported_stage': stage, 'constraints': event.get('constraints', []),
                        'target_ids': sorted({r['target_id'] for r in event.get('demand_matches', [])}),
                        'document_sha256': sorted({r['sha256'] for r in event['document_refs'] if r['sha256'] in accepted}),
                        'accepted_at': max((accepted[r['sha256']] or '' for r in event['document_refs'] if r['sha256'] in accepted), default=''),
                        'acceptance': 'reported_observation', 'capacity_adopted': False})
    records.sort(key=lambda r: (r['report_date'], r['id']), reverse=True)
    return records


def fast_reading_shas(data):
    """Small eligible HTML cohort; only dispatch order changes, never depth/score."""
    return sorted({sha for r in news_records(data) for sha in r['document_sha256']})


def projection(data, events=None):
    events = read_events(data) if events is None else events
    news = news_records(data, events)
    accepted = receipt_documents(data)
    ready = {r['id'] for r in news}
    counts = Counter()
    rows = []
    for event in events:
        sources = any(public_url(u) for s in event.get('sources', []) for u in s.get('urls', []))
        authored = event.get('editorial_event') or {}
        tasks = []
        project = authored.get('project') or {}
        quick_review = event['id'] in ready and event.get('structured_evidence_status') == 'quotes_verified' and all(project.get(k) for k in ('name','country','city','phase')) and authored.get('stage') not in (None,'unknown')
        if event['id'] in ready:
            tasks.append({'kind': 'news', 'state': 'ready_for_snapshot', 'owner': 'Spark 发布器',
                          'next_action': '随独立事件快照交付项目动态，不等待长报告；不计入正式 GW。'})
        elif not sources:
            tasks.append({'kind': 'source', 'state': 'awaiting_source', 'owner': 'inews / M5 补源',
                          'next_action': '查原 sources.json 和新闻记录；无法准确配对时重新取得来源，保留缺口。'})
        elif bound_urls(event, accepted) and not project_event(event):
            tasks.append({'kind': 'research', 'state': 'awaiting_research', 'owner': '研究核验',
                          'next_action': '按部件/公司/研究需求处理；非园区事件不强行建立园区身份。'})
        else:
            tasks.append({'kind': 'source_binding', 'state': 'awaiting_binding', 'owner': '研究接收与核验',
                          'next_action': '核对来源与原件/事件的对应关系；有 URL 不等于已核验可发布。'})
        if project_event(event) and not event.get('matched_site_id'):
            tasks.append({'kind': 'identity', 'state': 'awaiting_identity', 'owner': '研究核验',
                          'next_action': '确认主体、地点、园区与分期；新项目建立身份，不能只按同公司合并。'})
        observations = authored.get('capacities') or event.get('capacity_observations') or []
        if observations:
            tasks.append({'kind': 'capacity', 'state': 'priority_research_review' if quick_review else 'awaiting_capacity_review', 'owner': '研究核验',
                          'next_action': '逐数核对 IT/设施/电网、阶段、分期、日期与重复关系，完成研究采用后更新容量。'})
        else:
            tasks.append({'kind': 'capacity', 'state': 'not_disclosed', 'owner': 'inews / 研究核验',
                          'next_action': '容量未披露保持空值；不阻塞来源明确的项目动态。'})
        for task in tasks: counts[task['kind']] += 1
        if quick_review: counts['priority_research_review'] += 1
        rows.append({'event_id': event['id'], 'title': event['title'], 'tasks': tasks,
                     'delivery_lane': 'news' if event['id'] in ready else 'source' if not sources else 'research' if bound_urls(event, accepted) and not project_event(event) else 'source_binding',
                     'last_processed_at': max((r.get('received_at') or '' for r in event.get('delivery_receipts', [])), default='') or
                        max((r['accepted_at'] for r in news if r['id']==event['id']), default='') or None,
                     'review_priority': 0 if quick_review else 1 if event['id'] in ready else 2,
                     'formal_update': 'not_adopted'})
    rows.sort(key=lambda r: (r['review_priority'], r['delivery_lane'], r['event_id']))
    return {'version': 1, 'news': news[:500], 'news_total': len(news), 'news_truncated': len(news)>500,
            'task_counts': dict(counts), 'records': rows[:1000], 'total': len(rows),
            'formal_updates': None, 'formal_update_status': 'check_formal_project_registry',
            'scope': '逐事件交付与补证分流；动态不等待整批阅读，正式项目与 GW 仍以研究登记为准。'}


def pipeline_records(data):
    """Public allowlist: titles/dates/URLs only; no editorial body or PDF content."""
    return [{'id': 'daily-'+r['id'], 'state': 'lead', 'site_id': None, 'company_ids': [],
             'first_seen': r['accepted_at'], 'last_seen': r['accepted_at'], 'title': r['title'],
             'reported_stage': r['reported_stage'] if r['reported_stage'] in ('operating','construction','paused','cancelled') else 'reported',
             'reported_capacity': None, 'match_method': None, 'origin': 'daily_html',
             'events': [{'title': r['title'], 'url': u, 'published_at': 0, 'event_type': 'project_milestone',
                         'reported_stage': r['reported_stage'], 'reported_capacity': None,
                         'matched_site_id': None, 'site_candidates': [], 'capacity_observations': [],
                         'constraints': r['constraints'], 'target_ids': r['target_ids']} for u in r['urls'][:5]],
             'report_date': r['report_date'], 'review_note': '日报来源对应已登记；项目身份与容量仍待核验，未计入正式 GW。'}
            for r in news_records(data)]
