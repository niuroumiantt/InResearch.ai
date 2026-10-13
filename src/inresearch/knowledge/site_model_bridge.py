"""Read-only, version-pinned site/scenario bridge; never adopt research facts."""
import copy
import hashlib
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit, parse_qs


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _sha(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value)


def _url(value):
    parsed = urlsplit(value)
    return (parsed.scheme == 'https' and parsed.hostname and not parsed.username and not parsed.password
            and not {'token','access_token','api_key','password','secret','authorization'}.intersection(
                k.casefold() for k in parse_qs(parsed.query, keep_blank_values=True)))


def _review(item):
    review = item['review']
    if digest(review) != item['review_sha256'] or not all(_sha(review.get(k)) for k in
            ('input_sha256', 'result_sha256', 'checklist_sha256')):
        raise ValueError('bridge_review_changed')
    sources = {s['id']: s for s in review['sources']}
    evidence = {e['id']: e for e in review['items']}
    if len(sources) != len(review['sources']) or len(evidence) != len(review['items']):
        raise ValueError('bridge_review_identity')
    for source in sources.values():
        if not _url(source['url']) or not _sha(source['sha256']) or not source.get('checked_scope'):
            raise ValueError('bridge_review_source')
    for fact in evidence.values():
        if fact.get('source_id') and (fact['source_id'] not in sources or not fact.get('locator')):
            raise ValueError('bridge_evidence_source')
    derivations = review['derivations']
    outputs = {}
    for d in derivations:
        if (d['review_state'] != 'candidate' or d['source_id'] not in sources
                or not d.get('formula') or not d.get('scope') or not d.get('assumptions')
                or not d.get('locator') or d['output_item_id'] not in evidence
                or not d['input_item_ids'] or not set(d['input_item_ids']) <= evidence.keys()):
            raise ValueError('bridge_derivation')
        if d['output_item_id'] in outputs or evidence[d['output_item_id']]['state'] != 'candidate':
            raise ValueError('bridge_derivation_output')
        outputs[d['output_item_id']] = d['input_item_ids']
    def visit(node, active):
        if node in active:
            raise ValueError('bridge_derivation_cycle')
        for child in outputs.get(node, []):
            visit(child, active | {node})
    for node in outputs:
        visit(node, set())
    for block in item['blockers']:
        if block['automatic_fill'] is not False or not set(block['evidence_ids']) <= evidence.keys():
            raise ValueError('bridge_blocker')
        if evidence[block['id']]['state'] != 'anomaly':
            raise ValueError('bridge_blocker_state')
    # Each declared unresolved/clarified anomaly must have a model-use decision.
    if {e['id'] for e in evidence.values() if e['state'] == 'anomaly'} != {b['id'] for b in item['blockers']}:
        raise ValueError('bridge_missing_blocker')
    return sources, evidence


def validate(doc, projects, spec):
    if doc.get('schema_version') != 2 or not doc.get('version') or not doc.get('mapping_version'):
        raise ValueError('bridge_version')
    sites = {r['site_id']: r for r in projects}
    seen = set()
    for item in doc['sites']:
        sid = item['site_id']
        if sid in seen or sid not in sites:
            raise ValueError('bridge_identity')
        seen.add(sid)
        scope = item['scope']
        if not scope.get('id') or scope['physical_scope'] != 'whole_site' or not scope.get('excluded'):
            raise ValueError('bridge_scope')
        obs = next((o for o in sites[sid].get('observations', []) if o['id'] == item['observation_id']), None)
        if (not obs or digest(obs) != item['expected_observation_sha256']
                or obs['scope'] != scope['physical_scope'] or obs['effective_at'] != scope['effective_at']
                or obs['kind'] != 'estimated' or obs.get('adoption', {}).get('review', {}).get('decision') != 'adopted'
                or obs['fields'].get('capacity_it_mw') != item['expected_it_mw']):
            raise ValueError('bridge_observation_changed')
        if sites[sid].get('country') != 'US' or sites[sid].get('province') != 'Texas':
            raise ValueError('bridge_region_scope')
        if not 0 < item['expected_it_mw'] <= spec['inputs']['it_mw']['max']:
            raise ValueError('bridge_capacity_bounds')
        sources, evidence = _review(item)
        ids = set()
        for claim in item['configurations'] + item['economic_candidates']:
            if claim['id'] in ids or claim['status'] != 'candidate':
                raise ValueError('bridge_candidate_not_adopted')
            ids.add(claim['id'])
            if not _url(claim['source_url']) or not claim.get('locator'):
                raise ValueError('bridge_source')
            if (claim['measurement_kind'] not in ('estimated', 'reported') or not claim.get('missing')
                    or not claim.get('evidence_ids') or not set(claim['evidence_ids']) <= evidence.keys()
                    or any(evidence[i]['state'] != 'candidate' for i in claim['evidence_ids'])):
                raise ValueError('bridge_candidate_scope')
            quantity = claim.get('quantity')
            value = quantity['value'] if quantity else claim.get('value')
            if value is not None and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                raise ValueError('bridge_quantity')
        rules = item['rules']
        # Phase one permits exactly these two rules; no candidate-to-parameter rules.
        if (len(rules) != 2 or {r['target'] for r in rules} != {'it_mw', 'site'}
                or rules[0]['id'] != 'it-capacity-v1' or rules[0]['kind'] != 'observation'
                or rules[0]['source_field'] != 'capacity_it_mw' or rules[0]['target'] != 'it_mw'
                or rules[1]['kind'] != 'regional_reference' or rules[1]['value'] != 'us_texas'
                or rules[0]['evidence_ids'] != ['body-it'] or evidence['body-it']['state'] != 'existing_observation'
                or evidence['body-it'].get('observation_id') != item['observation_id']):
            raise ValueError('bridge_rule_targets')
        for b in item['blockers']:
            if not set(b['blocked_targets']) <= spec['inputs'].keys():
                raise ValueError('bridge_blocker_target')
            for rule in rules:
                if rule['target'] in b['blocked_targets']:
                    if (b['id'] != 'source-label-check' or rule['id'] != 'it-capacity-v1'
                            or b.get('exception_rule_ids') != ['it-capacity-v1']):
                        raise ValueError('bridge_blocked_rule')
        if set(item['demo_assumptions']) != {'load_factor', 'pue'}:
            raise ValueError('bridge_demo_assumptions')
        for key, value in item['demo_assumptions'].items():
            cfg = spec['inputs'][key]
            multiplier = 100 if cfg.get('display') == 'percent' else 1
            if type(value) not in (int, float) or not math.isfinite(value) or not cfg['min'] <= value*multiplier <= cfg['max']:
                raise ValueError('bridge_assumption_bounds')
    return doc


