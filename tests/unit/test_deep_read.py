import io
import hashlib
import json
import random
import re
from collections import Counter
from contextlib import redirect_stdout, ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from inresearch.interfaces import deep_read as CLI
from inresearch.knowledge import fact_contract as FC, provenance as PROV
from inresearch.materials import reading_policy as POLICY, text_similarity as SIM
from inresearch.delivery import reading_packet as PACKET
from inresearch.storage import jsonl as JSONL
from inresearch.materials.records import result_revision
import inresearch.adapters.office_grid as office_grid
from deep_read_fixtures import (make_app, METRICS, SHA, fact, other, problems, problems_for,
    L1_ROW, PROVENANCE_DEBT, DANGLING_SOURCE_IDS, KNOWN_DIM_NAMES, FILLED_THIS_BATCH)
L2 = make_app()

class RecordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-test-')
        base = Path(self.temp.name)
        self.facts = base / 'facts.json'
        self.facts.write_text(json.dumps(
            {'version': '0.1', 'records': []}, ensure_ascii=False), encoding='utf-8')
        self._saved = (L2.facts_path, L2.receipt_log, L2.load_metrics, L2.all_results)
        L2.facts_path = self.facts
        L2.receipt_log = base / 'l2_read.jsonl'
        L2.load_metrics = lambda: METRICS
        # --doc 的完整哈希也要解得出一份判定（手打错一位的哈希不该通过），
        # 所以夹具把这几个 sha 注册进判定表。
        registered = {sha: {'sha256': sha, 'rel': '夹具.pdf', 'score': 9, 'status': 'ok'}
                      for sha in (SHA, 'b' * 64, 'c' * 64)}
        L2.all_results = lambda: registered

    def tearDown(self):
        (L2.facts_path, L2.receipt_log, L2.load_metrics, L2.all_results) = self._saved
        self.temp.cleanup()

    def record(self, facts, **flags):
        path = Path(self.temp.name) / 'incoming.json'
        path.write_text(json.dumps(facts, ensure_ascii=False), encoding='utf-8')
        args = type('A', (), {'facts': str(path), 'doc': flags.get('doc'),
                              'partial': flags.get('partial', False), 'show': 5})
        out = io.StringIO()
        with redirect_stdout(out):
            CLI.cmd_record(L2, args)
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

    def test_recording_marks_the_document_processed(self):
        self.record([fact()], doc=SHA)
        rows = [json.loads(l) for l in L2.receipt_log.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[0]['sha256'], SHA)
        self.assertEqual(rows[0]['facts'], 1)

    def test_failed_receipt_log_can_be_replayed_without_duplicate_facts(self):
        from unittest.mock import patch
        with patch.object(L2, 'remember_processing', side_effect=OSError('interrupted after fact commit')):
            with self.assertRaises(OSError):
                self.record([fact()], doc=SHA)
        report = self.record([fact()], doc=SHA)
        self.assertEqual(report['replayed'], 1)
        self.assertEqual(report['facts_total'], 1)
        self.assertTrue(L2.receipt_log.exists())

    def test_other_material_cannot_mark_this_document_processed(self):
        report = self.record([fact()], doc='b' * 64)
        self.assertEqual(report['accepted'], 0)
        self.assertFalse(L2.receipt_log.exists())
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

    def test_a_document_with_no_facts_still_has_processing_receipt(self):
        """Zero facts is a legitimate outcome; inventing one is not."""
        report = self.record([], doc='c' * 64)
        self.assertEqual(report['accepted'], 0)
        self.assertIn('c' * 64, L2.receipt_log.read_text(encoding='utf-8'))

    # -- --doc 收前缀 -----------------------------------------------------
    # 前缀原样写进已读台账，而队列只认完整 sha，于是文件没被记成已读、
    # 下一轮又被开了一次包。skip 与 attribute 都解前缀，只有 record 不解。
    # 用 SHA 本身的前缀：主干另有一条规矩——事实自证的 sha 必须与 --doc 一致，
    # 换个哈希会先撞上那一条，测不到前缀解析。
    def resolving(self, results):
        return patch.object(L2, 'all_results', lambda: results)

    def test_a_prefix_is_resolved_to_the_full_hash(self):
        with self.resolving({SHA: {'sha256': SHA, 'rel': '一份.pdf'}}):
            self.record([fact()], doc=SHA[:12])
        rows = [json.loads(l) for l in
                L2.receipt_log.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows[0]['sha256'], SHA)

    def test_a_prefix_that_matches_nothing_stops_before_anything_is_written(self):
        with self.resolving({}):
            with self.assertRaises(ValueError):
                self.record([fact()], doc=SHA[:12])
        self.assertEqual(json.loads(self.facts.read_text(encoding='utf-8'))['records'], [])
        self.assertFalse(L2.receipt_log.exists())

    def test_an_ambiguous_prefix_stops_too(self):
        with self.resolving({SHA: {'sha256': SHA},
                             'a' * 63 + 'b': {'sha256': 'a' * 63 + 'b'}}):
            with self.assertRaises(ValueError):
                self.record([fact()], doc=SHA[:12])
        self.assertEqual(json.loads(self.facts.read_text(encoding='utf-8'))['records'], [])

    def test_a_full_hash_that_names_no_document_is_refused(self):
        """手打错一位的 64 位哈希曾照样通过，还往已读台账写了一行垃圾。

        自证的前提是那串东西真的指向什么：不在判定里的完整哈希既进不了队列、
        也标不了任何文件为已读。
        """
        with self.resolving({}):
            with self.assertRaises(ValueError) as caught:
                self.record([fact()], doc=SHA)
        self.assertIn('完整哈希', str(caught.exception))
        self.assertEqual(json.loads(self.facts.read_text(encoding='utf-8'))['records'], [])
        self.assertFalse(L2.receipt_log.exists())


