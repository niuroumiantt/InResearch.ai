"""Scoped C3 checks for observations and calculations, never model calibration."""
from inresearch.materials.demand_bindings import resolve

VERSION = 'scoped-quantitative-support-v1'
KINDS = {'observation', 'calculation'}
STATUSES = {'usable_reference', 'partial_support', 'out_of_scope', 'missing_evidence'}
CHECKS = ('scope_check', 'units_check', 'time_check', 'basis_check',
          'derivation_check', 'comparability_check')
INSTRUCTIONS = """
This packet includes an explicit quantitative_support_contract. Review source
observations/calculations in their original kind; never relabel them as author
claims to pass routing. Preserve the measured system, location/phase, software,
workload, units, effective time, estimate assumptions and actual source precision.
A benchmark is a scoped reference, not a universal production GPU rate. Derived
per-GPU allocation is not an independently measured GPU. Facility, IT, connection
quota, forecasts, interconnection construction and approval waiting time differ.
For EVERY review add quantitative_checks with nonempty scope_check, units_check,
time_check, basis_check, derivation_check and comparability_check strings. State
not applicable explicitly, with a reason; do not invent missing conditions.
Also add parameter_assessments: one entry per contract request, retaining its
requirement_id and question_id, with status usable_reference|partial_support|
out_of_scope|missing_evidence, nonempty rationale and model_input_verified:false.
Requested reading is not evidence that a requirement has been fulfilled. Match
the actual claim to the requested scope. Usable reference does not certify a
model input, close a question or authorize replacing a current parameter.
Every proposed B observation/calculation receives an independent second check.
All existing A routing, source support, demand and conflict rules still apply.
"""
SAMPLE_INSTRUCTIONS = """
Independently verify quantitative_checks and every parameter_assessment against
native context and the requested scope. Check numerical meaning, assumptions,
units, time, system configuration and derivation. A source receipt is not support;
an approximate/derived reference must retain that nature. Uncertainty means false.
"""


def contract(requests, root):
    return {'version': VERSION, 'requests': resolve(requests, root)}


def checked_contract(packet):
    value = packet.get('quantitative_support_contract')
    if value is not None and (not isinstance(value, dict) or value.get('version') != VERSION
                             or not isinstance(value.get('requests'), list) or not value['requests']):
        raise ValueError('invalid_quantitative_support_contract')
    return value


def validate(packet, row):
    value = checked_contract(packet)
    if value is None:
        return
    checks = row.get('quantitative_checks')
    if not isinstance(checks, dict) or set(checks) != set(CHECKS) or any(
            not isinstance(checks[k], str) or not checks[k].strip() for k in CHECKS):
        raise ValueError('quantitative_scope_checks_required')
    assessments = row.get('parameter_assessments')
    expected = {(r['requirement_id'], r['question_id']) for r in value['requests']}
    if not isinstance(assessments, list) or len(assessments) != len(expected):
        raise ValueError('complete_parameter_assessments_required')
    identities = []
    for item in assessments:
        if (not isinstance(item, dict) or set(item) != {'requirement_id', 'question_id', 'status',
                                                     'rationale', 'model_input_verified'}
                or any(not isinstance(item[k], str) for k in ('requirement_id', 'question_id', 'status'))
                or item['status'] not in STATUSES or item['model_input_verified'] is not False
                or not isinstance(item['rationale'], str) or not item['rationale'].strip()):
            raise ValueError('invalid_parameter_assessment')
        identities.append((item['requirement_id'], item['question_id']))
        if (item['status'] in {'usable_reference', 'partial_support'}
                and item['question_id'] not in row.get('question_ids', [])):
            raise ValueError('parameter_support_requires_reviewed_question_match')
    if set(identities) != expected:
        raise ValueError('parameter_assessment_identity_mismatch')
