#!/usr/bin/env python3
"""A contract nothing enforces is a comment.

fact.schema.json states the rules that make two numbers comparable - every
caliber dimension present, the unit as declared, a locator someone can follow
back.  These tests are what turns those sentences into a gate.  The fixture
metrics mirror the real ones in shape, so a rule that passes here passes on
framework/metrics.json too.
"""
import io
import hashlib
import json
import re
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from inresearch.workflow import deep_read as L2
import inresearch.adapters.office_grid as office_grid

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
    'noted_metric': {
        'metric_id': 'noted_metric', 'name': '带警告的指标', 'unit': '亿美元', 'module': 'M10',
        'note': '**表头单位与实际数值不符**，照表头换算会错一百万倍。',
        'caliber_dims': [{'id': 'scope', 'name': '范围', 'values': ['甲', '乙']}],
    },
}

SHA = 'a' * 64


def fact(**over):
    base = {
        'fact_id': 'luan-ct-cost-gc-2022',
        'metric_id': 'dc_construction_cost_per_sqm',
        'entity': {'type': 'project', 'id': 'cn-ah-luan-ct', 'label': '六安 CT'},
        'value': 4406.0, 'unit': '元/㎡',
        'caliber': {'stage': '招标控制价', 'scope': '施工总包'},
        'as_of': '2022-01',
        'evidence': {'sha256': SHA, 'locator': '封面限价 79,483,818.90 元', 'grade': 'S2'},
        'depth': '精读', 'bound': 'point', 'corroboration': '已交叉验证',
    }
    base.update(over)
    return base


def other(**over):
    """A fact about a different site, so it is a different claim."""
    over.setdefault('entity', {'type': 'project', 'id': 'cn-gd-gz-dc', 'label': '广州'})
    over.setdefault('fact_id', 'gz-dc-cost-gc-2022')
    return fact(**over)


def problems(f, seen=None, claims=None):
    return L2.check_fact(f, METRICS, seen if seen is not None else set(), claims)


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
        self.assertEqual(problems(fact(value=None, notes="原文未披露")), [])
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
        self.assertEqual(problems(fact(derived=True, notes='总包减去室外市政', derivation='总包 - 室外市政')), [])

    def test_ranges_and_withheld_values_share_the_stored_fact_contract(self):
        for interval in ([2, 1], [1], [True, 3], [0, float('inf')], ['1', '3']):
            self.assertTrue(problems(fact(value=None, value_range=interval)))
        self.assertTrue(problems(fact(value_range=[1, 3])))
        self.assertTrue(problems(fact(value=None)))
        self.assertTrue(problems(fact(derived=True, notes='   ')))
        self.assertEqual(problems(fact(value=None, value_range=[1, 3])), [])
        from inresearch.knowledge import facts
        for candidate in (fact(value=None), fact(value_range=[1, 3]),
                          fact(value=None, value_range=[1, 3]),
                          fact(derived=True, notes='已说明但没有公式')):
            facts.validate([candidate], METRICS)
            self.assertEqual(bool(facts.errors), bool(problems(candidate)))

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
        report = self.record([fact(), other()])
        self.assertEqual(report['accepted'], 2)
        stored = json.loads(self.facts.read_text(encoding='utf-8'))['records']
        self.assertEqual(len(stored), 2)

    def test_one_bad_fact_holds_the_whole_batch(self):
        report = self.record([fact(), other(fact_id='bad', unit='wrong')])
        self.assertEqual(report['accepted'], 0)
        self.assertEqual(json.loads(self.facts.read_text(encoding='utf-8'))['records'], [])

    def test_partial_takes_the_good_ones(self):
        report = self.record([fact(), other(fact_id='bad', unit='wrong')], partial=True)
        self.assertEqual(report['accepted'], 1)
        self.assertEqual(report['rejected'], 1)

    def test_a_fact_id_already_in_the_store_is_refused(self):
        self.record([fact()])
        report = self.record([fact()])
        self.assertEqual(report['accepted'], 0)

    def test_recording_marks_the_document_read(self):
        self.record([fact()], doc=SHA)
        rows = [json.loads(l) for l in L2.READ_LOG.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[0]['sha256'], SHA)
        self.assertEqual(rows[0]['facts'], 1)

    def test_failed_read_log_can_be_replayed_without_duplicate_facts(self):
        from unittest.mock import patch
        with patch.object(L2, 'append_record', side_effect=OSError('interrupted after fact commit')):
            with self.assertRaises(OSError):
                self.record([fact()], doc=SHA)
        report = self.record([fact()], doc=SHA)
        self.assertEqual(report['replayed'], 1)
        self.assertEqual(report['facts_total'], 1)
        self.assertTrue(L2.READ_LOG.exists())

    def test_other_material_cannot_mark_this_document_read(self):
        report = self.record([fact()], doc='b' * 64)
        self.assertEqual(report['accepted'], 0)
        self.assertFalse(L2.READ_LOG.exists())
        self.assertEqual(json.loads(self.facts.read_text())['records'], [])

    def test_two_bare_forecasts_of_one_year_do_not_both_land(self):
        """The wiring, not just the rule: record must build and keep the index."""
        report = self.record([fact(fact_id='idc-2023e-a', as_of='2023E'),
                              fact(fact_id='idc-2023e-b', as_of='2023E', value=99.0)])
        self.assertEqual(report['accepted'], 0)

    def test_the_index_survives_between_runs(self):
        self.record([fact(fact_id='idc-2023e-a', as_of='2023E')])
        report = self.record([fact(fact_id='idc-2023e-b', as_of='2023E', value=99.0)])
        self.assertEqual(report['accepted'], 0)

    def test_the_same_year_at_two_vintages_both_land(self):
        self.record([fact(fact_id='idc-2023e-at-2019', as_of='2023E@2019-01')])
        report = self.record([fact(fact_id='idc-2023e-at-2021',
                                   as_of='2023E@2021-06', value=99.0)])
        self.assertEqual(report['accepted'], 1)

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


class ClaimIdentityTests(unittest.TestCase):
    """Two records are the same claim when metric, entity, date and caliber match.

    The rule was read off the existing fact layer, not invented for it: all 119
    records index without a single collision, and the pairs that look like
    duplicates - 4406 against 3736.6 元/㎡ for one project in one month, 5.00
    against 6.54 backlog years in one quarter - are separated by caliber, which
    is exactly what caliber is for.
    """

    def setUp(self):
        self.claims = {}

    def add(self, f):
        """What cmd_record does on acceptance."""
        self.claims[L2.claim_key(f)] = f['fact_id']
        key = L2.forecast_key(f)
        if key is not None:
            self.claims.setdefault(key, f['fact_id'])

    def test_the_same_claim_under_a_new_id_is_refused(self):
        self.add(fact())
        bad = problems(fact(fact_id='same-thing-again'), claims=self.claims)
        self.assertTrue(any('同口径同时点同 bound 已有一条' in p for p in bad), bad)

    def test_the_same_metric_and_date_in_another_caliber_is_a_different_claim(self):
        """4406 元/㎡ 施工总包 and 3736.6 土建本体 are both true of one month."""
        self.add(fact())
        shell = fact(fact_id='luan-ct-cost-shell-2022', value=3736.6,
                     caliber={'stage': '招标控制价', 'scope': '土建本体'})
        self.assertEqual(problems(shell, claims=self.claims), [])

    def test_a_range_is_two_records_one_upper_one_lower(self):
        """「1800-2100 万只」 is one expert call, and it needs both ends.

        Without bound in the key the second end is refused as a duplicate and
        the range collapses to whichever end happened to be recorded first.
        """
        low = fact(fact_id='hs-2026e-low', value=1800.0, bound='lower')
        self.assertEqual(problems(low, claims=self.claims), [])
        self.add(low)
        high = fact(fact_id='hs-2026e-high', value=2100.0, bound='upper')
        self.assertEqual(problems(high, claims=self.claims), [])

    def test_a_point_still_collides_with_a_point(self):
        """bound in the key must not open a hole for plain duplicates."""
        self.add(fact())
        bad = problems(fact(fact_id='same-thing-again'), claims=self.claims)
        self.assertTrue(any('同口径同时点同 bound 已有一条' in p for p in bad), bad)
        self.assertTrue(any('bound: upper 与 bound: lower' in p for p in bad), bad)

    def test_a_point_and_a_bound_at_one_key_are_not_the_same_record(self):
        """一个点估计和一个上界不是同一条：上界说的是「不超过」，点说的是「就是」。"""
        self.add(fact())
        ceiling = fact(fact_id='luan-ct-cost-ceiling', value=5000.0, bound='upper')
        self.assertEqual(problems(ceiling, claims=self.claims), [])

    def test_two_uppers_at_one_key_still_collide(self):
        upper = fact(fact_id='hs-2026e-high', value=2100.0, bound='upper')
        self.add(upper)
        bad = problems(fact(fact_id='hs-2026e-high-again', value=2200.0,
                            bound='upper'), claims=self.claims)
        self.assertTrue(any('同口径同时点同 bound 已有一条' in p for p in bad), bad)

    def test_both_ends_of_a_forecast_range_survive_the_vintage_check(self):
        """The forecast collision is keyed on bound too, or a bare 2026E range
        loses one end to 「同一年份的预测已有一条」."""
        low = fact(fact_id='dc-2026e-low', as_of='2026E', value=1800.0,
                   bound='lower')
        self.assertEqual(problems(low, claims=self.claims), [])
        self.add(low)
        high = fact(fact_id='dc-2026e-high', as_of='2026E', value=2100.0,
                    bound='upper')
        self.assertEqual(problems(high, claims=self.claims), [])

    def test_two_bare_forecasts_of_one_bound_still_collide(self):
        self.add(fact(fact_id='dc-2026e-low', as_of='2026E', value=1800.0,
                      bound='lower'))
        bad = problems(fact(fact_id='dc-2026e-low-again', as_of='2026E',
                            value=1750.0, bound='lower'), claims=self.claims)
        self.assertTrue(any('带上做出时点' in p for p in bad), bad)

    def test_a_different_entity_is_a_different_claim(self):
        self.add(fact())
        self.assertEqual(problems(other(), claims=self.claims), [])

    def test_two_forecasts_of_one_year_without_vintages_collide(self):
        """IDC's successive revisions: same metric, same year, one bare 2023E."""
        self.add(fact(fact_id='idc-2023e-first', as_of='2023E'))
        bad = problems(fact(fact_id='idc-2023e-second', as_of='2023E', value=99.0),
                       claims=self.claims)
        self.assertTrue(any('带上做出时点' in p for p in bad), bad)
        self.assertTrue(any('再预测不构成交叉验证' in p for p in bad), bad)

    def test_vintages_tell_the_two_revisions_apart(self):
        first = fact(fact_id='idc-2023e-at-2019', as_of='2023E@2019-01')
        self.assertEqual(problems(first, claims=self.claims), [])
        self.add(first)
        second = fact(fact_id='idc-2023e-at-2021', as_of='2023E@2021-06', value=99.0)
        self.assertEqual(problems(second, claims=self.claims), [])

    def test_one_forecast_on_its_own_needs_no_vintage(self):
        self.assertEqual(problems(fact(fact_id='lone-2026e', as_of='2026E'),
                                  claims=self.claims), [])

    def test_the_check_is_off_when_no_index_is_passed(self):
        """The old two-argument call still means what it meant."""
        self.assertEqual(problems(fact()), [])

    def test_the_existing_fact_layer_indexes_without_collision(self):
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        records = store['records']
        self.assertGreater(len(records), 100)
        claims = {}
        for f in records:
            key, forecast = L2.claim_key(f), L2.forecast_key(f)
            self.assertNotIn(key, claims, f['fact_id'])
            if forecast is not None and '@' not in f['as_of']:
                self.assertNotIn(forecast, claims, f['fact_id'])
            claims[key] = f['fact_id']
            if forecast is not None:
                claims.setdefault(forecast, f['fact_id'])


L1_ROW = {
    'sha256': 'd' * 64, 'rel': '报告/未命名表格.xlsx', 'suffix': '.xlsx',
    'status': 'ok', 'score': 9, 'score_status': 'scored', 'level': 'p',
    'category': 'M10', 'org': '未知', 'year': '未知', 'title': '机柜功率密度测算',
    'keep_original_name': False, 'size': 4096,
}


class EffectiveResultTests(unittest.TestCase):
    def test_failed_retry_does_not_remove_a_document_from_the_deep_read_queue(self):
        with tempfile.TemporaryDirectory(prefix='m4-l2-effective-') as directory:
            path = Path(directory) / 'results.jsonl'
            path.write_text('\n'.join(json.dumps(row) for row in [
                L1_ROW, {'sha256': L1_ROW['sha256'], 'status': 'error',
                         'error': 'model_timeout'}]) + '\n')
            with patch.object(L2.L1, 'RESULTS', path), \
                    patch.object(L2, 'read_documents', return_value=set()), \
                    patch.object(L2, 'load_metrics', return_value=METRICS), \
                    patch.object(L2, 'load_facts', return_value={'records': []}):
                self.assertEqual([row['sha256'] for row in L2.eligible()],
                                 [L1_ROW['sha256']])

    def test_successful_reassessment_still_replaces_the_previous_score(self):
        with tempfile.TemporaryDirectory(prefix='m4-l2-effective-') as directory:
            path = Path(directory) / 'results.jsonl'
            path.write_text('\n'.join(json.dumps(row) for row in [
                L1_ROW, {**L1_ROW, 'score': 7},
                {'sha256': L1_ROW['sha256'], 'status': 'error'}]) + '\n')
            with patch.object(L2.L1, 'RESULTS', path):
                self.assertEqual(L2.all_results()[L1_ROW['sha256']]['score'], 7)


