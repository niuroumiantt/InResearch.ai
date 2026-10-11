"""Build the actual Dockerfile twice; prove asset reuse and image isolation."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(*args):
    return subprocess.check_output(args, text=True)


def main():
    tags = ['inresearch-cache-test-'+uuid.uuid4().hex[:12]+':'+v for v in ('a','b')]
    with tempfile.TemporaryDirectory(prefix='inresearch-cache-test-') as temp:
        context = Path(temp)
        shutil.copyfile(ROOT/'deploy/Dockerfile', context/'Dockerfile')
        shutil.copyfile(ROOT/'.dockerignore', context/'.dockerignore')
        for name in ('web/assets', 'docs/design', 'docs/inbox'):
            (context/name).mkdir(parents=True)
            (context/name/'asset.bin').write_bytes(b'cached-asset'*1024)
        (context/'docs/LIBRARY_SCORES.csv').write_text('unchanged,asset\n')
        (context/'data').mkdir()
        (context/'.git').mkdir()
        (context/'.git/config').write_text('FAKE_SECRET_MUST_NOT_ENTER_IMAGE')
        (context/'.env').write_text('FAKE_SECRET_MUST_NOT_ENTER_IMAGE')
        (context/'data/private.sqlite').write_text('FAKE_DATABASE')
        times=[]
        try:
            for index, tag in enumerate(tags):
                (context/'data/object_observations.json').write_text(json.dumps({'release':index}))
                started=time.monotonic()
                subprocess.run(['docker','build','--progress=plain','-t',tag,str(context)],check=True)
                times.append(round(time.monotonic()-started,3))
            layers=[json.loads(run('docker','image','inspect',tag))[0]['RootFS']['Layers'] for tag in tags]
            assert len(layers[0])>=6 and layers[0][:-1]==layers[1][:-1] and layers[0][-1]!=layers[1][-1], layers
            for index, tag in enumerate(tags):
                probe="""import json,pathlib
r=pathlib.Path('/app')
assert json.load(open(r/'data/object_observations.json'))['release']==INDEX
for p in ['web/assets/asset.bin','docs/design/asset.bin','docs/inbox/asset.bin','docs/LIBRARY_SCORES.csv']:assert (r/p).is_file(),p
for p in ['.git/config','.env','data/private.sqlite']:assert not (r/p).exists(),p
""".replace('INDEX',str(index))
                run('docker','run','--rm','--network=none','--read-only',tag,'python3','-c',probe)
            print(json.dumps({'cache_layers_preserved':len(layers[0])-1,'build_seconds':times,'image_content_and_secret_isolation':'passed'}))
        finally:
            for tag in tags:
                subprocess.run(['docker','image','rm',tag],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
