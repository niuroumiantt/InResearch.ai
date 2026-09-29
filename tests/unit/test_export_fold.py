"""图谱 3.0 旧对象 ID 的折算在导出端、外部快照叠加与接收端共用一张表（registry.object_resolver）。"""
import contextlib
import io
import unittest

from inresearch.delivery import reader_export, snapshot_overlay
from inresearch.knowledge import registry
from inresearch.materials import artifacts

try:
    from tests.unit import test_continuous_reader as reader_fixture
except ImportError:  # discover -s tests/unit imports the fixture module as a top-level name
    import test_continuous_reader as reader_fixture

OBJECTS = [{'id': 'root', 'name': '数据中心'},
           {'id': 'system:storage', 'name': '存储', 'aliases': ['ecosystem:storage']},
           {'id': 'part:gpu', 'name': 'GPU'}]
ALLOWED = {'object_ids': {'root', 'system:storage', 'part:gpu'}, 'question_ids': {'q1'}}
LEGACY = ['ecosystem:storage', 'scope:M06', 'part:gpu', 'part:nope']


class ResolverTests(unittest.TestCase):
    def test_known_stays_alias_folds_prefix_goes_to_root_unknown_is_none(self):
        resolve = registry.object_resolver(OBJECTS, ['scope:'])
        self.assertEqual([resolve(v) for v in LEGACY], ['system:storage', 'root', 'part:gpu', None])
        no_root = registry.object_resolver(OBJECTS[1:], ['scope:'])
        self.assertIsNone(no_root('scope:M06'), 'a prefix folds to root only when the registry has a root')
        self.assertIsNone(registry.object_resolver(OBJECTS)('scope:M06'), 'no prefixes, no folding')


class ProjectionTests(unittest.TestCase):
    DOC = {'doc_id': 'doc-' + 'a' * 64, 'sha256': 'a' * 64, 'original_name': 'x.pdf', 'original_rel': 'originals/x.pdf',
           'library_rel': None, 'chunks_total': 1, 'chunks_read': 1, 'state': 'complete', 'revision_id': 'rev-1',
           'report_rel': 'artifacts/report.json', 'report_sha256': 'b' * 64}

    def report(self, object_ids):
        return {'classification': {'title': 't'}, 'coverage': {'complete': True, 'pages_total': 1},
                'object_ids': object_ids, 'question_ids': ['q1'],
                'evidence': [{'id': 'ev1', 'page_index': 1, 'object_ids': object_ids, 'question_ids': ['q1']}],
                'claims': [{'text': 'c', 'object_ids': object_ids, 'question_ids': ['q1']}]}

    def test_legacy_ids_fold_and_only_the_unresolvable_go_to_proposals(self):
        resolve = registry.object_resolver(OBJECTS, ['scope:'])
        piece = reader_export.project_document(self.DOC, [], self.report(LEGACY), ALLOWED, resolve)
        self.assertEqual(piece['entry']['object_ids'], ['part:gpu', 'root', 'system:storage'])
        self.assertEqual(piece['evidence'][0]['object_ids'], ['part:gpu', 'root', 'system:storage'])
        self.assertEqual(piece['statements'][0]['object_ids'], ['part:gpu', 'root', 'system:storage'])
        self.assertEqual(piece['entry']['mapping_status'], 'needs_review')
        self.assertEqual(piece['proposal']['unknown_ids'], {'object_ids': ['part:nope'], 'question_ids': []})
        piece = reader_export.project_document(self.DOC, [], self.report(LEGACY[:3]), ALLOWED, resolve)
        self.assertEqual(piece['entry']['mapping_status'], 'candidate_mapped')
        self.assertIsNone(piece['proposal'])

    def test_without_a_resolver_the_strict_projection_is_unchanged(self):
        piece = reader_export.project_document(self.DOC, [], self.report(LEGACY), ALLOWED)
        self.assertEqual(piece['entry']['object_ids'], ['part:gpu'])
        self.assertEqual(piece['proposal']['unknown_ids']['object_ids'], ['ecosystem:storage', 'part:nope', 'scope:M06'])


