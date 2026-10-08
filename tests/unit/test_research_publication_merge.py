import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from inresearch.workflow.research_publish import refresh_publication_base, source_bundle


def git(root, *args):
    return subprocess.run(['git', *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


class PublicationBaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.upstream = base/'upstream';self.upstream.mkdir()
        git(self.upstream, 'init', '--initial-branch=main')
        for key, value in (('user.name', 'Fixture'), ('user.email', 'fixture@example.invalid')):
            git(self.upstream, 'config', key, value)
        for name, value in {'data/research_knowledge.json': '{"statement":"baseline"}\n',
                            'framework/repository_manifest.json': 'baseline inventory\n',
                            'docs/REPOSITORY_REGISTER.md': 'baseline register\n',
                            'implementation.py': 'baseline source\n'}.items():
            p=self.upstream/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
        # The real governance command is verified separately. This fixture
        # generator makes a lossless inventory of the two concurrently changed
        # source/data files so Git integration can be tested in a tiny repository.
        (self.upstream/'manage.py').write_text('''import sys,json,pathlib
if sys.argv[1:]==['governance','--refresh']:
 p=pathlib.Path('.')
 value={'research':json.loads((p/'data/research_knowledge.json').read_text()),'source':(p/'implementation.py').read_text()}
 (p/'framework/repository_manifest.json').write_text(json.dumps(value))
 (p/'docs/REPOSITORY_REGISTER.md').write_text(json.dumps(value))
''')
        git(self.upstream, 'add', '.');git(self.upstream, 'commit', '-m', 'baseline')
        self.origin=base/'origin.git';git(base,'clone','--bare',str(self.upstream),str(self.origin))
        git(self.upstream,'remote','add','origin',str(self.origin))
        self.publication=base/'publication';git(base,'clone',str(self.origin),str(self.publication))
        for key, value in (('user.name', 'Fixture'), ('user.email', 'fixture@example.invalid')):
            git(self.publication, 'config', key, value)
        git(self.publication,'switch','-c','codex/review')
        (self.publication/'data/research_knowledge.json').write_text('{"statement":"reviewed new claim"}\n')
        (self.publication/'framework/repository_manifest.json').write_text('reviewed inventory\n')
        (self.publication/'docs/REPOSITORY_REGISTER.md').write_text('reviewed register\n')
        git(self.publication,'add','.');git(self.publication,'commit','-m','reviewed statement')
        self.head=git(self.publication,'rev-parse','HEAD')
        (self.upstream/'implementation.py').write_text('new upstream source\n')
        (self.upstream/'framework/repository_manifest.json').write_text('upstream inventory\n')
        (self.upstream/'docs/REPOSITORY_REGISTER.md').write_text('upstream register\n')
        git(self.upstream,'add','.');git(self.upstream,'commit','-m','upstream release')
        git(self.upstream,'push','origin','main')

    def test_derived_conflicts_keep_reviewed_claim_and_new_upstream_source(self):
        new=refresh_publication_base(self.publication,self.head)
        self.assertNotEqual(new,self.head)
        self.assertEqual(git(self.publication,'status','--porcelain'),'')
        self.assertEqual(json.loads((self.publication/'data/research_knowledge.json').read_text()),
                         {'statement':'reviewed new claim'})
        self.assertEqual((self.publication/'implementation.py').read_text(),'new upstream source\n')
        inventory=json.loads((self.publication/'framework/repository_manifest.json').read_text())
        self.assertEqual(inventory, {'research':{'statement':'reviewed new claim'},'source':'new upstream source\n'})
        self.assertEqual(refresh_publication_base(self.publication,new),new)

    def test_research_conflict_is_preserved_for_review(self):
        (self.upstream/'data/research_knowledge.json').write_text('{"statement":"different upstream research"}\n')
        git(self.upstream,'add','.');git(self.upstream,'commit','-m','research changed')
        git(self.upstream,'push','origin','main')
        with self.assertRaisesRegex(ValueError,'non_inventory_conflict_preserved'):
            refresh_publication_base(self.publication,self.head)
        data=(self.publication/'data/research_knowledge.json').read_text()
        self.assertIn('reviewed new claim',data)
        self.assertIn('different upstream research',data)
        self.assertIn('data/research_knowledge.json',git(self.publication,'diff','--name-only','--diff-filter=U'))

    def test_dirty_or_unexpected_head_cannot_be_rewritten(self):
        with self.assertRaisesRegex(ValueError,'worktree_changed'):
            refresh_publication_base(self.publication,'0'*40)
        (self.publication/'implementation.py').write_text('active user change\n')
        with self.assertRaisesRegex(ValueError,'worktree_changed'):
            refresh_publication_base(self.publication,self.head)
        self.assertEqual((self.publication/'implementation.py').read_text(),'active user change\n')

    def test_incremental_source_bundle_fast_forwards_offline_checkout(self):
        base=git(self.publication,'rev-parse','origin/main')
        git(self.publication,'fetch','origin','main');target=git(self.publication,'rev-parse','origin/main')
        bundle=source_bundle(self.publication,Path(self.tmp.name)/'releases',target,base)
        offline=Path(self.tmp.name)/'offline';git(Path(self.tmp.name),'clone',str(self.origin),str(offline))
        git(offline,'switch','--detach',base)
        git(offline,'bundle','verify',str(bundle))
        git(offline,'fetch',str(bundle),'refs/remotes/origin/main:refs/remotes/origin/main')
        git(offline,'merge','--ff-only',target)
        self.assertEqual(git(offline,'rev-parse','HEAD'),target)
        self.assertEqual((offline/'implementation.py').read_text(),'new upstream source\n')
        with self.assertRaisesRegex(ValueError,'not_ancestor'):
            source_bundle(self.publication,Path(self.tmp.name)/'releases',target,self.head)
        with self.assertRaisesRegex(ValueError,'not_current_main'):
            source_bundle(self.publication,Path(self.tmp.name)/'releases',base,base)
