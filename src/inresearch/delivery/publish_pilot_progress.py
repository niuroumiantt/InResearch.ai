"""Publish M5-local NVIDIA pilot status and complete candidate snapshot to AWS."""
import argparse
import json
import os
from pathlib import Path
import stat
import urllib.request
from urllib.parse import urlsplit


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    args = parser.parse_args(argv)
    for path in (args.status, args.snapshot):
        if path.is_symlink() or not path.is_file():
            raise ValueError('input must be a regular file')
    if args.status.stat().st_size > 2 * 1024 * 1024 or args.snapshot.stat().st_size > 14 * 1024 * 1024:
        raise ValueError('pilot progress payload exceeds upload limit')
    token_path = Path(os.environ.get('INRESEARCH_PILOT_TOKEN_FILE',
        Path.home() / '.local/state/inresearch.ai/nvidia-pilot.token')).expanduser()
    if token_path.is_symlink() or stat.S_IMODE(token_path.stat().st_mode) & 0o077:
        raise ValueError('receiver credential must be a private regular file')
    token = token_path.read_text().strip()
    if len(token) < 32:
        raise ValueError('receiver credential is not configured')
    payload = {'schema_version': 1,
        'status': json.loads(args.status.read_text(encoding='utf-8')),
        'snapshot': json.loads(args.snapshot.read_text(encoding='utf-8'))}
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
    endpoint = os.environ.get('INRESEARCH_PILOT_PROGRESS_URL', 'https://inresearch.ai/api/pilot-progress/nvidia')
    parsed = urlsplit(endpoint)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('publisher requires an HTTPS endpoint without embedded credentials')
    request = urllib.request.Request(endpoint, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    opener = urllib.request.build_opener(NoRedirect)
    with opener.open(request, timeout=120) as response:
        result = json.loads(response.read(4096))
    if result.get('ok') is not True:
        raise ValueError('receiver did not acknowledge pilot progress')
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