class AttributionTests(unittest.TestCase):
    """A 9-point workbook whose publisher never reached the preview.

    L1 judges on the first 6000 characters, and a spreadsheet's first 6000
    characters are column headers.  So the files scored highest on their
    numbers are the ones most likely to carry 未知 as their publisher - and an
    unattributed number cannot honestly be graded as first-hand.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-attr-')
        self.results = Path(self.temp.name) / 'l1_results.jsonl'
        self.results.write_text(json.dumps(L1_ROW, ensure_ascii=False) + '\n',
                                encoding='utf-8')
        self._saved = L2.L1.RESULTS
        L2.L1.RESULTS = self.results

    def tearDown(self):
        L2.L1.RESULTS = self._saved
        self.temp.cleanup()

    def attribute(self, **over):
        args = {'sha': 'd' * 8, 'org': None, 'unrecoverable': False, 'year': None,
                'title': None, 'evidence': '封面右下角'}
        args.update(over)
        out = io.StringIO()
        with redirect_stdout(out):
            L2.cmd_attribute(type('A', (), args))
        return json.loads(out.getvalue())

    def rows(self):
        return [json.loads(l) for l in
                self.results.read_text(encoding='utf-8').splitlines()]

    def test_an_unknown_publisher_is_asked_for(self):
        self.assertEqual(L2.unattributed(L1_ROW), ['org', 'year'])

    def test_a_named_publisher_is_not_asked_for(self):
        self.assertEqual(L2.unattributed({**L1_ROW, 'org': 'IDC', 'year': '2024'}), [])

    def test_an_empty_string_counts_as_unknown(self):
        self.assertIn('org', L2.unattributed({**L1_ROW, 'org': '  '}))

    def test_the_publisher_lands_in_the_new_filename(self):
        report = self.attribute(org='IDC', year='2024')
        self.assertIn('IDC', report['now'])
        self.assertIn('2024', report['now'])
        self.assertNotIn('IDC', report['was'] or '')

    def test_the_old_verdict_is_superseded_not_erased(self):
        self.attribute(org='IDC', year='2024')
        rows = self.rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['org'], '未知')
        self.assertEqual(rows[1]['org'], 'IDC')
        self.assertEqual(rows[1]['attributed']['was']['org'], '未知')
        self.assertEqual(rows[1]['attributed']['evidence'], '封面右下角')

    def test_saying_there_is_nothing_to_find_stops_the_asking(self):
        """Both fields were unknown when it was declared, so both were searched."""
        self.attribute(unrecoverable=True, evidence='封面/页眉/版权页均无署名')
        row = self.rows()[-1]
        self.assertEqual(row['unrecoverable'], ['org', 'year'])
        self.assertEqual(L2.unattributed(row), [])

    def test_a_year_given_alongside_is_not_declared_missing(self):
        """忠县's shape: the publisher is on the cover, the year is nowhere."""
        self.attribute(unrecoverable=True, year='2024', evidence='无署名，年份取自封面')
        row = self.rows()[-1]
        self.assertEqual(row['unrecoverable'], ['org'])
        self.assertEqual(row['year'], '2024')

    def test_a_publisher_and_a_shrug_cannot_both_be_given(self):
        with self.assertRaises(SystemExit):
            self.attribute(org='IDC', unrecoverable=True)

    def test_one_of_the_two_must_be_given(self):
        with self.assertRaises(SystemExit):
            self.attribute()

    def test_a_year_that_is_not_a_year_is_refused(self):
        with self.assertRaises(SystemExit):
            self.attribute(org='IDC', year='2024年')

    def test_an_ambiguous_sha_prefix_is_refused(self):
        with self.assertRaises(SystemExit):
            self.attribute(sha='e' * 8, org='IDC')

    def test_nothing_is_renamed_here(self):
        report = self.attribute(org='IDC', year='2024')
        self.assertIn('restage', report['renamed_by'])

    def pack(self, row, meta=None):
        """Real inventoried bytes with a deterministic document extractor."""
        source = Path(self.temp.name) / 'source.txt'
        source.write_text('第一页正文\n\n[p.2] 第二页')
        row = {**row, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        saved = (L2.eligible, L2.full_text, L2.L1.readable_path,
                 L2.load_metrics, L2.load_questions, L2.load_facts, L2.PACKET_DIR)
        L2.eligible = lambda min_score=8, include_read=False, since=0: [row]
        L2.full_text = lambda path, suffix: ('第一页正文\n\n[p.2] 第二页',
                                            meta if meta is not None else {'pages': 2})
        L2.L1.readable_path = lambda r: (source, False)
        L2.load_metrics = lambda: METRICS
        L2.load_questions = lambda: {}
        L2.load_facts = lambda: {'records': []}
        L2.PACKET_DIR = Path(self.temp.name) / 'packets'
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                L2.cmd_pack(type('A', (), {'sha': None, 'min_score': 8,
                                           'again': False, 'since': 0}))
            report = json.loads(out.getvalue())
            brief = (L2.PACKET_DIR / row['sha256'][:16] / 'brief.md').read_text(encoding='utf-8')
        finally:
            (L2.eligible, L2.full_text, L2.L1.readable_path, L2.load_metrics,
             L2.load_questions, L2.load_facts, L2.PACKET_DIR) = saved
        return report, brief

    def test_the_packet_asks_for_the_publisher(self):
        """The section has to reach the brief, not merely exist in the module."""
        report, brief = self.pack(L1_ROW)
        self.assertEqual(report['unattributed'], ['org', 'year'])
        self.assertIn('这份文件的出处，L1 没认出来', brief)
        self.assertIn('attribute --sha ' + report['sha256'][:16], brief)

    def test_a_truncated_document_says_so_in_its_own_packet(self):
        """A reader who thinks they saw the whole sheet reports the last row as the last."""
        _, brief = self.pack(L1_ROW, meta={'truncated': True})
        self.assertIn('不是全文', brief)
        self.assertIn('不要把最后一行当作表格的最后一行', brief)

    def test_a_whole_document_carries_no_such_warning(self):
        _, brief = self.pack(L1_ROW, meta={'pages': 2})
        self.assertNotIn('不是全文', brief)

    def test_l2_asks_for_far_more_than_a_preview(self):
        """L1 judges from a preview; L2 records numbers and needs the document."""
        self.assertGreater(L2.FULL_TEXT_CHARS, 20 * office_grid.MAX_CHARS)

    def test_an_attributed_document_is_not_asked_again(self):
        report, brief = self.pack({**L1_ROW, 'org': 'IDC', 'year': '2024'})
        self.assertIsNone(report['unattributed'])
        self.assertNotIn('L1 没认出来', brief)
        self.assertIn('## 你要产出什么', brief)


class QueueOutputTests(unittest.TestCase):
    """The queue has to print the argument the next command takes.

    `pack` addresses a document by hash.  A queue listing only names sends you
    hunting for the hash of the row you just decided to read - and the name is
    truncated, so the hash inside it may not even be there.
    """

    grep = None

    def queue(self, rows, grep=None):
        self.grep = grep
        saved = (L2.eligible, L2.load_metrics, L2.load_facts,
                 L2.all_results, L2.read_documents)
        L2.eligible = lambda min_score=8, include_read=False, since=0: rows
        L2.load_metrics = lambda: METRICS
        L2.load_facts = lambda: {'records': []}
        L2.all_results = lambda: {r['sha256']: r for r in rows}
        L2.read_documents = lambda: set()
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                L2.cmd_queue(type('A', (), {'min_score': 8, 'show': 5,
                                            'grep': self.grep, 'since': 0}))
        finally:
            (L2.eligible, L2.load_metrics, L2.load_facts,
             L2.all_results, L2.read_documents) = saved
        return out.getvalue()

    def test_each_row_carries_the_hash_pack_needs(self):
        text = self.queue([L1_ROW])
        self.assertIn(L1_ROW['sha256'][:16], text.splitlines()[-1])

    def test_an_unattributed_document_is_marked_in_the_list(self):
        self.assertIn('出处未知', self.queue([L1_ROW]))
        self.assertNotIn('出处未知',
                         self.queue([{**L1_ROW, 'org': 'IDC', 'year': '2024'}]))

    def test_a_known_publisher_with_no_year_is_not_called_unattributed(self):
        """09p_未知_中国移动_忠县… has a publisher; only its year is missing."""
        row = {**L1_ROW, 'org': '中国移动', 'year': '未知'}
        text = self.queue([row])
        self.assertIn('年份未知', text)
        self.assertNotIn('出处未知', text)

    def test_grep_finds_one_document_in_a_long_queue(self):
        """The reading order is by coverage, so the row you want is anywhere."""
        rows = [{**L1_ROW, 'sha256': '%064x' % i,
                 'proposed_name': '09p_2022_某院_机房工程 %d.pdf' % i} for i in range(30)]
        rows.append({**L1_ROW, 'sha256': 'f' * 64,
                     'proposed_name': '09p_2022_某院_忠县通信机房 工艺对土建要求表.xlsx'})
        text = self.queue(rows, grep='忠县')
        self.assertIn('匹配「忠县」1 条（共 31 条待读）', text)
        self.assertIn('f' * 16, text)
        self.assertNotIn('机房工程 3.pdf', text)

    def test_grep_matches_the_original_path_too(self):
        row = {**L1_ROW, 'rel': '设计院图纸/忠县/要求表.xlsx', 'proposed_name': '09p_x.xlsx'}
        self.assertIn(row['sha256'][:16], self.queue([row], grep='忠县'))

    def test_without_grep_nothing_is_filtered_and_nothing_is_announced(self):
        text = self.queue([L1_ROW])
        self.assertNotIn('匹配', text)
        self.assertIn(L1_ROW['sha256'][:16], text)

    def test_the_header_counts_the_gap(self):
        report = json.loads(self.queue([L1_ROW]).splitlines()[0])
        self.assertEqual(report['unattributed'], 1)
        self.assertEqual(report['eligible_unread'], 1)


class EmptyBatchTests(unittest.TestCase):
    """Zero facts is legal.  An unwritten facts.json is not, and they printed alike.

    The first real run recorded `{"accepted": 0, "rejected": 0}` against a
    10-point workbook and marked it read for good.  The file on disk turned out
    to hold `[]` - which says nothing about whether anyone read the document.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-empty-')
        base = Path(self.temp.name)
        self.facts = base / 'facts.json'
        self.facts.write_text(json.dumps({'version': '0.1', 'records': []}),
                              encoding='utf-8')
        self._saved = (L2.FACTS, L2.READ_LOG, L2.load_metrics)
        L2.FACTS, L2.READ_LOG, L2.load_metrics = self.facts, base / 'read.jsonl', lambda: METRICS

    def tearDown(self):
        (L2.FACTS, L2.READ_LOG, L2.load_metrics) = self._saved
        self.temp.cleanup()

    def record(self, incoming, doc=None):
        path = Path(self.temp.name) / 'incoming.json'
        path.write_text(json.dumps(incoming, ensure_ascii=False), encoding='utf-8')
        out = io.StringIO()
        with redirect_stdout(out):
            L2.cmd_record(type('A', (), {'facts': str(path), 'doc': doc,
                                         'partial': False, 'show': 5}))
        return json.loads(out.getvalue().splitlines()[0])

    def test_an_empty_batch_says_so_and_says_how_to_reopen(self):
        report = self.record([], doc='e' * 64)
        self.assertEqual(report['incoming'], 0)
        self.assertIn('pack --again', report['note'])

    def test_a_batch_that_lands_carries_no_such_note(self):
        report = self.record([fact()])
        self.assertEqual(report['incoming'], 1)
        self.assertNotIn('note', report)

    def test_a_batch_that_is_wholly_rejected_is_not_called_empty(self):
        """Nothing landed either way, but the reasons are opposite."""
        report = self.record([fact(unit='wrong')])
        self.assertEqual(report['incoming'], 1)
        self.assertIn('全有或全无', report['note'])
        self.assertNotIn('pack --again', report['note'])


class PackAgainTests(unittest.TestCase):
    """A document marked read by accident could never be packed again."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-again-')
        self._saved = (L2.read_documents, L2.all_results, L2.load_facts, L2.load_metrics)
        L2.read_documents = lambda: {L1_ROW['sha256']}
        L2.all_results = lambda: {L1_ROW['sha256']: L1_ROW}
        L2.load_facts = lambda: {'records': []}
        L2.load_metrics = lambda: METRICS

    def tearDown(self):
        (L2.read_documents, L2.all_results, L2.load_facts, L2.load_metrics) = self._saved
        self.temp.cleanup()

    def test_a_read_document_is_out_of_the_queue(self):
        self.assertEqual(L2.eligible(8), [])

    def test_and_can_be_reopened_on_purpose(self):
        self.assertEqual([r['sha256'] for r in L2.eligible(8, include_read=True)],
                         [L1_ROW['sha256']])

    def test_reopening_requires_naming_the_document(self):
        """Without --sha it would reopen whatever sorts first, which is not the ask."""
        with self.assertRaises(SystemExit):
            L2.cmd_pack(type('A', (), {'sha': None, 'min_score': 8, 'again': True}))



class RestrictionTests(unittest.TestCase):
    """Score and admissibility are different questions.

    The first re-judged batch surfaced a quarterly whose cover reads
    "Confidential for Western Digital Corp. / Not to be distributed".  It
    scored 8, and 8 is right - it is a real first-hand source and the library
    should know it is there.  What it must not do is flow through L2 into
    facts that get quoted, which at 8 points it otherwise would, near the
    front of the queue.
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-flag-')
        self.results = Path(self.temp.name) / 'l1_results.jsonl'
        self.results.write_text(json.dumps(
            {**L1_ROW, 'org': 'Forward Insights', 'year': '2025'},
            ensure_ascii=False) + '\n', encoding='utf-8')
        self._saved = (L2.L1.RESULTS, L2.load_metrics, L2.load_facts, L2.read_documents)
        L2.L1.RESULTS = self.results
        L2.load_metrics = lambda: METRICS
        L2.load_facts = lambda: {'records': []}
        L2.read_documents = lambda: set()

    def tearDown(self):
        (L2.L1.RESULTS, L2.load_metrics, L2.load_facts, L2.read_documents) = self._saved
        self.temp.cleanup()

    def flag(self, **over):
        args = {'sha': L1_ROW['sha256'][:8], 'confidential': False, 'pii': False,
                'clear': False, 'evidence': '封面：Not to be distributed'}
        args.update(over)
        out = io.StringIO()
        with redirect_stdout(out):
            L2.cmd_flag(type('A', (), args))
        return json.loads(out.getvalue())

    def rows(self):
        return [json.loads(l) for l in
                self.results.read_text(encoding='utf-8').splitlines()]

    def test_an_unflagged_document_is_in_the_queue(self):
        self.assertEqual([r['sha256'] for r in L2.eligible(8)], [L1_ROW['sha256']])

    def test_flagging_it_takes_it_out(self):
        report = self.flag(confidential=True)
        self.assertEqual(report['now'], ['confidential'])
        self.assertEqual(L2.eligible(8), [])

    def test_the_score_and_the_file_are_untouched(self):
        self.flag(confidential=True)
        row = self.rows()[-1]
        self.assertEqual(row['score'], L1_ROW['score'])
        self.assertEqual(row['rel'], L1_ROW['rel'])
        self.assertIn('分数都不变', self.flag(pii=True)['effect'])

    def test_the_reason_travels_with_the_flag(self):
        self.flag(confidential=True)
        row = self.rows()[-1]
        self.assertEqual(row['flagged'][0]['evidence'], '封面：Not to be distributed')
        self.assertEqual(row['flagged'][0]['fields'], ['confidential'])

    def test_personal_information_is_the_other_gate(self):
        self.flag(pii=True)
        self.assertEqual(L2.eligible(8), [])

    def test_a_flag_can_be_lifted(self):
        self.flag(confidential=True)
        report = self.flag(confidential=True, clear=True, evidence='看错了，封面无此字样')
        self.assertEqual(report['now'], [])
        self.assertEqual(len(L2.eligible(8)), 1)

    def test_lifting_one_flag_leaves_the_other(self):
        self.flag(confidential=True)
        self.flag(pii=True)
        self.flag(confidential=True, clear=True, evidence='机密那条看错了')
        self.assertEqual(L2.eligible(8), [])

    def test_a_flag_with_no_field_named_is_refused(self):
        with self.assertRaises(SystemExit):
            self.flag()

    def test_the_queue_counts_what_it_excluded(self):
        self.flag(confidential=True)
        out = io.StringIO()
        with redirect_stdout(out):
            L2.cmd_queue(type('A', (), {'min_score': 8, 'show': 5, 'grep': None, 'since': 0}))
        self.assertEqual(json.loads(out.getvalue().splitlines()[0])['restricted_excluded'], 1)


class UnrecoverableScopeTests(unittest.TestCase):
    """Saying the publisher cannot be found must not silence the year ask.

    They are looked for in different places and found separately: 忠县's
    workbook names 中国移动 on its cover and no year anywhere.
    """

    def test_an_unrecoverable_publisher_still_leaves_the_year_asked(self):
        row = {**L1_ROW, 'org_unrecoverable': True}
        self.assertEqual(L2.unattributed(row), ['year'])

    def test_both_can_be_declared_unrecoverable(self):
        row = {**L1_ROW, 'unrecoverable': ['org', 'year']}
        self.assertEqual(L2.unattributed(row), [])

    def test_a_field_that_is_present_is_not_reported_either_way(self):
        row = {**L1_ROW, 'org': 'IDC', 'org_unrecoverable': True}
        self.assertEqual(L2.unattributed(row), ['year'])


class RecencyTests(unittest.TestCase):
    """A 2016 工程量清单 and a 2026 预测 at the same score are not equally useful.

    The first re-judged batch was one 2016 project forty files deep, and the
    reading order - module coverage, then score - had no idea.
    """

    def row(self, sha, year, score=9, module='M10', name=None):
        return {**L1_ROW, 'sha256': sha, 'score': score, 'category': module,
                'year': year, 'proposed_name': name or '%02d_%s_x.xlsx' % (score, year)}

    def order(self, rows, **kw):
        saved = (L2.all_results, L2.read_documents, L2.load_facts, L2.load_metrics)
        L2.all_results = lambda: {r['sha256']: r for r in rows}
        L2.read_documents = lambda: set()
        L2.load_facts = lambda: {'records': []}
        L2.load_metrics = lambda: METRICS
        try:
            return [r['sha256'] for r in L2.eligible(8, **kw)]
        finally:
            (L2.all_results, L2.read_documents, L2.load_facts, L2.load_metrics) = saved

    def test_the_newer_document_comes_first(self):
        old = self.row('1' + 'a' * 63, '2016')
        new = self.row('2' + 'a' * 63, '2026')
        self.assertEqual(self.order([old, new])[0], new['sha256'])

    def test_score_still_outranks_recency(self):
        """Recency breaks ties; it does not promote a weaker document."""
        strong_old = self.row('1' + 'a' * 63, '2016', score=10)
        weak_new = self.row('2' + 'a' * 63, '2026', score=8)
        self.assertEqual(self.order([strong_old, weak_new])[0], strong_old['sha256'])

    def test_a_document_with_no_year_sorts_with_the_oldest(self):
        """It cannot claim to be current; `attribute` is how it moves up."""
        undated = self.row('1' + 'a' * 63, '未知', name='09p_未知_x.xlsx')
        dated = self.row('2' + 'a' * 63, '2016')
        self.assertEqual(self.order([undated, dated])[0], dated['sha256'])

    def test_since_drops_everything_older(self):
        old = self.row('1' + 'a' * 63, '2016')
        new = self.row('2' + 'a' * 63, '2024')
        self.assertEqual(self.order([old, new], since=2020), [new['sha256']])

    def test_the_year_is_taken_from_the_name_when_the_field_is_blank(self):
        row = {**L1_ROW, 'year': '未知',
               'proposed_name': '09p_2023_IDC_Global DataSphere__abc.xlsx'}
        self.assertEqual(L2.document_year(row), 2023)

    def test_a_year_that_is_not_a_year_is_not_read_as_one(self):
        row = {**L1_ROW, 'year': '未知', 'proposed_name': 'x.xlsx', 'rel': 'a/b.xlsx'}
        self.assertEqual(L2.document_year(row), 0)

    def test_a_declared_year_beats_a_number_in_the_path(self):
        row = {**L1_ROW, 'year': '2025', 'rel': '2016工程/x.xlsx'}
        self.assertEqual(L2.document_year(row), 2025)


class ConfidentialScopeTests(unittest.TestCase):
    """A machine footer reading Confidential is boilerplate here, not a restriction.

    Most vendor decks in this corpus carry one.  Gating on the word would take
    most of the library out of the fact layer and buy nothing.  The flag is for
    an explicit restriction naming a recipient, and only a person sets it.
    """

    def test_nothing_is_flagged_automatically(self):
        self.assertEqual(L2.restricted(L1_ROW), [])

    def test_the_wording_says_what_the_flag_is_for(self):
        text = L2.RESTRICTIONS['confidential']
        self.assertIn('限定收件方', text)
        self.assertIn('不是泛用的机密页脚', text)


# The fact layer as it actually stands, not a fixture of it.  Every other test
# here builds its own metrics and its own facts; this one reads the two files
# the project ships, because a contract change that invalidates recorded data
# is a real event and nothing was watching for it.
#
# 119 facts were recorded before evidence.sha256 became required.  The contract
# is not relaxed for them - they simply owe it, and this number is the debt.
# Pay one back and this test goes red, which is the point: the debt must not
# change quietly in either direction.
PROVENANCE_DEBT = 38

# Facts cite a source_id, and most of those ids name no row in sources.json.
# check_fact cannot see this - it never reads sources.json - so it is pinned
# here instead, where it stays visible until someone decides what to do.
DANGLING_SOURCE_IDS = 27


class LiveFactLayerTests(unittest.TestCase):
    def setUp(self):
        self.repo = L2.REPO
        self.metrics = L2.load_metrics()
        self.records = L2.load_facts()['records']

    def test_every_recorded_fact_satisfies_the_current_menu(self):
        """Adding a caliber dimension to a metric invalidates facts that lack it."""
        seen, failures = set(), {}
        for fact in self.records:
            problems = [p for p in L2.check_fact(fact, self.metrics, seen)
                        if 'sha256' not in p]
            if problems:
                failures[fact['fact_id']] = problems
            seen.add(fact['fact_id'])
        self.assertEqual(failures, {})

    def test_the_hash_debt_is_exactly_what_is_owed(self):
        owing = [f['fact_id'] for f in self.records
                 if not re.fullmatch(r'[0-9a-f]{64}',
                                     str((f.get('evidence') or {}).get('sha256') or ''))]
        self.assertEqual(len(owing), PROVENANCE_DEBT,
                         '溯源债务变了。补回来了就把 PROVENANCE_DEBT 改小；'
                         '涨了说明有新事实绕过了 evidence.sha256')

    def test_no_new_fact_may_join_the_debt(self):
        """The contract itself never bends: a hashless fact is refused on record."""
        naked = fact(evidence={'locator': '第 3 页', 'grade': 'S2'})
        self.assertTrue(any('sha256' in p for p in problems(naked)))

    def test_the_dangling_source_references_are_pinned(self):
        doc = json.loads((self.repo / 'data/sources.json').read_text(encoding='utf-8'))
        rows = doc if isinstance(doc, list) else (doc.get('sources') or doc.get('records'))
        known = {s.get('source_id') for s in rows if isinstance(s, dict)}
        cited = {(f.get('evidence') or {}).get('source_id') for f in self.records} - {None}
        self.assertEqual(len(cited - known), DANGLING_SOURCE_IDS,
                         '悬空的 source_id 数量变了——补上了就把 DANGLING_SOURCE_IDS 改小')

    def test_the_menu_and_the_facts_agree_on_module(self):
        """A fact's module comes from its metric; an unknown metric has no module."""
        for fact_row in self.records:
            self.assertIn(fact_row['metric_id'], self.metrics, fact_row['fact_id'])


class MenuTests(unittest.TestCase):
    """What the packet shows a reader, and what it used to leave out."""

    def test_a_metrics_own_note_reaches_the_packet(self):
        """It carried the traps that span dimensions and was never printed."""
        text = L2.metric_menu('M10', METRICS)
        self.assertIn('照表头换算会错一百万倍', text)

    def test_the_dimensions_still_come_with_theirs(self):
        self.assertIn('caliber.scope', L2.metric_menu('M10', METRICS))

    def test_other_modules_are_indexed_by_id(self):
        """A document sits in one module; its numbers do not."""
        index = L2.other_modules_index('M04', METRICS)
        self.assertIn('dc_construction_cost_per_sqm', index)
        self.assertIn('noted_metric', index)
        self.assertNotIn('free_form_metric', index)   # that one is M04's own

    def test_the_index_does_not_spell_out_calibers(self):
        """139 metrics with full dimensions would bury the document itself."""
        index = L2.other_modules_index('M04', METRICS)
        self.assertNotIn('caliber.', index)
        self.assertNotIn('招标控制价', index)

    def test_a_module_with_no_metrics_says_so_rather_than_going_blank(self):
        self.assertIn('先在 metrics.json 里补指标定义', L2.metric_menu('M99', METRICS))


class LiveMenuTests(unittest.TestCase):
    """The real menu, on the two metrics whose confusion is already recorded."""

    def setUp(self):
        self.metrics = L2.load_metrics()

    def test_the_two_capex_metrics_point_at_each_other(self):
        """3,610 and 3,511 are the same four companies and must never be one series."""
        company = self.metrics['hyperscaler_capex_total']
        datacentre = self.metrics['dc_it_capex']
        self.assertIn('dc_it_capex', company['note'])
        self.assertIn('hyperscaler_capex_total', datacentre['note'])

    def test_the_unit_trap_is_stated_where_a_reader_will_meet_it(self):
        text = L2.metric_menu('M01', self.metrics)
        self.assertIn('错一百万倍', text)

    def test_the_original_segment_names_are_kept_verbatim(self):
        values = {d['id']: d['values'] for d in self.metrics['dc_it_capex']['caliber_dims']}
        self.assertIn('Top 4 US Cloud', values['segment'])
        self.assertIn('Asia Pacific excl. China', values['region'])
        self.assertIn('DCPI & Other DC', values['technology'])

    def test_the_aggregate_rows_are_marked_as_aggregates(self):
        segment = next(d for d in self.metrics['dc_it_capex']['caliber_dims']
                       if d['id'] == 'segment')
        self.assertIn('Hyperscalers', segment['values'])
        self.assertIn('不可与它的成分项一起加总', segment['note'])


class CorrectedNoteTests(unittest.TestCase):
    """Three口径 statements that were wrong, each caught by arithmetic.

    The first versions were written by copying: one from the workbook's own
    NOTES page, one from a spoken summary, one from assuming a column header
    meant what it said.  None had been checked against the numbers, and all
    three were wrong.  These tests pin the corrections so they cannot drift
    back to the plausible-sounding version.
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def test_the_shipment_column_must_be_divided_by_a_thousand(self):
        """Units (000's) holds unit counts, not thousands - the header lies twice."""
        note = self.metrics['server_unit_shipments']['note']
        self.assertIn('除以 1000', note)
        self.assertIn('6,022.49', note)             # the check that proved it
        self.assertNotIn('不需要换算', note)

    def test_hyperscalers_is_three_segments_not_five(self):
        segment = next(d for d in self.metrics['dc_it_capex']['caliber_dims']
                       if d['id'] == 'segment')
        self.assertIn('就这三项', segment['note'])
        self.assertIn('2,459.05', segment['note'])  # 1993.23 + 339.65 + 126.18
        self.assertNotIn('AI Model Builders + Rest of Cloud', segment['note'])

    def test_the_regions_add_up_and_the_note_says_so(self):
        """The workbook's NOTES claim a containment its own pivot contradicts."""
        for mid in ('dc_it_capex', 'server_mfg_revenue', 'server_unit_shipments',
                    'server_asp'):
            note = next(d for d in self.metrics[mid]['caliber_dims']
                        if d['id'] == 'region')['note']
            self.assertIn('六行互斥', note, mid)
            self.assertIn('以数据为准', note, mid)

    def test_storage_is_admitted_and_the_ampersand_is_the_row_label(self):
        for mid in ('server_mfg_revenue', 'server_unit_shipments', 'server_asp'):
            values = next(d for d in self.metrics[mid]['caliber_dims']
                          if d['id'] == 'server_class')['values']
            self.assertIn('Storage Systems', values, mid)
            self.assertIn('General-Purpose & Other', values, mid)
            self.assertNotIn('General-Purpose and Other', values, mid)

    def test_the_unverified_storage_splits_stay_out_of_the_enum(self):
        """Named in the workbook, hierarchy unchecked - so not invented into place."""
        dim = next(d for d in self.metrics['server_asp']['caliber_dims']
                   if d['id'] == 'server_class')
        self.assertNotIn('All Flash Arrays', dim['values'])
        self.assertIn('尚未校验', dim['note'])


class SkipTests(unittest.TestCase):
    """读了，菜单里没有位置——这条路以前是死的。

    pack 不带 --sha 永远返回队首那一份，所以一个记不下任何东西的读者除了
    「record --doc 空数组」没有别的出路，而那一招把文件记成已读、把发现丢掉。
    发现才是重点：它是菜单落后于语料的唯一信号，而且必须活着走到改菜单的
    那台机器上——所以缺口写进 repo，已读账本仍留在本机。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-skip-')
        base = Path(self.temp.name)
        self.results = base / 'l1_results.jsonl'
        self.results.write_text(json.dumps(
            {**L1_ROW, 'org': 'IDC', 'year': '2025'}, ensure_ascii=False) + '\n',
            encoding='utf-8')
        self._saved = (L2.L1.RESULTS, L2.GAPS, L2.READ_LOG, L2.load_metrics,
                       L2.load_facts)
        L2.L1.RESULTS = self.results
        L2.GAPS = base / 'metric_gaps.jsonl'
        L2.READ_LOG = base / 'l2_read.jsonl'
        L2.load_metrics = lambda: METRICS
        L2.load_facts = lambda: {'records': []}

    def tearDown(self):
        (L2.L1.RESULTS, L2.GAPS, L2.READ_LOG, L2.load_metrics,
         L2.load_facts) = self._saved
        self.temp.cleanup()

    def skip(self, gaps, doc=None, reason=None):
        out = io.StringIO()
        with redirect_stdout(out):
            L2.cmd_skip(type('A', (), {'doc': doc or L1_ROW['sha256'][:8],
                                       'gap': gaps, 'reason': reason}))
        return json.loads(out.getvalue())

    def gaps(self, filled=()):
        out = io.StringIO()
        with redirect_stdout(out):
            L2.cmd_gaps(type('A', (), {'filled': list(filled)}))
        return out.getvalue()

    def test_the_queue_advances(self):
        self.assertEqual([r['sha256'] for r in L2.eligible(8)], [L1_ROW['sha256']])
        self.skip(['server_class 缺 x86'])
        self.assertEqual(L2.eligible(8), [])

    def test_the_gap_is_what_survives(self):
        report = self.skip(['server_class 缺 x86'])
        self.assertEqual(report['gaps_recorded'], 1)
        rows = L2.open_gaps()
        self.assertEqual([r['gap'] for r in rows], ['server_class 缺 x86'])
        self.assertEqual(rows[0]['sha256'], L1_ROW['sha256'])
        self.assertEqual(rows[0]['rel'], L1_ROW['rel'])

    def test_one_document_can_report_several_gaps(self):
        self.skip(['server_class 缺 x86', '缺 storage_scope 维度',
                   '缺 counterparty_role 维度'])
        self.assertEqual(len(L2.open_gaps()), 3)
        self.assertEqual(len({r['sha256'] for r in L2.open_gaps()}), 1)

    def test_the_same_gap_twice_is_one_gap(self):
        """两次翻同一份文件报同一个缺口，不该在菜单待办上算两笔。"""
        self.skip(['server_class 缺 x86'])
        self.skip(['server_class 缺 x86'])
        self.assertEqual(len(L2.open_gaps()), 1)

    def test_the_same_gap_from_another_document_is_a_separate_row(self):
        """counterparty_role 在三个模块都撞上了——那正是要看见的东西。"""
        # L1_ROW is 'd' * 64, so this one must not start with d - the fourth
        # time a fixture sha prefix has collided in this suite.
        other = {**L1_ROW, 'sha256': 'b7' + 'c' * 62, 'rel': '别的/文件.xlsx'}
        with self.results.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(other, ensure_ascii=False) + '\n')
        self.skip(['缺 counterparty_role 维度'])
        self.skip(['缺 counterparty_role 维度'], doc='b7cccccc')
        self.assertEqual(len(L2.open_gaps()), 2)

    def test_the_read_ledger_says_it_was_a_skip_not_a_read(self):
        """零条事实和「读了但存不下」印出来一样，就等于没记。"""
        self.skip(['server_class 缺 x86'], reason='整表都是 x86 口径')
        row = json.loads(L2.READ_LOG.read_text(encoding='utf-8').splitlines()[-1])
        self.assertEqual(row['facts'], 0)
        self.assertEqual(row['skipped'], '整表都是 x86 口径')
        self.assertEqual(row['gaps'], [L2.open_gaps()[0]['gap_id']])

    def test_the_default_reason_is_the_menu(self):
        self.skip(['server_class 缺 x86'])
        row = json.loads(L2.READ_LOG.read_text(encoding='utf-8').splitlines()[-1])
        self.assertEqual(row['skipped'], '菜单没有位置')

    def test_the_way_back_is_in_the_output(self):
        """跳过不是丢弃：最终我们还是要都读的。"""
        report = self.skip(['server_class 缺 x86'])
        self.assertIn('pack --again --sha', report['note'])
        self.assertIn(L1_ROW['sha256'][:12], report['note'])

    def test_an_ambiguous_sha_is_refused(self):
        with self.results.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps({**L1_ROW, 'sha256': L1_ROW['sha256'][:8] + 'e' * 56},
                                ensure_ascii=False) + '\n')
        with self.assertRaises(SystemExit):
            self.skip(['随便'])

    def test_filling_a_gap_clears_it(self):
        gap_id = self.skip(['server_class 缺 x86'])['gap_ids'][0]
        self.gaps(filled=[gap_id])
        self.assertEqual(L2.open_gaps(), [])

    def test_filling_one_leaves_the_others(self):
        ids = self.skip(['缺 x86', '缺 storage_scope'])['gap_ids']
        self.gaps(filled=[ids[0]])
        self.assertEqual([r['gap'] for r in L2.open_gaps()], ['缺 storage_scope'])

    def test_filling_an_unknown_gap_is_refused(self):
        with self.assertRaises(SystemExit):
            self.gaps(filled=['000000000000'])

    def test_filling_the_same_gap_twice_is_refused(self):
        """第二次销账多半是记错了账，不该悄悄成功。"""
        gap_id = self.skip(['缺 x86'])['gap_ids'][0]
        self.gaps(filled=[gap_id])
        with self.assertRaises(SystemExit):
            self.gaps(filled=[gap_id])

    def test_the_listing_names_the_document_and_the_module(self):
        self.skip(['server_class 缺 x86'])
        listing = self.gaps()
        self.assertIn('server_class 缺 x86', listing)
        self.assertIn(L1_ROW['rel'], listing)
        self.assertIn('"open_gaps": 1', listing)

    def test_a_malformed_line_does_not_take_the_ledger_down(self):
        self.skip(['缺 x86'])
        with L2.GAPS.open('a', encoding='utf-8') as fh:
            fh.write('{ 半行\n')
        self.assertEqual(len(L2.open_gaps()), 1)


class FilledGapTests(unittest.TestCase):
    """M4 读表时撞到菜单没有位置的三处，补上之后钉住。

    每一处都是「两个数看着可比、其实不是一件事」，正是这份契约存在的理由。
    第四处（counterparty_role 供应方/需求方）没补——加一维会让该指标既有的
    每一条事实全部失效，而我还不知道它命中的是哪三个模块，猜着加不如不加。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def dim(self, mid, dim_id):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == dim_id)

    # -- x86 是另一套切法，不是第五类 -------------------------------------
    def test_x86_is_recordable(self):
        for mid in ('server_mfg_revenue', 'server_unit_shipments', 'server_asp'):
            self.assertIn('x86', self.dim(mid, 'server_class')['values'], mid)

    def test_both_halves_of_the_partition_exist(self):
        """只能记 x86 记不了非 x86，等于下一次还要 skip。"""
        for mid in ('server_mfg_revenue', 'server_unit_shipments', 'server_asp'):
            self.assertIn('非x86', self.dim(mid, 'server_class')['values'], mid)

    def test_the_note_says_the_two_taxonomies_do_not_add(self):
        for mid in ('server_mfg_revenue', 'server_unit_shipments', 'server_asp'):
            note = self.dim(mid, 'server_class')['note']
            self.assertIn('不能混着加总', note, mid)

    def test_the_four_dell_oro_classes_are_untouched(self):
        """补一套分类不该动掉原来那套。"""
        for mid in ('server_mfg_revenue', 'server_unit_shipments', 'server_asp'):
            values = self.dim(mid, 'server_class')['values']
            for v in ('Accelerated/High-End', 'General-Purpose & Other',
                      'All Servers', 'Storage Systems'):
                self.assertIn(v, values, (mid, v))

    # -- 同样叫「存储系统总额」的两个数差好几倍 ---------------------------
    def test_storage_scope_is_a_declared_dimension(self):
        for mid in ('server_mfg_revenue', 'server_asp'):
            self.assertEqual(self.dim(mid, 'storage_scope')['values'],
                             ['External OEM', 'Internal-ODM', 'Total',
                              '不适用（非存储口径）'], mid)

    def test_shipments_needs_no_storage_scope(self):
        """存储没有台数（原表 Units are not available），这一维在那儿无意义。"""
        with self.assertRaises(StopIteration):
            self.dim('server_unit_shipments', 'storage_scope')

    def test_the_note_refuses_to_hand_over_a_ratio_to_copy(self):
        """三条口径写错的教训：断言换算关系的 note 必须附算式，否则叫人自己算。"""
        note = self.dim('server_mfg_revenue', 'storage_scope')['note']
        self.assertIn('自己算', note)
        self.assertIn('不要抄这句', note)

    def test_every_existing_fact_of_those_metrics_carries_the_new_dim(self):
        """加一维就让既有事实全部失效——回填过才算补完。"""
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        rows = [f for f in store['records']
                if f['metric_id'] in ('server_mfg_revenue', 'server_asp')]
        self.assertTrue(rows)
        for f in rows:
            self.assertIn('storage_scope', f.get('caliber') or {}, f['fact_id'])

    def test_no_storage_row_was_backfilled_as_not_applicable(self):
        """存储行的口径要人判，机械回填成「不适用」就是造一条假事实。"""
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        for f in store['records']:
            cal = f.get('caliber') or {}
            if cal.get('server_class') == 'Storage Systems':
                self.assertNotEqual(cal.get('storage_scope'), '不适用（非存储口径）',
                                    f['fact_id'])

    # -- 仅机电设备 -------------------------------------------------------
    def test_mechanical_and_electrical_only_is_recordable(self):
        scope = self.dim('dc_investment_per_rack', 'scope')
        self.assertIn('仅机电设备', scope['values'])
        self.assertIn('不是「含机电主设备」的子集', scope['note'])

    def test_the_older_scope_values_survive(self):
        values = self.dim('dc_investment_per_rack', 'scope')['values']
        for v in ('土建本体', '施工总包', '含机电主设备', '含IT设备的项目总投资'):
            self.assertIn(v, values, v)


class M07MenuTests(unittest.TestCase):
    """M07 光通信：18 条缺口一次补齐后的钉子。

    这一批全是「同一个词指两件事」：BOM 成本与全成本、产品级与公司级毛利率、
    名义产能与有效产出、市场需求与厂商出货、「其他」客户与「未拆分」。
    每一条 note 挡的都是一次具体的读错。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def dim(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == did)

    def test_every_new_metric_exists_with_a_unit_and_a_module(self):
        for mid in ('optics_module_price', 'optics_module_unit_cost',
                    'optics_gross_margin', 'optics_module_power',
                    'optics_module_reach', 'aec_shipment', 'optics_market_size',
                    'optics_demand_share_by_customer',
                    'optics_supplier_share_at_customer', 'gpu_to_optics_ratio',
                    'optics_production_capacity', 'optics_capacity_utilization',
                    'optics_supply_gap', 'company_revenue', 'company_net_income',
                    'company_net_margin', 'earnings_vs_consensus_delta'):
            metric = self.metrics[mid]
            self.assertTrue(metric['unit'], mid)
            self.assertEqual(metric['module'], 'M07', mid)
            self.assertTrue(metric['caliber_dims'], mid)

    # -- 那个 0.7 会被读反 -------------------------------------------------
    def test_the_bom_note_carries_the_arithmetic_that_settles_the_direction(self):
        """表头写「70% = BOM Cost」，读反就把毛利率算高一截。"""
        note = self.dim('optics_module_unit_cost', 'cost_scope')['note']
        self.assertIn('493', note)
        self.assertIn('704', note)
        self.assertIn('小的那个是 BOM', note)

    # -- 同一份报告里的两个毛利率 ------------------------------------------
    def test_margin_level_separates_product_from_company(self):
        values = self.dim('optics_gross_margin', 'margin_level')['values']
        self.assertEqual(values, ['产品级', '公司级'])

    def test_a_company_margin_is_not_a_product_margin(self):
        self.assertIn('44.8%', self.dim('optics_gross_margin', 'margin_level')['note'])

    # -- 名义产能不是能出的货 ----------------------------------------------
    def test_capacity_basis_carries_its_arithmetic(self):
        note = self.dim('optics_production_capacity', 'capacity_basis')['note']
        self.assertIn('1500 × 0.8 = 1200', note)

    # -- 缺口的符号不靠正负号 ----------------------------------------------
    def test_the_gap_sign_lives_in_a_dimension_not_in_the_value(self):
        gap = self.dim('optics_supply_gap', 'gap_side')
        self.assertEqual(gap['values'], ['供不应求', '供过于求'])
        self.assertIn('value 一律取正数', gap['note'])

    def test_the_gap_depends_on_which_demand_case(self):
        self.assertIn('demand_case', [d['id'] for d in
                                      self.metrics['optics_supply_gap']['caliber_dims']])

    # -- 未拆分 ≠ 其他 -----------------------------------------------------
    def test_unsplit_is_not_the_same_as_other(self):
        for mid in ('optics_module_shipment', 'aec_shipment',
                    'optics_demand_share_by_customer'):
            values = self.dim(mid, 'customer')['values']
            self.assertIn('其他', values, mid)
            self.assertIn('未拆分', values, mid)

    def test_the_note_says_why_they_differ(self):
        self.assertIn('「未拆分」不是「其他」',
                      self.dim('optics_module_shipment', 'customer')['note'])

    # -- 市场需求 ≠ 未披露 -------------------------------------------------
    def test_market_demand_is_its_own_shipment_basis(self):
        d = self.dim('optics_module_shipment', 'shipment_basis')
        self.assertIn('市场需求', d['values'])
        self.assertIn('未披露', d['values'])

    def test_the_note_flags_the_rows_recorded_before_the_value_existed(self):
        """约十条需求数记在「未披露」下，要拿原表逐条改判，不能按 fact_id 批量改。"""
        note = self.dim('optics_module_shipment', 'shipment_basis')['note']
        self.assertIn('逐条改判', note)
        self.assertIn('不要在没有原文的情况下', note)

    # -- 合并档不是两档之和 ------------------------------------------------
    def test_the_merged_speed_bucket_cannot_be_split_or_summed(self):
        for mid in ('optics_module_shipment', 'aec_shipment',
                    'optics_module_price', 'optics_module_power'):
            d = self.dim(mid, 'speed')
            self.assertIn('400G/800G 合并档', d['values'], mid)
            self.assertIn('合计', d['values'], mid)
            self.assertIn('不能拆开', d['note'], mid)

    # -- 配比是系数不是常数 ------------------------------------------------
    def test_the_ratio_metric_says_the_architecture_moves_it(self):
        note = self.dim('gpu_to_optics_ratio', 'architecture')['note']
        self.assertIn('1:4 变 1:8', note)
        self.assertIn('不能外推', note)

    def test_the_ratio_note_refuses_the_single_market_wide_multiplier(self):
        note = self.metrics['gpu_to_optics_ratio']['note']
        self.assertIn('得到的都不是市场需求', note)

    # -- 币种没写就不许替原文断定 ------------------------------------------
    def test_an_unstated_currency_stays_unstated(self):
        for mid in ('company_revenue', 'company_net_income'):
            d = self.dim(mid, 'currency')
            self.assertIn('未注明', d['values'], mid)
            self.assertIn('不要替原文断定', d['note'], mid)

    # -- AEC 不进光模块出货曲线 --------------------------------------------
    def test_aec_is_a_separate_metric_not_a_product_form(self):
        self.assertNotIn('AEC', self.dim('optics_module_shipment', 'product_form')['values'])
        self.assertIn('替代读成增长', self.metrics['aec_shipment']['note'])

    # -- 距离既是分组也是被测量 --------------------------------------------
    def test_reach_is_both_a_grouping_and_a_measurement(self):
        self.assertIn('reach', [d['id'] for d in
                                self.metrics['optics_module_price']['caliber_dims']])
        self.assertEqual(self.metrics['optics_module_reach']['unit'], 'm')

    # -- 加了维就要回填 ----------------------------------------------------
    def test_every_shipment_fact_carries_both_new_dimensions(self):
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        rows = [f for f in store['records']
                if f['metric_id'] == 'optics_module_shipment']
        self.assertGreater(len(rows), 30)
        # 区间的上界是后来另一台机器补的，与它自己的下界共用一个口径——
        # 两端共用口径是 bound 这个字段的定义，不是巧合。
        for f in rows:
            self.assertIn(f['caliber'].get('product_form'), ('光模块', '光引擎', '未注明'),
                          f['fact_id'])
            self.assertIsNotNone(f['caliber'].get('customer'), f['fact_id'])
            # 回填值是「光模块 / 未拆分」。填别的必须在 notes 里说清为什么——
            # 天孚那八条是光引擎（配图图例写的是 Optical Engines），
            # 分客户那批是真的按客户切过的，两者都不是默认值。
            if f['caliber']['product_form'] != '光模块':
                self.assertIn('光引擎', f['notes'], f['fact_id'])
            if f['caliber']['customer'] != '未拆分':
                # 按客户切过的数必须锚在那个客户自己的单元格上——locator 里
                # 应当出现这个客户名（原文列名）。否则就是把总量挂到了某一家头上。
                self.assertIn(f['caliber']['customer'], f['evidence']['locator'],
                              f['fact_id'])


class M02MenuTests(unittest.TestCase):
    """M02 云与运营商：15 条缺口。

    这一批的主题是**方向与层级**——谁买谁卖、哪一层加总、按什么排名。
    读错方向会把买方读成卖方，读错层级会把同一笔钱算两遍。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def dim(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == did)

    def test_every_new_metric_exists(self):
        for mid in ('it_infra_spend', 'storage_capacity_shipped',
                    'vendor_market_share', 'dc_service_revenue',
                    'dc_service_revenue_share', 'top10_revenue_share',
                    'dc_market_growth', 'operator_rack_capacity',
                    'large_dc_count', 'operator_headcount',
                    'operator_asset_balance', 'operator_credential_count'):
            self.assertEqual(self.metrics[mid]['module'], 'M02', mid)
            self.assertTrue(self.metrics[mid]['unit'], mid)

    # -- 方向反了 ---------------------------------------------------------
    def test_counterparty_role_stops_a_buyer_being_read_as_a_seller(self):
        d = self.dim('server_unit_shipments', 'counterparty_role')
        self.assertEqual(d['values'], ['供应方', '需求方', '全市场（未分侧）'])
        self.assertIn('方向正好反了', d['note'])

    def test_the_market_total_is_neither_side_and_says_so(self):
        """既有 8 条的 entity 是 global-server-market，不是哪一家。"""
        note = self.dim('server_unit_shipments', 'counterparty_role')['note']
        self.assertIn('不要把它当成「未注明」', note)

    #: 迁移当时库里仅有的 8 条 server_unit_shipments，全部出自 Dell'Oro 那本工作簿。
    #: 这一串写死是故意的：这条测试钉的是「迁移没有把既有事实改错方向」，
    #: 不是「这个指标永远只有 8 条」——语料继续读下去必然会有新的。
    MIGRATED_SHIPMENT_FACTS = (
        'delloro-jul26-srvunits-all-servers-2026e',
        'delloro-jul26-srvunits-all-servers-2030e',
        'delloro-jul26-srvunits-accelerated-high-end-2026e',
        'delloro-jul26-srvunits-accelerated-high-end-2030e',
        'delloro-jul26-srvunits-general-purpose-and-other-2026e',
        'delloro-jul26-srvunits-general-purpose-and-other-2030e',
        'delloro-jul26-srvunits-storage-systems-2026e',
        'delloro-jul26-srvunits-storage-systems-2030e',
    )

    def test_the_existing_shipment_facts_were_backfilled_as_market_totals(self):
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        rows = {f['fact_id']: f for f in store['records']
                if f['metric_id'] == 'server_unit_shipments'}
        for fid in self.MIGRATED_SHIPMENT_FACTS:
            self.assertIn(fid, rows)
            self.assertEqual(rows[fid]['caliber']['counterparty_role'], '全市场（未分侧）', fid)
            self.assertIn('market', rows[fid]['entity']['id'], fid)

    def test_later_shipment_facts_state_which_side_they_are(self):
        """新读进来的可以是供应方或需求方，但三个取值之外的一律不收。"""
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        allowed = {'供应方', '需求方', '全市场（未分侧）'}
        for f in store['records']:
            if f['metric_id'] != 'server_unit_shipments':
                continue
            self.assertIn(f['caliber'].get('counterparty_role'), allowed, f['fact_id'])

    def test_unsplit_is_not_the_same_as_not_applicable(self):
        d = self.dim('server_unit_shipments', 'buyer_category')
        self.assertIn('未拆分', d['values'])
        self.assertIn('不适用（非需求侧口径）', d['values'])
        self.assertIn('两者不同', d['note'])

    # -- 同一笔钱算两遍 ---------------------------------------------------
    def test_the_overlap_is_a_recordable_row_not_a_footnote(self):
        d = self.dim('it_infra_spend', 'product_scope')
        self.assertIn('服务器内含存储（重叠额）', d['values'])
        self.assertIn('服务器 + 存储 − 重叠额 = 服务器与存储合计', d['note'])

    def test_demand_side_spend_is_not_the_supply_side_revenue_metric(self):
        self.assertIn('不是同一个指标', self.metrics['it_infra_spend']['note'])

    # -- 父子层级不可一起加总 ---------------------------------------------
    def test_the_carrier_hierarchy_note_carries_its_arithmetic(self):
        note = self.dim('dc_service_revenue', 'operator_type')['note']
        self.assertIn('23.8 + 16.7 + 13.8 = 54.3', note)
        self.assertIn('加总只能取一层', note)

    def test_the_two_shares_at_one_level_add_to_a_hundred(self):
        note = self.dim('dc_service_revenue_share', 'operator_type')['note']
        self.assertIn('54.3% + 第三方 45.7% = 100.0', note)

    # -- 按什么排名决定了是哪十家 -----------------------------------------
    def test_top10_says_the_ranking_basis_changes_the_membership(self):
        d = self.dim('top10_revenue_share', 'ranking_basis')
        self.assertEqual(d['values'], ['按机架规模', '按收入', '按容量'])
        self.assertIn('决定了这十家是哪十家', d['note'])

    def test_top10_revenue_is_not_top10_pipeline(self):
        note = self.metrics['top10_revenue_share']['note']
        self.assertIn('top10_pipeline_share', note)
        self.assertIn('不是同一个指标', note)

    # -- 实测与趋势判断 ---------------------------------------------------
    def test_a_trend_statement_is_not_a_measurement(self):
        for mid in ('dc_market_growth', 'it_infra_spend'):
            d = self.dim(mid, 'basis')
            self.assertIn('趋势判断', d['values'], mid)
        self.assertIn('造出一个不存在的加速', self.metrics['dc_market_growth']['note'])

    # -- 广东不含深圳 -----------------------------------------------------
    def test_guangdong_excluding_shenzhen_is_its_own_value(self):
        d = self.dim('server_unit_shipments', 'subregion')
        self.assertIn('广东（不含深圳）', d['values'])
        self.assertIn('深圳', d['values'])
        self.assertIn('不要自己合并成「广东」', d['note'])

    # -- 「至少几路」是区间 -----------------------------------------------
    def test_socket_values_are_ranges_that_contain_each_other(self):
        d = self.dim('server_unit_shipments', 'socket_capability')
        self.assertIn('是区间不是点', d['note'])
        self.assertIn('不能相加', d['note'])

    # -- 台数份额 ≠ 金额份额 ----------------------------------------------
    def test_share_by_units_and_by_value_are_different_numbers(self):
        d = self.dim('vendor_market_share', 'measure')
        self.assertIn('4.7 个百分点', d['note'])

    # -- 两个门槛互相包含 -------------------------------------------------
    def test_the_two_size_thresholds_cannot_be_added(self):
        d = self.dim('large_dc_count', 'size_threshold')
        self.assertIn('被超 1000 的那批包含', d['note'])

    # -- 在建工程未转固 ---------------------------------------------------
    def test_construction_in_progress_is_not_yet_fixed_assets(self):
        d = self.dim('operator_asset_balance', 'asset_item')
        self.assertIn('转固之前不在固定资产里', d['note'])

    # -- PB 不是 EB -------------------------------------------------------
    def test_the_capacity_metric_warns_about_the_other_unit(self):
        note = self.metrics['storage_capacity_shipped']['note']
        self.assertIn('1 EB = 1000 PB', note)
        self.assertIn('换算完也不是同一件事', note)


class M05M09MenuTests(unittest.TestCase):
    """M05 选址与工程门槛、M09 设备与场地：9 条缺口。

    这一批的主题是**单位与门槛方向**。一堆数挤在一个指标下、单位各不相同，
    是最容易造出「同一条序列」假象的地方；而「不小于 8000m」与「不大于 1Ω」
    写成同一个正数，方向丢了就读反了。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def dim(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == did)

    def test_every_new_metric_exists(self):
        for mid, module in (('site_hazard_setback', 'M05'),
                            ('backup_autonomy', 'M05'),
                            ('room_dimension', 'M05'),
                            ('room_environment_limit', 'M05'),
                            ('installed_equipment_capacity', 'M05'),
                            ('grounding_resistance', 'M05'),
                            ('video_retention_period', 'M05'),
                            ('equipment_unit_price', 'M09'),
                            ('site_logistics_spec', 'M09')):
            self.assertEqual(self.metrics[mid]['module'], module, mid)

    # -- 门槛方向不靠正负号 ------------------------------------------------
    def test_every_threshold_metric_declares_its_direction(self):
        for mid in ('site_hazard_setback', 'backup_autonomy', 'room_dimension',
                    'grounding_resistance', 'video_retention_period',
                    'site_logistics_spec'):
            self.assertIn('bound_sense', [d['id'] for d in
                                          self.metrics[mid]['caliber_dims']], mid)

    def test_setback_says_value_is_always_positive(self):
        self.assertIn('value 一律取正数',
                      self.dim('site_hazard_setback', 'bound_sense')['note'])

    # -- 等级差五倍 --------------------------------------------------------
    def test_a_setback_without_a_tier_is_meaningless(self):
        note = self.metrics['site_hazard_setback']['note']
        self.assertIn('8000m', note)
        self.assertIn('不带 tier 的距离门槛没有意义', note)

    def test_the_two_tier_systems_do_not_convert(self):
        for mid in ('site_hazard_setback', 'room_floor_load', 'room_clear_height'):
            self.assertIn('不可互相换算', self.dim(mid, 'tier')['note'], mid)

    # -- 四种后备撑的不是同一段时间 ----------------------------------------
    def test_backup_types_must_not_be_summed(self):
        note = self.dim('backup_autonomy', 'backup_type')['note']
        self.assertIn('绝不可相加', note)
        self.assertIn('串在不同的故障链上', note)

    def test_the_backup_unit_is_minutes_with_the_conversion_spelled_out(self):
        self.assertIn('12 小时 = 720 分钟', self.metrics['backup_autonomy']['note'])

    def test_the_fuel_coefficient_is_not_a_value_of_this_metric(self):
        self.assertIn('0.22 公斤', self.metrics['backup_autonomy']['note'])
        self.assertIn('换算系数不是本指标的值', self.metrics['backup_autonomy']['note'])

    # -- 同一个尺寸因用途不同差一倍 ----------------------------------------
    def test_purpose_separates_two_correct_numbers(self):
        note = self.dim('room_dimension', 'purpose')['note']
        self.assertIn('500mm', note)
        self.assertIn('250mm', note)
        self.assertIn('两个都对的数看着是矛盾的', note)

    # -- 允许值不是推荐值 --------------------------------------------------
    def test_allowed_is_not_recommended(self):
        note = self.dim('room_environment_limit', 'limit_type')['note']
        self.assertIn('允许值是不越界就行，推荐值是应当落在其中', note)

    # -- 铭牌容量写着，IT 负荷没写 -----------------------------------------
    def test_installed_capacity_refuses_to_infer_the_it_load(self):
        note = self.metrics['installed_equipment_capacity']['note']
        self.assertIn('铭牌容量是原文写着的，IT 负荷不是', note)
        self.assertIn('把写着的记下来，把推不出的留白', note)

    def test_redundancy_unstated_stays_unstated(self):
        note = self.dim('installed_equipment_capacity', 'capacity_basis')['note']
        self.assertIn('不要替原文断定', note)
        self.assertIn('75%', note)

    def test_kw_and_kva_are_declared_not_assumed(self):
        d = self.dim('installed_equipment_capacity', 'unit_kind')
        self.assertEqual(d['values'], ['kW', 'kVA'])
        self.assertIn('不可互换', d['note'])

    # -- 单价跨计量单位不可比 ----------------------------------------------
    def test_unit_price_is_grouped_by_its_unit_of_measure(self):
        d = self.dim('equipment_unit_price', 'uom')
        self.assertIn('跨 uom 不可比', d['note'])

    def test_the_spec_must_reach_the_notes(self):
        note = self.metrics['equipment_unit_price']['note']
        self.assertIn('规格进 spec 维，同时写进 notes', note)
        self.assertIn('1800kW 与 400kW 差一个数量级', note)

    def test_all_in_price_is_not_the_bare_equipment_price(self):
        self.assertIn('三成以上',
                      self.dim('equipment_unit_price', 'price_scope')['note'])

    # -- 一个指标装多种单位时靠维度分组 ------------------------------------
    def test_mixed_unit_metrics_forbid_cross_item_comparison(self):
        for mid, did in (('site_logistics_spec', 'spec_item'),
                         ('room_environment_limit', 'parameter')):
            self.assertIn('不要跨', self.dim(mid, did)['note'], mid)

    # -- 国标与企标 --------------------------------------------------------
    def test_the_code_minimum_is_split_into_national_and_carrier(self):
        d = self.dim('room_floor_load', 'basis')
        self.assertIn('规范最低（国标）', d['values'])
        self.assertIn('规范最低（运营商企标）', d['values'])
        self.assertIn('规范最低', d['values'])      # 旧值保留给既有事实

    def test_the_existing_engineering_facts_were_backfilled(self):
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        rows = [f for f in store['records']
                if f['metric_id'] in ('room_floor_load', 'room_clear_height')]
        self.assertTrue(rows)
        self.assertTrue(any(f.get('bound') == 'upper' for f in rows),
                        '上界那条应当也在，且同样带着这两维')
        for f in rows:
            self.assertEqual(f['caliber']['tier'], '未注明', f['fact_id'])
            self.assertEqual(f['caliber']['build_type'], '未注明', f['fact_id'])

    # -- 纯机电清单的分项对不上现有切法 ------------------------------------
    def test_the_mechanical_only_denominator_and_its_escape_hatch(self):
        self.assertIn('机电设备清单合计',
                      self.dim('cost_share_by_trade', 'denominator')['values'])
        self.assertIn('其他机电分项', self.dim('cost_share_by_trade', 'trade')['values'])
        self.assertIn('不要硬塞进最像的那个 trade',
                      self.dim('cost_share_by_trade', 'denominator')['note'])


class TextFingerprintTests(unittest.TestCase):
    """同一份报告的两个副本，字节不同、sha256 不同，正文一字不差。

    M4 撞到的：两份中国信通院第三方运营商报告，41 页、23,935 字、正文 md5
    完全一致，sha256 不同，于是排进阅读队列两次。sha256 认的是字节，
    读者认的是内容——去重要在内容那一层做。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-fp-')
        base = Path(self.temp.name)
        self._saved = (L2.TEXT_MD5, L2.read_documents)
        L2.TEXT_MD5 = base / 'l2_text_md5.jsonl'
        L2.read_documents = lambda: set(self.read)
        self.read = set()

    def tearDown(self):
        (L2.TEXT_MD5, L2.read_documents) = self._saved
        self.temp.cleanup()

    def fp(self, text, pages=41):
        return L2.text_fingerprint(text, {'pages': pages})

    BODY = '中国第三方数据中心运营商分析报告。' * 40      # 逾 500 字

    def test_a_re_export_with_different_bytes_has_the_same_fingerprint(self):
        """换行被重排、空白被压掉，读者看到的还是同一篇。"""
        other = self.BODY.replace('。', '。\n   ')
        self.assertEqual(self.fp(self.BODY), self.fp(other))

    def test_a_different_document_has_a_different_fingerprint(self):
        self.assertNotEqual(self.fp(self.BODY), self.fp(self.BODY + '另起一段。'))

    def test_a_shared_front_matter_with_a_different_page_count_is_not_a_twin(self):
        """同一套模板的季度报告可以共用很长的开头，那不是同一份。"""
        self.assertNotEqual(self.fp(self.BODY, pages=41),
                            self.fp(self.BODY, pages=52))

    def test_too_little_text_gets_no_fingerprint(self):
        """十几个字的扫描件封面会撞上语料里的每一份扫描件。"""
        self.assertIsNone(self.fp('目录'))
        self.assertIsNone(self.fp('封面' * 100))          # 仍不足 500 字
        self.assertIsNotNone(self.fp('封面' * 300))

    # -- 台账 -------------------------------------------------------------
    def test_a_twin_is_only_a_twin_once_the_other_one_was_read(self):
        """还没读过的副本不算——两份都在队列里时，先读到哪份都行。"""
        L2.remember_fingerprint('a' * 64, 'deadbeef')
        self.assertEqual(L2.already_read_with_same_text('b' * 64, 'deadbeef'), [])
        self.read.add('a' * 64)
        self.assertEqual(L2.already_read_with_same_text('b' * 64, 'deadbeef'),
                         ['a' * 64])

    def test_a_document_is_never_its_own_twin(self):
        L2.remember_fingerprint('a' * 64, 'deadbeef')
        self.read.add('a' * 64)
        self.assertEqual(L2.already_read_with_same_text('a' * 64, 'deadbeef'), [])

    def test_no_fingerprint_means_no_twin_check(self):
        L2.remember_fingerprint('a' * 64, 'deadbeef')
        self.read.add('a' * 64)
        self.assertEqual(L2.already_read_with_same_text('b' * 64, None), [])

    def test_a_malformed_line_does_not_take_the_ledger_down(self):
        L2.remember_fingerprint('a' * 64, 'deadbeef')
        with L2.TEXT_MD5.open('a', encoding='utf-8') as fh:
            fh.write('{ 半行\n')
        self.assertEqual(L2.fingerprints(), {'a' * 64: 'deadbeef'})

    # -- 开包了但还没读的副本 ---------------------------------------------
    def test_a_packed_but_unread_copy_is_reported(self):
        """第三对副本就是这么漏的：两份同一轮开包，都还没读，什么都没响。"""
        L2.remember_fingerprint('a' * 64, 'deadbeef')
        self.assertEqual(
            L2.packed_not_read_with_same_text('b' * 64, 'deadbeef'), ['a' * 64])

    def test_a_read_copy_is_not_reported_here(self):
        """已读的那条路由 already_read_with_same_text 管，两边不重复报。"""
        L2.remember_fingerprint('a' * 64, 'deadbeef')
        self.read.add('a' * 64)
        self.assertEqual(
            L2.packed_not_read_with_same_text('b' * 64, 'deadbeef'), [])

    def test_a_document_is_never_its_own_open_twin(self):
        L2.remember_fingerprint('a' * 64, 'deadbeef')
        self.assertEqual(
            L2.packed_not_read_with_same_text('a' * 64, 'deadbeef'), [])

    def test_no_fingerprint_means_no_open_twin_check(self):
        L2.remember_fingerprint('a' * 64, 'deadbeef')
        self.assertEqual(L2.packed_not_read_with_same_text('b' * 64, None), [])

    def test_the_last_write_wins(self):
        """重抽一遍得到不同的正文（抽取器修好了），以新的为准。"""
        L2.remember_fingerprint('a' * 64, 'old')
        L2.remember_fingerprint('a' * 64, 'new')
        self.assertEqual(L2.fingerprints()['a' * 64], 'new')


class BackfillProvenanceTests(unittest.TestCase):
    """119 条事实没有内容哈希——但那不等于出处丢了。

    其中 81 条在 evidence.source_id 里写着一个十二位十六进制串，那就是
    sha256[:12]：身份一直在，只是缩写到了 join 不上的程度。展开它要 L1 账本，
    而账本在读文件的那台机器上，不在仓库里——所以这是一条命令，不是一次编辑。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-prov-')
        base = Path(self.temp.name)
        self.ledger = base / 'l1.jsonl'
        self.facts = base / 'facts.json'
        self._saved = (L2.L1.RESULTS, L2.FACTS, L2.REPO)
        L2.L1.RESULTS = self.ledger
        L2.FACTS = self.facts
        L2.REPO = base                      # 没有 sources.json，走前缀这条路

    def tearDown(self):
        (L2.L1.RESULTS, L2.FACTS, L2.REPO) = self._saved
        self.temp.cleanup()

    def write(self, evidences, ledger_shas):
        self.facts.write_text(json.dumps({'records': [
            {'fact_id': 'f%d' % n, 'metric_id': 'm', 'evidence': e}
            for n, e in enumerate(evidences)]}, ensure_ascii=False), encoding='utf-8')
        self.ledger.write_text('\n'.join(
            json.dumps({'sha256': s, 'rel': 'x/%s' % s[:8], 'suffix': '.pdf',
                        'status': 'ok'}) for s in ledger_shas) + '\n',
            encoding='utf-8')

    def run_it(self, commit=False):
        out = io.StringIO()
        with redirect_stdout(out):
            L2.cmd_backfill_provenance(type('A', (), {'commit': commit, 'show': 5}))
        lines = out.getvalue().splitlines()
        # 第一行可能是「读不到清单」的提示，报告是带 owing_before 的那一行
        report = next(json.loads(l) for l in lines
                      if l.startswith('{') and 'owing_before' in l)
        return report, out.getvalue()

    def stored(self):
        return json.loads(self.facts.read_text(encoding='utf-8'))['records']

    SHA = 'a1b2c3d4e5f6' + '0' * 52

    def test_a_prefix_becomes_the_full_hash(self):
        self.write([{'source_id': self.SHA[:12], 'locator': 'p.1'}], [self.SHA])
        report, _ = self.run_it(commit=True)
        self.assertEqual(report['按前缀补全'], 1)
        self.assertEqual(self.stored()[0]['evidence']['sha256'], self.SHA)

    def test_a_dry_run_writes_nothing(self):
        """本项目的规矩：每一步真改之前先干跑一遍。"""
        self.write([{'source_id': self.SHA[:12]}], [self.SHA])
        report, text = self.run_it(commit=False)
        self.assertEqual(report['按前缀补全'], 1)
        self.assertIn('干跑', text)
        self.assertNotIn('sha256', self.stored()[0]['evidence'])

    def test_an_ambiguous_prefix_is_refused_not_guessed(self):
        """十二位十六进制撞车极不可能——但「不太可能」不是往事实层写错哈希的理由。"""
        twin = self.SHA[:12] + 'f' * 52
        self.write([{'source_id': self.SHA[:12]}], [self.SHA, twin])
        report, text = self.run_it(commit=True)
        self.assertEqual(report['前缀撞车（未动）'], 1)
        self.assertEqual(report['按前缀补全'], 0)
        self.assertIn('撞车', text)
        self.assertNotIn('sha256', self.stored()[0]['evidence'])

    def test_a_prefix_the_ledger_does_not_know_is_reported_as_such(self):
        """十二位十六进制既进不了账本前缀、也还原不成缓存键时，如实说这两条路都断了。"""
        self.write([{'source_id': 'ffffffffffff'}], [self.SHA])
        report, text = self.run_it(commit=True)
        self.assertEqual(report['查不到（未动）'], 1)
        self.assertIn('也不是能还原的 reader 缓存键', text)
        self.assertNotIn('sha256', self.stored()[0]['evidence'])

    def test_a_named_source_is_not_mistaken_for_a_prefix(self):
        self.write([{'source_id': 'chinatelecom-luan-cost-2022'}], [self.SHA])
        report, _ = self.run_it(commit=True)
        self.assertEqual(report['按前缀补全'], 0)
        self.assertEqual(report['查不到（未动）'], 1)

    def test_a_fact_that_already_has_a_hash_is_left_alone(self):
        self.write([{'sha256': 'b' * 64, 'source_id': self.SHA[:12]}], [self.SHA])
        report, _ = self.run_it(commit=True)
        self.assertEqual(report['owing_before'], 0)
        self.assertEqual(self.stored()[0]['evidence']['sha256'], 'b' * 64)

    def test_the_report_says_what_the_debt_will_be_afterwards(self):
        """跑完要改 PROVENANCE_DEBT，命令自己把新数字算出来。"""
        self.write([{'source_id': self.SHA[:12]}, {'source_id': 'ffffffffffff'}],
                   [self.SHA])
        report, text = self.run_it(commit=True)
        self.assertEqual(report['owing_after'], 1)
        self.assertIn('PROVENANCE_DEBT 改成 1', text)

    def test_uppercase_is_not_a_hex_prefix(self):
        """sha256 一律小写；大写串是别的东西，不要当成前缀去 join。"""
        self.write([{'source_id': self.SHA[:12].upper()}], [self.SHA])
        report, _ = self.run_it(commit=True)
        self.assertEqual(report['按前缀补全'], 0)

    def test_the_live_debt_is_what_no_route_could_reach(self):
        """真实语料：81 条已按缓存键还清，剩下的 38 条没有一条还写着十二位十六进制。

        原先这条测试断言「119 条里 81 条写着 sha256 前缀」。前半句对，后半句
        不对——那 81 个十二位十六进制串一个都不是 sha256 前缀，它们是 reader
        的缓存键（docs/inbox/path_migrations/cache_key_remap_20260818.json 里
        一查便知），得先换成路径、再去 moves.jsonl 里换成内容哈希。按前缀 join
        的那条路在真实语料上命中率是 0。

        还清之后剩下的 38 条是真的没有出处线索：35 条 source_id 为空，3 条写的
        是人给的名字（chinatelecom-luan-cost-2022 之类），两者都不指向任何文件。
        """
        (L2.L1.RESULTS, L2.FACTS, L2.REPO) = self._saved
        store = L2.load_facts()
        owing = L2.owing_provenance(store['records'])
        self.assertEqual(len(owing), PROVENANCE_DEBT)
        abbreviated = [f for f in owing
                       if L2.HEX12.match(str((f['evidence'] or {}).get('source_id') or ''))]
        self.assertEqual(abbreviated, [], '还有能按缓存键还的债没还')

    def test_cache_keys_are_not_sha256_prefixes(self):
        """这条钉住上面那句话里最容易被想当然的部分。"""
        (L2.L1.RESULTS, L2.FACTS, L2.REPO) = self._saved
        remap = json.loads(L2.CACHE_REMAP.read_text(encoding='utf-8'))
        ledger = L2.all_results()
        prefixes = {sha[:12] for sha in ledger}
        collide = [k for k in remap if k in prefixes]
        self.assertEqual(collide, [],
                         '缓存键与 sha256 前缀撞上了，按前缀 join 会写错哈希')


class RangeCaliberTests(unittest.TestCase):
    """区间的两端共用一个口径——这是 bound 这个字段的定义。

    两台机器并行改动时撞出来的：M4 按 #150 的新写法补了四条区间上界，
    而我同时给那几个指标加了维度。合并后上界缺维，下界不缺。
    补齐时不是猜，是照它自己那一端抄——两端如果口径不同，它们本来就不是
    同一个区间的两端。
    """

    def setUp(self):
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        self.records = store['records']
        self.by_id = {f['fact_id']: f for f in self.records}

    def test_the_corpus_actually_holds_ranges_now(self):
        """1800-2100 万只——当初逼出 bound 那条改动的就是它。"""
        bounded = [f for f in self.records if f.get('bound')]
        self.assertGreater(len(bounded), 4)

    def test_both_ends_of_every_range_share_one_caliber(self):
        pairs = 0
        for fact in self.records:
            if fact.get('bound') != 'upper':
                continue
            twin = self.by_id.get(fact['fact_id'][:-6])
            if twin is None:            # 上界不一定按这个命名法配对
                continue
            pairs += 1
            self.assertEqual(fact['caliber'], twin['caliber'], fact['fact_id'])
            self.assertEqual(fact['metric_id'], twin['metric_id'], fact['fact_id'])
            self.assertEqual(str(fact['as_of']), str(twin['as_of']), fact['fact_id'])
        self.assertGreater(pairs, 3)

    def test_an_upper_is_never_below_its_lower(self):
        for fact in self.records:
            if fact.get('bound') != 'upper' or fact.get('value') is None:
                continue
            twin = self.by_id.get(fact['fact_id'][:-6])
            if twin is None or twin.get('value') is None:
                continue
            self.assertGreaterEqual(fact['value'], twin['value'], fact['fact_id'])

    def test_every_range_end_validates_against_the_current_menu(self):
        metrics = L2.load_metrics()
        for fact in self.records:
            if not fact.get('bound'):
                continue
            problems = [p for p in L2.check_fact(fact, metrics, set(), None)
                        if 'sha256' not in p]
            self.assertEqual(problems, [], fact['fact_id'])


class M03M04MenuTests(unittest.TestCase):
    """M03 资本开支、M04 电力：17 条缺口。

    这一批的主题是**同一份报告里两个都对、方向相反的数**——
    美国近一半的电力增长来自数据中心，全球口径下不到 10%；
    2030 年用电 945 与 1260 出自同一页的两个情景。
    单独引用任何一个都能得出一个立场。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def dim(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == did)

    def test_every_new_metric_exists(self):
        for mid, module in (('capex_growth_rate', 'M03'),
                            ('forecast_revision_delta', 'M03'),
                            ('capex_share_by_segment', 'M03'),
                            ('installed_server_base', 'M03'),
                            ('dc_electricity_consumption', 'M04'),
                            ('dc_demand_source_mix', 'M04'),
                            ('dc_demand_source_share', 'M04'),
                            ('dc_share_of_load_growth', 'M04'),
                            ('gas_turbine_demand_annual', 'M04'),
                            ('gas_turbine_units', 'M04'),
                            ('dc_capacity_additions_annual', 'M04'),
                            ('vendor_order_target', 'M04'),
                            ('corporate_ppa_capacity', 'M04'),
                            ('ppa_coverage_share', 'M04')):
            self.assertEqual(self.metrics[mid]['module'], module, mid)
            self.assertTrue(self.metrics[mid]['unit'], mid)

    # -- 四个情景不是四家打架 ----------------------------------------------
    def test_scenario_is_not_basis(self):
        d = self.dim('dc_electricity_consumption', 'scenario')
        for v in ('Base Case', 'Lift-Off', 'High Efficiency', 'Headwinds'):
            self.assertIn(v, d['values'], v)
        self.assertIn('945', d['note'])
        self.assertIn('1260', d['note'])
        self.assertIn('出自同一页', d['note'])

    def test_a_single_scenario_is_not_the_base_case(self):
        note = self.dim('dc_electricity_consumption', 'scenario')['note']
        self.assertIn('单一情景', self.dim('dc_electricity_consumption',
                                           'scenario')['values'])
        self.assertIn('不要拿它当 Base Case', note)

    def test_foreign_scenario_names_are_reported_not_mapped(self):
        self.assertIn('不要硬映射',
                      self.dim('dc_electricity_consumption', 'scenario')['note'])

    # -- TWh 不是 GW -------------------------------------------------------
    def test_energy_is_not_power(self):
        note = self.metrics['dc_electricity_consumption']['note']
        self.assertIn('TWh 不是 GW', note)
        self.assertIn('global_dc_it_load', note)
        self.assertIn('绝不可互换或直接换算', note)

    # -- 两个都对、方向相反 ------------------------------------------------
    def test_the_pair_that_must_be_stored_together(self):
        note = self.metrics['dc_share_of_load_growth']['note']
        self.assertIn('成对存储', note)
        self.assertIn('只录其中一条等于挑了一个立场', note)

    def test_it_is_distinguished_from_the_geographic_concentration_metric(self):
        self.assertIn('load_growth_concentration',
                      self.metrics['dc_share_of_load_growth']['note'])

    # -- 存量地理分布不需要新指标 ------------------------------------------
    def test_stock_concentration_reuses_the_existing_dimension(self):
        """查过菜单才动手：basis_type 已经能区分存量与增量。"""
        d = self.dim('load_growth_concentration', 'scope')
        self.assertIn('前五集群', d['values'])
        self.assertIn('不需要另立指标', d['note'])
        self.assertIn('存量占比',
                      self.dim('load_growth_concentration', 'basis_type')['values'])

    # -- 产能没有需求就证不出结论 ------------------------------------------
    def test_demand_exists_because_the_conclusion_needs_both_sides(self):
        note = self.metrics['gas_turbine_demand_annual']['note']
        self.assertIn('96GW', note)
        self.assertIn('64GW', note)
        self.assertIn('在库里就是不可复现的', note)

    # -- 台数看得出单机在变大 ----------------------------------------------
    def test_unit_counts_reveal_what_capacity_alone_hides(self):
        note = self.metrics['gas_turbine_units']['note']
        self.assertIn('240-267MW', note)
        self.assertIn('看不出单机在变大还是变多', note)

    # -- 三种订单口径 ------------------------------------------------------
    def test_order_basis_separates_three_numbers_from_one_page(self):
        d = self.dim('gas_turbine_dc_order_share', 'order_basis')
        # 后来又从另一份报告里冒出第四种口径「总承诺量」，见 M09MenuTests
        self.assertEqual(d['values'], ['新增订单', '在手订单', '总承诺量', '前瞻指引'])
        self.assertIn('看着是同一个指标在打架', d['note'])

    def test_an_unstated_measure_stays_unstated(self):
        d = self.dim('gas_turbine_dc_order_share', 'measure')
        self.assertIn('未注明', d['values'])
        self.assertIn('改写成一条假的「知道」', d['note'])

    def test_the_four_order_share_facts_were_backfilled_from_their_own_notes(self):
        """回填依据在每条事实自己的 notes 里，不是按 fact_id 猜的。"""
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        rows = {f['fact_id']: f for f in store['records']
                if f['metric_id'] == 'gas_turbine_dc_order_share'}
        # 迁移当时的四条，回填依据写在各自 notes 里；之后新读的条目不在此列——
        # GEV 那两条正是为了「在手订单」与「前瞻指引」两个新取值才录进来的。
        migrated = ('gas-turbine-dc-order-share-2024', 'siemens-dc-order-share-fy2025',
                    'big3-dc-order-share-2026-low', 'big3-dc-order-share-2026-high')
        for fid in migrated:
            self.assertIn(fid, rows)
            self.assertEqual(rows[fid]['caliber']['order_basis'], '新增订单', fid)
        # 分母写着 58GW，是容量口径
        self.assertEqual(rows['gas-turbine-dc-order-share-2024']['caliber']['measure'],
                         '按容量')
        # 原文明说计量口径未说明，库内已标 [未核]
        self.assertEqual(rows['siemens-dc-order-share-fy2025']['caliber']['measure'],
                         '未注明')

    # -- 上修 67% 与下修 67% -----------------------------------------------
    def test_revision_direction_keeps_the_value_positive(self):
        d = self.dim('forecast_revision_delta', 'revision_direction')
        self.assertIn('value 一律取正数', d['note'])

    def test_revision_is_not_the_consensus_delta(self):
        note = self.metrics['forecast_revision_delta']['note']
        self.assertIn('capex_vs_consensus_delta', note)
        self.assertIn('前者说的是分歧，后者说的是改口', note)

    # -- 存量不是流量 ------------------------------------------------------
    def test_installed_base_is_not_shipments(self):
        note = self.metrics['installed_server_base']['note']
        self.assertIn('server_unit_shipments', note)
        self.assertIn('存量不是流量', note)

    def test_the_tier_thresholds_are_themselves_facts(self):
        note = self.dim('installed_server_base', 'provider_tier')['note']
        self.assertIn('这些门槛本身也是事实', note)

    # -- 「超过一半」是下界 ------------------------------------------------
    def test_more_than_half_is_a_lower_bound(self):
        note = self.metrics['capex_share_by_segment']['note']
        self.assertIn('下界不是点估计', note)
        self.assertIn('不要自己取中值', note)

    # -- CAGR 要带窗口 -----------------------------------------------------
    def test_a_cagr_without_its_window_is_unusable(self):
        note = self.dim('capex_growth_rate', 'period_basis')['note']
        self.assertIn('必须在 notes 里写明起止年', note)

    def test_growth_rates_do_not_add_up(self):
        self.assertIn('两个分部各增 30% 不等于合计增 30%',
                      self.metrics['capex_growth_rate']['note'])

    # -- PPA 三个相邻指标 --------------------------------------------------
    def test_ppa_capacity_is_none_of_the_three_neighbours(self):
        note = self.metrics['corporate_ppa_capacity']['note']
        self.assertIn('green_direct_capacity', note)
        self.assertIn('contracted_power_capacity', note)
        self.assertIn('三者测的是三件事', note)

    def test_built_and_under_construction_do_not_add(self):
        self.assertIn('不可相加',
                      self.dim('corporate_ppa_capacity', 'status')['note'])

    def test_coverage_is_a_paper_figure(self):
        self.assertIn('不等于「实际覆盖」',
                      self.metrics['ppa_coverage_share']['note'])


class M09MenuTests(unittest.TestCase):
    """M09 供电架构与设备端：14 条缺口。

    这一批的主题是**相对值**——+382%、3.4x、157% 裕度、2.0 倍订单收入比。
    相对值离开基准和条件就是一个没有意义的数字，而它偏偏最容易被摘出来引用。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def dim(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == did)

    def test_every_new_metric_exists(self):
        for mid in ('power_architecture_spec', 'conductor_capacity_index',
                    'rack_load_swing', 'storage_response_window',
                    'generation_ratio', 'electrical_material_intensity',
                    'circuit_current_margin', 'major_equipment_count',
                    'tech_milestone_year', 'book_to_bill',
                    'vendor_order_backlog', 'vendor_capacity_investment'):
            self.assertEqual(self.metrics[mid]['module'], 'M09', mid)
            self.assertTrue(self.metrics[mid]['unit'], mid)

    # -- 相对值必须声明基准 ------------------------------------------------
    def test_every_relative_metric_declares_its_baseline(self):
        for mid, did in (('conductor_capacity_index', 'baseline'),
                         ('generation_ratio', 'baseline_generation')):
            self.assertIn('相对值必须声明基准', self.dim(mid, did)['note'], mid)

    def test_the_conductor_index_is_conditional_not_physical(self):
        note = self.dim('conductor_capacity_index', 'condition')['note']
        self.assertIn('不是物理常数', note)
        self.assertIn('48A', note)

    def test_two_multiples_must_not_be_divided(self):
        """性能 50x ÷ TDP 1.75x ≠ 能效 28.6x——两个倍数的基准配置不同。"""
        note = self.metrics['generation_ratio']['note']
        self.assertIn('不能相除', note)
        self.assertIn('compute_efficiency', note)

    # -- 25% 是推出来的，算式在 note 里 ------------------------------------
    def test_the_rms_penalty_carries_its_derivation(self):
        note = self.metrics['rack_load_swing']['note']
        self.assertIn('(1.5² + 0.5²) / 2 = 1.25', note)
        self.assertIn('derived: true', note)

    def test_the_rms_arithmetic_actually_holds(self):
        """note 里写的算式，这里真算一遍——上一轮三条口径写错就是没算过。"""
        mean, peak = 1.0, 1.5
        trough = 2 * mean - peak
        self.assertAlmostEqual((peak ** 2 + trough ** 2) / 2, 1.25)

    def test_the_swing_parameters_share_a_unit_but_not_a_meaning(self):
        note = self.dim('rack_load_swing', 'parameter')['note']
        self.assertIn('绝不可放进同一条序列', note)

    # -- 两种裕度算法差 100 个百分点 ---------------------------------------
    def test_the_margin_definition_changes_the_number(self):
        note = self.dim('circuit_current_margin', 'margin_definition')['note']
        self.assertIn('370', note)
        self.assertIn('144', note)
        self.assertIn('257%', note)
        self.assertIn('157%', note)

    def test_the_margin_arithmetic_holds(self):
        self.assertAlmostEqual(370 / 144 * 100, 256.9, places=1)
        self.assertAlmostEqual((370 - 144) / 144 * 100, 156.9, places=1)

    # -- 架构宣称不是出货事实 ----------------------------------------------
    def test_an_architecture_claim_is_not_a_shipped_fact(self):
        self.assertIn('架构上限', self.dim('rack_density_shipping', 'stat')['values'])
        self.assertIn('架构宣称',
                      self.dim('rack_density_shipping', 'power_basis')['values'])
        self.assertIn('一句宣传语就变成了',
                      self.dim('rack_density_shipping', 'stat')['note'])

    def test_the_shared_basis_dimension_carries_the_same_warning(self):
        self.assertIn('架构宣称', self.dim('power_architecture_spec', 'basis')['values'])

    # -- 订单口径 ----------------------------------------------------------
    def test_total_commitment_is_a_fourth_order_basis(self):
        d = self.dim('gas_turbine_dc_order_share', 'order_basis')
        self.assertIn('总承诺量', d['values'])
        self.assertIn('24 ÷ 87 = 27.6%', d['note'])

    def test_book_to_bill_has_two_rulers(self):
        note = self.dim('book_to_bill', 'ratio_basis')['note']
        self.assertIn('3.3', note)
        self.assertIn('是两把尺子', note)

    def test_greater_than_signs_become_bounds(self):
        self.assertIn('用 bound: lower 记', self.metrics['book_to_bill']['note'])

    def test_backlog_is_not_the_cloud_contract_metric(self):
        note = self.metrics['vendor_order_backlog']['note']
        self.assertIn('mega_contract_backlog', note)
        self.assertIn('三个数不换算、不相加', note)

    # -- 币种混排 ----------------------------------------------------------
    def test_mixed_currencies_are_declared(self):
        for mid in ('vendor_order_backlog', 'vendor_capacity_investment'):
            d = self.dim(mid, 'currency')
            for v in ('美元', '欧元', '韩元', '未注明'):
                self.assertIn(v, d['values'], (mid, v))

    def test_investment_and_output_do_not_add(self):
        note = self.dim('vendor_capacity_investment', 'amount_type')['note']
        self.assertIn('更不能相加', note)

    def test_the_korean_split_adds_up_and_says_so(self):
        note = self.dim('vendor_capacity_investment', 'growth_source')['note']
        self.assertIn('7000 + 1000 = 8000', note)

    # -- 台数要配冗余 ------------------------------------------------------
    def test_equipment_count_needs_redundancy_to_be_readable(self):
        d = self.dim('major_equipment_count', 'redundancy')
        self.assertIn('未注明', d['values'])
        self.assertIn('不要替它断定', d['note'])

    def test_at_least_ten_is_a_lower_bound(self):
        self.assertIn('bound: lower', self.metrics['major_equipment_count']['note'])

    # -- 同一个里程碑两个年份都对 ------------------------------------------
    def test_two_dates_for_one_milestone_are_not_a_contradiction(self):
        note = self.dim('tech_milestone_year', 'view_holder')['note']
        self.assertIn('可以都对', note)
        self.assertIn('看着是矛盾的', note)

    def test_the_milestone_metric_cites_its_precedent(self):
        self.assertIn('ethernet_ib_crossover_year',
                      self.metrics['tech_milestone_year']['note'])

    # -- 项目合计不是强度 --------------------------------------------------
    def test_a_project_total_is_not_an_intensity(self):
        note = self.dim('electrical_material_intensity', 'denominator')['note']
        self.assertIn('项目合计不是强度', note)
        self.assertIn('2712m', note)

    # -- 毫秒统一 ----------------------------------------------------------
    def test_the_storage_window_is_milliseconds_with_the_conversion(self):
        self.assertIn('10 s = 10000 ms', self.metrics['storage_response_window']['note'])


class M11MenuTests(unittest.TestCase):
    """M11 投资与项目经济：21 条缺口，M4 记下的最后一批。

    这一批里有三条卡在枚举值上——**region 必填却没有「未披露」**，
    于是一条没写地域的数只能靠猜。那不是某个指标的毛病，是全库 194 处的毛病。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def dim(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == did)

    def test_every_new_metric_exists(self):
        for mid in ('investor_survey_share', 'investor_composition_share',
                    'dc_build_cost_per_mw', 'it_power_density_per_area',
                    'project_tco', 'project_irr', 'contract_prepayment_share',
                    'unit_cost_premium', 'compute_cost_generational_delta',
                    'storage_network_surcharge', 'network_design_saving',
                    'compute_demand_by_workload_share', 'ops_quality_loss',
                    'scheduler_preference_share', 'dc_securitization_issuance',
                    'retail_power_price_change', 'gpu_hourly_tco'):
            self.assertEqual(self.metrics[mid]['module'], 'M11', mid)
            self.assertTrue(self.metrics[mid]['unit'], mid)

    # -- 全库 194 处的系统性缺口 -------------------------------------------
    def test_every_region_dimension_can_say_it_was_never_stated(self):
        missing = [(mid, 'region') for mid, v in self.metrics.items()
                   for d in v.get('caliber_dims', [])
                   if d['id'] == 'region' and '未披露' not in d['values']]
        self.assertEqual(missing, [])

    def test_the_region_note_says_it_is_not_a_shortcut(self):
        note = self.dim('dc_build_cost_per_mw', 'region')['note']
        self.assertIn('不是偷懒的出口', note)
        self.assertIn('带着一个我们编的属性进了库', note)

    def test_unstated_region_is_never_silent(self):
        """迁移当时没有一条既有事实被改成「未披露」；之后用它的必须说明理由。

        原先这条断言全库一条都不能有，那是迁移当天的快照。但这个取值本来就是
        为「原文真的没写地域」准备的——高盛那份的空置率 3% 与 48 百万美元/MW
        正是它的第一批用户。所以规则改成：可以用，但必须在 notes 里写明原文
        为什么没有地域，不能默默填进去。
        """
        store = json.loads((L2.REPO /
                            'data/facts.json').read_text(encoding='utf-8'))
        for f in store['records']:
            if (f.get('caliber') or {}).get('region') != '未披露':
                continue
            self.assertIn('未披露', f.get('notes') or '', f['fact_id'])

    # -- 另两处枚举 --------------------------------------------------------
    def test_a_third_party_back_calculation_is_not_a_design_value(self):
        d = self.dim('dc_pue', 'basis')
        self.assertIn('第三方推算', d['values'])
        self.assertIn('2.2GW', d['note'])

    def test_the_pue_note_owns_up_to_the_arithmetic_not_matching(self):
        """2.2 ÷ 1.8 = 1.222，而原文写「约 1.25」——差在哪没交代，就说没交代。"""
        note = self.dim('dc_pue', 'basis')['note']
        self.assertIn('1.222', note)
        self.assertIn('不要替原文改数，也不要假装两者一致', note)
        self.assertAlmostEqual(2.2 / 1.8, 1.2222, places=4)

    def test_a_model_input_is_not_a_market_price(self):
        d = self.dim('gpu_hourly_rate_spot', 'price_type')
        self.assertIn('模型隐含价', d['values'])
        self.assertIn('一句没发生过的事实', d['note'])

    # -- 调查数据的裁决 ----------------------------------------------------
    def test_survey_metrics_are_marked_three_ways(self):
        """名字带「调查」、basis 有「调查结果」、还有 respondent_scope 维。"""
        for mid in ('investor_survey_share', 'scheduler_preference_share'):
            self.assertIn('调查结果', self.dim(mid, 'basis')['values'], mid)
            self.assertIn('respondent_scope',
                          [d['id'] for d in self.metrics[mid]['caliber_dims']], mid)

    def test_the_ruling_is_stated_in_the_note(self):
        note = self.metrics['investor_survey_share']['note']
        self.assertIn('测的是「有多少人这么说」', note)
        self.assertIn('没有样本量的百分比不能与任何别的调查比', note)

    def test_rounding_is_recorded_as_found_not_forced_to_a_hundred(self):
        self.assertIn('28 + 53 + 18 = 99',
                      self.metrics['investor_survey_share']['note'])

    def test_non_exclusive_options_may_exceed_a_hundred(self):
        note = self.dim('scheduler_preference_share', 'requirement')['note']
        self.assertIn('加总可以超过 100%', note)

    # -- 算式 --------------------------------------------------------------
    def test_the_build_cost_carries_its_arithmetic(self):
        note = self.metrics['dc_build_cost_per_mw']['note']
        self.assertIn('12,000 ÷ 250 = **48 百万美元/MW**', note)
        self.assertEqual(12000 / 250, 48.0)

    def test_the_density_says_we_computed_it_not_the_source(self):
        note = self.metrics['it_power_density_per_area']['note']
        self.assertIn('90,000 ÷ 44,593', note)
        self.assertIn('原文没有直接给这个数', note)
        self.assertAlmostEqual(90000 / 44593, 2.018, places=3)

    def test_the_imperial_conversion_is_given(self):
        self.assertIn('92.9 W/ft²', self.metrics['it_power_density_per_area']['note'])

    # -- TCO 不是 capex ----------------------------------------------------
    def test_tco_and_capex_are_separated_by_a_dimension(self):
        d = self.dim('project_tco', 'amount_scope')
        self.assertIn('TCO（全周期）', d['values'])
        self.assertIn('资本开支', d['values'])
        self.assertIn('最常见的错误', d['note'])

    # -- 成本不是价格 ------------------------------------------------------
    def test_cost_per_gpu_hour_is_not_the_rental_rate(self):
        note = self.metrics['gpu_hourly_tco']['note']
        self.assertIn('2.38', note)
        self.assertIn('2.8', note)
        self.assertIn('差额是租方的毛利', note)

    # -- 无穷大不是一个数 --------------------------------------------------
    def test_an_infinite_irr_is_recorded_as_prose_not_a_number(self):
        note = self.metrics['contract_prepayment_share']['note']
        self.assertIn('「无穷大」不是一个数', note)
        self.assertIn('value 留白', note)

    def test_a_negative_npv_is_not_forced_into_an_irr(self):
        self.assertIn('不要硬折成一个 IRR 数字', self.metrics['project_irr']['note'])

    # -- 同一条链上的两个点 ------------------------------------------------
    def test_sixteen_and_sixtyone_are_one_chain_not_two_numbers(self):
        note = self.dim('unit_cost_premium', 'cost_driver')['note']
        self.assertIn('同一条链上的两个点', note)
        self.assertIn('加总只能取一层', note)

    def test_two_stages_of_one_design_do_not_add(self):
        note = self.metrics['network_design_saving']['note']
        self.assertIn('24.9% 与 31.6% 是同一方案的两档优化', note)

    def test_the_saving_base_is_declared(self):
        self.assertIn('不是集群总成本',
                      self.dim('network_design_saving', 'cost_base')['note'])

    # -- 含义相反的百分比 --------------------------------------------------
    def test_losses_and_gains_share_a_unit_but_not_a_series(self):
        note = self.dim('ops_quality_loss', 'effect')['note']
        self.assertIn('含义相反的都有', note)
        self.assertIn('绝不可放进同一条序列', note)

    def test_ops_losses_do_not_sum(self):
        self.assertIn('不可相加成「总折损」', self.metrics['ops_quality_loss']['note'])

    # -- 时点决定这条数还对不对 --------------------------------------------
    def test_the_training_share_is_time_critical(self):
        note = self.metrics['compute_demand_by_workload_share']['note']
        self.assertIn('2024-10', note)
        self.assertIn('半年后就是错的', note)

    def test_neocloud_demand_is_not_the_whole_market(self):
        self.assertIn('不等于全市场',
                      self.dim('compute_demand_by_workload_share',
                               'customer_scope')['note'])

    # -- 图里读不到年份就别按顺序假设 --------------------------------------
    def test_unreadable_chart_years_must_be_recovered_not_assumed(self):
        note = self.metrics['dc_securitization_issuance']['note']
        self.assertIn('必须回原文对齐年份', note)
        self.assertIn('不要按顺序假设', note)

    def test_sasb_may_be_double_counted_with_cmbs(self):
        self.assertIn('会重复计',
                      self.dim('dc_securitization_issuance', 'instrument')['note'])


class NeighbourMetricTests(unittest.TestCase):
    """相邻指标之间的交叉引用——菜单长到 220 个之后自己扫出来的。

    加完 81 个指标之后我扫了一遍全库，找同单位且命名相似的对。
    绝大多数是刻意的区分（价格 vs 成本、供给 vs 需求、按金额 vs 按台数），
    但有两处相邻得足以让人录错，而两边都没提对方。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def test_occupancy_and_vacancy_warn_against_converting(self):
        """看着互补，分母常常不是同一个——拿 100 去减就是造数。"""
        for mid, other in (('dc_occupancy_rate', 'dc_vacancy_rate'),
                           ('dc_vacancy_rate', 'dc_occupancy_rate')):
            note = self.metrics[mid]['note']
            self.assertIn(other, note, mid)
            self.assertIn('不要互相换算', note, mid)

    def test_they_sit_in_different_modules_which_is_why_it_matters(self):
        """两个模块的读者各看各的菜单，不交叉引用就看不见对方。"""
        self.assertNotEqual(self.metrics['dc_occupancy_rate']['module'],
                            self.metrics['dc_vacancy_rate']['module'])

    def test_the_generic_share_metric_points_at_the_specific_ones(self):
        note = self.metrics['vendor_market_share']['note']
        for specific in ('cowos_market_share', 'hdd_top2_share',
                         'self_asic_hyperscaler_gpu_share'):
            self.assertIn(specific, note, specific)
        self.assertIn('不要往这里塞', note)

    def test_no_two_metrics_share_an_id(self):
        ids = [v['metric_id'] for v in
               json.loads((L2.REPO /
                           'framework/metrics.json').read_text(
                               encoding='utf-8'))['metrics']]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_metric_has_a_unit_a_module_and_at_least_one_dimension(self):
        for mid, v in self.metrics.items():
            self.assertTrue(v.get('unit'), mid)
            self.assertTrue(v.get('module'), mid)
            self.assertTrue(v.get('caliber_dims'), mid)

    def test_no_enum_has_a_duplicate_or_blank_value(self):
        for mid, v in self.metrics.items():
            for d in v.get('caliber_dims', []):
                values = d.get('values') or []
                self.assertEqual(len(values), len(set(values)), (mid, d['id']))
                for value in values:
                    self.assertTrue(str(value).strip(), (mid, d['id']))


def problems_for(f):
    """跑一遍校验，只看与 corroboration 有关的那部分。"""
    return [x for x in problems(f) if 'corroboration' in x]


class SameOriginTests(unittest.TestCase):
    """「看着是两个来源，追到底是同一个」——M4 一轮里撞了两次。

    (a) 同一作者原样重用自己的段落：SemiAnalysis 2025-03 写的「2.99 / 23.92 /
        574.08」与它自己 2024-10 那份逐字相同。
    (b) 两家转述同一个原始信源：东吴与伯恩斯坦都说 GEV 2026 年中 20GW、
        2028 年 24GW，而两边的原始信源都是 GEV 自己的指引。

    两次都只能写进 notes——corroboration 三个取值里没有一个说得出这件事。
    """

    def test_the_fourth_value_exists_everywhere_it_is_declared(self):
        self.assertIn('同源转述', L2.CORROBORATION)
        schema = json.loads((L2.REPO /
                             'data/schema/fact.schema.json').read_text(encoding='utf-8'))
        self.assertIn('同源转述',
                      schema['properties']['corroboration']['enum'])

    def test_the_other_validator_agrees(self):
        """facts.py 是另一条校验路径，两边枚举必须一致，否则一条合法事实
        在一个地方通过、在另一个地方被拒。"""
        import importlib

        facts = importlib.import_module('inresearch.knowledge.facts')
        self.assertEqual(set(L2.CORROBORATION), facts.CORROB)

    def test_a_fact_may_declare_it(self):
        problems = problems_for(fact(corroboration='同源转述'))
        self.assertEqual(problems, [])

    def test_an_invalid_value_still_names_all_four(self):
        bad = problems_for(fact(corroboration='大概算验过了'))
        self.assertTrue(any('同源转述' in p for p in bad), bad)

    def test_the_schema_says_why_it_is_worse_than_pending(self):
        """待验证是「还没有第二个来源」，同源转述是「有第二份文件但它不是第二个来源」。"""
        schema = json.loads((L2.REPO /
                             'data/schema/fact.schema.json').read_text(encoding='utf-8'))
        desc = schema['properties']['corroboration']['description']
        self.assertIn('比「待交叉验证」更该警惕', desc)
        self.assertIn('它不是第二个来源', desc)

    def test_the_schema_keeps_both_worked_examples(self):
        schema = json.loads((L2.REPO /
                             'data/schema/fact.schema.json').read_text(encoding='utf-8'))
        desc = schema['properties']['corroboration']['description']
        self.assertIn('574.08', desc)          # 同一作者重用自己
        self.assertIn('20GW', desc)            # 两家转述同一信源

    def test_it_records_what_cannot_be_told_apart(self):
        """五个月「价格没动」，是市场没动还是没重写这段——分不出来就记下分不出来。"""
        schema = json.loads((L2.REPO /
                             'data/schema/fact.schema.json').read_text(encoding='utf-8'))
        self.assertIn('从这两份文件本身分不出来',
                      schema['properties']['corroboration']['description'])

#: 出现在 note 里就该真的存在的维名——「spec 维」曾经只在 note 里存在过。
KNOWN_DIM_NAMES = {'spec', 'sub_trade', 'option', 'bucket', 'scenario',
                   'tier', 'customer', 'region', 'measure', 'basis'}


class FreeTextDimensionTests(unittest.TestCase):
    """有些口径维本来就是开放的，我上一版用占位值和 note 假装它是枚举。

    三处同一个错，都是 M4 在真语料上撞出来的：
      equipment_unit_price 的 note 写着「规格写进 spec 维」，而那一维根本不存在——
        同一份清单里 ≥600kVA 与 ≥200kVA 两台 UPS 撞同一个 claim_key；
      investor_survey_share.option 与 investor_composition_share.bucket
        的取值是一个占位词「见 notes」，同一题的两个选项同样撞键。

    占位值比不填更糟：不填会被 check_fact 当场拒掉，占位值会静悄悄地
    把两条数并成一条。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def dim(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == did)

    # -- 契约层 -----------------------------------------------------------
    def test_a_free_text_value_is_accepted(self):
        """换一个从没出现过的规格串照样收——枚举做不到这件事。"""
        metrics, store = L2.load_metrics(), L2.load_facts()
        probe = json.loads(json.dumps(
            next(f for f in store['records']
                 if f['metric_id'] == 'equipment_unit_price')))
        probe['fact_id'] = 'probe-new-spec'
        probe['caliber']['spec'] = '风冷冷水机组，制冷量≥350kW，COP≥3.2'
        self.assertEqual(L2.check_fact(probe, metrics, set(), None), [])

    def test_a_placeholder_is_refused_with_the_reason(self):
        d = self.dim('equipment_unit_price', 'spec')
        self.assertTrue(d.get('free_text'))
        for junk in ('见 notes', '同上', '待补', 'N/A', '—'):
            self.assertIn(junk, L2.PLACEHOLDER_VALUES)

    def test_the_refusal_says_what_the_dimension_is_for(self):
        metrics = L2.load_metrics()
        store = L2.load_facts()
        probe = json.loads(json.dumps(
            next(f for f in store['records']
                 if f['metric_id'] == 'equipment_unit_price')))
        probe['fact_id'] = 'probe-placeholder'
        probe['caliber']['spec'] = '见 notes'
        bad = L2.check_fact(probe, metrics, set(), None)
        self.assertTrue(any('占位词不是取值' in p for p in bad), bad)
        self.assertTrue(any('把两条数区分开' in p for p in bad), bad)

    def test_blank_and_missing_are_both_refused(self):
        metrics, store = L2.load_metrics(), L2.load_facts()
        base = next(f for f in store['records']
                    if f['metric_id'] == 'equipment_unit_price')
        blank = json.loads(json.dumps(base)); blank['fact_id'] = 'p1'
        blank['caliber']['spec'] = '   '
        self.assertTrue(any('不能留空' in p
                            for p in L2.check_fact(blank, metrics, set(), None)))
        gone = json.loads(json.dumps(base)); gone['fact_id'] = 'p2'
        del gone['caliber']['spec']
        self.assertTrue(any('缺 spec' in p
                            for p in L2.check_fact(gone, metrics, set(), None)))

    # -- 三处占位都清掉了 --------------------------------------------------
    def test_no_dimension_anywhere_still_holds_a_placeholder(self):
        for mid, metric in self.metrics.items():
            for d in metric.get('caliber_dims', []):
                for value in d.get('values') or ():
                    self.assertNotIn(str(value), L2.PLACEHOLDER_VALUES, (mid, d['id']))

    def test_every_dimension_is_either_an_enum_or_free_text(self):
        """两者都不是的维，check_fact 会放行任何字符串——等于没有约束。"""
        for mid, metric in self.metrics.items():
            for d in metric.get('caliber_dims', []):
                self.assertTrue(d.get('values') or d.get('free_text'), (mid, d['id']))

    def test_the_three_free_text_dimensions_are_declared_as_such(self):
        for mid, did in (('equipment_unit_price', 'spec'),
                         ('cost_share_by_trade', 'sub_trade'),
                         ('investor_survey_share', 'option'),
                         ('investor_composition_share', 'bucket')):
            d = self.dim(mid, did)
            self.assertTrue(d.get('free_text'), (mid, did))
            self.assertNotIn('values', d, (mid, did))

    def test_no_note_promises_a_dimension_that_does_not_exist(self):
        """equipment_unit_price 的 note 曾许诺过一个不存在的 spec 维。"""
        import re
        for mid, metric in self.metrics.items():
            declared = {d['id'] for d in metric.get('caliber_dims', [])}
            text = (metric.get('note') or '') + ''.join(
                d.get('note', '') for d in metric.get('caliber_dims', []))
            # 只找「把东西放进某维」这种许诺句式。说「没有 region 维」是在
            # 解释缺席，不是许诺存在——第一版正则把那种也算进来了。
            for named in re.findall(
                    r'(?:写进|填进|填|记进|记入|放进|进)\s*([a-z][a-z_]{2,})\s*维', text):
                if named in KNOWN_DIM_NAMES:
                    self.assertIn(named, declared, (mid, named))

    # -- 撞键真的解开了 ----------------------------------------------------
    def test_two_specs_of_one_equipment_no_longer_collide(self):
        store = L2.load_facts()
        keys, seen = [], {}
        for f in store['records']:
            if f['metric_id'] != 'equipment_unit_price':
                continue
            key = L2.claim_key(f)
            self.assertNotIn(key, seen, (f['fact_id'], seen.get(key)))
            seen[key] = f['fact_id']
            keys.append(key)
        self.assertGreater(len(keys), 4)

    def test_each_spec_came_from_its_own_locator(self):
        """回填不是照 fact_id 猜的：每条的规格都写在它自己的 locator 里。"""
        store = L2.load_facts()
        rows = [f for f in store['records']
                if f['metric_id'] == 'equipment_unit_price']
        self.assertTrue(rows)
        for f in rows:
            spec = f['caliber']['spec']
            self.assertIn('规格描述：', f['evidence']['locator'], f['fact_id'])
            self.assertIn(spec, f['evidence']['locator'], f['fact_id'])


class AsymmetricDimensionTests(unittest.TestCase):
    """容量侧有 product_category、金额侧没有——我上一版留下的不对称。

    后果不是少一维那么轻：IDC 存储表的品类金额被 claim_key 判成与同
    storage_scope 的合计重复，实测挡下 5 条。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()

    def values(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims']
                    if d['id'] == did)['values']

    def test_both_sides_now_carry_the_same_categories(self):
        capacity = self.values('storage_capacity_shipped', 'product_category')
        revenue = self.values('server_mfg_revenue', 'product_category')
        for v in capacity:
            self.assertIn(v, revenue, v)

    def test_the_revenue_side_also_needs_a_non_storage_escape(self):
        """金额侧还装着服务器行，容量侧不装。"""
        self.assertIn('不适用（非存储口径）',
                      self.values('server_mfg_revenue', 'product_category'))
        self.assertNotIn('不适用（非存储口径）',
                         self.values('storage_capacity_shipped', 'product_category'))

    def test_the_note_carries_the_arithmetic_that_explains_the_gap(self):
        """这一维正是「IDC 与 Dell'Oro 差好几倍」的出处所在。"""
        note = next(d for d in self.metrics['server_mfg_revenue']['caliber_dims']
                    if d['id'] == 'product_category')['note']
        self.assertIn('185.14', note)
        self.assertIn('77.83', note)
        self.assertIn('185.14 ÷ 77.83 = 2.38', note)
        self.assertAlmostEqual(185.14 / 77.83, 2.38, places=2)

    def test_the_backfill_split_storage_rows_from_server_rows(self):
        store = L2.load_facts()
        rows = [f for f in store['records']
                if f['metric_id'] == 'server_mfg_revenue']
        self.assertTrue(rows)
        for f in rows:
            got = f['caliber']['product_category']
            if f['caliber']['server_class'] == 'Storage Systems':
                self.assertNotEqual(got, '不适用（非存储口径）', f['fact_id'])
            else:
                self.assertEqual(got, '不适用（非存储口径）', f['fact_id'])

    def test_sub_trade_keeps_the_original_line_items(self):
        d = next(x for x in self.metrics['cost_share_by_trade']['caliber_dims']
                 if x['id'] == 'sub_trade')
        self.assertTrue(d.get('free_text'))
        self.assertIn('原始分项结构就此丢失', d['note'])
        self.assertIn('分项与合计不可一起加总', d['note'])


class SplitDimensionSymmetryTests(unittest.TestCase):
    """服务器/存储这一族的切法维矩阵——我是一条缺口一条缺口加上去的，从没让它自洽。

    切法维是「把同一批对象切开」的维：谁买的、哪个省、哪个行业、哪个品类、
    站在哪一侧。它与测量限定维（basis、price_type、stat）不同——后者说的是
    这个数怎么来的，前者说的是这个数覆盖谁。

    先后撞了两次，都是同一格：
      product_category 容量侧有、金额侧没有，挡下 5 条；
      subregion/vertical 台数侧有、金额侧没有，中国外置存储的省份与行业
        拆分存不下。
    两次都是同一张 IDC 表的两半——**同一份文件里的两列，只在一侧声明了维。**

    这个类不主张每一格都要填满，主张的是：**每一格的有无都要是当下有据的选择，
    并且看得见。**下面那张表就是当下的选择，改动它必须同时改这里。
    """

    #: 这一族里各指标当下声明的切法维。改菜单时同步改这里——
    #: 让「加了一维却忘了对面」在测试里就红，而不是等语料撞出来。
    EXPECTED = {
        'server_unit_shipments':
            {'subregion', 'vertical', 'buyer_category', 'counterparty_role'},
        'server_mfg_revenue':
            {'subregion', 'vertical', 'product_category', 'storage_scope'},
        'server_asp':
            {'subregion', 'vertical', 'storage_scope'},
        'storage_capacity_shipped':
            {'subregion', 'vertical', 'product_category', 'buyer_category',
             'storage_scope'},
        'it_infra_spend':
            {'subregion', 'vertical', 'buyer_category'},
        'vendor_market_share':
            {'subregion', 'vertical'},
        'installed_server_base':
            {'counterparty_role'},
    }

    SPLIT_DIMS = ('subregion', 'vertical', 'product_category',
                  'buyer_category', 'counterparty_role', 'storage_scope')

    def setUp(self):
        self.metrics = L2.load_metrics()

    def declared(self, mid):
        return {d['id'] for d in self.metrics[mid]['caliber_dims']
                if d['id'] in self.SPLIT_DIMS}

    def test_the_matrix_matches_what_is_declared(self):
        for mid, expected in self.EXPECTED.items():
            self.assertEqual(self.declared(mid), expected, mid)

    def test_the_two_halves_of_one_idc_table_agree(self):
        """台数与金额出自同一张表，按同一套省份与行业切——两侧必须都能装。"""
        for dim_id in ('subregion', 'vertical'):
            for mid in ('server_unit_shipments', 'server_mfg_revenue',
                        'server_asp', 'storage_capacity_shipped',
                        'vendor_market_share'):
                self.assertIn(dim_id, self.declared(mid), (mid, dim_id))

    def test_capacity_and_revenue_agree_on_product_category(self):
        """第一次撞的那格，两侧现在一致。"""
        for mid in ('server_mfg_revenue', 'storage_capacity_shipped'):
            self.assertIn('product_category', self.declared(mid), mid)

    def test_the_shared_dimension_note_says_why_both_sides_need_it(self):
        for mid in ('server_mfg_revenue', 'storage_capacity_shipped'):
            note = next(d for d in self.metrics[mid]['caliber_dims']
                        if d['id'] == 'subregion')['note']
            self.assertIn('台数侧与金额侧必须一致', note, mid)

    def test_no_family_metric_lost_a_split_dimension(self):
        """加维只会往上加；哪天某一格消失了，必是误删。"""
        for mid, expected in self.EXPECTED.items():
            self.assertTrue(expected <= self.declared(mid), mid)

    def test_every_existing_fact_in_the_family_carries_them_all(self):
        store = L2.load_facts()
        for f in store['records']:
            mid = f['metric_id']
            if mid not in self.EXPECTED:
                continue
            for dim_id in self.EXPECTED[mid]:
                self.assertIn(dim_id, f['caliber'], (f['fact_id'], dim_id))

    #: 迁移当天库里就有的那批，回填只能填全国或不适用。之后读进来的可以真按省、
    #: 按行业切——IDC 那份 2024 中国 AI 服务器就是按省份与行业各拆一套的。
    #: 这条测试钉的是「回填没有凭空给既有事实按上一个省份」，不是「这一族永远不许按省切」。
    #: 回填批次——#155 加维时库里已有的 47 条，加上 #156 补的 33 条
    #: （那 33 条是我加维时 M4 正在按加维前的菜单录的，合并后缺维）。
    #: 这是一个封闭的历史集合，从两次回填的 commit 里逐条取出来写死。
    #: **不要改用前缀或子串去圈它**：这条测试被前缀白名单和「-prov- 排除」
    #: 两套启发式先后打过补丁，而白名单里本来就漏了 idc-cn-x86-revenue*——
    #: 只是那批碰巧没按省切，才一直没红。集合是确定的，就该按集合写。
    BACKFILL_BATCH = frozenset((
        'delloro-jul26-srvasp-accelerated-high-end-2026e',
        'delloro-jul26-srvasp-accelerated-high-end-2030e',
        'delloro-jul26-srvasp-all-servers-2026e', 'delloro-jul26-srvasp-all-servers-2030e',
        'delloro-jul26-srvasp-general-purpose-and-other-2026e',
        'delloro-jul26-srvasp-general-purpose-and-other-2030e',
        'delloro-jul26-srvrev-accelerated-high-end-2026e',
        'delloro-jul26-srvrev-accelerated-high-end-2030e',
        'delloro-jul26-srvrev-all-servers-2026e', 'delloro-jul26-srvrev-all-servers-2030e',
        'delloro-jul26-srvrev-general-purpose-and-other-2026e',
        'delloro-jul26-srvrev-general-purpose-and-other-2030e',
        'idc-cii-2020-spend-alibaba-overlap', 'idc-cii-2020-spend-alibaba-server',
        'idc-cii-2020-spend-alibaba-storage', 'idc-cii-2020-spend-alibaba-total',
        'idc-cii-2020-spend-amazon-overlap', 'idc-cii-2020-spend-amazon-server',
        'idc-cii-2020-spend-amazon-storage', 'idc-cii-2020-spend-apple-overlap',
        'idc-cii-2020-spend-apple-server', 'idc-cii-2020-spend-apple-storage',
        'idc-cii-2020-spend-baidu-overlap', 'idc-cii-2020-spend-baidu-server',
        'idc-cii-2020-spend-baidu-storage', 'idc-cii-2020-spend-baidu-total',
        'idc-cii-2020-spend-google-overlap', 'idc-cii-2020-spend-google-server',
        'idc-cii-2020-spend-google-storage', 'idc-cii-2020-spend-meta-overlap',
        'idc-cii-2020-spend-meta-server', 'idc-cii-2020-spend-meta-storage',
        'idc-cii-2020-spend-microsoft-overlap', 'idc-cii-2020-spend-microsoft-server',
        'idc-cii-2020-spend-microsoft-storage', 'idc-cii-2020-spend-tencent-overlap',
        'idc-cii-2020-spend-tencent-server', 'idc-cii-2020-spend-tencent-storage',
        'idc-cii-2020-spend-tencent-total', 'idc-cn-x86-revenue-2018q1',
        'idc-cn-x86-revenue-2018q2', 'idc-cn-x86-revenue-2018q3',
        'idc-cn-x86-revenue-2018q4', 'idc-cn-x86-revenue-2019q1',
        'idc-cn-x86-revenue-2019q2', 'idc-cn-x86-revenue-2019q3',
        'idc-cn-x86-revenue-2019q4', 'idc-cn-x86-revenue-2020q1',
        'idc-cn-x86-revenue-2020q2', 'idc-cn-x86-revenue-2020q3',
        'idc-cn-x86-revenue-fc-2019', 'idc-cn-x86-revenue-fc-2020',
        'idc-cn-x86-revenue-fc-2021', 'idc-cn-x86-revenue-fc-2022',
        'idc-cn-x86-revenue-fc-2023', 'idc-cn-x86-revenue-fc-2024',
        'idc-ess-capacity-external-2016q1', 'idc-ess-capacity-external-2021q3',
        'idc-ess-capacity-external-2025', 'idc-ess-capacity-internal-2016q1',
        'idc-ess-capacity-internal-2021q3', 'idc-ess-capacity-internal-2025',
        'idc-ess-capacity-total-2016q1', 'idc-ess-capacity-total-2021q3',
        'idc-ess-capacity-total-2025', 'idc-ess-value-external-2016q1',
        'idc-ess-value-external-2021q3', 'idc-ess-value-external-2025',
        'idc-ess-value-internal-2016q1', 'idc-ess-value-internal-2021q3',
        'idc-ess-value-internal-2025', 'idc-ess-value-total-2016q1',
        'idc-ess-value-total-2021q3', 'idc-ess-value-total-2025',
        'idc-prc-external-storage-2019', 'idc-prc-external-storage-2020',
        'idc-prc-external-storage-2021', 'idc-prc-external-storage-2022',
        'idc-prc-external-storage-2023', 'idc-prc-external-storage-2024',
    ))

    def test_the_backfill_batch_is_a_closed_historical_set(self):
        """80 条是数出来的，不是估出来的：#155 的 47 条 + #156 的 33 条。

        这条测试连同上一条被 M4 先后打过两次补丁，因为我第一版把「回填当天的
        快照」写成了永久断言——语料一按省切就红。它教过我一次正确的形状
        （MIGRATED_SHIPMENT_FACTS 按 fact_id 写死），我在这里没照做。
        """
        self.assertEqual(len(self.BACKFILL_BATCH), 80)
        store = L2.load_facts()
        present = {f['fact_id'] for f in store['records']}
        missing = sorted(self.BACKFILL_BATCH - present)
        self.assertEqual(missing, [], '回填批次里的事实不该消失')

    def test_every_backfilled_fact_is_in_a_family_metric(self):
        store = {f['fact_id']: f for f in L2.load_facts()['records']}
        for fid in self.BACKFILL_BATCH:
            self.assertIn(store[fid]['metric_id'], self.EXPECTED, fid)

    def test_the_backfill_never_claimed_a_province(self):
        """既有事实一条都没有按省切过——回填只能填全国或不适用。

        只查真的声明了这两维的指标。第一版对族内所有指标一律断言，
        而 installed_server_base 并没有 subregion——它的分层门槛事实一录进来
        就把这条测试弄红了，红的是测试不是数据。
        """
        store = L2.load_facts()
        for f in store['records']:
            expected = self.EXPECTED.get(f['metric_id'])
            if not expected:
                continue
            if f['fact_id'] not in self.BACKFILL_BATCH:
                # 回填之后读进来的可以真按省、按行业切——IDC 那份 2024 中国 AI
                # 服务器就是按省份与行业各拆一套的（北京占 49.9%、互联网占 57.9%）。
                # 这条测试钉的是「回填没有凭空给既有事实按上一个省份」，
                # 不是「这一族永远不许按省切」。
                continue
            if 'subregion' in expected:
                self.assertIn(f['caliber'].get('subregion'),
                              ('全国', '不适用（非中国口径）'), f['fact_id'])
            if 'vertical' in expected:
                self.assertEqual(f['caliber'].get('vertical'), '未拆分', f['fact_id'])


class FourthRoundGapTests(unittest.TestCase):
    """M4 第四轮的五条缺口。其中一条是它自己填错了、当场标错并报上来的。"""

    def setUp(self):
        self.metrics = L2.load_metrics()

    def dim(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == did)

    # -- 混在一起的「存储容量」没有意义 ------------------------------------
    def test_media_separates_hdd_from_flash(self):
        d = self.dim('storage_capacity_shipped', 'media')
        self.assertEqual(d['values'], ['HDD', 'Flash-SSD', '合计'])
        self.assertIn('差一个量级', d['note'])

    def test_the_media_note_carries_the_ratio_it_claims(self):
        note = self.dim('storage_capacity_shipped', 'media')['note']
        self.assertIn('97,419.6 ÷ 12,305.9 = 7.92', note)
        self.assertAlmostEqual(97419.6 / 12305.9, 7.92, places=2)

    def test_every_capacity_fact_says_which_media(self):
        for f in L2.load_facts()['records']:
            if f['metric_id'] == 'storage_capacity_shipped':
                self.assertIn('media', f['caliber'], f['fact_id'])

    # -- 五家最大买方的总值对不上 ------------------------------------------
    def test_the_unreconciled_total_has_its_own_value(self):
        d = self.dim('it_infra_spend', 'product_scope')
        self.assertIn('原表 Total Value（含未定义残差）', d['values'])

    def test_the_note_records_that_95_of_100_held(self):
        """逐行验过 100 家——这个数字本身就是这条取值存在的理由。"""
        note = self.dim('it_infra_spend', 'product_scope')['note']
        self.assertIn('100 家全对', note)
        self.assertIn('95 家成立', note)
        self.assertIn('−139.24', note)          # Facebook，负号，方向相反
        self.assertIn('不可参与任何加总校验', note)

    # -- 重型燃机不是柴油发电机组 ------------------------------------------
    def test_the_gas_turbine_value_exists_now(self):
        self.assertIn('燃气轮机', self.dim('major_equipment_count', 'equipment')['values'])

    def test_the_mislabelled_fact_was_corrected(self):
        rows = {f['fact_id']: f for f in L2.load_facts()['records']}
        got = rows['dw-gev-heavy-duty-units-2026e']
        self.assertEqual(got['caliber']['equipment'], '燃气轮机')
        self.assertEqual(got['caliber']['count_basis'], '产量台数')

    def test_the_correction_is_recorded_in_the_fact_itself(self):
        """账本是追加式的，改判要留痕——不能改完就当没发生过。"""
        rows = {f['fact_id']: f for f in L2.load_facts()['records']}
        notes = rows['dw-gev-heavy-duty-units-2026e']['notes']
        self.assertIn('已改判', notes)
        self.assertIn('当时枚举里没有燃机', notes)

    def test_order_output_and_installed_counts_are_three_things(self):
        d = self.dim('major_equipment_count', 'count_basis')
        for v in ('新签订单台数', '产量台数', '装机台数'):
            self.assertIn(v, d['values'], v)
        self.assertIn('订单是将来要交的，产量是当期能造的，装机是已经在跑的', d['note'])

    # -- 1230 行逐回路 -----------------------------------------------------
    def test_a_circuit_can_be_named(self):
        d = self.dim('circuit_current_margin', 'circuit_id')
        self.assertTrue(d.get('free_text'))
        self.assertIn('1230 行', d['note'])

    def test_the_minimum_is_not_the_average(self):
        note = self.dim('circuit_current_margin', 'stat')['note']
        self.assertIn('一条余量充足的母线救不了一条贴着载流量走的馈线', note)

    def test_the_two_existing_rows_are_marked_as_an_aggregate(self):
        """那两条是一批回路归并出的区间两端，不是某一条回路。"""
        rows = [f for f in L2.load_facts()['records']
                if f['metric_id'] == 'circuit_current_margin']
        self.assertTrue(rows)
        for f in rows:
            self.assertEqual(f['caliber']['circuit_id'], '汇总（非单回路）', f['fact_id'])
            self.assertEqual(f['caliber']['stat'], '区间端', f['fact_id'])


class FifthRoundGapTests(unittest.TestCase):
    """M4 第五轮报上来的 46 条缺口——本批补的菜单。

    这一批里有三件事值得单独盯：一是「规格进事实层」的裁决终于落了地，
    M08 与 M14 两族规格指标都挂在它下面；二是三条 note 里的算术我写错了，
    是逐个加过之后才发现的，下面的测试把算术本身钉住，不是钉那句话；
    三是补维必须连同既有事实一起回填，否则主干当场红——上一轮就是这么红的。
    """

    def setUp(self):
        self.metrics = L2.load_metrics()
        self.facts = L2.load_facts()['records']

    def dim(self, mid, did):
        return next(d for d in self.metrics[mid]['caliber_dims'] if d['id'] == did)

    def dims(self, mid):
        return {d['id'] for d in self.metrics[mid]['caliber_dims']}

    # -- 补的维必须连同既有事实一起回填 ------------------------------------
    def test_every_fact_still_passes_after_the_menu_changed(self):
        """补维当场回填，是上一轮把主干撞红之后立的规矩。

        剩下的 38 条是早年遗留的 sha256 欠账，与本批无关：M4 已经确认
        它们没有可走的回填路径（35 条 source_id 为空、3 条只有人给的名字）。
        这个数字只许降不许升——升了说明本批又漏了一处回填。
        """
        metrics, seen, owed = self.metrics, set(), []
        for f in self.facts:
            bad = L2.check_fact(f, metrics, seen)
            seen.add(f.get('fact_id'))
            for e in bad:
                self.assertIn('sha256', e, '%s: %s' % (f.get('fact_id'), e))
                owed.append(f['fact_id'])
        self.assertLessEqual(len(owed), 38)

    def test_no_two_facts_share_a_claim_key(self):
        """回填口径维会改 claim_key——填错一格就是把两条数撞成一条。"""
        seen = {}
        for f in self.facts:
            key = L2.claim_key(f)
            self.assertNotIn(key, seen,
                             '%s 与 %s 撞了 claim_key' % (f['fact_id'], seen.get(key)))
            seen[key] = f['fact_id']

    def test_the_chip_demand_rows_say_which_vendor(self):
        """三条都是全市场口径：两条是十一家逐行相加，一条是报告的整体预测。"""
        rows = [f for f in self.facts if f['metric_id'] == 'cn_ai_chip_demand']
        self.assertEqual(len(rows), 3)
        for f in rows:
            self.assertEqual(f['caliber']['vendor'], '全市场', f['fact_id'])

    def test_the_projection_rows_say_which_scenario(self):
        """RAND 的 158-253 是一个留存率参数的区间，不是两个情景——故填「单一情景」。

        填「基准」会暗示原文另有一个高增长情景与之对照，那是我们编的。
        scenario 这一维是为 EPRI 的 300/800 那种「同机构两情景」加的。
        """
        rows = [f for f in self.facts
                if f['metric_id'] == 'model_projected_generation_need']
        self.assertTrue(rows)
        for f in rows:
            self.assertEqual(f['caliber']['scenario'], '单一情景', f['fact_id'])
        self.assertIn('单一情景',
                      self.dim('model_projected_generation_need', 'scenario')['values'])
        self.assertIn('EPRI',
                      self.dim('model_projected_generation_need', 'scenario')['note'])

    def test_the_material_rows_say_which_system(self):
        """互连铜缆与动力电缆都是「电气材料」，加到一起得不到任何东西。"""
        rows = [f for f in self.facts
                if f['metric_id'] == 'electrical_material_intensity']
        self.assertTrue(rows)
        for f in rows:
            self.assertIn(f['caliber']['system'], ('供配电', '接地与防雷'), f['fact_id'])
        by_id = {f['fact_id']: f for f in rows}
        self.assertEqual(by_id['ulanqab-p3-material-ground-steel']['caliber']['system'],
                         '接地与防雷')
        self.assertEqual(by_id['ulanqab-p3-material-tray-indoor']['caliber']['system'],
                         '供配电')

    # -- 三条我写错了的 note，钉的是算术不是那句话 --------------------------
    def test_the_tco_identity_does_not_hold_on_two_of_five(self):
        """原表五组里两组差 0.1。我先写成「五组全对得上」，是加过才发现的。

        钉住算术本身：哪天有人「修正」了那两个数去凑恒等式，这里会红。
        """
        rows = [(0.9, 5.7, 6.5), (0.5, 4.3, 4.8), (0.5, 3.9, 4.3),
                (0.8, 1.7, 2.5), (0.6, 2.9, 3.5)]
        off = [r for r in rows if abs(r[0] + r[1] - r[2]) > 1e-9]
        self.assertEqual(len(off), 2)
        for power, hw, total in off:
            self.assertAlmostEqual(power + hw - total, 0.1, places=9)
        note = self.dim('task_tco', 'cost_item')['note']
        self.assertIn('五组里两组差 0.1', note)
        self.assertIn('[未核]', note)
        self.assertIn('不要拿这个恒等式做硬校验', note)
        self.assertNotIn('五组全对得上', note)

    def test_the_chip_revenue_columns_do_add_up(self):
        """按年逐列加，四列分毫不差。我先按错列取值，得出过「加不上」的假结论。"""
        cols = {2024: ([355.8, 73.7], 429.5),
                2025: ([1263.6, 77.2, 120.3], 1461.1),
                2026: ([982.8, 982.8, 154.6], 2120.2),
                2027: ([702.0, 1965.6, 198.1], 2865.7)}
        for year, (parts, total) in cols.items():
            self.assertAlmostEqual(sum(parts), total, places=9, msg=str(year))
        note = self.dim('chip_revenue_cn', 'scope')['note']
        self.assertIn('四列全部分毫不差', note)
        self.assertIn('先犯过一次', note)

    def test_the_three_pue_multipliers_are_three_different_numbers(self):
        """含 PUE 与不含差的不是同一个倍数——1.5 / 1.4 / 1.2，原表一机一个。"""
        got = [round(9.3 / 6.2, 4), round(12.04 / 8.6, 4), round(116.64 / 97.2, 4)]
        self.assertEqual(got, [1.5, 1.4, 1.2])
        note = self.dim('server_power_and_training_time', 'pue_included')['note']
        self.assertIn('差的不是同一个倍数', note)
        self.assertIn('[未核]', note)

    def test_the_cluster_total_power_confirms_the_node_count(self):
        """667 台不是我编的：GB200 667 × 116.64kW = 77.8MW，与原表对上。"""
        self.assertAlmostEqual(3000 * 9.3 / 1000, 27.9, places=2)
        self.assertAlmostEqual(3000 * 12.04 / 1000, 36.12, places=2)
        self.assertAlmostEqual(667 * 116.64 / 1000, 77.8, places=1)
        self.assertAlmostEqual(1344 / 2.016, 666.67, places=2)
        self.assertAlmostEqual(396 / 0.132, 3000, places=6)

    def test_the_bom_lines_add_to_the_stated_total(self):
        """40,964 万元是加出来的，不是抄来的。"""
        total = 340 * 84 + (21 + 15 + 45) * 84 + 500 + 1500 + 20 * 96 + 1680
        self.assertEqual(total, 40964)
        self.assertIn('总价 40,964 万元', self.metrics['cluster_bom_cost']['note'])

    def test_the_cost_composition_adds_exactly(self):
        self.assertAlmostEqual(13890247.76 + 1250122.30, 15140370.06, places=2)
        self.assertIn('加总核对过，分毫不差',
                      self.metrics['cost_composition_by_item']['note'])

    def test_the_cloud_shares_and_amounts_both_close(self):
        amounts = [12, 113, 40, 82, 97, 52, 22, 69, 325]
        shares = [2, 14, 5, 10, 12, 6, 3, 8, 40]
        self.assertEqual(sum(amounts), 812)
        self.assertEqual(sum(shares), 100)
        self.assertAlmostEqual(113 / 812 * 100, 13.9, places=1)

    def test_the_foundry_split_adds_to_the_total_every_year(self):
        for parts, total in (([2, 0, 0], 2), ([9, 1, 0], 10),
                             ([0, 10, 10], 20), ([0, 6, 20], 26)):
            self.assertEqual(sum(parts), total)
        self.assertIn('可互校', self.metrics['foundry_capacity']['note'])

    def test_the_cooling_route_shares_close_to_a_hundred(self):
        self.assertEqual(65 + 34 + 1, 100)
        self.assertIn('加总为 100%', self.metrics['cooling_route_share']['note'])
        self.assertIn('分母完全不同',
                      self.dim('cooling_route_share', 'denominator')['note'])

    def test_the_liquid_cooling_growth_matches_the_stated_rate(self):
        self.assertAlmostEqual(184 / 110.8 - 1, 0.661, places=3)
        self.assertAlmostEqual((1300 / 365) ** 0.25 - 1, 0.374, places=3)

    def test_the_grid_share_note_carries_the_unit_conversion(self):
        """1,660 亿 kW·h = 166 TWh——单位不换算，占比与总量就对不上分母。"""
        self.assertEqual(1660 / 10, 166)
        self.assertIn('1,660 亿 kW·h = 166 TWh',
                      self.metrics['dc_power_share_of_grid']['note'])

    def test_gb300_gains_only_on_fp4(self):
        self.assertAlmostEqual(1080 / 720, 1.5, places=9)
        self.assertEqual(180, 180)                      # FP16 两代相同
        self.assertAlmostEqual(20.7 / 13.8, 1.5, places=9)
        note = self.metrics['accelerator_compute_spec']['note']
        self.assertIn('FP16 与 FP8 完全一样', note)
        self.assertIn('容量涨了 50% 而带宽没动',
                      self.metrics['accelerator_memory_spec']['note'])

    def test_the_domestic_chip_price_gap_is_what_the_note_says(self):
        self.assertAlmostEqual(12 / 3.5, 3.43, places=2)
        self.assertIn('3.4 倍', self.dim('chip_unit_price_cn', 'channel')['note'])

    # -- 规格进事实层的裁决 ------------------------------------------------
    def test_the_ruling_is_written_down_where_the_contract_lives(self):
        """裁决要留在契约里，不能只活在一次对话里。"""
        note = json.loads(
            (L2.REPO / 'framework/metrics.json').read_text(encoding='utf-8'))['note']
        self.assertIn('进事实层，不另建一层', note)
        self.assertIn('会改变这个裁决的情形', note)

    def test_every_spec_metric_declares_where_the_spec_came_from(self):
        """规格多数来自券商转述与发布会转录，来源等级必须跟着数走。"""
        for mid in ('accelerator_compute_spec', 'accelerator_memory_spec',
                    'interconnect_bandwidth_spec', 'rack_component_count',
                    'chip_design_spec', 'interconnect_lane_rate'):
            d = self.dim(mid, 'spec_basis')
            self.assertIn('厂商规格书', d['values'], mid)
            self.assertIn('券商转述', d['values'], mid)

    def test_a_spec_metric_names_the_product_in_free_text(self):
        """型号是这一族的主键，占位词会把两款芯片撞成一条。"""
        for mid in ('accelerator_compute_spec', 'accelerator_memory_spec',
                    'interconnect_bandwidth_spec', 'rack_component_count',
                    'chip_design_spec', 'interconnect_lane_rate'):
            self.assertTrue(self.dim(mid, 'product').get('free_text'), mid)

    def test_lane_rate_and_link_bandwidth_are_two_metrics(self):
        """1.8TB/s 与 224Gbps 差一个通道数，同列就读不出差在哪。"""
        self.assertEqual(self.metrics['interconnect_lane_rate']['unit'], 'Gbps/通道')
        self.assertEqual(self.metrics['interconnect_bandwidth_spec']['unit'], 'GB/s')
        self.assertIn('永不并列', self.metrics['interconnect_lane_rate']['note'])
        self.assertIn('DAC 无源铜缆',
                      self.dim('interconnect_lane_rate', 'medium')['values'])
        self.assertIn('<5m（机柜内）',
                      self.dim('interconnect_lane_rate', 'reach_band')['values'])

    def test_in_rack_copper_is_its_own_route_on_the_milestone_menu(self):
        d = self.dim('tech_milestone_year', 'tech')
        self.assertIn('机柜内铜互连', d['values'])
        self.assertIn('不是「光互连」的反面', d['note'])

    # -- 单价与数量 --------------------------------------------------------
    def test_quantity_has_a_metric_of_its_own(self):
        """事实层一条只有一个 value，数量要能被乘，就只能是另一条数。"""
        q = self.metrics['equipment_quantity']
        for did in ('equipment', 'spec', 'uom', 'stage', 'region', 'basis'):
            self.assertIn(did, self.dims('equipment_quantity'), did)
        self.assertAlmostEqual(669223.01 * 6, 4015338.06, places=2)
        self.assertIn('669,223.01 元/台 × 6 台 = 4,015,338.06 元', q['note'])

    def test_the_quantity_flag_points_at_a_real_row(self):
        """quantity_note 填「已同记数量」而没有对应的一条，那个标记就是在说谎。"""
        self.assertIn('已同记数量',
                      self.dim('equipment_unit_price', 'quantity_note')['values'])
        self.assertIn('那个标记就是在说谎',
                      self.metrics['equipment_quantity']['note'])

    def test_price_and_quantity_share_the_keys_they_join_on(self):
        price, qty = self.dims('equipment_unit_price'), self.dims('equipment_quantity')
        for did in ('equipment', 'spec', 'uom', 'stage', 'region'):
            self.assertIn(did, price, did)
            self.assertIn(did, qty, did)

    def test_the_price_metric_can_hold_a_dollar_quote(self):
        """液冷快接是美元报价，而这个指标此前单位是元、没有币种维。"""
        self.assertIn('美元', self.dim('equipment_unit_price', 'currency')['values'])
        self.assertIn('液冷快接', self.dim('equipment_unit_price', 'equipment')['values'])

    # -- 那三条口径提示不是缺口，不许被当成缺口销账 --------------------------
    def test_the_reread_flags_are_still_open(self):
        """「口径提示（非缺口）」是重读清单，销账等于把它抹掉。

        RAND 那 100 页与冷源那份全套控制价，菜单补齐后要整份重读；
        销账要等重读做完，不是等菜单补完。
        """
        open_ids = {r['gap_id'] for r in L2.open_gaps()}
        for gid in ('c0d3e7fcefb7', 'a43dec696fcc', 'df8fbc0c4037',
                    '99b7788670eb'):
            self.assertIn(gid, open_ids, gid)

    def test_the_menu_gaps_this_batch_filled_are_closed(self):
        open_ids = {r['gap_id'] for r in L2.open_gaps()}
        for gid in FILLED_THIS_BATCH:
            self.assertNotIn(gid, open_ids, gid)


#: 本批销账的 gap_id——显式名单，不靠前缀或字样匹配。
#: 上一轮的教训：按 fact_id 里的字样批量判定，同一条测试被打了两次补丁还是不对。
FILLED_THIS_BATCH = frozenset((
    '6af0f6ef29ca', 'fb2fd593a96b', '79dcfab07590',
    'c887218bba8c', 'b2b357ea5a41', '21b8800b45b4', '5647700326f0',
    'a4ceb4989ff9', 'c6eac4df9d6f', '3d289012079d', 'd6ab0f6695c7',
    '668882d117c0', '836448f119cb', 'f93ec7230288', 'dce7db166f51',
    '4881b5e1ee08', '268ef629bbc5', '8b630833198b', 'af071d00d08f',
    '0223b5b69287', '1d9cb156e7fa', '6240a391fd12', 'e860f4415f38',
    '65767b0dfd12', '9bc7abd1f421',
    '0287d488eb08', '1f84210a930d', 'cbce461c8ad4', '2749a0c3ae47',
    'f29dcf1e1431',
    '678b422a1179', 'dbaef8d19b23', '793dd357eb7b', 'd22737f33f3e',
    '2f91e8fea8b5', 'e7a7f6d9e10d', '66f3c0cb1669', '550c2c739b1b',
))


if __name__ == '__main__':
    unittest.main()
