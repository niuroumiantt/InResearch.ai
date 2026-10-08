"""Non-destructive Spark preservation audit and consistent SQLite backups."""
import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from inresearch.paths import project_root
from inresearch.storage.files import write_json


def audit(data, root, snapshot=False):
    data = Path(data).resolve()
    policy = json.loads((Path(root)/'framework/material_retention.json').read_text())
    if policy.get('automatic_expiry') or policy.get('delete_unique_materials'):
        raise ValueError('retention_policy_requires_no_automatic_deletion')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory = data/'material-reviews/retention'/stamp
    catalogs, missing = {}, []
    for relative in ('acquisition/catalog.sqlite', 'catalog/catalog.sqlite'):
        path = data/relative
        if not path.is_file():
            missing.append(relative);continue
        source = sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=30)
        try:
            refs = source.execute('SELECT relative_path FROM observations').fetchall() if relative.startswith('acquisition/') else source.execute('SELECT original_rel FROM documents').fetchall()
            absent = []
            for (ref,) in refs:
                if not ref: absent.append('(missing path)');continue
                candidate = Path(ref) if Path(ref).is_absolute() else data/ref
                if not candidate.is_file(): absent.append(ref)
            entry = {'references': len(refs), 'missing': len(absent), 'missing_examples': absent[:10]}
            if snapshot:
                directory.mkdir(parents=True, exist_ok=True, mode=0o700)
                target = directory/(relative.replace('/', '-')+'.sqlite')
                backup = sqlite3.connect(target)
                try: source.backup(backup)
                finally: backup.close()
                # Reopen so SQLite reads the copied header rather than keeping
                # the destination connection's pre-backup journal-mode cache.
                # Only this new standalone snapshot is changed, not the source.
                finalize = sqlite3.connect(target)
                try:
                    if finalize.execute('PRAGMA journal_mode=DELETE').fetchone()[0]!='delete':
                        raise ValueError('snapshot_journal_not_standalone')
                finally: finalize.close()
                check = sqlite3.connect(target.as_uri()+'?mode=ro', uri=True)
                try:
                    if check.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                        raise ValueError('snapshot_integrity_failed')
                finally: check.close()
                entry['snapshot_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
            catalogs[relative] = entry
        finally: source.close()
    result = {'policy': policy, 'catalogs': catalogs, 'missing_catalogs': missing,
              'scope': 'Catalog-referenced originals only; not a full cloud/NAS inventory or independent disaster backup.',
              'automatic_deletion': False, 'at': stamp}
    write_json(directory/'receipt.json', result)
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data-root', type=Path, required=True)
    ap.add_argument('--root', type=Path, default=project_root())
    ap.add_argument('--snapshot', action='store_true')
    args=ap.parse_args()
    print(json.dumps(audit(args.data_root, args.root, args.snapshot), ensure_ascii=False))


if __name__ == '__main__': main()
