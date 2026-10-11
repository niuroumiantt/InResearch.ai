"""Plan physical-site refresh work inside the existing review queue.

Only site_tracking_* tables are written. A planned period is a completed scan,
never collection, reading, C3 adoption or publication. Source executors and the
project publication lane are not connected by this planner.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from inresearch.knowledge import site_timeline
from inresearch.knowledge.industry import public_url
from inresearch.knowledge.news_policy import INEWS_DATACENTER_URL
from inresearch.knowledge.target_request_contract import resolve_request
from inresearch.workflow.daily_dispatch import bound_urls, project_event, receipt_documents

BEIJING = timezone(timedelta(hours=8))
CADENCES = ('daily', 'weekly', 'monthly')
CAPACITY = {'capacity_it_mw', 'capacity_it_mw_by_status', 'capacity_assessment'}
# Accepted optional fields must not silently become missing-data requirements.
# Refresh them when present; absence of water/energy or additional roles is valid.
REQUIRED = frozenset(('name', 'developer', 'tenant', 'owner', 'operator', 'builder',
                      'status', 'lifecycle', 'power_status', 'utility', 'capacity_facility_mw'))
EVENT_FIELDS = {'status', 'lifecycle', 'power_status'} | CAPACITY
IDENTITY_FIELDS = {'site_id', 'country', 'location', 'region', 'coordinates', 'aliases', 'duplicate_of', 'sources'}
TERMINAL = ('completed', 'cancelled', 'superseded')
MAX_ARCHIVE_CHECKS = 128
MAX_ARCHIVE_BYTES = 16*1024*1024
DAILY_REFERENCE_SCAN_VERSION = 1


class ArchiveBudget(ValueError):
    pass


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(encoded(value).encode()).hexdigest()


def periods(at):
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError('site_tracking_clock_requires_timezone')
    today = at.astimezone(BEIJING).date()
    return {'daily': today.isoformat(), 'weekly': (today-timedelta(days=today.weekday())).isoformat(),
            'monthly': today.strftime('%Y-%m')}


def read(path, default=None):
    if not path.exists() and default is not None:
        return default
    if path.is_symlink():
        raise ValueError('site_tracking_symlink_input')
    return json.loads(path.read_text())


def expand(fields):
    fields = set(fields)
    if fields & CAPACITY:
        fields |= CAPACITY
    return sorted(fields)


class SiteTracking:
    def __init__(self, connection, data):
        self.db, self.data = connection, Path(data).resolve()
        if self.db.in_transaction:
            raise ValueError('site_tracking_requires_idle_connection')
        self.db.execute('''CREATE TABLE IF NOT EXISTS site_tracking_periods(
            cadence TEXT PRIMARY KEY, period TEXT NOT NULL, input_sha256 TEXT NOT NULL,
            planned_at TEXT NOT NULL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS site_tracking_checks(
            cadence TEXT PRIMARY KEY, period TEXT NOT NULL, signature TEXT NOT NULL,
            state TEXT NOT NULL, retry_after REAL NOT NULL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS site_tracking_runs(
            id TEXT PRIMARY KEY, cadence TEXT NOT NULL, period TEXT NOT NULL,
            input_sha256 TEXT NOT NULL, state TEXT NOT NULL, attempted_at TEXT NOT NULL,
            retry_after REAL NOT NULL, attempts INTEGER NOT NULL, error TEXT,
            summary TEXT NOT NULL, catch_up_from TEXT)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS site_tracking_recent_runs ON site_tracking_runs(cadence,attempted_at DESC)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS site_tracking_attempts(
            id INTEGER PRIMARY KEY, run_id TEXT NOT NULL, attempted_at TEXT NOT NULL,
            state TEXT NOT NULL, error TEXT, summary TEXT NOT NULL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS site_tracking_archives(
            sha256 TEXT PRIMARY KEY, archive TEXT NOT NULL, file_signature TEXT NOT NULL,
            checked_at TEXT NOT NULL)''')
        self.db.execute('''CREATE TABLE IF NOT EXISTS site_tracking_tasks(
            id TEXT PRIMARY KEY, merge_key TEXT NOT NULL, site_id TEXT, state TEXT NOT NULL,
            fields TEXT NOT NULL, blockers TEXT NOT NULL, request TEXT NOT NULL,
            scope TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            error TEXT, previous_task_id TEXT)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS site_tracking_merge ON site_tracking_tasks(merge_key)')
        self.db.execute('''CREATE TABLE IF NOT EXISTS site_tracking_triggers(
            id TEXT PRIMARY KEY, task_id TEXT NOT NULL, cadence TEXT NOT NULL,
            period TEXT NOT NULL, source_key TEXT NOT NULL, source_version TEXT NOT NULL,
            fields TEXT NOT NULL, reasons TEXT NOT NULL, evidence TEXT NOT NULL,
            baseline_sha256 TEXT, planned_at TEXT NOT NULL)''')
        self.db.execute('CREATE INDEX IF NOT EXISTS site_tracking_source ON site_tracking_triggers(cadence,source_key)')
        self.db.commit()

    def _signature(self, root, cadence, availability=False):
        paths = [Path(root)/'data/projects.json', Path(root)/'framework/tco_targets.json']
        if cadence == 'daily':
            paths += [self.data/rel for rel in ('acquisition/project-pipeline.json',
                'acquisition/daily-events.json', 'material-reviews/daily-deliveries')]
            if availability:
                paths += [self.data/'acquisition/catalog.sqlite', self.data/'acquisition/catalog.sqlite-wal']
        result = []
        for path in paths:
            try:
                s = path.lstat()
                result.append([str(path), s.st_ino, s.st_size, s.st_mtime_ns, s.st_mode])
            except FileNotFoundError:
                result.append([str(path), None])
        return digest([DAILY_REFERENCE_SCAN_VERSION, result]) if cadence == 'daily' else digest(result)

    def _snapshot(self, root, cadence):
        root = Path(root)
        projects = read(root/'data/projects.json')['records']
        targets = read(root/'framework/tco_targets.json')
        result = {'projects': projects, 'targets': targets}
        if cadence == 'daily':
            # Invalidate a successful scan from before per-reference gap checks.
            result['reference_scan_version'] = DAILY_REFERENCE_SCAN_VERSION
            result['pipeline'] = read(self.data/'acquisition/project-pipeline.json', {'version': 1, 'records': {}})
            result['daily'] = read(self.data/'acquisition/daily-events.json', {'version': 2, 'records': {}, 'parses': {}})
            result['accepted'] = receipt_documents(self.data)
            result['receipt_events'] = {}
            for path in (self.data/'material-reviews/daily-deliveries').glob('*.json'):
                if path.is_symlink() or path.stat().st_size > 1024*1024:
                    continue
                receipt = read(path)
                if receipt.get('producer') != 'inews_geluoke' or receipt.get('status') != 'indexed_candidate':
                    continue
                for document in receipt.get('documents', []):
                    if document.get('sha256') in result['accepted']:
                        sha = document['sha256']
                        result['receipt_events'][sha] = sorted(set(result['receipt_events'].get(sha, [])) | set(document.get('event_ids', [])))
            catalog = self.data/'acquisition/catalog.sqlite'
            # WAL changes can make a previously unavailable archive available.
            result['catalog_signature'] = [(p.name, p.stat().st_size, p.stat().st_mtime_ns)
                for p in (catalog, catalog.with_name(catalog.name+'-wal')) if p.exists()]
        if not isinstance(projects, list) or not isinstance(targets.get('targets'), list):
            raise ValueError('site_tracking_invalid_register')
        if (any(not isinstance(p, dict) or not isinstance(p.get('site_id'), str) for p in projects)
                or any(not isinstance(t, dict) or not isinstance(t.get('id'), str) for t in targets['targets'])):
            raise ValueError('site_tracking_invalid_register_row')
        return result

    def _archive(self, row):
        sha, relative = row['sha256'], row['relative_path']
        path = self.data/relative
        if (not relative.startswith('acquisition/blobs/'+sha[:2]+'/'+sha+'.')
                or path.is_symlink() or not path.resolve().is_relative_to(self.data)):
            raise ValueError('site_tracking_archive_missing_or_changed')
        stat = path.stat()
        limit = 4*1024*1024 if 'kind' in row.keys() and row['kind'] == 'news_lead' else 64*1024*1024
        if stat.st_size > limit:
            raise ValueError('site_tracking_source_exceeds_delivery_size_limit')
        signature = [stat.st_ino, stat.st_size, stat.st_mtime_ns]
        ref = {'sha256': sha, 'archive': relative, 'file_signature': signature}
        if sha not in self.archive_cache:
            cached = self.db.execute('SELECT * FROM site_tracking_archives WHERE sha256=?', (sha,)).fetchone()
            if cached:
                self.archive_cache[sha] = {'sha256': sha, 'archive': cached['archive'],
                                           'file_signature': json.loads(cached['file_signature'])}
        if self.archive_cache.get(sha) == ref:
            return ref
        if self.archive_checks >= MAX_ARCHIVE_CHECKS or (self.archive_checks and self.archive_bytes+stat.st_size > MAX_ARCHIVE_BYTES):
            raise ArchiveBudget('archive_check_budget_pending')
        self.archive_checks += 1
        self.archive_bytes += stat.st_size
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024*1024), b''):
                h.update(block)
        after = path.stat()
        if h.hexdigest() != sha or [after.st_ino, after.st_size, after.st_mtime_ns] != signature:
            raise ValueError('site_tracking_archive_missing_or_changed')
        self.archive_cache[sha] = ref
        return ref

    def _events(self, snapshot):
        """Consume received bytes; retain their role, never promote metadata to originals."""
        pipeline, daily = snapshot['pipeline'], snapshot['daily']
        if pipeline.get('version') != 1 or daily.get('version') not in (1, 2):
            raise ValueError('site_tracking_invalid_event_ledger')
        events, issues = [], []
        catalog = self.data/'acquisition/catalog.sqlite'
        if not catalog.is_file():
            if pipeline['records'] or daily['records']:
                issues.append('acquisition_catalog_missing')
            return events, issues
        con = sqlite3.connect(catalog.as_uri()+'?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        try:
            self.archive_cache, self.archive_checks, self.archive_bytes = {}, 0, 0
            archives = {}
            news = {}
            news_ids = [str(e['id']) for lead in pipeline['records'].values() for e in lead['events']]
            for row in con.execute('''SELECT i.id, i.source, i.kind, i.metadata,
                    o.sha256,o.relative_path,o.request_json FROM items i JOIN observations o ON i.id=o.item_id
                    WHERE i.source='inews' AND i.kind='news_lead'
                        AND CAST(json_extract(i.metadata,'$.id') AS TEXT) IN (SELECT value FROM json_each(?))
                        AND o.id=(SELECT max(id) FROM observations WHERE item_id=i.id)
                    ORDER BY o.id''', (encoded(news_ids),)):
                meta, request = json.loads(row['metadata']), json.loads(row['request_json'])
                proof = meta.get('upstream_selection') or {}
                if (proof.get('url') == INEWS_DATACENTER_URL
                        and proof.get('verification') == 'direct_https_feed_v1'
                        and request.get('upstream_selection', {}).get('url') == INEWS_DATACENTER_URL):
                    try:
                        ref = self._archive(row)
                    except ArchiveBudget:
                        issues.append('archive_check_budget_pending')
                        continue
                    value = read(self.data/ref['archive'])
                    news[str(value['id'])] = (value, ref)
            document_shas = sorted({r.get('sha256') for event in daily['records'].values()
                for r in event.get('document_refs', []) if r.get('sha256') in snapshot['accepted']})
            # supplied_research uses SHA as source_key, so this lookup uses the
            # existing UNIQUE(source,source_key), not a scan of all observations.
            for row in con.execute('''SELECT o.sha256,o.relative_path FROM items i JOIN observations o ON i.id=o.item_id
                    WHERE i.source='fetchreports' AND i.source_key IN (SELECT value FROM json_each(?))
                        AND o.sha256=i.source_key''', (encoded(document_shas),)):
                archives.setdefault(row['sha256'], []).append(dict(row))
            for lead in pipeline['records'].values():
                for event in lead['events']:
                    key = 'news:'+str(event['id'])
                    original = news.get(str(event['id']))
                    if original is None or original[0].get('url') != event.get('url'):
                        issues.append(key+':metadata_archive_unavailable')
                        continue
                    value, ref = original
                    if any(value.get(k) != event.get(k) for k in ('title', 'title_zh')):
                        issues.append(key+':pipeline_metadata_changed')
                        continue
                    linked = lead.get('state') == 'linked' and bool(lead.get('review_note')) and bool(lead.get('site_id'))
                    semantic_ref = {k: ref[k] for k in ('sha256', 'archive')}
                    events.append({'key': key, 'version': digest([semantic_ref, event, lead.get('site_id'), linked]),
                        'site_id': lead['site_id'] if linked else event.get('matched_site_id'),
                        'identity_verified': bool(linked),
                        'target_ids': value.get('target_ids') or [], 'fields': EVENT_FIELDS,
                        'reasons': ['source_withdrawn'] if event.get('withdrawn') else ['received_event'],
                        'blockers': ['native_source_collection_required'] + (['source_withdrawn_requires_review'] if event.get('withdrawn') else []),
                        'evidence': [{**ref, 'role': 'news_metadata', 'url': value.get('url')} ]})
            active = {i for p in daily.get('parses', {}).values() for i in p['event_ids']} if daily.get('parses') else set(daily['records'])
            for key, event in daily['records'].items():
                if key not in active or not project_event(event):
                    continue
                refs = []
                for index, document in enumerate(event.get('document_refs', [])):
                    sha = document.get('sha256')
                    reference = 'daily:'+key+':reference:'+str(index)+':'+str(sha)+':'
                    if sha not in snapshot['accepted']:
                        issues.append(reference+'receiver_receipt_missing')
                        continue
                    if key not in snapshot['receipt_events'].get(sha, []):
                        issues.append(reference+'receipt_event_membership_missing')
                        continue
                    candidates = archives.get(sha, [])
                    if not candidates:
                        issues.append(reference+'catalog_archive_unavailable')
                        continue
                    try:
                        refs.append({**self._archive(candidates[0]), 'role': 'daily_html',
                                     'locator': document.get('section')})
                    except ArchiveBudget:
                        issues.append(reference+'archive_check_budget_pending')
                if not refs:
                    issues.append('daily:'+key+':received_document_archive_unavailable')
                    continue
                urls = bound_urls(event, snapshot['accepted'])
                support = sorted(({k: ref[k] for k in ('sha256', 'archive', 'locator')}
                                  for ref in refs), key=encoded)
                events.append({'key': 'daily:'+key, 'version': digest([event, support]),
                    'site_id': event.get('matched_site_id'),
                    'identity_verified': event.get('identity_review') == 'resolved',
                    'target_ids': sorted({r['target_id'] for r in event.get('demand_matches', [])}),
                    'fields': EVENT_FIELDS | set((event.get('editorial_event') or {}).get('project', {})).intersection(site_timeline.FIELDS),
                    'reasons': ['source_withdrawn'] if event.get('withdrawn') else ['received_event'],
                    'blockers': ['native_source_collection_required'] + ([] if urls else ['source_binding_required']) +
                                (['source_withdrawn_requires_review'] if event.get('withdrawn') else []),
                    'evidence': refs})
        finally:
            con.close()
        return events, sorted(set(issues))

    def _request(self, ids, targets):
        """Freeze candidates, not a dispatch decision based on headline matching."""
        by_id = {t['id']: t for t in targets['targets']}
        definitions, blockers = [], ['demand_mapping_required', 'source_collection_executor_not_connected',
                                      'site_review_executor_not_connected', 'project_publication_not_connected']
        for ident in sorted(set(ids)):
            target = by_id.get(ident)
            if target is None:
                blockers.append('target_missing:'+ident)
                continue
            requirements = target.get('request', {}).get('requirements', [])
            if requirements:
                blockers.append('requirement_selection_required:'+ident)
                blockers.extend('candidate_source_team_not_connected:'+r['id']+':'+r['source_team']
                                for r in requirements if r.get('team_state') == 'not_connected')
            else:
                selected = resolve_request(target)
                if selected.get('team_state') == 'not_connected':
                    blockers.append('source_team_not_connected:'+selected['source_team'])
            definitions.append({'target_id': ident, 'definition_sha256': digest(target), 'definition': target})
        return {'status': 'candidate_only', 'target_ids': sorted(set(ids)),
                'target_version': targets['version'], 'definitions': definitions}, blockers

    def _plans(self, snapshot, cadence, today):
        sites = {p['site_id']: p for p in snapshot['projects']
                 if not p.get('duplicate_of') and 'portfolio' not in p['site_id']}
        plans, issues = [], []
        if cadence == 'daily':
            events, issues = self._events(snapshot)
            for event in events:
                site = sites.get(event['site_id'])
                scope = ({k: site.get(k) for k in ('site_id', 'country', 'location', 'region')}
                         if site else {'unresolved_event': event['key']})
                blockers = event['blockers'] + ([] if site and event['identity_verified'] else ['physical_identity_requires_review'])
                plans.append(dict(site=site, scope=scope, target_ids=event['target_ids'],
                    fields=expand(event['fields']), reasons=event['reasons'],
                    source_key=event['key'], source_version=event['version'],
                    evidence=event['evidence'], blockers=blockers))
        else:
            for ident, site in sorted(sites.items()):
                view = site_timeline.current(site, today)
                scope = {k: site.get(k) for k in ('site_id', 'country', 'location', 'region')}
                if cadence == 'weekly':
                    quantities = view.get('quantity_fields') or {}
                    def present(field):
                        # Native ranges intentionally project to scalar None (or
                        # empty scalar parts). Their bounds still supply a value.
                        return quantities.get(field, view.get(field)) not in (None, '', [], {})
                    missing = {f for f in REQUIRED if not present(f)}
                    # Empty phase parts and nullable assessment are valid when
                    # either an IT headline or explicit phase quantities exist.
                    if not present('capacity_it_mw') and not present('capacity_it_mw_by_status'):
                        missing |= CAPACITY
                    overdue = set(view['tracking']['review_due_fields'])
                    conflict = {f for c in view['tracking']['conflicts'] for f in
                                (CAPACITY if c['field'] == 'it_capacity_bundle' else [c['field']])}
                    fields = expand(missing | overdue | conflict)
                    if not fields:
                        continue
                    reasons = ([f'missing:{f}' for f in sorted(missing)] +
                               [f'overdue:{f}' for f in sorted(overdue)] +
                               [f'conflict:{f}' for f in sorted(conflict)])
                else:
                    fields = sorted(site_timeline.FIELDS | IDENTITY_FIELDS)
                    reasons = ['identity_coverage_review', 'source_coverage_review']
                    if not any(public_url(s.get('url')) for s in site.get('sources', [])):
                        reasons.append('source_coverage_missing')
                plans.append(dict(site=site, scope=scope, target_ids=[], fields=fields,
                    reasons=reasons, source_key='site:'+ident, source_version=digest(site),
                    evidence=[{'role': 'formal_register_reference', 'site_id': ident,
                               'source_urls': [s['url'] for s in site.get('sources', []) if public_url(s.get('url'))]}],
                    blockers=['native_source_collection_required']))
        for plan in plans:
            plan['request'], extra = self._request(plan.pop('target_ids'), snapshot['targets'])
            plan['blockers'] = sorted(set(plan['blockers'] + extra))
        return plans, issues

    def _enqueue(self, plan, cadence, period, stamp):
        request, scope = plan['request'], plan['scope']
        merge_key = digest([scope, request['target_ids']])
        ident = digest([merge_key, request])
        family = self.db.execute('SELECT * FROM site_tracking_tasks WHERE merge_key=? ORDER BY created_at DESC,rowid DESC', (merge_key,)).fetchall()
        old = next((r for r in family if r['request'] == encoded(request) and r['state'] not in TERMINAL), None)
        if old:
            ident = old['id']
        previous = next((r for r in family if r['id'] != ident), None)
        # A source version is consumed once across days. Weekly/monthly scans
        # deliberately request another review, without claiming one occurred.
        trigger_id = digest([merge_key, request, cadence, None if cadence == 'daily' else period,
                             plan['source_key'], plan['source_version'], plan['fields'], plan['reasons']])
        if self.db.execute('SELECT 1 FROM site_tracking_triggers WHERE id=?', (trigger_id,)).fetchone():
            return 0
        if not old and family:
            # A later refresh is new work, never a resurrection of an adopted receipt.
            ident = digest([ident, cadence, period, plan['source_version']])
            old = self.db.execute('SELECT * FROM site_tracking_tasks WHERE id=?', (ident,)).fetchone()
            previous = next((r for r in family if r['id'] != ident), None)
        fields = expand(set(plan['fields']) | (set(json.loads(old['fields'])) if old else set()))
        blockers = sorted(set(plan['blockers']) | (set(json.loads(old['blockers'])) if old else set()))
        if not old:
            self.db.execute('INSERT INTO site_tracking_tasks VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                (ident, merge_key, plan['site']['site_id'] if plan['site'] else None, 'blocked', encoded(fields),
                 encoded(blockers), encoded(request), encoded(scope), stamp, stamp, None, previous['id'] if previous else None))
            if previous and previous['state'] in ('blocked', 'queued'):
                self.db.execute("UPDATE site_tracking_tasks SET state='superseded',error='request_definition_changed',updated_at=? WHERE id=?", (stamp, previous['id']))
        else:
            # Preserve failures, leases and future executor state. Planning cannot
            # retry or complete an execution, nor alter its model budget.
            self.db.execute('UPDATE site_tracking_tasks SET fields=?,blockers=?,updated_at=? WHERE id=?',
                            (encoded(fields), encoded(blockers), stamp, ident))
        self.db.execute('INSERT OR IGNORE INTO site_tracking_triggers VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (trigger_id, ident, cadence, period, plan['source_key'], plan['source_version'],
             encoded(plan['fields']), encoded(plan['reasons']), encoded(plan['evidence']),
             digest(plan['site']) if plan['site'] else None, stamp))
        return 1

    def tick(self, root, at=None):
        at = at or datetime.now(timezone.utc)
        current = periods(at)
        stamp = at.astimezone(timezone.utc).isoformat()
        for cadence, period in current.items():
            previous = self.db.execute('SELECT * FROM site_tracking_periods WHERE cadence=?', (cadence,)).fetchone()
            if previous and previous['period'] > period:
                continue
            input_sha = digest(['input_unavailable', str(Path(root).resolve())])
            signature = None
            try:
                checked = self.db.execute('SELECT * FROM site_tracking_checks WHERE cadence=?', (cadence,)).fetchone()
                availability = bool(checked and checked['state'] != 'planned')
                basic_signature = self._signature(root, cadence)
                signature = self._signature(root, cadence, True) if availability else basic_signature
                if (checked and checked['period'] == period and checked['signature'] == signature
                        and (checked['state'] == 'planned' or checked['retry_after'] > at.timestamp())):
                    continue
                snapshot = self._snapshot(root, cadence)
                input_sha = digest(snapshot)
                if previous and previous['period'] == period and previous['input_sha256'] == input_sha:
                    with self.db:
                        self._checked(cadence, period, basic_signature, 'planned', 0)
                    continue
                rid = digest([cadence, period, input_sha])
                last = self.db.execute('SELECT * FROM site_tracking_runs WHERE id=?', (rid,)).fetchone()
                if last and last['retry_after'] > at.timestamp():
                    continue
                plans, issues = self._plans(snapshot, cadence, current['daily'])
                if self._signature(root, cadence, availability) != signature:
                    raise ValueError('site_tracking_inputs_changed_during_scan')
                with self.db:
                    if cadence == 'daily':
                        for ref in getattr(self, 'archive_cache', {}).values():
                            self.db.execute('''INSERT INTO site_tracking_archives VALUES(?,?,?,?)
                                ON CONFLICT(sha256) DO UPDATE SET archive=excluded.archive,
                                file_signature=excluded.file_signature,checked_at=excluded.checked_at''',
                                (ref['sha256'], ref['archive'], encoded(ref['file_signature']), stamp))
                    added = sum(self._enqueue(p, cadence, period, stamp) for p in plans)
                    state = 'partial' if issues else 'planned'
                    self._run(cadence, period, input_sha, state, stamp, at.timestamp(),
                              issues, {'triggers_added': added, 'tasks_considered': len(plans)}, previous)
                    self._checked(cadence, period, self._signature(root, cadence, True) if issues else basic_signature,
                                  state, at.timestamp()+300 if issues else 0)
                    if not issues:
                        self.db.execute('INSERT INTO site_tracking_periods VALUES(?,?,?,?) ON CONFLICT(cadence) DO UPDATE SET period=excluded.period,input_sha256=excluded.input_sha256,planned_at=excluded.planned_at',
                                        (cadence, period, input_sha, stamp))
            except (OSError, ValueError, KeyError, TypeError, AttributeError, sqlite3.Error) as exc:
                # Isolate failed scans from old research batches and other cadences.
                # Rollback has already discarded any partial task transaction.
                with self.db:
                    self._run(cadence, period, input_sha, 'failed', stamp, at.timestamp(),
                              [type(exc).__name__+':'+str(exc)[:200]], {}, previous)
                    if signature is not None:
                        self._checked(cadence, period, self._signature(root, cadence, True), 'failed', at.timestamp()+300)
        return self.status()

    def _checked(self, cadence, period, signature, state, retry_after):
        self.db.execute('''INSERT INTO site_tracking_checks VALUES(?,?,?,?,?)
            ON CONFLICT(cadence) DO UPDATE SET period=excluded.period,signature=excluded.signature,
            state=excluded.state,retry_after=excluded.retry_after''', (cadence, period, signature, state, retry_after))

    def _run(self, cadence, period, input_sha, state, stamp, timestamp, errors, summary, previous):
        rid = digest([cadence, period, input_sha])
        self.db.execute('''INSERT INTO site_tracking_runs VALUES(?,?,?,?,?,?,?,1,?,?,?)
            ON CONFLICT(id) DO UPDATE SET state=excluded.state,attempted_at=excluded.attempted_at,
            retry_after=excluded.retry_after,attempts=site_tracking_runs.attempts+1,
            error=excluded.error,summary=excluded.summary''',
            (rid, cadence, period, input_sha, state, stamp,
             timestamp+300 if errors else 0, encoded(errors) if errors else None,
             encoded(summary), previous['period'] if previous and previous['period'] != period else None))
        self.db.execute('INSERT INTO site_tracking_attempts(run_id,attempted_at,state,error,summary) VALUES(?,?,?,?,?)',
                        (rid, stamp, state, encoded(errors) if errors else None, encoded(summary)))

    def status(self):
        return status(self.db)


def status(connection):
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='site_tracking_periods'").fetchone():
        return {'state': 'not_initialized'}
    latest = []
    for cadence in sorted(CADENCES):
        row = connection.execute('''SELECT * FROM site_tracking_runs WHERE cadence=?
            ORDER BY attempted_at DESC,rowid DESC LIMIT 1''', (cadence,)).fetchone()
        if row is None:
            continue
        item = dict(row)
        errors = json.loads(item['error']) if item['error'] else []
        item['error_count'] = len(errors)
        item['errors_truncated'] = len(errors) > 8
        item['error_sha256'] = digest(errors) if errors else None
        # Full source-specific failures remain in the private run/attempt rows.
        # The worker logs this projection on every poll, including idle polls.
        item['error'] = encoded([str(error)[:200] for error in errors[:8]]) if errors else None
        latest.append(item)
    return {'timezone': 'Asia/Shanghai',
            'periods': [dict(r) for r in connection.execute('SELECT * FROM site_tracking_periods ORDER BY cadence')],
            'task_states': {r[0]: r[1] for r in connection.execute('SELECT state,count(*) FROM site_tracking_tasks GROUP BY state')},
            'latest_runs': latest,
            'collection_completed': None, 'adopted_updates': None, 'published_updates': None,
            'scope': 'planning watermarks only; source collection, Reader/C3 and project publication require separate execution receipts'}
