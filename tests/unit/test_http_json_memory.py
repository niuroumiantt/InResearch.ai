"""Behavior and bounded-memory checks for JSON HTTP responses."""
import gzip
import io
import json
from pathlib import Path
import tempfile
import tracemalloc
import unittest
from unittest.mock import patch

from inresearch.interfaces import http


class _Headers(dict):
    def get(self, key, default=''):
        return super().get(key, default)


class _CountingSink:
    def __init__(self):
        self.length = 0

    def write(self, data):
        self.length += len(data)
        return len(data)


class _FakeHandler:
    def __init__(self, *, accept_encoding='', command='GET', sink=None, on_headers=None):
        self.headers = _Headers({'Accept-Encoding': accept_encoding})
        self.command = command
        self.path = '/api/test'
        self.wfile = sink if sink is not None else io.BytesIO()
        self.response_code = None
        self.response_headers = {}
        self.headers_sent = False
        self.on_headers = on_headers

    def send_response(self, code):
        self.response_code = code

    def send_header(self, key, value):
        self.response_headers[key.lower()] = value

    def end_headers(self):
        self.headers_sent = True
        if self.on_headers:
            self.on_headers()


class HttpJsonMemoryTests(unittest.TestCase):
    def _call_json(self, handler, code, value, compressed=False):
        with tempfile.TemporaryDirectory() as td:
            logs = Path(td) / 'logs'
            logs.mkdir()
            with patch.object(http, 'workspace_path', return_value=logs):
                return http.Handler._json(handler, code, value, compressed=compressed)

    def test_json_body_is_exact_utf8_and_content_length_matches(self):
        value = {'园区': '张家口数据中心', 'metrics': [1, None, {'PUE': 1.2}], 'ok': True}
        handler = _FakeHandler()

        self._call_json(handler, 207, value)

        expected = json.dumps(value, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':')).encode('utf-8')
        self.assertEqual(handler.response_code, 207)
        self.assertEqual(handler.wfile.getvalue(), expected)
        self.assertEqual(handler.response_headers['content-length'], str(len(expected)))
        self.assertEqual(handler.response_headers['content-type'], 'application/json; charset=utf-8')

    def test_health_and_small_json_do_not_resolve_or_create_runtime_logs(self):
        for path, command, compressed in [('/healthz', 'GET', False),
                                           ('/healthz', 'HEAD', False),
                                           ('/api/whoami', 'GET', False),
                                           ('/api/test', 'GET', True)]:
            handler = _FakeHandler(command=command, accept_encoding='gzip')
            handler.path = path
            value = {'ok': True, 'service': 'inresearch'}
            with self.subTest(path=path, command=command, compressed=compressed), \
                 patch.object(http, 'workspace_path', side_effect=AssertionError('runtime read')), \
                 patch.object(http.tempfile, 'TemporaryFile', side_effect=AssertionError('disk write')):
                http.Handler._json(handler, 200, value, compressed=compressed)
            self.assertEqual(handler.response_code, 200)
            if command == 'HEAD':
                self.assertEqual(handler.wfile.getvalue(), b'')
            else:
                body = handler.wfile.getvalue()
                self.assertEqual(json.loads(gzip.decompress(body) if compressed else body), value)

    def test_gzip_negotiation_honors_zero_quality_and_positive_quality(self):
        value = {'site': '园区甲', 'capacity': 10}
        denied = _FakeHandler(accept_encoding='gzip;q=0, br')
        self._call_json(denied, 200, value, compressed=True)
        plain = json.dumps(value, ensure_ascii=False, allow_nan=False,
                           separators=(',', ':')).encode('utf-8')
        self.assertNotIn('content-encoding', denied.response_headers)
        self.assertEqual(denied.wfile.getvalue(), plain)

        allowed = _FakeHandler(accept_encoding='br, gzip;q=0.5')
        self._call_json(allowed, 200, value, compressed=True)
        compressed = allowed.wfile.getvalue()
        self.assertEqual(allowed.response_headers['content-encoding'], 'gzip')
        self.assertEqual(gzip.decompress(compressed), plain)
        self.assertEqual(allowed.response_headers['content-length'], str(len(compressed)))

        case_insensitive = _FakeHandler(accept_encoding='GZIP;Q=0.5')
        self._call_json(case_insensitive, 200, value, compressed=True)
        self.assertEqual(case_insensitive.response_headers.get('content-encoding'), 'gzip')

    def test_head_sends_get_length_without_a_body(self):
        value = {'items': ['张家口', '乌兰察布']}
        get = _FakeHandler()
        head = _FakeHandler(command='HEAD')

        self._call_json(get, 200, value)
        self._call_json(head, 200, value)

        self.assertEqual(head.response_headers['content-length'],
                         get.response_headers['content-length'])
        self.assertEqual(head.wfile.getvalue(), b'')

    def test_large_response_spills_under_private_logs_and_closes_temporary_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'repo'
            logs = root / 'logs'
            logs.mkdir(parents=True)
            value = {'records': [{'text': '园区数据中心' * 200000}]}
            real_factory = http.tempfile.SpooledTemporaryFile
            created = []

            def create_spool(*args, **kwargs):
                stream = real_factory(*args, **kwargs)
                created.append((stream, kwargs.copy()))
                return stream

            def private_logs(relative, requested_root=None):
                self.assertEqual(relative, 'logs')
                self.assertEqual(Path(requested_root), root)
                return logs

            handler = _FakeHandler(sink=_CountingSink(), on_headers=lambda: self.assertTrue(
                created[0][0]._rolled))
            with patch.object(http, 'ROOT', root), \
                    patch.object(http, 'workspace_path', side_effect=private_logs), \
                    patch.object(http.tempfile, 'SpooledTemporaryFile', side_effect=create_spool):
                http.Handler._json(handler, 200, value)

            stream, options = created[0]
            expected_len = len(json.dumps(value, ensure_ascii=False, allow_nan=False,
                                          separators=(',', ':')).encode('utf-8'))
            self.assertGreater(expected_len, 2 * 1024 * 1024)
            self.assertLess(expected_len, 5 * 1024 * 1024)
            self.assertEqual(Path(options['dir']).resolve(), logs.resolve())
            self.assertNotEqual(Path(options['dir']).resolve(), Path(tempfile.gettempdir()).resolve())
            self.assertEqual(handler.wfile.length, expected_len)
            self.assertEqual(handler.response_headers['content-length'], str(expected_len))
            self.assertTrue(stream.closed)
            self.assertEqual(list(logs.iterdir()), [])

    def test_utf8_encoding_failure_occurs_before_response_headers(self):
        handler = _FakeHandler()
        with self.assertRaises(UnicodeEncodeError):
            self._call_json(handler, 200, {'invalid': '\ud800'})
        self.assertFalse(handler.headers_sent)
        self.assertIsNone(handler.response_code)
        self.assertEqual(handler.wfile.getvalue(), b'')

    def test_multimegabyte_unicode_peak_is_bounded_vs_legacy_full_string_and_bytes(self):
        value = {'records': [{'text': '园区数据中心' * 200000}]}

        def legacy_response():
            text = json.dumps(value, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':'))
            encoded = text.encode('utf-8')
            return len(encoded)

        tracemalloc.start()
        legacy_size = legacy_response()
        _, legacy_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        sink = _CountingSink()
        handler = _FakeHandler(sink=sink)
        tracemalloc.start()
        self._call_json(handler, 200, value)
        _, streaming_peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        self.assertGreater(legacy_size, 2 * 1024 * 1024)
        self.assertLess(legacy_size, 5 * 1024 * 1024)
        self.assertEqual(sink.length, legacy_size)
        self.assertLess(streaming_peak, legacy_peak * 0.7,
                        f'streaming peak {streaming_peak} vs legacy peak {legacy_peak}')


if __name__ == '__main__':
    unittest.main()
