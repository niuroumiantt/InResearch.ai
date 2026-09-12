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
import re
from contextlib import redirect_stdout
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m4_l2 as L2
import m4_office_text

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
        self.record([fact()], doc='b' * 64)
        rows = [json.loads(l) for l in L2.READ_LOG.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[0]['sha256'], 'b' * 64)
        self.assertEqual(rows[0]['facts'], 1)

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
        store = json.loads((Path(L2.__file__).resolve().parent.parent /
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
        """cmd_pack with the filesystem and the model stubbed out."""
        saved = (L2.eligible, L2.full_text, L2.L1.readable_path,
                 L2.load_metrics, L2.load_questions, L2.load_facts, L2.PACKET_DIR)
        L2.eligible = lambda min_score=8, include_read=False, since=0: [row]
        L2.full_text = lambda path, suffix: ('第一页正文\n\n[p.2] 第二页',
                                            meta if meta is not None else {'pages': 2})
        L2.L1.readable_path = lambda r: (Path('/nonexistent'), False)
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
        self.assertIn('attribute --sha ' + L1_ROW['sha256'][:16], brief)

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
        self.assertGreater(L2.FULL_TEXT_CHARS, 20 * m4_office_text.MAX_CHARS)

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
PROVENANCE_DEBT = 119

# Facts cite a source_id, and most of those ids name no row in sources.json.
# check_fact cannot see this - it never reads sources.json - so it is pinned
# here instead, where it stays visible until someone decides what to do.
DANGLING_SOURCE_IDS = 27


class LiveFactLayerTests(unittest.TestCase):
    def setUp(self):
        self.repo = Path(L2.__file__).resolve().parent.parent
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
        store = json.loads((Path(L2.__file__).resolve().parent.parent /
                            'data/facts.json').read_text(encoding='utf-8'))
        rows = [f for f in store['records']
                if f['metric_id'] in ('server_mfg_revenue', 'server_asp')]
        self.assertTrue(rows)
        for f in rows:
            self.assertIn('storage_scope', f.get('caliber') or {}, f['fact_id'])

    def test_no_storage_row_was_backfilled_as_not_applicable(self):
        """存储行的口径要人判，机械回填成「不适用」就是造一条假事实。"""
        store = json.loads((Path(L2.__file__).resolve().parent.parent /
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
        store = json.loads((Path(L2.__file__).resolve().parent.parent /
                            'data/facts.json').read_text(encoding='utf-8'))
        rows = [f for f in store['records']
                if f['metric_id'] == 'optics_module_shipment']
        self.assertGreater(len(rows), 30)
        for f in rows:
            self.assertEqual(f['caliber'].get('product_form'), '光模块', f['fact_id'])
            self.assertEqual(f['caliber'].get('customer'), '未拆分', f['fact_id'])


if __name__ == '__main__':
    unittest.main()
