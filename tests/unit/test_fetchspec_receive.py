import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from inresearch.materials.fetchspec_receive import PackageError, receive
from inresearch.adapters.acquisition import product_documents


class FetchspecReceiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.package = self.base / 'delivery'
        self.body = b'%PDF-1.4 test payload'
        self.sha = hashlib.sha256(self.body).hexdigest()
        self.relative = f'files/{self.sha[:2]}/{self.sha}.pdf'
        (self.package / Path(self.relative).parent).mkdir(parents=True)
        (self.package / self.relative).write_bytes(self.body)
        self.item = {'source_item_id': 'nvidia:item-1', 'source': {'publisher': 'NVIDIA',
            'url': 'https://example.com/datasheet.pdf', 'categories': ['GPU', 'Inference']},
            'retrieved_at': '2026-09-26T00:00:00Z', 'sha256': self.sha, 'bytes': len(self.body),
            'content_type': 'application/pdf', 'format': 'pdf', 'completeness': {'state': 'complete'},
            'access_scope': {'state': 'public'}, 'version_relation': {'type': 'original'}, 'path': self.relative}
        manifest = {'contract_version': '1.0', 'provider_id': 'fetchspec', 'delivery_id': 'test-1',
            'task_id_or_discovery': 'discovery', 'collector_revision': 'abc', 'files_included': True,
            'company_id': 'nvidia', 'items': [self.item]}
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        (self.package / 'SHA256SUMS').write_text(f'{self.sha}  {self.relative}\n')
        self.data = self.base / 'data'

    def tearDown(self):
        self.tmp.cleanup()

    def test_receive_archives_by_content_and_hands_pdf_to_reader(self):
        first = receive(self.repo, self.package, self.data)
        self.assertEqual(first['status'], 'received')
        original = self.data / 'originals' / self.sha[:2] / self.sha / (self.sha + '.pdf')
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), self.sha)
        handoff = self.data / 'raw-materials/fetchspec/GPU' / (self.sha + '.pdf')
        self.assertTrue(handoff.exists())
        self.assertEqual(receive(self.repo, self.package, self.data), first)
        receipt = json.loads((self.repo / 'data/raw/supply-center/receipts.json').read_text())
        self.assertEqual(receipt['deliveries']['test-1']['received_items'], 1)
        found = product_documents(self.data, company_id='nvidia', category='GPU', format='pdf')
        self.assertEqual(found['total'], 1)
        self.assertEqual(found['records'][0]['sha256'], self.sha)
        self.assertEqual(found['records'][0]['acceptance'], 'candidate')

    def test_bad_hash_is_rejected_before_data_write(self):
        (self.package / self.relative).write_bytes(b'corrupt')
        with self.assertRaises(PackageError):
            receive(self.repo, self.package, self.data)
        self.assertFalse((self.data / 'originals').exists())

    def test_contract_11_rejects_non_english_or_chinese_attachment(self):
        self.item['source'].update({'language': 'ja', 'categories': ['GPU']})
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest['contract_version'] = '1.1'
        manifest['items'] = [self.item]
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(PackageError):
            receive(self.repo, self.package, self.data)
        self.assertFalse((self.data / 'originals').exists())

    def test_restricted_attachment_is_rejected_before_archiving(self):
        self.item['access_scope']['state'] = 'restricted'
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest['items'] = [self.item]
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(PackageError):
            receive(self.repo, self.package, self.data)
        self.assertFalse((self.data / 'originals').exists())

    def test_dot_path_categories_cannot_escape_the_fetchspec_library(self):
        self.item['source']['categories'] = ['..']
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest['items'] = [self.item]
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        receive(self.repo, self.package, self.data)
        expected = self.data / 'raw-materials/fetchspec/uncategorized' / (self.sha + '.pdf')
        self.assertTrue(expected.exists())
        self.assertFalse((self.data / 'raw-materials' / (self.sha + '.pdf')).exists())

    def test_unsupported_legacy_doc_file_is_preserved_but_not_reader_handed_off(self):
        self.body = bytes.fromhex('d0cf11e0a1b11ae1') + b'WordDocument test content'
        self.sha = hashlib.sha256(self.body).hexdigest()
        self.item.update({'sha256': self.sha, 'bytes': len(self.body)})
        self.item.update({'format': 'doc', 'content_type': 'application/msword'})
        self.item['path'] = f'files/{self.sha[:2]}/{self.sha}.doc'
        old = self.package / self.relative
        old.unlink()
        (self.package / Path(self.item['path']).parent).mkdir(parents=True, exist_ok=True)
        ppt_path = self.package / self.item['path']
        ppt_path.write_bytes(self.body)
        self.item['bytes'] = len(self.body)
        (self.package / 'manifest.json').write_text(json.dumps({'contract_version': '1.0', 'provider_id': 'fetchspec',
            'delivery_id': 'test-1', 'task_id_or_discovery': 'discovery', 'collector_revision': 'abc',
            'files_included': True, 'items': [self.item]}))
        (self.package / 'SHA256SUMS').write_text(f'{self.sha}  {self.item["path"]}\n')
        result = receive(self.repo, self.package, self.data)
        self.assertEqual(result['status'], 'needs_supplement')
        self.assertEqual(result['items'][0]['reader_handoff'], 'extractor_required')
        self.assertFalse((self.data / 'raw-materials').exists())

    def test_delivery_identity_collision_does_not_overwrite_receipt(self):
        receive(self.repo, self.package, self.data)
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest['collector_revision'] = 'changed'
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaises(PackageError):
            receive(self.repo, self.package, self.data)

    def test_same_delivery_rehydrates_a_different_empty_data_root(self):
        first = receive(self.repo, self.package, self.data)
        second_root = self.base / 'restored-data'
        second = receive(self.repo, self.package, second_root)
        self.assertEqual(second, first)
        handoff = second_root / 'raw-materials/fetchspec/GPU' / (self.sha + '.pdf')
        self.assertTrue(handoff.exists())
        self.assertEqual(product_documents(second_root, company_id='nvidia')['total'], 1)

    def test_new_version_is_preserved_as_a_review_event(self):
        old_sha = 'b' * 64
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest['items'][0]['version_relation'] = {'type': 'new_version', 'supersedes_sha256': old_sha}
        manifest['delivery_id'] = 'test-update'
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        result = receive(self.repo, self.package, self.data)
        self.assertEqual(result['updates'][0]['change_type'], 'specification_revision')
        self.assertEqual(result['updates'][0]['previous_sha256'], old_sha)
        self.assertTrue(result['updates'][0]['review_required'])


if __name__ == '__main__':
    unittest.main()
