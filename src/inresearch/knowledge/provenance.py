"""Resolve recorded content identities conservatively; no filename heuristics."""
import hashlib
import json
import re

HEX12 = re.compile(r'^[0-9a-f]{12}$')
SHA = re.compile(r'^[0-9a-f]{64}$')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def owing_provenance(records):
    return [f for f in records if not (f.get('evidence') or {}).get('sha256')]


def cache_candidates(keys, remap, moves):
    # Only explicit successful move endpoints count. Basenames, notes and
    # JSON substring matches cannot supply content identity.
    paths = {}
    for row in moves:
        sha = row.get('sha256', '')
        if not SHA.fullmatch(sha) or not row.get('ok') or row.get('event') not in {'move', 'revert'}:
            continue
        for field in ('from', 'to'):
            if row.get(field):
                paths.setdefault(row[field], set()).add(sha)
    return {key: {sha for field in ('new_path', 'pre_path')
                  for sha in paths.get((remap.get(key) or {}).get(field), ())}
            for key in keys if key in remap}


def repair_plan(store, ledger, inventory, sources, remap, moves):
    """Return a reviewable plan; conflicting routes never get precedence by order."""
    prefixes, paths = {}, {}
    for sha in ledger:
        if SHA.fullmatch(sha):
            prefixes.setdefault(sha[:12], set()).add(sha)
    for row in inventory:
        sha = row.get('sha256', '')
        if not SHA.fullmatch(sha) or row.get('error'):
            continue
        for path in row.get('paths') or [row.get('original_rel') or row.get('rel')]:
            if path:
                paths.setdefault(path, set()).add(sha)
    owing = owing_provenance(store['records'])
    keys = {str((f.get('evidence') or {}).get('source_id') or '') for f in owing}
    cached = cache_candidates(keys, remap, moves)
    candidates, ambiguous, unknown = [], [], []
    for fact in owing:
        evidence = fact.get('evidence') or {}
        sid = str(evidence.get('source_id') or '')
        local = evidence.get('local_file') or (sources.get(sid) or {}).get('local_file')
        routes = {}
        if HEX12.fullmatch(sid) and prefixes.get(sid):
            routes['prefix'] = prefixes[sid]
        if sid in remap:
            # A registered cache key is a different namespace. An unresolved
            # cache route must not silently become a coincident SHA prefix.
            routes['cache_key'] = cached.get(sid, set())
        if local:
            routes['path'] = paths.get(local, set())
        hits = set().union(*routes.values()) if routes else set()
        if len(hits) == 1 and all(routes.values()):
            candidates.append(dict(fact_id=fact['fact_id'], sha256=next(iter(hits)),
                                   methods=sorted(routes), source_id=sid, local_file=local,
                                   evidence_paths=sorted({p for p in [local, *[(remap.get(sid) or {}).get(field)
                                       for field in ('new_path', 'pre_path')]] if p})))
        elif hits:
            ambiguous.append(dict(fact_id=fact['fact_id'], prefix=sid, matches=sorted(hits),
                                  why='身份解析路径冲突或存在未解析的明确路径'))
        else:
            unknown.append(dict(fact_id=fact['fact_id'], source_id=sid or None,
                                local_file=local,
                                why='既不是可唯一解析的 sha256 前缀，也不是能还原的 reader 缓存键或精确登记路径'))
    plan = dict(facts_sha256=digest(store), candidates=candidates, ambiguous=ambiguous,
                unknown=unknown, owing_before=len(owing), owing_after=len(owing)-len(candidates))
    plan['plan_sha256'] = digest(plan)
    return plan
