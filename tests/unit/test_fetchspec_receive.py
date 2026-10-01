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

    def test_default_receive_archives_by_content_but_holds_reader_handoff(self):
        first = receive(self.repo, self.package, self.data)
        self.assertEqual(first['status'], 'received')
        original = self.data / 'originals' / self.sha[:2] / self.sha / (self.sha + '.pdf')
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), self.sha)
        handoff = self.data / 'raw-materials/fetchspec/GPU' / (self.sha + '.pdf')
        self.assertFalse(handoff.exists())
        self.assertEqual(first['reader_handoff_count'], 0)
        self.assertEqual(first['items'][0]['reader_handoff'], 'held')
        self.assertEqual(receive(self.repo, self.package, self.data), first)
        receipt = json.loads((self.repo / 'data/raw/supply-center/receipts.json').read_text())
        self.assertEqual(receipt['deliveries']['test-1']['received_items'], 1)
        found = product_documents(self.data, company_id='nvidia', category='GPU', format='pdf')
        self.assertEqual(found['total'], 1)
        self.assertEqual(found['records'][0]['sha256'], self.sha)
        self.assertEqual(found['records'][0]['acceptance'], 'candidate')

    def test_explicit_reader_selection_hands_off_only_selected_files(self):
        second_body = b'%PDF-1.4 second test payload'
        second_sha = hashlib.sha256(second_body).hexdigest()
        second_rel = f'files/{second_sha[:2]}/{second_sha}.pdf'
        second_path = self.package / second_rel
        second_path.parent.mkdir(parents=True)
        second_path.write_bytes(second_body)
        self.item['source']['categories'] = ['Networking']
        manifest = json.loads((self.package / 'manifest.json').read_text())
        second_item = dict(self.item, source_item_id='nvidia:item-2', source=dict(self.item['source']),
                           sha256=second_sha, bytes=len(second_body), path=second_rel)
        manifest['items'].append(second_item)
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        (self.package / 'SHA256SUMS').write_text(
            f'{self.sha}  {self.relative}\n{second_sha}  {second_rel}\n')

        result = receive(self.repo, self.package, self.data, reader_sha256=[self.sha])

        selected = self.data / 'raw-materials/fetchspec/GPU' / (self.sha + '.pdf')
        held = self.data / 'raw-materials/fetchspec/Networking' / (second_sha + '.pdf')
        self.assertTrue(selected.exists())
        self.assertFalse(held.exists())
        self.assertEqual(result['reader_handoff_count'], 1)
        self.assertEqual({item['sha256']: item['reader_handoff'] for item in result['items']},
                         {self.sha: 'eligible', second_sha: 'held'})

    def test_reader_selection_must_belong_to_delivery_before_any_write(self):
        with self.assertRaises(PackageError):
            receive(self.repo, self.package, self.data, reader_sha256=['f' * 64])
        self.assertFalse((self.data / 'originals').exists())

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

    def test_contract_20_binds_files_to_registered_generated_targets_and_parts(self):
        target_id = 'P.compute_accelerator.spec'
        (self.repo / 'framework').mkdir()
        (self.repo / 'framework/tco_targets.json').write_text(json.dumps({'targets': [{
            'id': target_id, 'team': 'fetchspec', 'part_id': 'compute_accelerator'
        }]}))
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest.update(contract_version='2.0', target_ids=[target_id])
        manifest['items'][0]['source']['language'] = 'en'
        manifest['items'][0]['target_ids'] = [target_id]
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        result = receive(self.repo, self.package, self.data)
        self.assertEqual(result['research_context']['target_ids'], [target_id])
        self.assertEqual(result['research_context']['part_ids'], ['compute_accelerator'])
        self.assertEqual(result['items'][0]['target_ids'], [target_id])

    def test_contract_20_rejects_unknown_target_before_archiving(self):
        (self.repo / 'framework').mkdir()
        (self.repo / 'framework/tco_targets.json').write_text(json.dumps({'targets': []}))
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest.update(contract_version='2.0', target_ids=['P.unknown.spec'])
        manifest['items'][0]['source']['language'] = 'en'
        manifest['items'][0]['target_ids'] = ['P.unknown.spec']
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        with self.assertRaisesRegex(PackageError, 'generated_target_not_found'):
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
        expected = self.data / 'product-library/fetchspec/uncategorized' / (self.sha + '.pdf')
        self.assertTrue(expected.exists())
        self.assertFalse((self.data / 'raw-materials').exists())
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

    def use_body(self, body, fmt, content_type):
        (self.package / self.relative).unlink()
        self.sha = hashlib.sha256(body).hexdigest()
        path = f'files/{self.sha[:2]}/{self.sha}.{fmt}'
        (self.package / Path(path).parent).mkdir(parents=True, exist_ok=True)
        (self.package / path).write_bytes(body)
        self.item.update({'sha256': self.sha, 'bytes': len(body), 'format': fmt, 'content_type': content_type, 'path': path})
        manifest = json.loads((self.package / 'manifest.json').read_text())
        manifest['items'] = [self.item]
        (self.package / 'manifest.json').write_text(json.dumps(manifest))
        (self.package / 'SHA256SUMS').write_text(f'{self.sha}  {path}\n')

    def test_official_json_component_is_archived_by_content(self):
        self.use_body(json.dumps({'part-title': 'MT65B18G16120A00QH-92:A',
                                  'details': [{'id': 'density', 'name': 'Component Density', 'value': '36GB'}]}).encode(),
                      'json', 'application/json')
        result = receive(self.repo, self.package, self.data)
        self.assertEqual(result['items'][0]['sha256'], self.sha)
        self.assertEqual(result['items'][0]['reader_handoff'], 'extractor_required')
        self.assertEqual(product_documents(self.data, format='json')['total'], 1)

    def test_json_that_is_not_an_object_is_rejected_before_archiving(self):
        for body in (b'[1, 2]', b'{"a": ', b'<html></html>'):
            with self.subTest(body=body):
                self.setUp()
                self.use_body(body, 'json', 'application/json')
                with self.assertRaisesRegex(PackageError, 'format'):
                    receive(self.repo, self.package, self.data)
                self.assertFalse((self.data / 'originals').exists())

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
        self.assertFalse(handoff.exists())
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
