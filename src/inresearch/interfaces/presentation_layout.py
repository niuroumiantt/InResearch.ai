"""Stateless public presentation utility; no research/file-store capabilities."""
from collections import OrderedDict, deque
from io import BytesIO
import json
import os
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
from zipfile import ZipFile

from inresearch.delivery.presentation_layout import MAX_UPLOAD, PPTX_MIME
from inresearch.interfaces import auth

SLOT = threading.BoundedSemaphore(1)
RATE_LOCK = threading.Lock()
REQUESTS = OrderedDict()
# infra/docs/cloudfront.md: AllViewerExceptHostHeader sends the public Origin
# unchanged but replaces Host with this dedicated origin name. Never trust an
# arbitrary forwarded-host header or allow an origin suffix/wildcard.
CDN_HOST = 'origin.inresearch.ai'
PUBLIC_ORIGINS = frozenset(('https://inresearch.ai', 'https://www.inresearch.ai'))


def rate_allowed(ip):
    now = time.monotonic()
    with RATE_LOCK:
        entries = REQUESTS.setdefault(ip, deque())
        while entries and entries[0] < now - 300:
            entries.popleft()
        REQUESTS.move_to_end(ip)
        while len(REQUESTS) > 1024:
            REQUESTS.popitem(last=False)
        if len(entries) >= 5:
            return False
        entries.append(now)
        return True


def post(handler, root):
    # Close the connection on early rejection so unread bodies cannot become a
    # second request. Custom header + same-origin check; no CORS or external I/O.
    handler.close_connection = True
    origin = handler.headers.get('Origin')
    try:
        parsed_origin = urlsplit(origin) if origin else None
    except ValueError:
        return handler._json(403, {'ok': False, 'error': '请求来源无效。'})
    host = handler.headers.get('Host')
    same_origin = not origin or (parsed_origin.scheme in ('http', 'https') and parsed_origin.netloc == host)
    cdn_origin = host == CDN_HOST and origin in PUBLIC_ORIGINS
    if (handler.headers.get('X-Requested-With') != 'presentation-layout'
            or handler.headers.get('Sec-Fetch-Site') == 'cross-site'
            or not (same_origin or cdn_origin)):
        return handler._json(403, {'ok': False, 'error': '请从本站排版窗口提交文件。'})
    if handler.headers.get('Transfer-Encoding') or len(handler.headers.get_all('Content-Length', [])) != 1:
        return handler._json(400, {'ok': False, 'error': '请求长度无效。'})
    try:
        size = int(handler.headers.get('Content-Length', '0'))
    except ValueError:
        size = 0
    if not 0 < size <= MAX_UPLOAD:
        return handler._json(413, {'ok': False, 'error': '请上传不超过 20 MB 的 PPTX 文件。'})
    if handler.headers.get('Content-Type', '').split(';')[0] not in (PPTX_MIME, 'application/octet-stream'):
        return handler._json(415, {'ok': False, 'error': '仅支持 PPTX 文件。'})
    mode = handler.headers.get('X-Layout-Mode', 'layout')
    if mode not in ('layout', 'fonts'):
        return handler._json(400, {'ok': False, 'error': '排版选项无效。'})
    if not SLOT.acquire(blocking=False):
        return handler._json(503, {'ok': False, 'error': '排版服务正在处理其他文件，请稍后重试。'})
    try:
        if not rate_allowed(auth.client_ip(handler)):
            return handler._json(429, {'ok': False, 'error': '每 5 分钟最多处理 5 份，请稍后重试。'})
        deadline, raw = time.monotonic() + 30, bytearray()
        while len(raw) < size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('upload deadline')
            handler.connection.settimeout(remaining)
            block = handler.rfile.read1(min(65536, size - len(raw)))
            if not block:
                break
            raw.extend(block)
        if len(raw) != size:
            return handler._json(400, {'ok': False, 'error': '文件上传不完整，请重试。'})
        # Run only our module; uploaded bytes are input, never code or filenames.
        env = dict(os.environ, PYTHONPATH=str(root / 'src'))
        worker = subprocess.run([sys.executable, '-m', 'inresearch.delivery.presentation_layout', mode],
                                input=raw, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                timeout=35, cwd=root, env=env)
        if worker.returncode:
            message = '文件无法安全处理，请拆分或另存为标准 PPTX 后重试。'
            if worker.returncode == 2:
                try:
                    message = json.loads(worker.stdout)['error']
                except (ValueError, KeyError):
                    pass
            return handler._json(422, {'ok': False, 'error': message})
        with ZipFile(BytesIO(worker.stdout)) as archive:
            report = json.loads(archive.read('layout-report.json'))
        handler.send_response(200)
        handler.send_header('Content-Type', 'application/zip')
        handler.send_header('Content-Disposition', 'attachment; filename="inresearch-formatted.zip"')
        handler.send_header('Cache-Control', 'no-store, private')
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.send_header('X-Layout-Slides', str(report['slides']))
        for status in ('reflowed', 'fonts_only', 'preserved'):
            handler.send_header('X-Layout-' + status.replace('_', '-'), str(report['counts'].get(status, 0)))
        handler.send_header('Content-Length', str(len(worker.stdout)))
        handler.end_headers()
        handler.connection.settimeout(30)
        handler.wfile.write(worker.stdout)
    except (TimeoutError, subprocess.TimeoutExpired):
        return handler._json(408, {'ok': False, 'error': '上传或处理超时，请拆分文件后重试。'})
    finally:
        SLOT.release()
