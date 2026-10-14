"""Explicit, isolated local reception of fetchdata-handoff/1 candidate packages.

No HTTP route, production storage, object matching, adoption or model writes.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('handoff_local_validator', ROOT/'scripts/validate_collector_handoff.py')
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
MARKER = 'inresearch-collector-sandbox/1\n'
METADATA = ('manifest.json', 'observations.jsonl', 'errors.jsonl', 'run-report.json', 'SHA256SUMS')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory(package):
    package = Path(package).resolve()
    manifest = validator._json(package, 'manifest.json')
    paths = sorted(set(METADATA) | {i['path'] for i in manifest['items']})
    if len(paths) > 10005:
        raise ValueError('local package file limit exceeded')
    hashes = {}
    size = 0
    for relative in paths:
        p = validator._file(package, relative)
        size += p.stat().st_size
        if p.stat().st_size > 20*1024*1024 or size > 80*1024*1024:
            raise ValueError('local receiver byte budget exceeded')
        hashes[relative] = digest(p.read_bytes())
    return hashes


@contextmanager
def sandbox(path):
    root = Path(path).expanduser()
    if not root.is_absolute() or root.is_symlink():
        raise ValueError('explicit absolute sandbox root required')
    root = root.resolve()
    if root == ROOT or ROOT in root.parents:
        raise ValueError('sandbox must be outside source checkout')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (root/'.sandbox.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        marker = root/'SANDBOX'
        if not marker.exists():
            if any(p.name != '.sandbox.lock' for p in root.iterdir()):
                raise ValueError('refuse existing unmarked directory/database')
            marker.write_text(MARKER)
        if marker.is_symlink() or marker.read_text() != MARKER:
            raise ValueError('not a collector sandbox')
        if (root/'receipts.sqlite3').is_symlink() or (root/'packages').is_symlink():
            raise ValueError('sandbox storage symlink rejected')
        yield root


def receive(package, sandbox_root):
    package = Path(package).expanduser()
    if package.is_symlink():
        raise ValueError('package root symlink rejected')
    package = package.resolve()
    # Freeze selected validated bytes before any persistent candidate reception.
    with tempfile.TemporaryDirectory(prefix='collector-receive-') as tmp:
        stage = Path(tmp).resolve()
        before = inventory(package)
        for relative in before:
            dest = stage/relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(validator._file(package, relative), dest)
        if inventory(stage) != before:
            raise ValueError('package changed during snapshot')
        report = validator.validate(stage)
        if not report['offline_valid']:
            raise ValueError('invalid package/candidates; retain source and repair separately')
        manifest = json.loads((stage/'manifest.json').read_text())
        rows = [r for _, r in validator._rows(stage, 'observations.jsonl')]
        provider, delivery = manifest['provider_id'], manifest['delivery_id']
        fingerprint = digest(canonical(before).encode())
        with sandbox(sandbox_root) as root:
            with sqlite3.connect(root/'receipts.sqlite3', timeout=10) as db:
                db.executescript('''
                  CREATE TABLE IF NOT EXISTS deliveries(
                    provider TEXT, id TEXT, fingerprint TEXT, receipt TEXT,
                    PRIMARY KEY(provider,id));
                  CREATE TABLE IF NOT EXISTS originals(sha TEXT PRIMARY KEY, first_received_at TEXT);
                  CREATE TABLE IF NOT EXISTS items(
                    provider TEXT,id TEXT,payload TEXT,first_received_at TEXT,PRIMARY KEY(provider,id));
                  CREATE TABLE IF NOT EXISTS observations(
                    provider TEXT,id TEXT,payload TEXT,first_received_at TEXT,PRIMARY KEY(provider,id));
                  CREATE TABLE IF NOT EXISTS delivery_observations(
                    provider TEXT,delivery TEXT,observation TEXT,PRIMARY KEY(provider,delivery,observation));
                ''')
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT fingerprint,receipt FROM deliveries WHERE provider=? AND id=?', (provider,delivery)).fetchone()
                archive = root/'packages'/fingerprint
                if existing:
                    if existing[0] != fingerprint:
                        raise ValueError('delivery ID collision; original receipt retained')
                    if inventory(archive) != before:
                        raise ValueError('received archive changed; investigate without overwriting')
                    return {**json.loads(existing[1]), 'replayed': True,
                            'current_receive_counts': {'new_originals': 0, 'new_source_items': 0, 'new_candidates': 0}}
                received = datetime.now(timezone.utc).isoformat()
                counts = {'new_originals': 0, 'new_source_items': 0, 'new_candidates': 0}
                for item in manifest['items']:
                    # Content/source identity is separate from acquisition events/clocks.
                    identity = {k:v for k,v in item.items() if k not in ('retrieved_at','reused_at','provenance_id')}
                    payload = canonical(identity)
                    old = db.execute('SELECT payload FROM items WHERE provider=? AND id=?', (provider,item['item_id'])).fetchone()
                    if old and old[0] != payload:
                        raise ValueError('source item ID collision')
                    if not old:
                        db.execute('INSERT INTO items VALUES(?,?,?,?)', (provider,item['item_id'],payload,received))
                        counts['new_source_items'] += 1
                    inserted = db.execute('INSERT OR IGNORE INTO originals VALUES(?,?)', (item['sha256'],received))
                    counts['new_originals'] += inserted.rowcount
                for row in rows:
                    payload = canonical(row)
                    old = db.execute('SELECT payload FROM observations WHERE provider=? AND id=?', (provider,row['observation_id'])).fetchone()
                    if old and old[0] != payload:
                        raise ValueError('observation ID collision; no overwrite or partial receive')
                    if not old:
                        db.execute('INSERT INTO observations VALUES(?,?,?,?)', (provider,row['observation_id'],payload,received))
                        counts['new_candidates'] += 1
                    db.execute('INSERT INTO delivery_observations VALUES(?,?,?)', (provider,delivery,row['observation_id']))
                receipt = {'receipt_contract': 'collector-local-receipt/1', 'local_only': True,
                    'provider_id': provider, 'delivery_id': delivery, 'package_sha256': fingerprint,
                    'collector_revision': manifest['collector_revision'], 'first_received_at': received,
                    'candidate_rows': len(rows), 'status': 'candidate_unreviewed', 'counts': counts,
                    'formal_adoption': False, 'model_parameters_written': 0, 'published': False}
                archive.parent.mkdir(mode=0o700, exist_ok=True)
                if archive.exists():
                    if inventory(archive) != before:
                        raise ValueError('archive conflict; preserve for inspection')
                else:
                    # Interrupted copies never occupy the final immutable archive path.
                    with tempfile.TemporaryDirectory(prefix='.pending-', dir=archive.parent) as pending:
                        target = Path(pending)/'package'
                        shutil.copytree(stage, target)
                        target.rename(archive)
                db.execute('INSERT INTO deliveries VALUES(?,?,?,?)', (provider,delivery,fingerprint,canonical(receipt)))
                db.commit()
                return {**receipt, 'replayed': False, 'current_receive_counts': counts}
