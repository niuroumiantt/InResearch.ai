"""Receive the explicitly enabled fetchstat source into permanent candidate storage.

SSH/file ingress only. No HTTP listener, crawler, Reader enqueue or adoption.
The immutable arrival journal survives failed projections; ACK follows verified
shared acquisition catalog + permanent original materialization.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import subprocess

from inresearch.adapters.acquisition import Collector, hash_file, encoded
from inresearch.materials.artifacts import private_dir
from inresearch.materials.collector_receive import _receive, inventory, canonical
from inresearch.storage.files import locked, sync_directory
from inresearch.paths import project_root

ROOT = project_root()
PROVIDER = 'fetchstat'
MARKER = 'inresearch-collector-production/1\n'


def authorize(manifest):
    contract = json.loads((ROOT/'framework/supply_contract.json').read_text())
    policy = contract.get('collector_reception', {})
    if (manifest['provider_id'] != PROVIDER
            or PROVIDER not in policy.get('enabled_providers', [])):
        raise ValueError('collector_provider_not_enabled')
    allowed = policy.get('sources', {}).get(PROVIDER, [])
    for item in manifest['items']:
        if (item['access_scope'] != 'public'
                or not any(item['source_id'] == source['source_id']
                           and item['source_item_id'] == source['native_id']
                           and item['url'] == source['url'] for source in allowed)):
            raise ValueError('collector_source_not_registered')


@contextmanager
def production_store(path):
    root = Path(path).resolve()
    private_dir(root)
    with (root/'.receiver.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        marker = root/'PRODUCTION'
        if not marker.exists():
            if any(p.name != '.receiver.lock' for p in root.iterdir()):
                raise ValueError('collector_store_unmarked')
            with marker.open('x') as output:
                output.write(MARKER); output.flush(); os.fsync(output.fileno())
            sync_directory(root)
            sync_directory(root.parent)
        if marker.is_symlink() or marker.read_text() != MARKER:
            raise ValueError('collector_store_wrong_mode')
        for name in ('receipts.sqlite3','packages'):
            if (root/name).is_symlink():
                raise ValueError('collector_store_symlink')
        yield root


def source_key(item):
    # Series identity stays stable across source byte versions; supplier item_id
    # and observation_id remain unchanged in the journal and per-version payload.
    return item['source_id'] + ':' + item['source_item_id']


def request_payload(manifest, item, rows):
    return {'contract': manifest['contract'], 'delivery_id': manifest['delivery_id'],
            'collector_revision': manifest['collector_revision'], 'item': item,
            'observations': [r for r in rows if r['source_item_id'] == item['item_id']],
            'acceptance': 'candidate_unreviewed'}


def projections(data, manifest):
    for item in manifest['items']:
        sha = item['sha256']; suffix = Path(item['path']).suffix.lower()
        yield item, data/'acquisition/blobs'/sha[:2]/(sha+suffix), data/'originals'/sha[:2]/sha/(sha+suffix)


def verified(data, manifest, rows):
    dbpath = data/'acquisition/catalog.sqlite'
    with sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True,timeout=10) as db:
        for item, blob, original in projections(data, manifest):
            for path in (blob, original):
                if path.is_symlink(): raise ValueError('collector_projection_symlink')
                if not path.is_file(): return False
                if hash_file(path) != item['sha256']: raise ValueError('collector_projection_corrupt')
            found = db.execute('SELECT id FROM items WHERE source=? AND source_key=?', (PROVIDER,source_key(item))).fetchone()
            if not found: return False
            observation = db.execute('SELECT request_json FROM observations WHERE item_id=? AND sha256=?', (found[0],item['sha256'])).fetchone()
            if not observation: return False
            if json.loads(observation[0]) != request_payload(manifest,item,rows):
                raise ValueError('collector_existing_version_conflict')
    return True


def materialize(data, package, manifest, rows):
    collector = Collector(data)
    def apply():
        for item, blob, original in projections(data, manifest):
            key = source_key(item)
            old = collector.db.execute('SELECT id FROM items WHERE source=? AND source_key=?', (PROVIDER,key)).fetchone()
            if old:
                ident = old['id']
            else:
                ident = collector.item(PROVIDER,key,'collector_document',item['url'],item['title'],
                    {'source_id':item['source_id'],'native_id':item['source_item_id'],
                     'supplier_item_id':item['item_id'],'first_delivery_id':manifest['delivery_id'],
                     'acceptance':'candidate_unreviewed','source_version_history':'observations.request_json'})
            existing = collector.db.execute('SELECT request_json FROM observations WHERE item_id=? AND sha256=?', (ident,item['sha256'])).fetchone()
            payload = request_payload(manifest,item,rows)
            if existing and json.loads(existing['request_json']) != payload:
                raise ValueError('collector_existing_version_conflict')
            # Avoid changing item.updated / observed_at on already materialized versions.
            if not existing or not blob.exists():
                got = collector.archive_file(ident, package/item['path'], blob.suffix, payload)
                if got != item['sha256']: raise ValueError('collector_archive_hash_mismatch')
            elif hash_file(blob) != item['sha256']:
                raise ValueError('collector_projection_corrupt')
            private_dir(original.parent)
            if original.is_symlink(): raise ValueError('collector_projection_symlink')
            if not original.exists():
                # Retain the source's native bytes; no Reader raw-materials handoff.
                os.link(blob, original)
            if hash_file(original) != item['sha256']: raise ValueError('collector_projection_corrupt')
            with blob.open('rb') as stream:
                os.fsync(stream.fileno())
            for directory in (original.parent,original.parent.parent,original.parent.parent.parent,blob.parent,blob.parent.parent):
                sync_directory(directory)
        return len(manifest['items'])
    try:
        return collector.run(PROVIDER,apply)
    finally:
        collector.close()


def receive(package, data_root):
    data = Path(data_root).expanduser()
    if not data.is_absolute() or data.is_symlink():
        raise ValueError('collector_absolute_data_root_required')
    data = data.resolve()
    catalog = data/'acquisition/catalog.sqlite'
    if not catalog.is_file() or catalog.is_symlink():
        raise ValueError('collector_existing_acquisition_catalog_required')
    root = data/'acquisition/collectors'/PROVIDER
    root.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.is_symlink(): raise ValueError('collector_store_symlink')
    with locked(root.parent/(PROVIDER+'-production')):
        arrival = _receive(package,root,store=production_store,production=True,guard=authorize)
        frozen = root/'packages'/arrival['package_sha256']
        manifest = json.loads((frozen/'manifest.json').read_text())
        rows = [json.loads(x) for x in (frozen/'observations.jsonl').read_text().splitlines()]
        with sqlite3.connect(root/'receipts.sqlite3') as db:
            db.execute('CREATE TABLE IF NOT EXISTS production_acks(provider TEXT,id TEXT,receipt TEXT,PRIMARY KEY(provider,id))')
            previous = db.execute('SELECT receipt FROM production_acks WHERE provider=? AND id=?', (PROVIDER,manifest['delivery_id'])).fetchone()
        complete = verified(data,manifest,rows)
        repaired = False
        if not complete:
            materialize(data,frozen,manifest,rows)
            if not verified(data,manifest,rows): raise ValueError('collector_projection_incomplete')
            repaired = bool(previous)
        if previous:
            return {**json.loads(previous[0]), 'replayed': True, 'projection_repaired': repaired,
                    'current_receive_counts': {'new_originals':0,'new_source_items':0,'new_candidates':0}}
        receipt = {k:v for k,v in arrival.items() if k not in ('replayed','current_receive_counts')}
        receipt.update(receipt_contract='collector-production-receipt/1',local_only=False,
            status='received_candidate_unreviewed', archive_completed_at=datetime.now(timezone.utc).isoformat(),
            acquisition_catalog='acquisition/catalog.sqlite', reader_enqueued=0, reviewed=0, adopted=0,
            receiver_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=Path(__file__).resolve().parents[3],text=True).strip(),
            receiver_definition_sha256=hash_file(Path(__file__).resolve()),
            source_policy_sha256=hash_file(ROOT/'framework/supply_contract.json'),
            recovered_after_pending=arrival['replayed'])
        with sqlite3.connect(root/'receipts.sqlite3') as db:
            db.execute('INSERT INTO production_acks VALUES(?,?,?)', (PROVIDER,manifest['delivery_id'],canonical(receipt)))
        sync_directory(root)
        return {**receipt,'replayed':False,'current_receive_counts':arrival['current_receive_counts']}


def main():
    import argparse
    import sys
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('package')
    parser.add_argument('--data-root',required=True)
    parser.add_argument('--expected-receiver-revision',required=True)
    args=parser.parse_args()
    try:
        actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        dirty=subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=ROOT,text=True).strip()
        if actual != args.expected_receiver_revision or dirty:
            raise ValueError('collector_receiver_revision_changed_or_dirty')
        print(json.dumps(receive(args.package,args.data_root),ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,sqlite3.Error,subprocess.SubprocessError) as error:
        print(json.dumps({'received':False,'error_type':type(error).__name__,
            'next_action':'retain package and arrival journal; retry intact package after diagnosis'}),file=sys.stderr)
        return 1

if __name__=='__main__':raise SystemExit(main())