class EffectiveResultTests(unittest.TestCase):
    def test_failed_retry_does_not_remove_a_document_from_the_deep_read_queue(self):
        with tempfile.TemporaryDirectory(prefix='m4-l2-effective-') as directory:
            path = Path(directory) / 'results.jsonl'
            path.write_text('\n'.join(json.dumps(row) for row in [
                L1_ROW, {'sha256': L1_ROW['sha256'], 'status': 'error',
                         'error': 'model_timeout'}]) + '\n')
            with patch.object(L2.materials, 'RESULTS', path), \
                    patch.object(L2, 'processed_documents', return_value=set()), \
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
            with patch.object(L2.materials, 'RESULTS', path):
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
        self._saved = L2.materials.RESULTS
        L2.materials.RESULTS = self.results

    def tearDown(self):
        L2.materials.RESULTS = self._saved
        self.temp.cleanup()

    def attribute(self, **over):
        args = {'sha': 'd' * 8, 'org': None, 'unrecoverable': False, 'year': None,
                'title': None, 'evidence': '封面右下角',
                'expected_revision': result_revision(L2.all_results()[L1_ROW['sha256']])}
        args.update(over)
        out = io.StringIO()
        with redirect_stdout(out):
            CLI.cmd_attribute(L2, type('A', (), args))
        return json.loads(out.getvalue())

    def rows(self):
        return [json.loads(l) for l in
                self.results.read_text(encoding='utf-8').splitlines()]

    def test_an_unknown_publisher_is_asked_for(self):
        self.assertEqual(POLICY.unattributed(L1_ROW), ['org', 'year'])

    def test_a_named_publisher_is_not_asked_for(self):
        self.assertEqual(POLICY.unattributed({**L1_ROW, 'org': 'IDC', 'year': '2024'}), [])

    def test_an_empty_string_counts_as_unknown(self):
        self.assertIn('org', POLICY.unattributed({**L1_ROW, 'org': '  '}))

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
        self.assertEqual(POLICY.unattributed(row), [])

    def test_a_year_given_alongside_is_not_declared_missing(self):
        """忠县's shape: the publisher is on the cover, the year is nowhere."""
        self.attribute(unrecoverable=True, year='2024', evidence='无署名，年份取自封面')
        row = self.rows()[-1]
        self.assertEqual(row['unrecoverable'], ['org'])
        self.assertEqual(row['year'], '2024')

    def test_a_publisher_and_a_shrug_cannot_both_be_given(self):
        with self.assertRaises(ValueError):
            self.attribute(org='IDC', unrecoverable=True)

    def test_one_of_the_two_must_be_given(self):
        with self.assertRaises(ValueError):
            self.attribute()

    def test_a_year_that_is_not_a_year_is_refused(self):
        with self.assertRaises(ValueError):
            self.attribute(org='IDC', year='2024年')

    def test_an_ambiguous_sha_prefix_is_refused(self):
        with self.assertRaises(ValueError):
            self.attribute(sha='e' * 8, org='IDC')

    def test_nothing_is_renamed_here(self):
        report = self.attribute(org='IDC', year='2024')
        self.assertIn('restage', report['renamed_by'])

    def pack(self, row, meta=None):
        """Real inventoried bytes with a deterministic document extractor."""
        source = Path(self.temp.name) / 'source.txt'
        source.write_text('第一页正文\n\n[p.2] 第二页')
        row = {**row, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        saved = (L2.eligible, L2.extractor, L2.materials.readable_path,
                 L2.load_metrics, L2.load_questions, L2.load_facts, L2.packet_dir)
        L2.eligible = lambda min_score=8, include_processed=False, since=0: [row]
        L2.extractor = lambda path, suffix: ('第一页正文\n\n[p.2] 第二页',
                                            meta if meta is not None else {'pages': 2})
        L2.materials.readable_path = lambda r: (source, False)
        L2.load_metrics = lambda: METRICS
        L2.load_questions = lambda: {}
        L2.load_facts = lambda: {'records': []}
        L2.packet_dir = Path(self.temp.name) / 'packets'
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                CLI.cmd_pack(L2, type('A', (), {'sha': None, 'min_score': 8,
                                           'again': False, 'since': 0}))
            report = json.loads(out.getvalue())
            brief = Path(json.loads(out.getvalue())['brief']).read_text(encoding='utf-8')
        finally:
            (L2.eligible, L2.extractor, L2.materials.readable_path, L2.load_metrics,
             L2.load_questions, L2.load_facts, L2.packet_dir) = saved
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
        self.assertGreater(PACKET.FULL_TEXT_CHARS, 20 * office_grid.MAX_CHARS)

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
                 L2.all_results, L2.processed_documents)
        L2.eligible = lambda min_score=8, include_processed=False, since=0: rows
        L2.load_metrics = lambda: METRICS
        L2.load_facts = lambda: {'records': []}
        L2.all_results = lambda: {r['sha256']: r for r in rows}
        L2.processed_documents = lambda: set()
        try:
            out = io.StringIO()
            with redirect_stdout(out):
                CLI.cmd_queue(L2, type('A', (), {'min_score': 8, 'show': 5,
                                            'grep': self.grep, 'since': 0}))
        finally:
            (L2.eligible, L2.load_metrics, L2.load_facts,
             L2.all_results, L2.processed_documents) = saved
        return out.getvalue()

    def test_each_row_carries_the_hash_pack_needs(self):
        text = self.queue([L1_ROW])
        self.assertIn(L1_ROW['sha256'][:16], text.splitlines()[-1])
        candidate=json.loads(text.splitlines()[0])['candidates'][0]
        self.assertEqual(candidate['sha256'],L1_ROW['sha256'])
        self.assertEqual(candidate['result_revision'],result_revision(L1_ROW))

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
        self.assertIn('匹配「忠县」1 条（共 31 条待处理）', text)
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
        self.assertEqual(report['eligible_unprocessed'], 1)


