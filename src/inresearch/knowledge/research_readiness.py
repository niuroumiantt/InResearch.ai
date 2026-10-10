"""Read-only research readiness and supply reconciliation, in explicit units.

No paths, source bodies, account data, writes, or implicit adoption. Runtime feeds
are observations from different scopes, never a cumulative conversion funnel.
"""
from collections import Counter


def _received(feed, target_id, key=None):
    if not isinstance(feed, dict) or not isinstance(feed.get('by_target'), dict):
        return None
    value = feed['by_target'].get(target_id, 0)
    if key:
        value = value.get(key) if isinstance(value, dict) else (0 if value == 0 else None)
    return value if type(value) is int and 0 <= value <= 10**9 else None


def summarize(target_doc, questions, knowledge, model, graph, *,
              completed_question_ids=None, supported_statement_ids=None, acquisition=None):
    targets = target_doc['targets']
    evidence = model.get('evidence', {})
    primary = {key: row for row in targets for key in row.get('feeds_primary', [])}
    unresolved = {key for key, value in evidence.items() if value.get('status') not in ('sourced', 'input')}
    drivers = {row['key']: row for row in model.get('sensitivity_drivers', [])}
    critical = []
    for key in sorted(unresolved, key=lambda k: (evidence[k].get('status') != 'needed', k not in drivers, k)):
        row = primary.get(key, {})
        critical.append({'key': key, 'label': drivers.get(key, {}).get('label', key),
            'status': evidence[key].get('status'), 'target_id': row.get('id'),
            'team': row.get('team'), 'team_state': row.get('team_state'),
            'declared_sensitivity_driver': key in drivers})
    acquisition = acquisition or {}
    provider_rows, differences = [], []
    for team in sorted({row['team'] for row in targets}):
        rows = [row for row in targets if row['team'] == team]
        statuses = Counter(row['status'] for row in rows)
        feed = acquisition.get('news_feed' if team == 'inews' else 'fetchspec_feed') if team in ('inews', 'fetchspec') else None
        counts = [_received(feed, row['id'], 'received_items' if team == 'fetchspec' else None) for row in rows]
        seen = [row for row, count in zip(rows, counts) if count is not None and count > 0]
        lagging = [row for row in seen if row['status'] == 'needed']
        provider_rows.append({'team': team, 'connected': any(row['team_state'] == 'connected' for row in rows),
            'targets': len(rows), 'statuses': dict(statuses),
            'runtime_observed_targets': len(seen) if isinstance(feed, dict) and isinstance(feed.get('by_target'), dict) else None,
            'runtime_received_git_needed': len(lagging) if isinstance(feed, dict) and isinstance(feed.get('by_target'), dict) else None,
            'runtime_scope': 'current_news_window' if team == 'inews' else 'received_originals' if team == 'fetchspec' else 'not_connected'})
        differences.extend({'target_id': row['id'], 'team': team, 'git_status': row['status']} for row in lagging)
    question_ids = {q['id'] for q in questions}
    mapped = {qid for row in targets for qid in row.get('request', {}).get('question_ids', []) if qid in question_ids}
    return {'schema_version': 1,
        'questions': {'total': len(questions),
            'answered': len(question_ids & set(completed_question_ids)) if completed_question_ids is not None else None,
            'with_exact_target_link': len(mapped),
            'targets_without_exact_question': sum(not row.get('request', {}).get('question_ids') for row in targets)},
        'formal': {'documents': len(knowledge.get('documents', [])), 'evidence': len(knowledge.get('evidence', [])),
            'statements': len(knowledge.get('statements', [])), 'answers': len(knowledge.get('answers', [])),
            'supported_statements': len(supported_statement_ids) if supported_statement_ids is not None else None},
        'model': {'inputs': len(model['inputs']), 'evidence_statuses': dict(Counter(v.get('status', 'unknown') for v in evidence.values())),
            'unresolved': len(unresolved), 'critical_inputs': critical,
            'mixed_sourced_targets': [row['id'] for row in targets if row['status'] == 'sourced' and
                any(evidence.get(key, {}).get('status') not in ('sourced', 'input') for key in row.get('model_inputs', []))]},
        'graph': {'relations': dict(Counter(row['type'] for row in graph.get('relations', [])))},
        'providers': provider_rows, 'reconciliation': differences,
        'boundaries': ['sourced is a registered source claim, not suitability for every scenario',
            'question links are same-node/variable retrieval, not semantic proof',
            'runtime presence does not change Git status or C3 adoption',
            'current news window and cumulative original receipts have different denominators']}
