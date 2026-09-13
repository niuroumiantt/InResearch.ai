"""Independent processes exercise the same mutations as HTTP and the CLI."""
import io
import json
import multiprocessing
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from inresearch.workflow import commands as commands
from inresearch.interfaces import cli as cli
from inresearch.storage import files as file_store
from inresearch.interfaces import http as serve


def price(root, index):
    commands.add_price(root, dict(series_id='s'+str(index), as_of='2026-09-13', value=index,
        unit='USD', grade='company', source_url='https://example.test', category='gpu', module='M06'))


class CommandFlows(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        file_store.write_json(self.root/'data/prices.json', {'records': []})

    def tearDown(self):
        self.temp.cleanup()

    def test_independent_processes_do_not_lose_records(self):
        context = multiprocessing.get_context('spawn')
        workers = [context.Process(target=price, args=(self.root, i)) for i in range(12)]
        for p in workers: p.start()
        for p in workers:
            p.join(20)
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(len(json.loads((self.root/'data/prices.json').read_text())['records']), 12)
        with self.assertRaises(commands.Rejected) as error:
            price(self.root, 1)
        self.assertEqual(error.exception.status, 409)

    def test_exception_and_failed_replace_keep_old_bytes(self):
        target = self.root/'data/prices.json'
        before = target.read_bytes()
        with self.assertRaises(ValueError), file_store.json_transaction(target) as doc:
            doc['records'].append({'invalid': True})
            raise ValueError('validation failed')
        self.assertEqual(target.read_bytes(), before)
        with patch.object(file_store.os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError): price(self.root, 1)
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(list(target.parent.glob('*.tmp-*')), [])
        price(self.root, 1)

    def test_cli_and_http_share_duplicate_and_validation_decisions(self):
        rec = dict(series_id='x', as_of='2026-09-13', value=2, unit='USD', grade='company',
                   source_url='https://example.test', category='gpu', module='M06')
        with patch('sys.stdin', io.StringIO(json.dumps(rec))), patch('sys.stdout', io.StringIO()):
            self.assertEqual(cli.main(['--root', str(self.root), 'add-price']), 0)
        h = object.__new__(serve.Handler)
        h._json = lambda status, body: (status, body)
        with patch.object(serve, 'ROOT', self.root):
            self.assertEqual(h.api_add_price(rec)[0], 409)
            self.assertEqual(h.api_add_price({**rec, 'series_id':'bad', 'grade':'invented'})[0], 400)
            self.assertEqual(h.api_add_price({**rec, 'series_id':'bad', 'value':True})[0], 400)
        self.assertEqual(len(json.loads((self.root/'data/prices.json').read_text())['records']), 1)

    def test_post_replace_sync_failure_is_visible_and_retry_does_not_duplicate(self):
        with patch.object(file_store, 'sync_directory', side_effect=OSError('injected fsync failure')):
            with self.assertRaises(file_store.CommitUncertain):
                price(self.root, 1)
        records = json.loads((self.root/'data/prices.json').read_text())['records']
        self.assertEqual(1, len(records))
        with self.assertRaises(commands.Rejected) as error:
            price(self.root, 1)
        self.assertEqual(409, error.exception.status)
        self.assertEqual(records, json.loads((self.root/'data/prices.json').read_text())['records'])

    def test_cli_and_http_expose_post_commit_uncertainty(self):
        output = io.StringIO()
        with patch.object(commands, 'add_price', side_effect=file_store.CommitUncertain()), \
             patch('sys.stdin', io.StringIO('{}')), patch('sys.stdout', output):
            self.assertEqual(1, cli.main(['--root', str(self.root), 'add-price']))
        self.assertEqual('visible_durability_unconfirmed', json.loads(output.getvalue())['commit_state'])
        h = object.__new__(serve.Handler)
        h._json = lambda status, body: (status, body)
        for command, call in [('add_price', lambda: h.api_add_price({})),
                              ('assign', lambda: h.api_assign({}))]:
            with patch.object(commands, command, side_effect=file_store.CommitUncertain()):
                status, body = call()
            self.assertEqual(503, status)
            self.assertEqual('visible_durability_unconfirmed', body['commit_state'])


if __name__ == '__main__':
    unittest.main()