class BarrenCohortTests(unittest.TestCase):
    """分数答的是「这事重不重要」，答不了「这份里有没有数」。

    一次 OCP 2025 会议的九份胶片与讨论环节粗筛都是 7 分，读完全是 0 条，
    却因为分数高排在前面，每轮吃掉一半名额。降权的判据只能是已经发生的事：
    同一家、同一年、同一体裁读过几份、出了几条。
    """

    def rows(self, *specs):
        out = {}
        for i, (org, year, doc_type) in enumerate(specs):
            sha = '%064x' % i
            out[sha] = {**L1_ROW, 'sha256': sha, 'org': org, 'year': year,
                        'doc_type': doc_type, 'score': 7, 'status': 'ok',
                        'rel': '%s-%d.pdf' % (org, i)}
        return out

    def app(self, rows, processed=(), produced=()):
        app = make_app()
        app.all_results = lambda: rows
        app.processed_documents = lambda: set(processed)
        app.load_facts = lambda: {'records': [
            {'evidence': {'sha256': sha}} for sha in produced]}
        app.coverage = lambda: Counter()
        return app

    def test_three_barren_siblings_demote_the_rest(self):
        rows = self.rows(*[('OCP', '2025', 'presentation')] * 5)
        shas = list(rows)
        app = self.app(rows, processed=shas[:3])
        self.assertEqual(list(app.barren_cohorts()), [('OCP', '2025', 'presentation')])

    def test_two_are_not_yet_a_pattern(self):
        rows = self.rows(*[('OCP', '2025', 'presentation')] * 5)
        app = self.app(rows, processed=list(rows)[:2])
        self.assertEqual(app.barren_cohorts(), {})

    def test_one_yield_clears_the_whole_cohort(self):
        """降权要能自己纠正——出了一条数，这批就不再算空。"""
        rows = self.rows(*[('OCP', '2025', 'presentation')] * 5)
        shas = list(rows)
        app = self.app(rows, processed=shas[:3], produced=[shas[0]])
        self.assertEqual(app.barren_cohorts(), {})

    def test_a_demoted_row_is_still_in_the_queue_just_last(self):
        rows = self.rows(*([('OCP', '2025', 'presentation')] * 4
                           + [('科智咨询', '2025', 'report')]))
        shas = list(rows)
        app = self.app(rows, processed=shas[:3])
        order = app.eligible(min_score=0)
        self.assertEqual(len(order), 2, '降权不是剔除，两条都还在队列里')
        self.assertEqual(order[0]['org'], '科智咨询')
        self.assertEqual(order[-1]['org'], 'OCP')

    def test_a_cohort_missing_org_or_year_is_never_demoted(self):
        """出处未知的材料凑不成一个批次，不能拿「未知」把它们归成一堆压掉。"""
        rows = self.rows(*[('未知', '未知', 'presentation')] * 5)
        app = self.app(rows, processed=list(rows)[:3])
        self.assertEqual(app.barren_cohorts(), {})

    def test_another_year_of_the_same_house_is_untouched(self):
        rows = self.rows(*([('OCP', '2025', 'presentation')] * 4
                           + [('OCP', '2024', 'presentation')]))
        app = self.app(rows, processed=list(rows)[:3])
        self.assertNotIn(('OCP', '2024', 'presentation'), app.barren_cohorts())


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
        self._saved = (L2.facts_path, L2.receipt_log, L2.load_metrics, L2.all_results)
        L2.facts_path, L2.receipt_log, L2.load_metrics = self.facts, base / 'read.jsonl', lambda: METRICS
        # --doc 的完整哈希也要解得出一份判定
        L2.all_results = lambda: {'e' * 64: {'sha256': 'e' * 64, 'rel': '空批次.pdf',
                                             'score': 9, 'status': 'ok'}}

    def tearDown(self):
        (L2.facts_path, L2.receipt_log, L2.load_metrics, L2.all_results) = self._saved
        self.temp.cleanup()

    def record(self, incoming, doc=None):
        path = Path(self.temp.name) / 'incoming.json'
        path.write_text(json.dumps(incoming, ensure_ascii=False), encoding='utf-8')
        out = io.StringIO()
        with redirect_stdout(out):
            CLI.cmd_record(L2, type('A', (), {'facts': str(path), 'doc': doc,
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
        self._saved = (L2.processed_documents, L2.all_results, L2.load_facts, L2.load_metrics)
        L2.processed_documents = lambda: {L1_ROW['sha256']}
        L2.all_results = lambda: {L1_ROW['sha256']: L1_ROW}
        L2.load_facts = lambda: {'records': []}
        L2.load_metrics = lambda: METRICS

    def tearDown(self):
        (L2.processed_documents, L2.all_results, L2.load_facts, L2.load_metrics) = self._saved
        self.temp.cleanup()

    def test_a_processed_document_is_out_of_the_queue(self):
        self.assertEqual(L2.eligible(8), [])

    def test_and_can_be_reopened_on_purpose(self):
        self.assertEqual([r['sha256'] for r in L2.eligible(8, include_processed=True)],
                         [L1_ROW['sha256']])

    def test_reopening_requires_naming_the_document(self):
        """Without --sha it would reopen whatever sorts first, which is not the ask."""
        with self.assertRaises(ValueError):
            CLI.cmd_pack(L2, type('A', (), {'sha': None, 'min_score': 8, 'again': True}))


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
        self._saved = (L2.materials.RESULTS, L2.load_metrics, L2.load_facts, L2.processed_documents)
        L2.materials.RESULTS = self.results
        L2.load_metrics = lambda: METRICS
        L2.load_facts = lambda: {'records': []}
        L2.processed_documents = lambda: set()

    def tearDown(self):
        (L2.materials.RESULTS, L2.load_metrics, L2.load_facts, L2.processed_documents) = self._saved
        self.temp.cleanup()

    def flag(self, **over):
        args = {'sha': L1_ROW['sha256'][:8], 'confidential': False, 'pii': False,
                'clear': False, 'evidence': '封面：Not to be distributed',
                'expected_revision': result_revision(L2.all_results()[L1_ROW['sha256']])}
        args.update(over)
        out = io.StringIO()
        with redirect_stdout(out):
            CLI.cmd_flag(L2, type('A', (), args))
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
        with self.assertRaises(ValueError):
            self.flag()

    def test_the_queue_counts_what_it_excluded(self):
        self.flag(confidential=True)
        out = io.StringIO()
        with redirect_stdout(out):
            CLI.cmd_queue(L2, type('A', (), {'min_score': 8, 'show': 5, 'grep': None, 'since': 0}))
        self.assertEqual(json.loads(out.getvalue().splitlines()[0])['restricted_excluded'], 1)


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
        self._saved = (L2.materials.RESULTS, L2.gaps.path, L2.receipt_log, L2.load_metrics,
                       L2.load_facts)
        L2.materials.RESULTS = self.results
        L2.gaps.path = base / 'metric_gaps.jsonl'
        L2.receipt_log = base / 'l2_read.jsonl'
        L2.load_metrics = lambda: METRICS
        L2.load_facts = lambda: {'records': []}

    def tearDown(self):
        (L2.materials.RESULTS, L2.gaps.path, L2.receipt_log, L2.load_metrics,
         L2.load_facts) = self._saved
        self.temp.cleanup()

    def skip(self, gaps, doc=None, reason=None):
        out = io.StringIO()
        with redirect_stdout(out):
            CLI.cmd_skip(L2, type('A', (), {'doc': doc or L1_ROW['sha256'][:8],
                                       'gap': gaps, 'reason': reason}))
        return json.loads(out.getvalue())

    def gaps(self, filled=()):
        out = io.StringIO()
        with redirect_stdout(out):
            CLI.cmd_gaps(L2, type('A', (), {'filled': list(filled)}))
        return out.getvalue()

    def test_the_queue_advances(self):
        self.assertEqual([r['sha256'] for r in L2.eligible(8)], [L1_ROW['sha256']])
        self.skip(['server_class 缺 x86'])
        self.assertEqual(L2.eligible(8), [])

    def test_the_gap_is_what_survives(self):
        report = self.skip(['server_class 缺 x86'])
        self.assertEqual(report['gaps_recorded'], 1)
        rows = L2.gaps.open()
        self.assertEqual([r['gap'] for r in rows], ['server_class 缺 x86'])
        self.assertEqual(rows[0]['sha256'], L1_ROW['sha256'])
        self.assertEqual(rows[0]['rel'], L1_ROW['rel'])

    def test_one_document_can_report_several_gaps(self):
        self.skip(['server_class 缺 x86', '缺 storage_scope 维度',
                   '缺 counterparty_role 维度'])
        self.assertEqual(len(L2.gaps.open()), 3)
        self.assertEqual(len({r['sha256'] for r in L2.gaps.open()}), 1)

    def test_the_same_gap_twice_is_one_gap(self):
        """两次翻同一份文件报同一个缺口，不该在菜单待办上算两笔。"""
        self.skip(['server_class 缺 x86'])
        self.skip(['server_class 缺 x86'])
        self.assertEqual(len(L2.gaps.open()), 1)

    def test_the_same_gap_from_another_document_is_a_separate_row(self):
        """counterparty_role 在三个模块都撞上了——那正是要看见的东西。"""
        # L1_ROW is 'd' * 64, so this one must not start with d - the fourth
        # time a fixture sha prefix has collided in this suite.
        other = {**L1_ROW, 'sha256': 'b7' + 'c' * 62, 'rel': '别的/文件.xlsx'}
        with self.results.open('a', encoding='utf-8') as fh:
            fh.write(json.dumps(other, ensure_ascii=False) + '\n')
        self.skip(['缺 counterparty_role 维度'])
        self.skip(['缺 counterparty_role 维度'], doc='b7cccccc')
        self.assertEqual(len(L2.gaps.open()), 2)

    def test_the_processing_receipt_preserves_the_skip_reason(self):
        """零条事实和「读了但存不下」印出来一样，就等于没记。"""
        self.skip(['server_class 缺 x86'], reason='整表都是 x86 口径')
        row = json.loads(L2.receipt_log.read_text(encoding='utf-8').splitlines()[-1])
        self.assertEqual(row['facts'], 0)
        self.assertEqual(row['skipped'], '整表都是 x86 口径')
        self.assertEqual(row['gaps'], [L2.gaps.open()[0]['gap_id']])

    def test_the_default_reason_is_the_menu(self):
        self.skip(['server_class 缺 x86'])
        row = json.loads(L2.receipt_log.read_text(encoding='utf-8').splitlines()[-1])
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
        with self.assertRaises(ValueError):
            self.skip(['随便'])

    def test_filling_a_gap_clears_it(self):
        gap_id = self.skip(['server_class 缺 x86'])['gap_ids'][0]
        self.gaps(filled=[gap_id])
        self.assertEqual(L2.gaps.open(), [])

    def test_filling_one_leaves_the_others(self):
        ids = self.skip(['缺 x86', '缺 storage_scope'])['gap_ids']
        self.gaps(filled=[ids[0]])
        self.assertEqual([r['gap'] for r in L2.gaps.open()], ['缺 storage_scope'])

    def test_filling_an_unknown_gap_is_refused(self):
        with self.assertRaises(ValueError):
            self.gaps(filled=['000000000000'])

    def test_filling_the_same_gap_twice_replays(self):
        """相同已完成请求可安全重放；未知 ID 仍拒绝。"""
        gap_id = self.skip(['缺 x86'])['gap_ids'][0]
        self.gaps(filled=[gap_id])
        report = json.loads(self.gaps(filled=[gap_id]))
        self.assertEqual(report['replayed'], 1)
        self.assertEqual(L2.gaps.open(), [])

    def test_the_listing_names_the_document_and_the_module(self):
        self.skip(['server_class 缺 x86'])
        listing = self.gaps()
        self.assertIn('server_class 缺 x86', listing)
        self.assertIn(L1_ROW['rel'], listing)
        self.assertIn('"open_gaps": 1', listing)

    def test_an_incomplete_tail_does_not_take_the_ledger_down(self):
        self.skip(['缺 x86'])
        with L2.gaps.path.open('a', encoding='utf-8') as fh:
            fh.write('{ 半行')
        self.assertEqual(len(L2.gaps.open()), 1)


class DeepReadJournalTests(unittest.TestCase):
    def test_committed_corruption_fails_and_torn_tail_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/'journal.jsonl'
            row = {'sha256': 'a' * 64, 'text_md5': 'ab', 'sketch': ['ab'], 'gap_id': 'g'}
            data = (json.dumps(row) + '\n').encode()
            for obj, attr, reader in [(L2, 'receipt_log', L2.processed_documents), (L2.similarity, 'path', L2.similarity.fingerprints),
                                 (L2.similarity, 'path', L2.similarity.sketches), (L2.gaps, 'path', L2.gaps.open)]:
                with self.subTest(reader=reader.__name__), patch.object(obj, attr, path):
                    path.write_bytes(data)
                    expected = reader()
                    path.write_bytes(data + b'{unfinished')
                    self.assertEqual(expected, reader())
                    self.assertEqual(data + b'{unfinished', path.read_bytes())
                    path.write_bytes(data + b'{broken}\n' + data)
                    with self.assertRaisesRegex(ValueError, 'invalid JSON record'):
                        reader()


class TextTwinRoutingTests(unittest.TestCase):
    """Equal extracted text is a review hint, not original identity or full coverage."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-twin-')
        base = Path(self.temp.name)
        self._saved = (L2.similarity.path, L2.receipt_log, L2.eligible, L2.extractor,
                       L2.materials.readable_path, L2.load_metrics, L2.load_questions,
                       L2.load_facts, L2.packet_dir)
        L2.similarity.path = base / 'l2_text_md5.jsonl'
        L2.receipt_log = base / 'l2_read.jsonl'
        L2.packet_dir = base / 'packets'
        self.text = '中国第三方数据中心运营商分析报告。' * 60
        source = base / 'copy.pdf'
        source.write_bytes('另一个字节序列'.encode('utf-8'))
        self.row = {**L1_ROW, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
        L2.eligible = lambda min_score=8, include_processed=False, since=0: [self.row]
        L2.extractor = lambda path, suffix: (self.text, {'pages': 41})
        L2.materials.readable_path = lambda r: (source, False)
        L2.load_metrics = lambda: METRICS
        L2.load_questions = lambda: {}
        L2.load_facts = lambda: {'records': []}
        # 已读过的那一份：同一正文、另一个 sha
        L2.similarity.remember('a' * 64, SIM.text_fingerprint(self.text, {'pages': 41}))
        L2.receipt_log.write_text(json.dumps({'sha256': 'a' * 64, 'facts': 3}) + '\n',
                               encoding='utf-8')

    def tearDown(self):
        (L2.similarity.path, L2.receipt_log, L2.eligible, L2.extractor, L2.materials.readable_path,
         L2.load_metrics, L2.load_questions, L2.load_facts, L2.packet_dir) = self._saved
        self.temp.cleanup()

    def pack(self, again=False):
        out = io.StringIO()
        with redirect_stdout(out), patch.object(L2, 'all_results', return_value={self.row['sha256']: self.row}):
            CLI.cmd_pack(L2, type('A', (), {'sha': self.row['sha256'][:12] if again else None,
                                       'min_score': 8, 'again': again, 'since': 0}))
        return json.loads(out.getvalue())

    def test_same_extracted_text_different_bytes_still_gets_its_own_packet(self):
        before = L2.receipt_log.read_bytes()
        report = self.pack()
        self.assertEqual(report['packed'], 1)
        self.assertEqual(report['sha256'], self.row['sha256'])
        self.assertEqual(report['same_text_already_processed'], ['a' * 64])
        self.assertNotIn(self.row['sha256'], L2.processed_documents())
        self.assertEqual(before, L2.receipt_log.read_bytes())
        self.assertTrue(Path(report['text']).is_file())

    def test_again_reopens_a_processed_document(self):
        JSONL.append_record(L2.receipt_log, {'sha256': self.row['sha256'], 'facts': 3})
        report = self.pack(again=True)
        self.assertEqual(report['packed'], 1)
        self.assertTrue(report['again'])

    def test_old_automatic_twin_record_is_preserved_but_not_counted_as_processed(self):
        JSONL.append_record(L2.receipt_log, {'sha256': self.row['sha256'], 'facts': 0, 'twin_of': ['a' * 64]})
        before = L2.receipt_log.read_bytes()
        self.assertNotIn(self.row['sha256'], L2.processed_documents())
        self.assertIn('a' * 64, L2.processed_documents())
        self.assertEqual(before, L2.receipt_log.read_bytes())
        # A later actual full read with no facts remains a valid completion.
        JSONL.append_record(L2.receipt_log, {'sha256': self.row['sha256'], 'facts': 0})
        self.assertIn(self.row['sha256'], L2.processed_documents())
        self.assertTrue(L2.receipt_log.read_bytes().startswith(before))


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
        self._saved = (L2.materials.RESULTS, L2.facts_path, L2.root)
        L2.materials.RESULTS = self.ledger
        L2.facts_path = self.facts
        L2.root = base                      # 没有 sources.json，走前缀这条路

    def tearDown(self):
        (L2.materials.RESULTS, L2.facts_path, L2.root) = self._saved
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
            CLI.cmd_backfill_provenance(L2, type('A', (), {'commit': commit, 'show': 5,
                'expected_plan': L2.backfill_provenance()['plan_sha256'] if commit else None}))
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
        """如实报告剩余缺口，不让命令自动降低测试基线。"""
        self.write([{'source_id': self.SHA[:12]}, {'source_id': 'ffffffffffff'}],
                   [self.SHA])
        report, text = self.run_it(commit=True)
        self.assertEqual(report['owing_after'], 1)
        self.assertIn('不自动修改测试基线', text)

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
        (L2.materials.RESULTS, L2.facts_path, L2.root) = self._saved
        store = L2.load_facts()
        owing = PROV.owing_provenance(store['records'])
        self.assertEqual(len(owing), PROVENANCE_DEBT)
        abbreviated = [f for f in owing
                       if PROV.HEX12.match(str((f['evidence'] or {}).get('source_id') or ''))]
        self.assertEqual(abbreviated, [], '还有能按缓存键还的债没还')

    def test_cache_keys_are_not_sha256_prefixes(self):
        """这条钉住上面那句话里最容易被想当然的部分。"""
        (L2.materials.RESULTS, L2.facts_path, L2.root) = self._saved
        remap = json.loads(L2.cache_remap.read_text(encoding='utf-8'))
        ledger = L2.all_results()
        prefixes = {sha[:12] for sha in ledger}
        collide = [k for k in remap if k in prefixes]
        self.assertEqual(collide, [],
                         '缓存键与 sha256 前缀撞上了，按前缀 join 会写错哈希')




class DisputeRecordTests(unittest.TestCase):
    """争议进库之后要能被找到：反向链接与一屏可审的报告。"""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-dispute-')
        base = Path(self.temp.name)
        self.facts = base / 'facts.json'
        prior = fact(fact_id='miit-2021', value=94.0, asserter='工信部')
        self.facts.write_text(json.dumps({'records': [prior]}, ensure_ascii=False),
                              encoding='utf-8')
        self.app = make_app()
        self.addCleanup(self.app._test_temporary.cleanup)
        self.app.facts_path = self.facts
        self.app.receipt_log = base / 'l2_read.jsonl'
        self.app.load_metrics = lambda: METRICS

    def tearDown(self):
        self.temp.cleanup()

    def record(self, facts):
        path = Path(self.temp.name) / 'incoming.json'
        path.write_text(json.dumps(facts, ensure_ascii=False), encoding='utf-8')
        out = io.StringIO()
        with redirect_stdout(out):
            CLI.cmd_record(self.app, type('A', (), {'facts': str(path), 'doc': None,
                                         'partial': False, 'show': 5}))
        lines = out.getvalue().splitlines()
        return json.loads(lines[0]), '\n'.join(lines[1:])

    def test_the_other_side_learns_it_is_contested(self):
        report, _ = self.record([fact(fact_id='caict-2021', value=111.6,
                                      asserter='中国信通院', disputes=['miit-2021'])])
        self.assertEqual(report['accepted'], 1)
        self.assertEqual(report['disputes_recorded'], 1)
        stored = {f['fact_id']: f for f in
                  json.loads(self.facts.read_text(encoding='utf-8'))['records']}
        self.assertEqual(stored['miit-2021']['disputed_by'], ['caict-2021'])

    # -- A 档分诊 --------------------------------------------------------
    # 一份文献综述里十几个估计两两相连是几十对「争议」，全送进 A 档就把 A 档
    # 淹掉，而淹掉比没有更糟：它让真正要人看的那几条排在第二十位。
    def test_a_spread_within_method_noise_does_not_queue_for_the_owner(self):
        """94 与 111.6 差 18%，是两家估计的离散，不是有人错了一个数量级。"""
        report, tail = self.record([fact(fact_id='caict-2021', value=111.6,
                                         asserter='中国信通院', disputes=['miit-2021'])])
        self.assertEqual(report['disputes_pending_a'], 0)
        self.assertEqual(report['disputes'][0]['kind'], FC.METHOD_DISPERSION)
        self.assertIn('方法离散', tail)

    def test_an_order_of_magnitude_gap_does_queue_for_the_owner(self):
        """1,103 对 94 差 11.7 倍，必有一方口径不同或算错，要人看。"""
        report, tail = self.record([fact(fact_id='ictresearch-2021', value=1103.43,
                                         asserter='ICTresearch', disputes=['miit-2021'])])
        self.assertEqual(report['disputes_pending_a'], 1)
        self.assertEqual(report['disputes'][0]['kind'], FC.ORDER_OF_MAGNITUDE)
        self.assertIn('C3 A 档待审', tail)

    def test_both_values_are_printed_side_by_side_for_the_owner(self):
        _, tail = self.record([fact(fact_id='ictresearch-2021', value=1103.43,
                                    asserter='ICTresearch', disputes=['miit-2021'])])
        self.assertIn('C3 A 档待审', tail)
        self.assertIn('工信部', tail)
        self.assertIn('ICTresearch', tail)
        self.assertIn('94', tail)
        self.assertIn('1103.43', tail)

    def test_a_withheld_side_is_treated_as_needing_the_owner(self):
        """看不见的差距不能假定它小。"""
        self.assertEqual(FC.dispute_kind(None), FC.ORDER_OF_MAGNITUDE)
        self.assertIsNone(FC.value_spread([{'value': None}, {'value': 94.0}]))
