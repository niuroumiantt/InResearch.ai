#!/usr/bin/env python3
"""A contract nothing enforces is a comment.

fact.schema.json states the rules that make two numbers comparable - every
caliber dimension present, the unit as declared, a locator someone can follow
back.  These tests are what turns those sentences into a gate.  The fixture
metrics mirror the real ones in shape, so a rule that passes here passes on
framework/metrics.json too.
"""
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_l2 as L2

METRICS = {
    'dc_construction_cost_per_sqm': {
        'metric_id': 'dc_construction_cost_per_sqm', 'unit': '元/㎡', 'module': 'M10',
        'caliber_dims': [
            {'id': 'stage', 'name': '造价阶段', 'values': ['招标控制价', '竣工结算价']},
            {'id': 'scope', 'name': '包含范围', 'values': ['土建本体', '施工总包']},
        ],
    },
    'free_form_metric': {
        'metric_id': 'free_form_metric', 'unit': 'MW', 'module': 'M04',
        'caliber_dims': [{'id': 'region', 'name': '地域'}],   # no enum: any text
    },
}

SHA = 'a' * 64


def fact(**over):
    base = {
        'fact_id': 'luan-ct-cost-gc-2022',
        'metric_id': 'dc_construction_cost_per_sqm',
        'value': 4406.0, 'unit': '元/㎡',
        'caliber': {'stage': '招标控制价', 'scope': '施工总包'},
        'as_of': '2022-01',
        'evidence': {'sha256': SHA, 'locator': '封面限价 79,483,818.90 元', 'grade': 'S2'},
        'depth': '精读', 'bound': 'point', 'corroboration': '已交叉验证',
    }
    base.update(over)
    return base


def problems(f, seen=None):
    return L2.check_fact(f, METRICS, seen if seen is not None else set())


class ValidatorTests(unittest.TestCase):
    def test_a_well_formed_fact_passes(self):
        self.assertEqual(problems(fact()), [])

    def test_an_unknown_metric_is_refused(self):
        self.assertIn('metric_id', ' '.join(problems(fact(metric_id='invented'))))

    def test_the_unit_must_match_the_metric_declaration(self):
        self.assertIn('unit', ' '.join(problems(fact(unit='美元/㎡'))))

    # --- caliber: the whole point of the layer -----------------------------

    def test_a_missing_caliber_dimension_is_refused(self):
        """Two costs are not comparable until both say control price or final."""
        found = problems(fact(caliber={'stage': '招标控制价'}))
        self.assertTrue(any('scope' in p for p in found), found)

    def test_a_caliber_value_outside_the_declared_set_is_refused(self):
        found = problems(fact(caliber={'stage': '拍脑袋', 'scope': '施工总包'}))
        self.assertTrue(any('stage' in p for p in found), found)

    def test_an_undeclared_caliber_dimension_is_refused(self):
        found = problems(fact(caliber={'stage': '招标控制价', 'scope': '施工总包', 'extra': 'x'}))
        self.assertTrue(any('extra' in p for p in found), found)

    def test_a_dimension_without_an_enum_takes_any_text(self):
        free = fact(metric_id='free_form_metric', unit='MW',
                    caliber={'region': '华东某省'})
        self.assertEqual(problems(free), [])

    # --- the discipline rules ----------------------------------------------

    def test_a_withheld_value_is_legal_but_an_absent_one_is_not(self):
        self.assertEqual(problems(fact(value=None)), [])
        missing = fact(); del missing['value']
        self.assertTrue(any('value' in p for p in problems(missing)))

    def test_a_value_that_is_not_a_number_is_refused(self):
        self.assertTrue(any('value' in p for p in problems(fact(value='约 4400'))))

    def test_an_empty_locator_is_refused(self):
        found = problems(fact(evidence={'sha256': SHA, 'locator': '   ', 'grade': 'S2'}))
        self.assertTrue(any('locator' in p for p in found), found)

    def test_a_missing_or_malformed_hash_is_refused(self):
        for bad in ({'locator': 'p.1', 'grade': 'S2'},
                    {'sha256': 'ZZZ', 'locator': 'p.1', 'grade': 'S2'},
                    {'sha256': 'a' * 63, 'locator': 'p.1', 'grade': 'S2'}):
            self.assertTrue(any('sha256' in p for p in problems(fact(evidence=bad))), bad)

    def test_only_close_reading_reaches_the_fact_layer(self):
        for depth in ('半自动', '目录级', '', None):
            self.assertTrue(any('depth' in p for p in problems(fact(depth=depth))), depth)
        for depth in ('精读', '据实生成'):
            self.assertEqual(problems(fact(depth=depth)), [])

    def test_a_derived_value_must_explain_itself(self):
        self.assertTrue(any('notes' in p for p in problems(fact(derived=True))))
        self.assertEqual(problems(fact(derived=True, notes='总包减去室外市政')), [])

    def test_a_repeated_fact_id_is_refused(self):
        self.assertTrue(any('重复' in p for p in problems(fact(), seen={'luan-ct-cost-gc-2022'})))

    def test_a_fact_id_must_be_lowercase_hyphenated(self):
        for bad in ('Luan_CT', '六安造价', '', None):
            self.assertTrue(any('fact_id' in p for p in problems(fact(fact_id=bad))), bad)

    def test_bound_and_corroboration_are_checked_when_present(self):
        self.assertTrue(any('bound' in p for p in problems(fact(bound='大概'))))
        self.assertTrue(any('corroboration' in p for p in problems(fact(corroboration='应该对'))))
        light = fact(); del light['bound']; del light['corroboration']
        self.assertEqual(problems(light), [])


