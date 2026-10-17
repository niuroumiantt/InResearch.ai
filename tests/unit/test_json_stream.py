import io
import json
import random
import tracemalloc
import unittest

from inresearch.storage.json_stream import load


class JsonStreamTests(unittest.TestCase):
    def test_complete_values_at_every_small_boundary(self):
        examples = [None, True, False, 0, -1, -0.125, 1.2e-20, '雪😀"\\\n',
                    {'x': [1, None, {}, [], {'雪': '😀'}], 'repeat': 'x' * 137},
                    [[], {}, '', 1000000000000000000000000000001]]
        for value in examples:
            raw = json.dumps(value, ensure_ascii=False)
            for width in range(1, 24):
                with self.subTest(width=width, value=str(value)[:30]):
                    self.assertEqual(load(io.StringIO(raw), chunk_size=width), value)

    def test_numeric_tokens_are_not_cut_at_buffer_end(self):
        raw = '[12345678901234567890, -12.345e-17, 0.001, 1e+100]'
        for width in range(1, 30):
            self.assertEqual(load(io.StringIO(raw), chunk_size=width), json.loads(raw))

    def test_malformed_documents_never_return_partial_success(self):
        for raw in ('', ' ', '[', '{', '[1,]', '{"a":1,}', '{"a":1 "b":2}',
                    '01', '1e', '1e+', '[truefalse]', 'nullx', '{}{}', '[]x',
                    '"abc', '"a\nb"', '{"a":', '{1:2}', '[1:2]', '\ufeff{}'):
            for width in (1, 2, 7, 65536):
                with self.subTest(raw=raw, width=width):
                    with self.assertRaises(ValueError):
                        load(io.StringIO(raw), chunk_size=width)

    def test_stdlib_hooks_and_duplicate_key_policy_preserved(self):
        raw = '{"x":1,"x":2,"rows":[{"x":3},{"x":4}],"tail":"' + '雪' * 100 + '"}'
        self.assertEqual(load(io.StringIO(raw), chunk_size=3), json.loads(raw))
        def strict(pairs):
            out = {}
            for key, value in pairs:
                if key in out:
                    raise ValueError('duplicate')
                out[key] = value
            return out
        for width in (3, 65536):
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                load(io.StringIO(raw), decoder=json.JSONDecoder(object_pairs_hook=strict), chunk_size=width)
        decoder = json.JSONDecoder(parse_float=str, parse_int=str,
                                   object_hook=lambda obj: {'wrapped': obj})
        raw = '{"x":[1,1.25,{"z":2}]}'
        self.assertEqual(load(io.StringIO(raw), decoder=decoder, chunk_size=3), decoder.decode(raw))

    def test_random_nested_values_and_long_unicode_string(self):
        rng = random.Random(1234)
        def make(depth=0):
            if depth > 3 or rng.randrange(3) == 0:
                return rng.choice([None, False, 0, 2e-10, '雪😀\\"\n' * rng.randrange(12)])
            if rng.randrange(2):
                return [make(depth+1) for _ in range(rng.randrange(8))]
            return {str(i): make(depth+1) for i in range(rng.randrange(8))}
        for _ in range(40):
            value = make()
            self.assertEqual(load(io.StringIO(json.dumps(value, ensure_ascii=False)), chunk_size=17), value)
        value = {'quote': '雪😀\\"' * 30000}
        self.assertEqual(load(io.StringIO(json.dumps(value, ensure_ascii=False))), value)

    def test_full_ledger_read_has_no_file_sized_unicode_buffer(self):
        # File bytes exist before tracing; this isolates the decoder's added
        # live memory and still verifies every row and the final record.
        raw = json.dumps([{'id': i, 'quote': '雪' * 1000} for i in range(1500)], ensure_ascii=False).encode()
        def measure(reader):
            tracemalloc.start()
            with io.TextIOWrapper(io.BytesIO(raw), encoding='utf-8') as stream:
                value = reader(stream)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            self.assertEqual(len(value), 1500)
            self.assertEqual(value[-1], {'id': 1499, 'quote': '雪' * 1000})
            return peak
        legacy = measure(lambda stream: json.loads(stream.read()))
        streamed = measure(load)
        self.assertLess(streamed, legacy * 0.8)

    def test_common_keys_shared_across_buffers_without_global_intern(self):
        value = load(io.StringIO(json.dumps([{'common_field': n} for n in range(2000)])), chunk_size=127)
        self.assertEqual(len({id(next(iter(row))) for row in value}), 1)
        unique = {'field_' + str(n): n for n in range(5000)}
        self.assertEqual(load(io.StringIO(json.dumps(unique)), chunk_size=127), unique)


if __name__ == '__main__':
    unittest.main()
