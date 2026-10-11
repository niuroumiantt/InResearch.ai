"""Derived research dependencies; never change evidence, answers or adoption."""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = 'data/raw/research-gaps/current.json'
SOURCES = ('framework/tco_targets.json', 'framework/research_demand_review.json',
           'data/datacenter_model.json', 'data/facts.json')


def build(root=ROOT):
    root = Path(root)
    docs = {name: json.loads((root / name).read_text()) for name in SOURCES}
    targets = docs[SOURCES[0]]['targets']
    model = docs[SOURCES[2]]
    records = []
    for target in targets:
        request = target['request']
        reasons = []
        if target['team_state'] == 'not_connected':
            reasons.append('source_channel_not_connected')
        if not request['question_ids']:
            reasons.append(request['mapping_review']['disposition'])
        if reasons:
            records.append({'id': 'target:' + target['id'], 'kind': 'target',
                'target_id': target['id'], 'source_owner': target['team'], 'decision_owner': 'research',
                'reasons': reasons, 'state': 'open',
                'next_action': '按已登记交付口径接通来源；缺少用途时先审核问题和关联，不生成占位答案。'})
    for target in targets:
        for requirement in target['request']['requirements']:
            key = requirement['model_input']
            status = model['evidence'][key]['status']
            if status in ('sourced', 'input'):
                continue
            records.append({'id': 'model:' + key, 'kind': 'model_input', 'model_input': key,
                'target_id': target['id'], 'requirement_id': requirement['id'],
                'source_owner': requirement['source_team'], 'decision_owner': requirement['decision_owner'],
                'source_channel': requirement['team_state'], 'evidence_status': status,
                'priority': requirement['priority'], 'affected_outputs': requirement['affected_outputs'],
                'question_ids': requirement['question_ids'], 'state': 'open',
                'next_action': requirement['deliverable'], 'acceptance': requirement['acceptance']})
    for fact in docs[SOURCES[3]]['records']:
        evidence = fact.get('evidence') or {}
        sha = str(evidence.get('sha256') or '')
        if len(sha) == 64 and all(c in '0123456789abcdefABCDEF' for c in sha):
            continue
        records.append({'id': 'fact:' + fact['fact_id'], 'kind': 'original_identity',
            'fact_id': fact['fact_id'], 'metric_id': fact['metric_id'],
            'source_owner': 'archive', 'decision_owner': 'research', 'state': 'open',
            'reasons': ['original_sha256_missing'], 'use_constraint': '不可作为新结论或模型验证的已核验原件依据；旧版本保留，公开输出仍受既有权限规则约束。',
            'next_action': '查原件目录及备份并核对上下文；同一原件才补哈希。新来源另建事实版本；找不到则保留缺口。'})
    return {'version': 1, 'reviewed_at': docs[SOURCES[1]]['reviewed_at'],
        'authority': '派生依赖清单；修改责任和验收回到需求审阅源，证据状态回到正式记录。',
        'source_sha256': {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in SOURCES},
        'counts': {'records': len(records), 'by_kind': dict(Counter(r['kind'] for r in records)),
            'unconnected_parent_targets': sum(t['team_state'] == 'not_connected' for t in targets),
            'same_cell_retrieval_empty': sum(not t['request']['candidate_question_ids'] for t in targets),
            'reviewed_purpose_empty': sum(not t['request']['question_ids'] for t in targets),
            'reviewed_purpose_links': sum(len(t['request']['question_links']) for t in targets)},
        'records': records}


def render(doc):
    return json.dumps(doc, ensure_ascii=False, indent=2) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--refresh', action='store_true')
    group.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    result = build()
    from inresearch.storage.layout import workspace_path
    path = (workspace_path(OUTPUT, ROOT) if os.environ.get('INRESEARCH_RUNTIME_ROOT') else
            Path.home() / '.local/share/inresearch.ai/research-gaps/current.json')
    if args.refresh:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render(result))
    if args.check and (not path.exists() or path.read_text() != render(result)):
        print('Research dependencies stale: python3 manage.py research-gaps --refresh')
        return 1
    print(json.dumps(result['counts'], ensure_ascii=False))
    return 0