class TemporalGrammarTests(unittest.TestCase):
    """A forecast is not an outturn, and a forecast has a vintage."""

    def accepted(self, value):
        return not any('as_of' in p for p in problems(fact(as_of=value)))

    def test_real_forms_from_the_existing_fact_layer_are_accepted(self):
        for value in ('2022', '2022-01', '2026-08-17', '2026-Q1', '2025-Q1E',
                      '2026E', '2025目标', '2025-2027E', '2025E@2024-04'):
            self.assertTrue(self.accepted(value), value)

    def test_nonsense_is_still_refused(self):
        for value in ('去年', '2022/01', '22-01', '', 'soon', '2022-Q9'):
            self.assertFalse(self.accepted(value), value)


class ChunkTests(unittest.TestCase):
    def test_chunks_break_on_blank_lines_and_keep_everything(self):
        text = '\n\n'.join('段落 %d %s' % (i, 'x' * 400) for i in range(40))
        pieces = L2.chunks(text, size=2000)
        self.assertGreater(len(pieces), 1)
        for piece in pieces:
            self.assertLessEqual(len(piece), 3000)
        rejoined = '\n\n'.join(pieces)
        self.assertEqual(rejoined.replace('\n', ''), text.replace('\n', ''))

    def test_a_short_text_is_one_chunk(self):
        self.assertEqual(L2.chunks('短文'), ['短文'])


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-test-')
        base = Path(self.temp.name)
        self.facts = base / 'facts.json'
        self.facts.write_text(json.dumps(
            {'version': '0.1', 'records': []}, ensure_ascii=False), encoding='utf-8')
        self._saved = (L2.FACTS, L2.READ_LOG, L2.load_metrics)
        L2.FACTS = self.facts
        L2.READ_LOG = base / 'l2_read.jsonl'
        L2.load_metrics = lambda: METRICS

    def tearDown(self):
        (L2.FACTS, L2.READ_LOG, L2.load_metrics) = self._saved
        self.temp.cleanup()

    def record(self, facts, **flags):
        path = Path(self.temp.name) / 'incoming.json'
        path.write_text(json.dumps(facts, ensure_ascii=False), encoding='utf-8')
        args = type('A', (), {'facts': str(path), 'doc': flags.get('doc'),
                              'partial': flags.get('partial', False), 'show': 5})
        out = io.StringIO()
        with redirect_stdout(out):
            L2.cmd_record(args)
        return json.loads(out.getvalue().splitlines()[0])

    def test_a_good_batch_lands(self):
        report = self.record([fact(), fact(fact_id='second-fact')])
        self.assertEqual(report['accepted'], 2)
        stored = json.loads(self.facts.read_text(encoding='utf-8'))['records']
        self.assertEqual(len(stored), 2)

    def test_one_bad_fact_holds_the_whole_batch(self):
        report = self.record([fact(), fact(fact_id='bad', unit='wrong')])
        self.assertEqual(report['accepted'], 0)
        self.assertEqual(json.loads(self.facts.read_text(encoding='utf-8'))['records'], [])

    def test_partial_takes_the_good_ones(self):
        report = self.record([fact(), fact(fact_id='bad', unit='wrong')], partial=True)
        self.assertEqual(report['accepted'], 1)
        self.assertEqual(report['rejected'], 1)

    def test_a_fact_id_already_in_the_store_is_refused(self):
        self.record([fact()])
        report = self.record([fact()])
        self.assertEqual(report['accepted'], 0)

    def test_recording_marks_the_document_read(self):
        self.record([fact()], doc='b' * 64)
        rows = [json.loads(l) for l in L2.READ_LOG.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[0]['sha256'], 'b' * 64)
        self.assertEqual(rows[0]['facts'], 1)

    def test_a_document_with_no_facts_still_counts_as_read(self):
        """Zero facts is a legitimate outcome; inventing one is not."""
        report = self.record([], doc='c' * 64)
        self.assertEqual(report['accepted'], 0)
        self.assertIn('c' * 64, L2.READ_LOG.read_text(encoding='utf-8'))




