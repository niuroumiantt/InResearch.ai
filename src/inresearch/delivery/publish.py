#!/usr/bin/env python3
"""Publish a candidate-only, rebuildable Spark projection over authenticated HTTPS."""
import json
import os
import argparse
import gzip
from pathlib import Path
import stat
import sys
import subprocess as subprocess
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from inresearch.workflow.reader import Reader
from inresearch.adapters.reader_model import ModelClient
from inresearch.materials.artifacts import encoded, atomic_json, now_iso
from inresearch.delivery import snapshot_overlay
from inresearch.knowledge.registry import object_resolver
from inresearch.workflow import commands


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path,
                        help='publish a Reader candidate snapshot exported on another trusted worker')
    args = parser.parse_args(argv)
    state = Path(os.environ.get('READER_STATE_ROOT', Path.home() / '.local/state/inresearch.ai'))
    destination = os.environ.get('READER_PUBLISH_URL', 'https://inresearch.ai/api/reader-snapshot')
    parsed = urlsplit(destination)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query:
        raise ValueError('publisher requires an HTTPS endpoint without embedded credentials')
    token_path = Path(os.environ.get('READER_PUBLISH_TOKEN_FILE', state / 'reader-sync.token'))
    if token_path.is_symlink() or stat.S_IMODE(token_path.stat().st_mode) & 0o077:
        raise ValueError('publisher token must be a private regular file')
    token = token_path.read_text().strip()
    if len(token) < 32:
        raise ValueError('publisher token is not configured')
    if args.snapshot:
        snapshot_path = args.snapshot.expanduser()
        if snapshot_path.is_symlink() or not snapshot_path.is_file():
            raise ValueError('candidate snapshot must be a regular file')
        if snapshot_path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('snapshot exceeds receiver limit; incremental export is required')
        payload = snapshot_overlay.validate_external(json.loads(snapshot_path.read_text(encoding='utf-8')), overlay=False)
        reader = None
    else:
        model = ModelClient()
        reader = Reader(model=model, data_root=os.environ.get('READER_DATA_ROOT'), state_root=state,
                        repo_root=os.environ.get('READER_REPO_ROOT')).initialize()
    try:
        if reader is not None:
            # Pin one SQLite snapshot while assembling references across tables.
            reader.conn.execute('BEGIN')
            payload = reader.export_snapshot()
            reader.conn.execute('COMMIT')
            worker = subprocess.run(['systemctl', '--user', 'is-active', 'inresearch-reader.service'],
                                    capture_output=True, text=True, timeout=10)
            if worker.returncode:
                payload['reader']['status'] = 'degraded'
                payload['reader'].setdefault('recent_failures', []).append({'error_code': 'worker_service_inactive'})
            payload['reader']['release'] = os.environ.get('READER_RELEASE', 'unknown')
            from inresearch.adapters import acquisition as acquisition
            payload['reader']['acquisition'] = acquisition.summary(reader.data)
            # Readings finished on another worker (M4) survive Spark's next publish.
            external = Path(os.environ.get('READER_EXTERNAL_SNAPSHOT_DIR', state / 'external-snapshots'))
            registry = reader.snapshot()
            allowed = {'object_ids': {r['id'] for r in registry['objects'] if isinstance(r, dict) and 'id' in r},
                       'question_ids': {r['id'] for r in registry['questions'] if isinstance(r, dict) and 'id' in r}}
            payload['reader']['external_overlay'] = snapshot_overlay.overlay(
                payload, snapshot_overlay.load_directory(external), allowed,
                object_resolver(registry['objects'], registry.get('legacy_root_prefixes')))
        document = encoded(payload).encode('utf-8')
        if len(document) > commands.SNAPSHOT_MAX_BYTES:
            raise ValueError('snapshot exceeds receiver limit; incremental export is required')
        # At 65.7 MB of JSON (2026-09-28) the plain body was 98 % of the 64 MiB wire limit.
        body = gzip.compress(document, compresslevel=6, mtime=0)
        if len(body) > commands.SNAPSHOT_WIRE_MAX_BYTES:
            raise ValueError('compressed snapshot exceeds receiver limit; incremental export is required')
        request = urllib.request.Request(destination, data=body, method='POST', headers={
            'Content-Type': 'application/json', 'Content-Encoding': 'gzip', 'Authorization': 'Bearer ' + token})
        try:
            with urllib.request.build_opener(NoRedirect).open(request, timeout=120) as response:
                result = json.loads(response.read(4096))
        except urllib.error.HTTPError as error:
            # The receiver's own short reason (e.g. a graph_version mismatch) is the
            # only way to tell why a publish was refused; it carries no source text.
            raise ValueError('receiver rejected snapshot: HTTP %d %s'
                             % (error.code, error.read(2000).decode('utf-8', 'replace'))) from None
        if result.get('ok') is not True:
            raise ValueError('receiver did not acknowledge snapshot')
        status = {'published': now_iso(), 'status': 'ok', 'bytes': len(document), 'sent_bytes': len(body),
                  'documents': len(payload['knowledge']['documents']), 'received_at': result.get('received_at'),
                  'source': 'external_candidate_snapshot' if args.snapshot else 'spark_reader_catalog'}
        atomic_json(state / ('publish-relay-status.json' if args.snapshot else 'publish-status.json'), status)
        print(encoded(status))
        return 0
    finally:
        if reader is not None:
            reader.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # No request headers, source text or model responses in journals.
        failure = {'status': 'failed', 'error': type(exc).__name__}
        if isinstance(exc, ValueError):
            failure['detail'] = str(exc)[:600]   # our own messages and the receiver's reason only
        print(json.dumps(failure, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(1)
