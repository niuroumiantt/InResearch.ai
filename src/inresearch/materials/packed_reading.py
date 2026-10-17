"""Frozen 64-fragment reading for untouched campus packages only.

The intake process lock serializes recipe choice and all writes. A dispatch is
journaled before its HTTP request; a lost outcome is never an invitation to
regenerate. Only a measured *input* overflow may split a not-yet-generated part.
"""
import hashlib
import json

from inresearch.adapters import models
from inresearch.materials.inbox import atomic

VERSION = 'campus-packed-reading-v1'
STAGE = 'native_campus_reading'
LEGACY = 'legacy-byte-reading'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def select_recipe(package_folder, source_sha, manifest_sha, package_id):
    """Do not upgrade any started package, including another task-SHA directory."""
    marker = package_folder/'reading-recipe.json'
    expected = {'version': VERSION, 'source_sha256': source_sha,
                'manifest_sha256': manifest_sha, 'package_id': package_id}
    if marker.exists():
        if json.loads(marker.read_text()) != expected:
            raise ValueError('campus_reading_recipe_changed')
        return VERSION
    # Even a partial or malformed old checkpoint proves the package was started.
    # Retain that recipe and let its existing integrity checks handle corruption.
    for path in package_folder.rglob('*'):
        if path.is_file() and (path.name in ('plan.json', 'progress.json', 'proposal.json')
                or path.name.startswith('chunk-') or path.name.startswith('adjudication')
                or path.name == 'dispatch.json'):
            return LEGACY
    atomic(marker, expected)
    return VERSION


def _bound_evidence(evidence, system, part, schema, *, over_budget=False):
    """Validate the durable adapter receipt against this exact frozen window."""
    if not isinstance(evidence, dict):
        raise ValueError('campus_reading_audit_changed')
    body, proof = evidence.get('request'), evidence.get('token_budget')
    if not isinstance(body, dict) or not isinstance(proof, dict):
        raise ValueError('campus_reading_audit_changed')
    request_sha = digest(body)
    if (evidence.get('request_sha256') != request_sha or proof.get('request_sha256') != request_sha
            or proof.get('input_sha256') != digest(part)
            or proof.get('system_sha256') != hashlib.sha256(system.encode()).hexdigest()
            or proof.get('schema_sha256') != digest(schema)
            or body.get('messages') != [{'role': 'system', 'content': system},
                                       {'role': 'user', 'content': encoded(part).decode()}]
            or body.get('format') != schema or body.get('model') != 'qwen3.8:27b'
            or body.get('options', {}).get('num_ctx') != 32768
            or body.get('options', {}).get('num_predict') != 4096
            or body.get('truncate') is not False or body.get('shift') is not False
            or body.get('think') is not False or body.get('stream') is not False
            or proof.get('version') != 'ollama-campus-token-v2'
            or proof.get('stage') != STAGE or proof.get('reading_recipe') != VERSION
            or proof.get('truncate') is not False or proof.get('shift') is not False
            or proof.get('think') is not False
            or proof.get('context') != 32768 or proof.get('max_output_tokens') != 4096
            or proof.get('reserve_tokens') != 1024
            or type(proof.get('input_tokens')) is not int or proof['input_tokens'] <= 0
            or not proof.get('model_binding') or not proof.get('tokenizer_binding')
            or (proof['input_tokens']+4096+1024 > 32768) != over_budget):
        raise ValueError('campus_reading_audit_changed')
    return proof


def _bound_result(result, evidence):
    response = evidence.get('response')
    model = result.get('_model', {}) if isinstance(result, dict) else {}
    if (not isinstance(response, dict) or evidence.get('response_sha256') != digest(response)
            or response.get('model') != 'qwen3.8:27b' or response.get('done') is not True
            or response.get('done_reason') != 'stop'
            or model.get('input_sha256') != evidence['token_budget']['input_sha256']):
        raise ValueError('campus_reading_audit_changed')
    parsed = models.json_object(response.get('message', {}).get('content'))
    if ({key: value for key, value in result.items() if key != '_model'}
            != {key: value for key, value in parsed.items() if key != '_model'}):
        raise ValueError('campus_reading_audit_changed')
    budget = model.get('token_budget', {})
    expected = {**evidence['token_budget'], 'generation_binding': {
        'model_binding_sha256': digest(evidence['token_budget']['model_binding']),
        'request_sha256': evidence['request_sha256'], 'actual_model': response['model'],
        'model_verified_before_and_after': True, 'response_sha256': digest(response)}}
    if budget != expected:
        raise ValueError('campus_reading_audit_changed')


def _audit_path(folder, index, failures, part):
    return folder/'reading-audits'/f'chunk-{index:05d}'/digest(part)/f'attempt-{failures+1:02d}'


def _verified_return(saved, dispatch, system, part, schema):
    if (not isinstance(saved, dict)
            or set(saved) != {'result', 'result_sha256', 'completion', 'completion_sha256'}
            or saved['result_sha256'] != digest(saved['result'])
            or saved['completion_sha256'] != digest(saved['completion'])):
        raise ValueError('campus_reading_audit_changed')
    evidence = saved['completion']
    _bound_evidence(evidence, system, part, schema)
    _bound_result(saved['result'], evidence)
    if not dispatch.exists() or json.loads(dispatch.read_text()) != {
            key: evidence[key] for key in ('request', 'request_sha256', 'token_budget')}:
        raise ValueError('campus_reading_audit_changed')
    return saved['result']