def load(root, projects):
    root = Path(root)
    path = root / 'data/site_model_bridges.json'
    if not path.exists():
        return None
    doc = json.loads(path.read_text())
    spec = json.loads((root / 'data/datacenter_model.json').read_text())
    validate(doc, projects, spec)
    bom=json.loads((root/'framework/bom.json').read_text())
    nodes={'system:'+k for k in bom['systems']} | {'part:'+p['id'] for p in bom['parts']}
    for site in doc['sites']:
        if any(c.get('node') not in nodes for c in site['configurations']):
            raise ValueError('bridge_configuration_node')
    return doc


def _public(value, shape):
    """Exact nested field boundary; unknown future metadata stays internal."""
    if isinstance(shape, dict):
        return {k: _public(value[k], child) for k, child in shape.items() if k in value}
    if isinstance(shape, list):
        return [_public(v, shape[0]) for v in value]
    if value is None or type(value) in (str, bool, int, float):
        return copy.deepcopy(value)
    raise ValueError('bridge_public_leaf')


def _fields(keys):
    return dict.fromkeys(keys.split())


SOURCE = {**_fields('id url status sha256 text_sha256 checked_scope total_pages remaining_pages'),
          'text_review_pages': [None], 'visual_review_pages': [None]}
DERIVATION = {**_fields('id output_item_id source_id locator formula scope review_state'),
              'input_item_ids': [None], 'assumptions': [None]}
EVIDENCE = {**_fields('id label state source_id locator reason observation_id'), 'observation_ids': [None],
            'followup': {**_fields('status conclusion at'), 'item_ids': [None]}}
CLAIM = {**_fields('id label content status measurement_kind effective_at scope source_url locator node value unit note'),
         'quantity': _fields('value unit'), 'relations': _fields('shared redundancy included_in'),
         'evidence_ids': [None], 'missing': [None]}
BRIDGE = {
    **_fields('site_id observation_id expected_it_mw review_sha256 expected_observation_sha256'),
    'scope': _fields('id label effective_at physical_scope included excluded actor accounting_basis'),
    'configurations': [CLAIM], 'economic_candidates': [CLAIM], 'unknowns': [None],
    'rules': [{**_fields('id target kind source_field conditions value'), 'evidence_ids': [None], 'independent_of': [None]}],
    'demo_assumptions': _fields('load_factor pue'),
    'coverage': [_fields('angle item state destination reason')],
    'blockers': [{**_fields('id status label reason automatic_fill'), 'evidence_ids': [None],
                  'blocked_targets': [None], 'exception_rule_ids': [None]}],
    'review': {**_fields('id reviewed_at input_sha256 result_sha256 checklist_version checklist_sha256 inventory_units report_exhaustive'),
               'item_counts': _fields('anomaly candidate excluded existing_observation not_applicable not_checked unknown unread_attachment'),
               'sources': [SOURCE], 'items': [EVIDENCE], 'derivations': [DERIVATION], 'limitations': [None]}}


def project(root, projects, site_id):
    doc = load(root, projects)
    if not doc:
        return None
    item = next((s for s in doc['sites'] if s['site_id'] == site_id), None)
    if not item:
        return None
    out = _public(item, BRIDGE)
    site = next(s for s in projects if s['site_id'] == site_id)
    obs = next(o for o in site['observations'] if o['id'] == item['observation_id'])
    out.update(version=doc['version'], mapping_version=doc['mapping_version'], data_sha256=digest(item),
               observation_sha256=digest(obs))
    out['model_source_sha256'] = hashlib.sha256((Path(root)/'data/datacenter_model.json').read_bytes()).hexdigest()
    out['capacity_source'] = {'observation_id': obs['id'], 'kind': obs['kind'],
                              'effective_at': obs['effective_at'], 'basis': obs['basis'],
                              'sources': [_public(v, _fields('url date grade note')) for v in obs.get('sources', [])],
                              'source_versions': [s['source_sha256'] for s in obs.get('source_versions', [])]}
    out['readiness'] = {'status': 'scenario_only', 'project_feasibility': 'not_verified'}
    return out
