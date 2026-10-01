"""Fetchspec 回流（2026-10-01，fetchspec 申请 #301）：按目标行汇总已接收的规格原件。

在 Spark 上随 acquisition.summary 一起发布，网站只读这份计数，不读运行库原件。只是计数与厂商名：
目标行 ID 本来就在公开的 framework/tco_targets.json 里；不含 URL、文件名、原件或研究结论。
"""
import json
import sqlite3
from pathlib import Path


def by_target(data_root):
    """{target_id: {received_items, companies, last_received_at, parameter_observations}}；台账不存在时为空。"""
    path = Path(data_root) / 'acquisition/catalog.sqlite'
    if not path.is_file():
        return {}
    con = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        rows = con.execute('''SELECT i.metadata, d.company_id, max(d.received_at)
            FROM items i JOIN product_documents d ON d.source_item_id = i.source_key
            WHERE i.source = 'fetchspec' GROUP BY i.id''').fetchall()
    finally:
        con.close()
    result = {}
    for metadata, company, received_at in rows:
        try:
            meta = json.loads(metadata)
        except (TypeError, ValueError):
            continue
        sha = meta.get('sha256')
        observations = meta.get('parameter_observations') or []
        for target in meta.get('target_ids') or []:
            if not isinstance(target, str):
                continue
            row = result.setdefault(target, {'shas': set(), 'companies': set(), 'last_received_at': None, 'parameter_observations': 0})
            if isinstance(sha, str):
                row['shas'].add(sha)
            if isinstance(company, str) and company:
                row['companies'].add(company)
            if isinstance(received_at, str) and (row['last_received_at'] is None or received_at > row['last_received_at']):
                row['last_received_at'] = received_at
            row['parameter_observations'] += sum(1 for o in observations if isinstance(o, dict) and o.get('target_id') == target)
    return {t: {'received_items': len(r['shas']), 'companies': sorted(r['companies']),
                'last_received_at': r['last_received_at'], 'parameter_observations': r['parameter_observations']}
            for t, r in sorted(result.items())}


def feed(data_root):
    return {'by_target': by_target(data_root)}