class OverlayTests(unittest.TestCase):
    def test_external_snapshot_ids_fold_before_filtering(self):
        entry = {'doc_id': 'doc-m4', 'id': 'doc-m4', 'coverage': {'complete': True}, 'acceptance': 'candidate'}
        statement = {'id': 'doc-m4:s0', 'document_id': 'doc-m4', 'acceptance': 'candidate', 'object_ids': list(LEGACY), 'question_ids': ['q1', 'q-gone']}
        external = {'knowledge': {'documents': [entry], 'evidence': [], 'statements': [statement], 'answers': []}}
        payload = {'knowledge': {'documents': [], 'evidence': [], 'statements': [], 'answers': []}}
        resolve = registry.object_resolver(OBJECTS, ['scope:'])
        summary = snapshot_overlay.overlay(payload, [('m4.json', external)], ALLOWED, resolve)
        self.assertEqual(payload['knowledge']['statements'][0]['object_ids'], ['system:storage', 'root', 'part:gpu'])
        self.assertEqual(payload['knowledge']['statements'][0]['question_ids'], ['q1'])
        self.assertEqual(summary['dropped_unknown_ids'], 2)
        payload = {'knowledge': {'documents': [], 'evidence': [], 'statements': [], 'answers': []}}
        snapshot_overlay.overlay(payload, [('m4.json', external)], ALLOWED)
        self.assertEqual(payload['knowledge']['statements'][0]['object_ids'], ['part:gpu'], 'no resolver keeps the strict filter')


class ReaderExportTests(unittest.TestCase):
    """A reading recorded under registry 2.0.0 is exported after the checkout moved to 3.0.0."""

    def setUp(self):
        import tempfile
        from pathlib import Path
        self.temp = tempfile.TemporaryDirectory(prefix='inresearch-fold-test-')
        self.base = Path(self.temp.name)
        self.clock, self.model = reader_fixture.Clock(), reader_fixture.Model()
        framework = self.base / 'repo/framework'
        framework.mkdir(parents=True)
        artifacts.atomic_json(framework / 'research_graph.json', {'version': '2.0.0', 'objects': [{'id': 'obj-server', 'name': '服务器'}]})
        artifacts.atomic_json(framework / 'research_questions.json', {'version': '2.0.0', 'records': [{'id': 'q-power', 'text': '服务器功率是什么？'}]})
        self.reader = reader_fixture.cr.Reader(self.base / 'data', self.base / 'state', self.base / 'repo', self.model, 0, 200, self.clock).initialize()
        raw = self.reader.data / 'raw-materials' / 'paper.txt'
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text('服务器功率为 300 W。\n这是完整正文与注释。\n', encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            self.reader.run(once=True)

    def tearDown(self):
        self.reader.close()
        self.temp.cleanup()

    def test_export_after_the_registry_moved_folds_the_old_object_id(self):
        self.assertEqual(self.reader.export_snapshot()['knowledge']['statements'][0]['object_ids'], ['obj-server'])
        artifacts.atomic_json(self.base / 'repo/framework/research_graph.json',
                              {'version': '3.0.0', 'legacy_root_prefixes': ['scope:'],
                               'objects': [{'id': 'root', 'name': '数据中心'}, {'id': 'part:server', 'name': '服务器', 'aliases': ['obj-server']}]})
        self.assertEqual(self.reader.snapshot()['legacy_root_prefixes'], ['scope:'])
        payload = self.reader.export_snapshot()
        self.assertEqual(payload['graph_version'], '3.0.0')
        self.assertEqual(payload['knowledge']['statements'][0]['object_ids'], ['part:server'])
        self.assertEqual(payload['knowledge']['evidence'][0]['object_ids'], ['part:server'])
        self.assertEqual(payload['knowledge']['documents'][0]['object_ids'], ['part:server'])
        self.assertEqual(payload['knowledge']['documents'][0]['mapping_status'], 'candidate_mapped')
        self.assertEqual(artifacts.read_json(self.reader.data / 'candidates/mapping-proposals.json')['records'], [])
        artifacts.atomic_json(self.base / 'repo/framework/research_graph.json', {'version': '3.0.1', 'objects': [{'id': 'root', 'name': '数据中心'}]})
        payload = self.reader.export_snapshot()
        self.assertEqual(payload['knowledge']['statements'][0]['object_ids'], [], 'an alias that disappeared is not guessed')
        self.assertEqual(payload['knowledge']['documents'][0]['mapping_status'], 'needs_review')


if __name__ == '__main__':
    unittest.main()