class SelfAuthoredTests(unittest.TestCase):
    """Reading our own output back as evidence double-counts the facts in it.

    A summary this project wrote was derived from the fact layer.  Feed it to
    L2 and those facts are recorded a second time, now carrying a grade and a
    locator, so a lone claim starts looking corroborated by an independent
    source.  The real queue surfaced three such files at the top - M05.md,
    M15.md and SUMMARY.md, all judged 8 - precisely because the thin modules
    sort first.
    """

    def test_our_own_org_label_is_excluded(self):
        for org in ('本项目', '内部研究', 'inresearch.ai'):
            self.assertTrue(L2.self_authored({'org': org, 'rel': 'a/b.md'}), org)

    def test_whitespace_around_the_label_does_not_smuggle_it_through(self):
        self.assertTrue(L2.self_authored({'org': '  本项目 ', 'rel': 'a/b.md'}))

    def test_our_own_output_directories_are_excluded(self):
        for rel in ('docs/SUMMARY.md', 'data/facts.json', 'framework/metrics.json',
                    'reports/verify_queue.md', '要删/reader/cache.txt'):
            self.assertTrue(L2.self_authored({'org': '某机构', 'rel': rel}), rel)

    def test_a_real_source_is_not_excluded(self):
        for row in ({'org': 'Dell\'Oro Group', 'rel': '报告/capex.pdf'},
                    {'org': '国际能源署', 'rel': '数据中心报告购买/iea.pdf'},
                    {'org': None, 'rel': 'raw/x.xlsx'},
                    {}):
            self.assertFalse(L2.self_authored(row), row)

    def test_a_directory_that_merely_starts_similarly_is_kept(self):
        self.assertFalse(L2.self_authored({'org': 'X', 'rel': 'documentation/x.pdf'}))
        self.assertFalse(L2.self_authored({'org': 'X', 'rel': 'database报告/x.pdf'}))


if __name__ == '__main__':
    unittest.main()
