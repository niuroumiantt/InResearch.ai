"""Editorial production belongs to inews; research consumers remain available."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from inresearch.adapters import editorial_sync
from inresearch.interfaces.cli import COMMANDS
from inresearch.paths import project_root


class EditorialOwnershipTests(unittest.TestCase):
    def test_no_article_producers_remain_in_research(self):
        root = project_root()
        retained_research = {
            'outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/acquire.py',
            'outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/research.py',
            'outputs/geluoke-research/2026-10-09-us-datacenter-power/work/tools/visual_sources_v3.py',
        }
        code = {str(p.relative_to(root)) for p in (root / 'outputs/geluoke-research').rglob('*')
                if p.is_file() and p.suffix in {'.py', '.js', '.cjs', '.sh'}}
        self.assertEqual(code, retained_research)
        self.assertFalse((root / 'scripts/editorial-outbox.py').exists())
        self.assertFalse((root / 'docs/geluoke/专题写作规则.md').exists())
        state = json.loads((root / 'framework/current_state.json').read_text())
        retired = {'scripts/editorial-outbox.py', 'docs/geluoke/专题写作规则.md'}
        for policy in state['policies']:
            if policy['status'] == 'current':
                self.assertNotIn(policy['source'], retired)
                self.assertTrue(retired.isdisjoint(policy.get('implementations', [])))

    def test_research_consumers_and_ui_atlas_remain(self):
        self.assertEqual(COMMANDS['editorial-sync'], 'inresearch.adapters.editorial_sync')
        self.assertEqual(COMMANDS['daily-receive'], 'inresearch.materials.daily_bundle')
        root = project_root()
        for name in ('deploy/spark-reader/inresearch-editorial.service',
                     'deploy/spark-reader/inresearch-editorial.timer',
                     'framework/10_visual_atlas.md', 'framework/visual_atlas.json',
                     'framework/visual_atlas_migration.json'):
            self.assertTrue((root / name).is_file(), name)
        service = (root / 'deploy/spark-reader/inresearch-editorial.service').read_text()
        self.assertIn('manage.py editorial-sync --receipt', service)

    def test_completed_article_bundle_needs_no_production_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            body = '# Research report\n\nPublished authored analysis.'.encode('utf-8')
            (folder / 'article.md').write_bytes(body)
            manifest = {
                'schema': 'editorial-delivery-v1', 'id': 'report-example',
                'title': 'Research report', 'article': 'article.md',
                'source_role': 'authored_analysis',
                'files': [{'path': 'article.md', 'bytes': len(body),
                           'sha256': hashlib.sha256(body).hexdigest()}],
            }
            (folder / 'manifest.json').write_text(json.dumps(manifest))
            received = editorial_sync.load_bundle(folder / 'manifest.json')
            self.assertEqual(received['text'], body.decode('utf-8'))
            self.assertEqual(received['source_role'], 'authored_analysis')
            self.assertEqual(received['references'], [])
            (folder / 'article.md').write_bytes(body + b'changed')
            with self.assertRaises(ValueError):
                editorial_sync.load_bundle(folder / 'manifest.json')


if __name__ == '__main__':
    unittest.main()
