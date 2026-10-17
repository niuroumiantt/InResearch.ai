"""Explicit local MLX runtime binding; never substitutes for Spark's GGUF identity."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

from inresearch.adapters.models import InferenceError, MAX_RESPONSE

RUNTIME = 'macos-mlx-0.40.5'
MANIFEST_SHA = '464021588235c36e23bd48a480c6c306ed1fc1e0619e97998267494a1be68de4'
EXECUTABLE = '/Applications/Ollama.app/Contents/Resources/ollama'


def enabled():
    return os.environ.get('INRESEARCH_CAMPUS_RUNTIME') == RUNTIME


def _require_host():
    if sys.platform != 'darwin':
        raise InferenceError('campus_macos_host_required')


def model_identity(base):
    from . import ollama_token_budget as b
    _require_host()
    if b._call(base+'/api/version').get('version') != '0.40.5':
        raise InferenceError('campus_token_ollama_version_unverified')
    root = Path.home()/'.ollama/models'
    path = root/'manifests-v2/ollama.com/library/qwen3.8/27b'
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA:
        raise InferenceError('campus_token_manifest_unverified')
    manifest = json.loads(raw)
    identities = []
    for row in [manifest['config'], *manifest['layers']]:
        sha = row.get('digest', '')
        if not re.fullmatch('sha256:[a-f0-9]{64}', sha):
            raise InferenceError('campus_token_manifest_unverified')
        blob = root/'blobs'/sha.replace(':', '-')
        identity = b._file_identity(blob, row['size'])
        # Like Spark, bind immutable weight file identities; hash all non-weight
        # renderer/tokenizer/config bytes, without rereading 31GB per window.
        if row['mediaType'] != 'application/vnd.ollama.image.tensor':
            if hashlib.sha256(blob.read_bytes()).hexdigest() != sha[7:]:
                raise InferenceError('campus_token_blob_unverified')
        identities.append({'digest': sha, 'file': identity})
    config = json.loads((root/'blobs'/manifest['config']['digest'].replace(':','-')).read_bytes())
    if (config.get('renderer') != 'qwen3.8' or config.get('parser') != 'qwen3.5'
            or config.get('model_format') != 'safetensors' or config.get('file_type') != 'mxfp8'
            or config.get('remote_host') or config.get('remote_model')):
        raise InferenceError('campus_token_renderer_unverified')
    tags = [r for r in b._call(base+'/api/tags').get('models', []) if r.get('name') == b.MODEL]
    if len(tags) != 1 or tags[0].get('digest') != MANIFEST_SHA:
        raise InferenceError('campus_token_tag_unverified')
    show = b._call(base+'/api/show', {'model': b.MODEL})
    if (show.get('remote_host') or show.get('remote_model') or show.get('system')
            or show.get('messages') or show.get('details', {}).get('format') != 'safetensors'):
        raise InferenceError('campus_token_template_unverified')
    return {'runtime': RUNTIME, 'ollama_version': '0.40.5', 'manifest_sha256': MANIFEST_SHA,
            'manifest_file': b._file_identity(path), 'layers_identity_sha256': b.digest(identities),
            'renderer': 'qwen3.8', 'parser': 'qwen3.5', 'show_sha256': b.digest(show),
            'executable': b._file_identity(Path(EXECUTABLE))}


def _process(pid):
    value = subprocess.check_output(['/bin/ps', '-p', str(pid), '-o',
                                     'uid=,ppid=,lstart=,command='], text=True, timeout=5).strip()
    fields = value.split(None, 7)
    if len(fields) != 8 or int(fields[0]) != os.getuid():
        raise InferenceError('campus_token_runner_unverified')
    return {'pid': pid, 'uid': int(fields[0]), 'ppid': int(fields[1]),
            'started': ' '.join(fields[2:7]), 'command': fields[7]}


def runner_identity(model):
    from . import ollama_token_budget as b
    _require_host()
    listing = subprocess.check_output(['/bin/ps', '-axo', 'pid=,command='], text=True, timeout=5)
    pattern = re.compile(r'^\s*(\d+) '+re.escape(EXECUTABLE)+r' runner --model qwen3\.8:27b --port (\d+)$')
    matches = [m for line in listing.splitlines() if (m := pattern.fullmatch(line))]
    if not matches:
        raise InferenceError('campus_token_runner_unavailable')
    if len(matches) != 1:
        raise InferenceError('campus_token_runner_unverified')
    pid, port = map(int, matches[0].groups())
    process = _process(pid); parent = _process(process['ppid'])
    if parent['command'] != EXECUTABLE+' serve' or not 1024 < port < 65536:
        raise InferenceError('campus_token_runner_unverified')
    sockets = subprocess.check_output(['/usr/sbin/lsof', '-nP', '-a', '-p', str(pid),
                    '-iTCP', '-sTCP:LISTEN', '-Fn'], text=True, timeout=5)
    if [line[1:] for line in sockets.splitlines() if line.startswith('n')] != ['127.0.0.1:'+str(port)]:
        raise InferenceError('campus_token_runner_unverified')
    status = b._call('http://127.0.0.1:'+str(port)+'/v1/status')
    if status.get('Status') != 0 or status.get('Progress') != 100 or status.get('ContextLength') != 262144:
        raise InferenceError('campus_token_runner_unverified')
    loaded = [r for r in b._call('http://127.0.0.1:11434/api/ps').get('models', [])
              if r.get('name') == b.MODEL]
    if len(loaded) != 1 or loaded[0].get('digest') != MANIFEST_SHA:
        raise InferenceError('campus_token_runner_unverified')
    return {'runtime': RUNTIME, 'port': port, 'process': process, 'parent': parent,
            'context': 262144, 'manifest_sha256': model['manifest_sha256']}


def tokenize(runner, rendered):
    from . import ollama_token_budget as b
    url = 'http://127.0.0.1:'+str(runner['port'])+'/v1/tokenize'
    request = urllib.request.Request(url, data=rendered.encode(), headers={'Content-Type':'text/plain; charset=utf-8'})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), b._NoRedirect())
    with opener.open(request, timeout=30) as response:
        if response.status != 200 or response.geturl() != url:
            raise InferenceError('campus_token_transport_unverified')
        raw = response.read(MAX_RESPONSE+1)
    if len(raw) > MAX_RESPONSE:
        raise InferenceError('campus_token_response_too_large')
    return json.loads(raw)


def resource_ready():
    _require_host()
    try:
        thermal = subprocess.check_output(['/usr/bin/pmset', '-g', 'therm'], text=True, timeout=5)
        if 'No thermal warning level has been recorded' not in thermal:
            return False, 'campus_waiting_for_temperature'
        if 'No performance warning level has been recorded' not in thermal:
            return False, 'campus_waiting_for_temperature'
        gpu = subprocess.check_output(['/usr/sbin/ioreg', '-r', '-c', 'AGXAccelerator', '-l'], text=True, timeout=5)
        utilization = [int(v) for v in re.findall(r'"Device Utilization %"=(\d+)', gpu)]
        if not utilization:
            return False, 'campus_gpu_status_unavailable'
        if max(utilization) >= 30:
            return False, 'campus_waiting_for_gpu'
        return True, ''
    except (OSError, ValueError, subprocess.SubprocessError):
        return False, 'campus_gpu_status_unavailable'