def generate(client, system, part, schema, folder, index, failures, before_completion):
    """Verify a durable return before promotion; never replay an unknown dispatch."""
    audit = _audit_path(folder, index, failures, part)
    dispatch = audit/'dispatch.json'
    response_path = audit/'response.json'
    returned_path = audit/'returned.json'
    if response_path.exists():
        saved = json.loads(response_path.read_text())
        result = _verified_return(saved, dispatch, system, part, schema)
        # Receipts predating the return journal remain valid and byte-identical.
        # A journal that does exist must still agree with the accepted response.
        if returned_path.exists() and json.loads(returned_path.read_text()) != saved:
            raise ValueError('campus_reading_audit_changed')
        return result
    if returned_path.exists():
        if (audit/'unverified.json').exists():
            raise models.InferenceError('campus_reading_completion_outcome_unverified')
        saved = json.loads(returned_path.read_text())
        result = _verified_return(saved, dispatch, system, part, schema)
        atomic(response_path, saved)
        return result
    if dispatch.exists() or (audit/'unverified.json').exists():
        raise models.InferenceError('campus_reading_completion_outcome_unverified')

    def before_dispatch(body, proof):
        evidence = {'request': body, 'request_sha256': digest(body), 'token_budget': proof}
        _bound_evidence(evidence, system, part, schema)
        # Called after the final GPU/model checks, immediately before sending.
        # Persist before dispatch so process death/timeout cannot silently replay.
        if dispatch.exists():
            raise ValueError('campus_reading_dispatch_already_exists')
        atomic(dispatch, evidence)

    try:
        result, evidence = client.generate_campus_reading(system, encoded(part).decode(),
            json_schema=schema, before_completion=before_completion, before_dispatch=before_dispatch)
    except models.InferenceError as error:
        completion = getattr(error, 'completion_evidence', None)
        if completion is not None:
            atomic(audit/'unverified.json', {'completion': completion,
                                           'completion_sha256': digest(completion)})
        raise
    # Persist the complete adapter return before any consumer binding checks.
    # The intake lock serializes these write-once journals. Failed validation
    # cannot erase the returned body or turn a later cycle into a new dispatch.
    if returned_path.exists():
        raise ValueError('campus_reading_audit_changed')
    atomic(returned_path, {'result': result, 'result_sha256': digest(result),
                          'completion': evidence, 'completion_sha256': digest(evidence)})
    saved = json.loads(returned_path.read_text())
    result = _verified_return(saved, dispatch, system, part, schema)
    atomic(response_path, saved)
    return result


def verify_cached(result, system, part, schema, folder, index, failures):
    if not (_audit_path(folder, index, failures, part)/'response.json').exists():
        raise ValueError('campus_reading_audit_missing')
    if generate(None, system, part, schema, folder, index, failures, None) != result:
        raise ValueError('campus_reading_audit_changed')


def _split(part):
    native = part['native_fragments']
    middle = len(native)//2
    return [{**part, 'native_fragments': native[:middle]},
            {**part, 'native_fragments': native[middle:]}]


def split_budget(error, plan, parts, index, folder, system, schema_for):
    """Only an adapter-proven pre-generation input overflow can change the plan."""
    from inresearch.adapters.ollama_token_budget import ReadingBudgetExceeded
    if not isinstance(error, ReadingBudgetExceeded):
        return False
    part = parts[index]
    evidence = error.budget_evidence
    _bound_evidence(evidence, system, part, schema_for(part), over_budget=True)
    # A dispatch for the same input would contradict the pre-generation proof.
    for path in (folder/'reading-audits'/f'chunk-{index:05d}'/digest(part)).rglob('dispatch.json'):
        raise ValueError('campus_reading_budget_after_dispatch')
    audit_path = folder/'input-budget-checks'/(digest(part)+'.json')
    if audit_path.exists() and json.loads(audit_path.read_text()) != evidence:
        raise ValueError('campus_reading_budget_evidence_changed')
    atomic(audit_path, evidence)
    if len(part['native_fragments']) < 2:
        # Full context plus one lossless fragment cannot be made smaller safely.
        raise error
    plan['splits'].append({'index': index, 'input_sha256': digest(part),
        'error': error.code, 'evidence_sha256': digest(evidence)})
    plan['parts'] = parts[:index]+_split(part)+parts[index+1:]
    return True


def validate_plan(plan, initial_parts, folder, system, schema_for):
    """Replay every measured binary split; repartitioning cannot rewrite history."""
    parts = list(initial_parts)
    for row in plan.get('splits', []):
        index = row.get('index')
        if type(index) is not int or not 0 <= index < len(parts):
            raise ValueError('campus_reading_split_changed')
        part = parts[index]
        if (row.get('error') != 'campus_reading_token_budget_exceeded'
                or row.get('input_sha256') != digest(part) or len(part['native_fragments']) < 2):
            raise ValueError('campus_reading_split_changed')
        evidence_path = folder/'input-budget-checks'/(digest(part)+'.json')
        if not evidence_path.exists():
            raise ValueError('campus_reading_split_evidence_missing')
        evidence = json.loads(evidence_path.read_text())
        if row.get('evidence_sha256') != digest(evidence):
            raise ValueError('campus_reading_split_changed')
        _bound_evidence(evidence, system, part, schema_for(part), over_budget=True)
        parts[index:index+1] = _split(part)
    if parts != plan.get('parts'):
        raise ValueError('campus_reading_split_changed')
