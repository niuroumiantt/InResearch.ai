"""交付回执 → Git 内载体（06「目标行状态四态与 Git 内登记载体」，2026-09-29）。

四态里的 delivered 只认 Git 内载体，而线上 register_delivery、Spark fetchspec-receive 与价格录入都只写运行库，
运行库永远不回 Git——所以此前没有任何路径能让一行进入 delivered。这里补上那条通道，且只有这一条：

    python3 manage.py deliveries import --assignments <运行库导出的 assignments.json> [--by 名字]
    python3 manage.py deliveries check

在作者 checkout 里运行：把运行库 ``data/assignments.json`` 里带 ``delivery`` 的记录（``register_delivery`` 写的交付指针）
逐条变成 ``data/event_cards.json`` 的事件卡（``target_id`` + ``origin_pointer``），然后重跑目标表，走 PR。
事件卡是 ``knowledge/targets.py`` 认的三种载体之一，任何数据类别的行都可以经它进入 delivered。
不自动、不在网站上跑、不改目标表本身；重复导入同一条指针是幂等的。
"""
import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from inresearch.paths import project_root

ROOT = project_root()
EVENT_CARDS = 'data/event_cards.json'
TARGETS = 'framework/tco_targets.json'


def load_cards(root):
    path = Path(root) / EVENT_CARDS
    if not path.exists():
        return {'version': '1.0', 'records': []}
    return json.loads(path.read_text(encoding='utf-8'))


def pointer_kind(value):
    """公网 URL 是 url；仓库内相对路径是 repo_path；其余拒绝。"""
    if not isinstance(value, str) or not value.strip():
        return None
    parts = urlsplit(value)
    if parts.scheme in ('http', 'https') and parts.hostname and not parts.username and not parts.password:
        return 'url'
    if not value.startswith('/') and '..' not in value.split('/') and ' ' not in value:
        return 'repo_path'
    return None


def import_assignments(root, assignments_path, by=None, today=None):
    """把运行库派工文件里的交付指针写成事件卡。返回 {imported, skipped, cards}。不重跑目标表。"""
    root = Path(root)
    today = today or date.today().isoformat()
    runtime = json.loads(Path(assignments_path).read_text(encoding='utf-8'))
    targets = {t['id']: t for t in json.loads((root / TARGETS).read_text(encoding='utf-8'))['targets']}
    doc = load_cards(root)
    seen = {(c.get('target_id'), c.get('origin_pointer')) for c in doc['records']}
    imported, skipped = [], []
    for rec in runtime.get('records', []):
        delivery = rec.get('delivery') or {}
        tid, pointer = rec.get('target_id'), delivery.get('evidence_path')
        kind = pointer_kind(pointer)
        if tid not in targets:
            skipped.append({'target_id': tid, 'reason': 'unknown target'})
            continue
        if kind is None:
            skipped.append({'target_id': tid, 'reason': 'no usable evidence_path'})
            continue
        if (tid, pointer) in seen:
            skipped.append({'target_id': tid, 'reason': 'already imported'})
            continue
        t = targets[tid]
        card = {'target_id': tid, 'part_id': t.get('part_id'), 'site_right_id': t.get('site_right_id'), 'team': t.get('team'),
                'origin_pointer': pointer, 'pointer_kind': kind, 'delivered_at': delivery.get('at'),
                'delivered_by': delivery.get('by') or rec.get('assignee'), 'note': (delivery.get('note') or '')[:500],
                'imported_at': today, 'imported_by': by or None, 'source': 'assignments.register_delivery'}
        doc['records'].append(card)
        seen.add((tid, pointer))
        imported.append(card)
    doc['version'] = doc.get('version', '1.0')
    doc['updated'] = today
    doc.setdefault('note', '事件卡：目标行的 Git 内交付载体之一（06）。每条 = 目标行 ID + 原件指针（公网 URL 或仓库内相对路径）。'
                           '只由 manage.py deliveries import 从运行库回执生成，不手写；进入 delivered 后仍不是序列，正式采用另走研究流程。')
    (root / EVENT_CARDS).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return {'imported': imported, 'skipped': skipped, 'cards': len(doc['records'])}


def check(root):
    """每张卡：目标行存在、指针可用、不重复。返回错误列表。"""
    root = Path(root)
    targets = {t['id'] for t in json.loads((root / TARGETS).read_text(encoding='utf-8'))['targets']}
    errors, seen = [], set()
    for c in load_cards(root)['records']:
        key = (c.get('target_id'), c.get('origin_pointer'))
        if c.get('target_id') not in targets:
            errors.append(f"event card for unknown target {c.get('target_id')}")
        if pointer_kind(c.get('origin_pointer')) is None:
            errors.append(f"event card {c.get('target_id')}: origin_pointer unusable")
        if key in seen:
            errors.append(f"duplicate event card {key}")
        seen.add(key)
    return errors


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    imp = sub.add_parser('import', help='runtime assignments.json → data/event_cards.json, then rebuild the target list')
    imp.add_argument('--assignments', required=True, help='path to the runtime assignments.json exported from the site')
    imp.add_argument('--by', help='who is importing (recorded on each card)')
    imp.add_argument('--no-refresh', action='store_true', help='do not rebuild framework/tco_targets.json afterwards')
    sub.add_parser('check', help='every card names an existing target with a usable pointer, no duplicates')
    args = ap.parse_args(argv)
    if args.cmd == 'check':
        errors = check(ROOT)
        for e in errors:
            print('ERROR:', e)
        print(f"event cards: {len(load_cards(ROOT)['records'])}; {'ok' if not errors else str(len(errors)) + ' error(s)'}")
        return 1 if errors else 0
    result = import_assignments(ROOT, args.assignments, by=args.by)
    print(json.dumps({'imported': len(result['imported']), 'skipped': result['skipped'], 'cards': result['cards']}, ensure_ascii=False))
    if not args.no_refresh:
        from inresearch.knowledge import targets as targets_mod
        doc = targets_mod.build(ROOT)
        (ROOT / targets_mod.TARGETS).write_text(targets_mod.render(doc), encoding='utf-8')
        print(f"targets rebuilt: delivered {doc['counts']['by_status']['delivered']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
