"""Native Reader reuse must retain source seals, locators and current demands."""
import copy
import json
import sqlite3
import unittest
from unittest.mock import patch

import test_continuous_reader as fixtures
from inresearch.materials.reader_contracts import IntegrityError
from inresearch.workflow import project_review_reader as adapter


class ReaderSiteReviewTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ReaderTests()
        self.f.setUp()
        self.addCleanup(self.f.tearDown)
        self.f.install_registry()
        self.text = 'Abilene has an estimated IT load of 421 MW, observed in July 2026.\n'
        self.f.put(text=self.text)
        self.f.run_reader()
        self.doc = self.f.first_doc()
        self.sha = self.doc['sha256']
        self.data = self.f.reader.data
        self.root = self.f.base/'repo'
        (self.root/'data').mkdir(exist_ok=True)
        (self.root/'data/projects.json').write_text(json.dumps({'records': [{'site_id': 'us-tx-abilene'}]}))
        self.source = {'source_url': 'https://example.org/native-source',
                       'source_provenance': {'method': 'received-source-fixture'},
                       'research_requests': [{'target_id': 'site-grid'}]}
        self.addCleanup(patch.stopall)
        patch.object(adapter, 'supplied_sources', return_value={self.sha: self.source}).start()
        patch.object(adapter, 'resolve_requests', side_effect=lambda r, root: r).start()
        self.context = adapter.prepare(self.root, self.data, [self.sha], 'us-tx-abilene')
        self.proposal = {'project': {'site_id': 'us-tx-abilene'},
                         'source_version': self.context['source_version'], 'target_ids': ['site-grid'],
                         'reader_sources': [{k: r[k] for k in ('source_sha256', 'reading_revision_id', 'report_sha256')}
                                            for r in self.context['document_refs']],
                         'assertions': [{'source_sha256': self.sha, 'locator': 'reader:page:1',
                                         'quote': self.text.strip()}]}

    def test_reuses_real_sealed_text_without_model_or_formal_write(self):
        calls = len(self.f.model.calls)
        projects = (self.root/'data/projects.json').read_bytes()
        with patch('inresearch.adapters.reader_model.ModelClient', side_effect=AssertionError('no new model')):
            result = adapter.resolve(self.root, self.data, self.proposal)
        self.assertEqual(result['source_texts'][self.sha], self.text)
        self.assertEqual(result['matched_site_id'], 'us-tx-abilene')
        self.assertEqual(len(self.f.model.calls), calls)
        self.assertEqual((self.root/'data/projects.json').read_bytes(), projects)
        self.assertEqual(result['publication_metadata'][self.sha]['published_at'], None)

    def test_wrong_revision_quote_page_and_unbound_target_rejected(self):
        for failure in ('revision', 'quote', 'page', 'target', 'binding', 'site'):
            p = copy.deepcopy(self.proposal)
            if failure == 'revision': p['reader_sources'][0]['report_sha256'] = '0'*64
            if failure == 'quote': p['assertions'][0]['quote'] = 'IT load is 843 MW now'
            if failure == 'page': p['assertions'][0]['locator'] = 'reader:page:2'
            if failure == 'target': p['target_ids'] = ['other-target']
            if failure == 'binding': p['source_version'] = '0'*64
            if failure == 'site': p['project']['site_id'] = 'adjacent-microsoft-campus'
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                adapter.resolve(self.root, self.data, p)

    def test_changed_original_cannot_reuse_previously_sealed_text(self):
        original = self.data/self.doc['original_rel']
        original.chmod(0o600)
        original.write_text('different bytes')
        with self.assertRaises(IntegrityError):
            adapter.resolve(self.root, self.data, self.proposal)

    def test_current_request_change_invalidates_new_review_without_rewriting_report(self):
        report = self.data/self.doc['report_rel']
        before = report.read_bytes()
        self.source['research_requests'] = [{'target_id': 'new-definition'}]
        with self.assertRaisesRegex(ValueError, 'binding_changed'):
            adapter.resolve(self.root, self.data, self.proposal)
        self.assertEqual(report.read_bytes(), before)

    def test_no_received_binding_cannot_publish_from_filename_or_model_date(self):
        with patch.object(adapter, 'supplied_sources', return_value={}):
            with self.assertRaisesRegex(ValueError, 'received_source'):
                adapter.resolve(self.root, self.data, self.proposal)

    def test_first_receipt_compares_both_real_ledgers_and_timezone_offsets(self):
        with sqlite3.connect(self.data/'catalog/catalog.sqlite') as db:
            db.execute('UPDATE sources SET received=1000 WHERE doc_id=?', ('doc-'+self.sha,))
        folder = self.data/'acquisition'
        folder.mkdir(exist_ok=True)
        with sqlite3.connect(folder/'catalog.sqlite') as db:
            db.execute('CREATE TABLE observations(sha256 TEXT, observed_at TEXT)')
            db.execute('INSERT INTO observations VALUES(?,?)', (self.sha, '2099-01-01T00:00:00+00:00'))
        first = adapter._first_received(self.data, self.sha)
        self.assertEqual(first['at'], '1970-01-01T00:16:40+00:00')
        self.assertEqual(first['provenance'], 'reader_first_recorded_intake_receipt')
        with sqlite3.connect(folder/'catalog.sqlite') as db:
            db.executemany('INSERT INTO observations VALUES(?,?)', [
                (self.sha, '1970-01-01T08:00:00+08:00'),
                (self.sha, '1970-01-01T00:01:00+00:00')])
        self.assertEqual(adapter._first_received(self.data, self.sha)['at'], '1970-01-01T08:00:00+08:00')

    def test_imprecise_or_invalid_archive_time_does_not_replace_actual_intake(self):
        expected = adapter._first_received(self.data, self.sha)
        folder = self.data/'acquisition'
        folder.mkdir(exist_ok=True)
        with sqlite3.connect(folder/'catalog.sqlite') as db:
            db.execute('CREATE TABLE observations(sha256 TEXT, observed_at TEXT)')
            db.executemany('INSERT INTO observations VALUES(?,?)', [(self.sha, '1969'), (self.sha, 'invalid')])
        self.assertEqual(adapter._first_received(self.data, self.sha), expected)


if __name__ == '__main__':
    unittest.main()
