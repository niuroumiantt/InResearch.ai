import io
import json
import unittest
from unittest import mock

from inresearch.adapters import models, reader_model

TEXT = dict(backend='ollama', url='http://127.0.0.1:11434', model='qwen3.8:27b', context=32768,
            max_output_tokens=4096, max_parallel=1, capabilities=('text_json',))


def sent_body(client, **kwargs):
    sent = {}

    def urlopen(req, timeout=None):
        sent.update(json.loads(req.data))
        reply = {'model': client.profile.model, 'done_reason': 'stop', 'message': {'content': '{"summary":"x","key_points":[]}'}}
        response = io.BytesIO(json.dumps(reply).encode())
        response.__enter__ = lambda *a: response
        response.__exit__ = lambda *a: False
        return response
    with mock.patch.object(models.urllib.request, 'urlopen', side_effect=urlopen):
        client.generate('s', 'u', **kwargs)
    return sent


class OllamaSchemaTests(unittest.TestCase):
    def test_task_schema_constrains_ollama_decoding(self):
        client = models.JsonModelClient(models.ModelProfile(**TEXT))
        schema = reader_model._schema('read')
        body = sent_body(client, json_schema=schema)
        self.assertEqual(body['format'], schema)
        self.assertIn('claims', body['format']['required'])

    def test_without_a_schema_plain_json_mode_is_kept(self):
        client = models.JsonModelClient(models.ModelProfile(**TEXT))
        self.assertEqual(sent_body(client)['format'], 'json')

    def test_every_reader_stage_sends_its_schema(self):
        seen = []

        class Recorder:
            def generate(self, system, user, **kwargs):
                seen.append(kwargs.get('json_schema'))
                return {}
        client = reader_model.ModelClient.__new__(reader_model.ModelClient)
        client.client = Recorder()
        for stage in ('triage', 'read', 'synthesize'):
            client.generate(stage, {'x': 1})
        self.assertEqual(seen, [reader_model._schema(s) for s in ('triage', 'read', 'synthesize')])

    def test_schema_does_not_change_the_frozen_reading_identity(self):
        profile = models.ModelProfile(**TEXT)
        self.assertNotIn('format', profile.identity)
        self.assertNotIn('json_schema', profile.identity)


if __name__ == '__main__':
    unittest.main()
