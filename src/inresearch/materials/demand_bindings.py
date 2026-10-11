"""Explicit source-to-demand links; these arrange reading, never prove support."""
import hashlib
import json
import re
from pathlib import Path

from inresearch.knowledge.target_request_contract import resolve_request, target_node


def requirement_digest(requirement):
    return hashlib.sha256(json.dumps(requirement, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate(value):
    """Validate frozen supplier metadata without interpreting a current rule."""
    if not isinstance(value, list) or not 1 <= len(value) <= 32:
        raise ValueError('invalid_research_requests')
    if len(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()) > 12000:
        raise ValueError('research_requests_context_too_large')
    required = {'target_version', 'target_id', 'requirement_id', 'requirement_sha256',
                'question_id', 'scope_values', 'purpose'}
    seen = set()
    for row in value:
        if not isinstance(row, dict) or not required <= row.keys() or set(row) - required - {'demand_id'}:
            raise ValueError('invalid_research_request')
        for key in required - {'scope_values', 'requirement_sha256'}:
            if not isinstance(row[key], str) or not row[key].strip() or len(row[key]) > (3000 if key == 'purpose' else 256):
                raise ValueError('invalid_research_request_' + key)
        if not re.fullmatch('[0-9a-f]{64}', str(row['requirement_sha256'])):
            raise ValueError('invalid_research_request_digest')
        if not row['requirement_id'].startswith(row['target_id'] + '::'):
            raise ValueError('research_request_parent_mismatch')
        scopes = row['scope_values']
        if (not isinstance(scopes, dict) or not 1 <= len(scopes) <= 32
                or any(not isinstance(k, str) or not 1 <= len(k) <= 80 or not isinstance(v, str)
                       or not v.strip() or len(v) > 500 for k, v in scopes.items())):
            raise ValueError('invalid_research_request_scope')
        if 'demand_id' in row and (not isinstance(row['demand_id'], str)
                or not re.fullmatch(r'demand-[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}', row['demand_id'])):
            raise ValueError('invalid_research_request_demand_id')
        identity = (row['requirement_id'], row['question_id'])
        if identity in seen:
            raise ValueError('duplicate_research_request')
        seen.add(identity)
    return value


def resolve(value, root):
    """Resolve only the exact registered definition, retaining its unverified state."""
    document = json.loads((Path(root) / 'framework/tco_targets.json').read_text())
    targets = {t['id']: t for t in document['targets']}
    out = []
    for row in validate(value):
        if row['target_version'] != document['version']:
            raise ValueError('research_request_target_version_changed')
        target = targets.get(row['target_id'])
        if target is None:
            raise ValueError('research_request_target_missing')
        request = resolve_request(target, row['requirement_id'])
        if requirement_digest(request) != row['requirement_sha256']:
            raise ValueError('research_request_definition_changed')
        if row['question_id'] not in request['question_ids']:
            raise ValueError('research_request_question_not_reviewed')
        if set(row['scope_values']) != set(request['scope_fields']):
            raise ValueError('research_request_scope_fields_mismatch')
        out.append(dict(row, node=target_node(target), model_input=request['model_input'],
                        source_team=request['source_team'], mechanism=request['mechanism'],
                        team_state=request['team_state'], acceptance=request['acceptance'],
                        evidence_status='unverified', relationship='requested_reading_only'))
    return out
