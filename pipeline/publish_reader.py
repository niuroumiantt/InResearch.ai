#!/usr/bin/env python3
"""Publish a candidate-only, rebuildable Spark projection over authenticated HTTPS."""
import json
import os
from pathlib import Path
import stat
import sys
import subprocess
import urllib.request
from urllib.parse import urlsplit

from continuous_reader import Reader, ModelClient, MODEL, encoded, atomic_json, now_iso


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def main():
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
    model = ModelClient(backend=os.environ.get('READER_BACKEND', 'ollama'),
                        url=os.environ.get('READER_URL', 'http://127.0.0.1:11434'),
                        model=os.environ.get('READER_MODEL', MODEL),
                        ocr_model=os.environ.get('READER_OCR_MODEL', ''))
    reader = Reader(model=model, data_root=os.environ.get('READER_DATA_ROOT'), state_root=state,
                    repo_root=os.environ.get('READER_REPO_ROOT')).initialize()
    try:
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
        import acquisition
        payload['reader']['acquisition'] = acquisition.summary(reader.data)
        body = encoded(payload).encode('utf-8')
        if len(body) > 64 * 1024 * 1024:
            raise ValueError('snapshot exceeds receiver limit; incremental export is required')
        request = urllib.request.Request(destination, data=body, method='POST', headers={
            'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
        with urllib.request.build_opener(NoRedirect).open(request, timeout=120) as response:
            result = json.loads(response.read(4096))
        if result.get('ok') is not True:
            raise ValueError('receiver did not acknowledge snapshot')
        status = {'published': now_iso(), 'status': 'ok', 'bytes': len(body),
                  'documents': len(payload['knowledge']['documents']), 'received_at': result.get('received_at')}
        atomic_json(state / 'publish-status.json', status)
        print(encoded(status))
        return 0
    finally:
        reader.close()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # No request headers, source text or model responses in journals.
        print(json.dumps({'status': 'failed', 'error': type(exc).__name__}), file=sys.stderr)
        raise SystemExit(1)
