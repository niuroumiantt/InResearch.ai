"""Exercise the actual Docker boundary without using production state or models."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def main():
    prefix = 'inresearch-storage-test-' + uuid.uuid4().hex[:12]
    images = [prefix + ':a', prefix + ':b']
    with tempfile.TemporaryDirectory(prefix=prefix) as directory:
        stage = Path(directory)
        runtime = stage / 'runtime'; runtime.mkdir()
        fixtures = stage / 'fixtures'; fixtures.mkdir()
        try:
            run('docker', 'build', '-t', images[0], '-f', 'deploy/Dockerfile', '.', cwd=ROOT)
            run('docker', 'run', '--rm', '--read-only', '--tmpfs', '/tmp:size=256m,mode=1777',
                '-v', str(fixtures) + ':/test-state', '-e', 'TMPDIR=/test-state',
                '-e', 'PYTHONPATH=/app/src:/app/tests/unit', images[0],
                'python3', '-m', 'unittest', 'test_storage_layout', '-v')
            facts = json.loads((ROOT / 'data/facts.json').read_text())
            facts['_release_fixture'] = 'version-b'
            (stage / 'facts.json').write_text(json.dumps(facts))
            (stage / 'Dockerfile').write_text(f'FROM {images[0]}\nCOPY facts.json /app/data/facts.json\n')
            run('docker', 'build', '-t', images[1], str(stage))
            probe = '''
import errno, hashlib, json, os
from pathlib import Path
from inresearch.storage.layout import initialize_runtime, workspace_path
from inresearch.workflow.commands import add_price
initialize_runtime()
try:
    Path('/app/.readonly-test').write_text('must be rejected by the kernel')
except OSError as error:
    assert error.errno == errno.EROFS, error
else:
    raise AssertionError('image root is writable')
if os.environ['STEP'] != 'rollback':
    add_price(Path('/app'), dict(series_id='release-'+os.environ['STEP'], as_of='2026-09-13',
              value=1, unit='$/hr', grade='media', category='gpu-rental', module='M13',
              source_url='https://example.test/isolated-release'))
print(json.dumps(dict(facts=hashlib.sha256(workspace_path('data/facts.json').read_bytes()).hexdigest(),
                     prices=hashlib.sha256(workspace_path('data/prices.json').read_bytes()).hexdigest())))
'''
            outputs = []
            for image, step in [(images[0], 'a'), (images[1], 'b'), (images[0], 'rollback')]:
                result = run('docker', 'run', '--rm', '--read-only', '--tmpfs', '/tmp:size=256m,mode=1777',
                             '-v', str(runtime) + ':/runtime', '-e', 'INRESEARCH_RUNTIME_ROOT=/runtime',
                             '-e', 'PYTHONPATH=/app/src', '-e', 'STEP=' + step, image,
                             'python3', '-c', probe, capture_output=True)
                outputs.append(json.loads(result.stdout))
            assert outputs[0]['facts'] != outputs[1]['facts']
            assert outputs[0]['facts'] == outputs[2]['facts']
            assert outputs[0]['prices'] != outputs[1]['prices']
            assert outputs[1]['prices'] == outputs[2]['prices']
            print(json.dumps({'verified': 'kernel read-only, HTTP/CLI, release A→B→A; runtime writes retained',
                              'releases': outputs}, ensure_ascii=False))
        finally:
            # Reuse the built test image: cleanup must not pull another image.
            # Only this TemporaryDirectory's files change ownership.
            try:
                exists = subprocess.run(['docker', 'image', 'inspect', images[0]],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
                if exists:
                    run('docker', 'run', '--pull=never', '--rm', '--user', '0:0',
                        '--entrypoint', 'chown', '-v', str(stage) + ':/test-state',
                        images[0], '-R', f'{os.getuid()}:{os.getgid()}', '/test-state')
            finally:
                subprocess.run(['docker', 'image', 'rm', *images], check=False)


if __name__ == '__main__':
    main()
