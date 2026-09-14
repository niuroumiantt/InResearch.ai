"""Independent processes exercise the same mutations as HTTP and the CLI."""
import io
import json
import multiprocessing
import sys
from types import SimpleNamespace
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


    def test_common_root_keeps_assignment_and_snapshot_versions_in_selected_workspace(self):
        from inresearch.knowledge import registry
        from test_research import complete_document
        for name in ('research_graph.json', 'research_questions.json'):
            file_store.write_json(self.root/'framework'/name,
                                  registry.read_json(registry.ROOT/'framework'/name))
        knowledge = {key: [] for key in registry.COLLECTIONS}
        file_store.write_json(self.root/'data/research_knowledge.json', knowledge)
        file_store.write_json(self.root/'data/assignments.json', {'records': []})
        task = registry.current_tasks(self.root)[0]['wid']
        def invoke(command, payload, explicit=True):
            output = io.StringIO()
            args = ['--root', str(self.root), command] if explicit else [command]
            with patch('sys.stdin', io.StringIO(json.dumps(payload))), patch('sys.stdout', output), \
                 patch.object(cli, 'ROOT', self.root):
                status = cli.main(args)
            return status, json.loads(output.getvalue())
        self.assertEqual(invoke('assign', {'workorder_id': task, 'assignee': 'fixture', 'status': '已派'})[0], 0)
        self.assertEqual(invoke('assign', {'workorder_id': task, 'status': '进行中'}, explicit=False)[0], 0)
        assignment = registry.read_json(self.root/'data/assignments.json')['records'][0]
        self.assertEqual((assignment['assignee'], assignment['status'], assignment['by']),
                         ('fixture', '进行中', 'local-cli'))
        payload = dict(generated='2026-09-14T00:00:00+00:00', knowledge=knowledge,
                       graph_version=registry.read_json(self.root/'framework/research_graph.json')['version'],
                       questions_version=registry.read_json(self.root/'framework/research_questions.json')['version'])
        self.assertEqual(invoke('receive-snapshot', payload)[0], 0)
        destination = self.root/'data/research_runtime.json'
        first = destination.read_bytes()
        self.assertEqual(invoke('receive-snapshot', payload)[1]['status'], 409)
        self.assertEqual(destination.read_bytes(), first)
        newer = {**payload, 'generated': '2026-09-14T00:00:01+00:00',
                 'knowledge': {**knowledge, 'documents': [complete_document()]}}
        self.assertEqual(invoke('receive-snapshot', newer, explicit=False)[0], 0)
        second = destination.read_bytes()
        self.assertEqual(invoke('receive-snapshot', payload)[1]['status'], 409)
        self.assertEqual(destination.read_bytes(), second)
        self.assertEqual(registry.read_json(destination)['knowledge']['documents'][0]['status'], 'candidate')
        self.assertEqual(registry.read_json(self.root/'data/research_knowledge.json'), knowledge)


class CommandDispatch(unittest.TestCase):
    def test_global_root_is_rejected_before_import_for_every_delegated_command(self):
        original = sys.argv
        with tempfile.TemporaryDirectory() as directory:
            for command in cli.COMMANDS:
                with self.subTest(command=command), patch.object(cli.importlib, 'import_module') as load, \
                     patch.object(cli.argparse.ArgumentParser, 'error', side_effect=SystemExit(2)) as error_call:
                    with self.assertRaises(SystemExit) as error:
                        cli.main(['--root', directory, command])
                    self.assertEqual(error.exception.code, 2)
                    message = error_call.call_args.args[0]
                    self.assertIn('global --root applies only to add-price, assign, receive-snapshot', message)
                    self.assertIn('use directory options supported by ' + command, message)
                    load.assert_not_called()
                    self.assertIs(sys.argv, original)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_child_arguments_are_forwarded_and_argv_restored_after_success_and_failure(self):
        original = sys.argv
        expected = ['inventory', '--root', '/fixture/source', '--out-dir', '/fixture/index', 'inventory']
        def child():
            self.assertEqual(sys.argv, expected)
            return 17
        for failure in (None, RuntimeError('child failed'), SystemExit(2)):
            with self.subTest(failure=failure):
                def run():
                    result = child()
                    if failure is not None:
                        raise failure
                    return result
                with patch.object(cli.importlib, 'import_module', return_value=SimpleNamespace(main=run)) as load:
                    if failure is None:
                        self.assertEqual(cli.main(expected), 17)
                    else:
                        with self.assertRaises(type(failure)):
                            cli.main(expected)
                    load.assert_called_once_with('inresearch.materials.inventory')
                self.assertIs(sys.argv, original)
        with patch.object(cli.importlib, 'import_module', side_effect=ImportError('unavailable')):
            with self.assertRaises(ImportError):
                cli.main(['inventory'])
        self.assertIs(sys.argv, original)

    def test_default_invocation_does_not_reuse_a_previous_child_command(self):
        original = ['manage.py', 'asset-check']
        seen = []
        def child():
            seen.append(list(sys.argv))
            return 0
        with patch('sys.argv', original), \
             patch.object(cli.importlib, 'import_module', return_value=SimpleNamespace(main=child)):
            cli.main(['inventory', '--help'])
            cli.main()
            self.assertIs(sys.argv, original)
        self.assertEqual(seen, [['inventory', '--help'], ['asset-check']])


if __name__ == '__main__':
    unittest.main()
