import io
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from inresearch.adapters import models, ocr_worker

ROOT = Path(__file__).resolve().parents[2]
OCR = dict(backend='ollama', url='http://127.0.0.1:11434', model='qwen3-vl:8b', context=8192,
           max_output_tokens=4096, max_parallel=1, capabilities=('vision_json',))


class RepeatPenaltyProfileTests(unittest.TestCase):
    def test_penalty_is_recorded_but_not_part_of_the_frozen_reading_identity(self):
        plain = models.ModelProfile(**OCR)
        guarded = models.ModelProfile(**OCR, repeat_penalty=1.05)
        self.assertNotIn('repeat_penalty', plain.identity)
        self.assertEqual(guarded.identity['repeat_penalty'], 1.05)
        self.assertEqual(models.reading_identity(guarded.identity), models.reading_identity(plain.identity))

    def test_out_of_range_or_non_ollama_penalties_are_refused(self):
        for value in (0.9, 2.5, True, '1.05'):
            with self.assertRaises(ValueError):
                models.ModelProfile(**OCR, repeat_penalty=value)
        with self.assertRaises(ValueError):
            models.ModelProfile(backend='claude_cli', url='', model='claude-sonnet-5', repeat_penalty=1.05)

    def test_only_the_ocr_profile_carries_the_penalty(self):
        config = json.loads((ROOT / 'deploy/models.json').read_text(encoding='utf-8'))
        carrying = {name for name, p in config['profiles'].items() if 'repeat_penalty' in p}
        self.assertEqual(carrying, {'spark_ocr'})
        self.assertEqual(models.ModelProfile(**config['profiles']['spark_ocr']).repeat_penalty, 1.05)

    def request_options(self, profile):
        sent = {}

        def urlopen(req, timeout=None):
            sent.update(json.loads(req.data))
            reply = {'model': profile.model, 'done_reason': 'stop',
                     'message': {'content': '{"text":"x","blank":false,"unreadable":false}'}}
            response = io.BytesIO(json.dumps(reply).encode())
            response.__enter__ = lambda *a: response
            response.__exit__ = lambda *a: False
            return response

        with mock.patch.object(models.urllib.request, 'urlopen', side_effect=urlopen):
            models.JsonModelClient(profile).generate('s', 'u')
        return sent['options']

    def test_penalty_reaches_ollama_only_when_configured(self):
        text = replace(models.ModelProfile(**OCR), capabilities=('text_json',))
        self.assertNotIn('repeat_penalty', self.request_options(text))
        self.assertEqual(self.request_options(replace(text, repeat_penalty=1.05))['repeat_penalty'], 1.05)


class PageRetryTests(unittest.TestCase):
    PAGE = {'text': 'x', 'blank': False, 'unreadable': False}

    def test_one_model_failure_is_retried(self):
        with mock.patch.object(ocr_worker, 'ocr', side_effect=[models.InferenceError('model_failure'), self.PAGE]) as call:
            self.assertEqual(ocr_worker.ocr_page('p.png'), self.PAGE)
        self.assertEqual(call.call_count, 2)

    def test_two_consecutive_failures_give_up(self):
        with mock.patch.object(ocr_worker, 'ocr', side_effect=[models.InferenceError('model_failure')] * 2) as call, \
             self.assertRaises(models.InferenceError):
            ocr_worker.ocr_page('p.png')
        self.assertEqual(call.call_count, 2)

    def test_other_errors_are_not_retried(self):
        with mock.patch.object(ocr_worker, 'ocr', side_effect=models.InferenceError('model_output_truncated')) as call, \
             self.assertRaises(models.InferenceError):
            ocr_worker.ocr_page('p.png')
        self.assertEqual(call.call_count, 1)


if __name__ == '__main__':
    unittest.main()
