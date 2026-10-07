"""Read-only, all-company audit of the current received product catalogs."""
import argparse
import json
from pathlib import Path
import sqlite3

from .catalog_ownership import audit
from .product_catalog import COMPANIES, database


def inspect(root):
    reports = []
    for company in COMPANIES:
        path = database(root, company)
        if not path.is_file():
            reports.append({'company_id':company, 'available':False, 'checked_entities':0})
            continue
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True) as db:
            run = db.execute('SELECT id,generated FROM runs ORDER BY generated DESC LIMIT 1').fetchone()
            if not run:
                reports.append({'company_id':company, 'available':False, 'checked_entities':0})
                continue
            rows = db.execute("""SELECT id,json_extract(payload,'$.name'),json_extract(payload,'$.company_id'),
                json_extract(payload,'$.source_url'),json_extract(payload,'$.product_url'),
                json_extract(payload,'$.source_sha256') FROM products WHERE run_id=? ORDER BY id""", (run[0],))
            products = [dict(zip(('id','name','company_id','source_url','product_url','source_sha256'), row)) for row in rows]
            reports.append({**audit(products, company), 'available':True, 'generated_at':run[1]})
    checked = sum(r['checked_entities'] for r in reports)
    return {'ok':checked > 0, 'checked_entities':checked, 'reports':reports,
            'conflicts':sum(r.get('conflicts',0) for r in reports),
            'review_required':sum(r.get('review_required',0) for r in reports)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(argv)
    value = inspect(args.root)
    print(json.dumps(value, ensure_ascii=False, indent=2))
    if not value['ok']:
        raise SystemExit('No received catalog entities checked; not an ownership pass.')


if __name__ == '__main__':
    main()
