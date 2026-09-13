import io
import hashlib
import json
import random
import re
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

class TextFingerprintTests(unittest.TestCase):
    """同一份报告的两个副本，字节不同、sha256 不同，正文一字不差。

    M4 撞到的：两份中国信通院第三方运营商报告，41 页、23,935 字、正文 md5
    完全一致，sha256 不同，于是排进阅读队列两次。sha256 认的是字节，
    读者认的是内容——去重要在内容那一层做。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-fp-')
        base = Path(self.temp.name)
        self._saved = (L2.similarity.path, L2.read_documents)
        L2.similarity.path = base / 'l2_text_md5.jsonl'
        L2.read_documents = lambda: set(self.read)
        self.read = set()

    def tearDown(self):
        (L2.similarity.path, L2.read_documents) = self._saved
        self.temp.cleanup()

    def fp(self, text, pages=41):
        return SIM.text_fingerprint(text, {'pages': pages})

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
        L2.similarity.remember('a' * 64, 'deadbeef')
        self.assertEqual(L2.similarity.same_text('b' * 64, 'deadbeef', L2.read_documents(), read=True), [])
        self.read.add('a' * 64)
        self.assertEqual(L2.similarity.same_text('b' * 64, 'deadbeef', L2.read_documents(), read=True),
                         ['a' * 64])

    def test_a_document_is_never_its_own_twin(self):
        L2.similarity.remember('a' * 64, 'deadbeef')
        self.read.add('a' * 64)
        self.assertEqual(L2.similarity.same_text('a' * 64, 'deadbeef', L2.read_documents(), read=True), [])

    def test_no_fingerprint_means_no_twin_check(self):
        L2.similarity.remember('a' * 64, 'deadbeef')
        self.read.add('a' * 64)
        self.assertEqual(L2.similarity.same_text('b' * 64, None, L2.read_documents(), read=True), [])

    def test_an_incomplete_tail_does_not_take_the_ledger_down(self):
        L2.similarity.remember('a' * 64, 'deadbeef')
        with L2.similarity.path.open('a', encoding='utf-8') as fh:
            fh.write('{ 半行')
        self.assertEqual(L2.similarity.fingerprints(), {'a' * 64: 'deadbeef'})

    # -- 开包了但还没读的副本 ---------------------------------------------
    def test_a_packed_but_unread_copy_is_reported(self):
        """第三对副本就是这么漏的：两份同一轮开包，都还没读，什么都没响。"""
        L2.similarity.remember('a' * 64, 'deadbeef')
        self.assertEqual(
            L2.similarity.same_text('b' * 64, 'deadbeef', L2.read_documents(), read=False), ['a' * 64])

    def test_a_read_copy_is_not_reported_here(self):
        """已读的那条路由 already_read_with_same_text 管，两边不重复报。"""
        L2.similarity.remember('a' * 64, 'deadbeef')
        self.read.add('a' * 64)
        self.assertEqual(
            L2.similarity.same_text('b' * 64, 'deadbeef', L2.read_documents(), read=False), [])

    def test_a_document_is_never_its_own_open_twin(self):
        L2.similarity.remember('a' * 64, 'deadbeef')
        self.assertEqual(
            L2.similarity.same_text('a' * 64, 'deadbeef', L2.read_documents(), read=False), [])

    def test_no_fingerprint_means_no_open_twin_check(self):
        L2.similarity.remember('a' * 64, 'deadbeef')
        self.assertEqual(L2.similarity.same_text('b' * 64, None, L2.read_documents(), read=False), [])

    def test_the_last_write_wins(self):
        """重抽一遍得到不同的正文（抽取器修好了），以新的为准。"""
        L2.similarity.remember('a' * 64, 'old')
        L2.similarity.remember('a' * 64, 'new')
        self.assertEqual(L2.similarity.fingerprints()['a' * 64], 'new')


class NearTwinTests(unittest.TestCase):
    """丢了一页的副本：text_md5 一字不差才算，这里管「差一页」。

    M4 撞到的：信通院《智算中心液冷产业全景研究报告（2025 年）》三个 PDF，
    28,615 / 28,932 / 29,032 字符，差的是版权声明页与页眉，三个 text_md5
    互不相同，于是什么都没响。前缀指纹也救不了——差的那一页在最前面。
    """

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='m4-l2-near-')
        base = Path(self.temp.name)
        self._saved = (L2.similarity.path, L2.read_documents)
        L2.similarity.path = base / 'l2_text_md5.jsonl'
        L2.read_documents = lambda: set(self.read)
        self.read = set()
        rng = random.Random(7)
        vocab = ['液冷', '智算中心', '冷板', '浸没', '单相', '相变', 'PUE', '机柜',
                 '服务器', '部署', '产业', '标准', '测试', '运营商', '能效']
        self.body = ''.join(rng.choice(vocab) for _ in range(4000))
        self.other = ''.join(rng.choice(vocab) for _ in range(4000))
        self.copyright_page = '版权声明本报告版权属于中国信息通信研究院引用请注明来源' * 15

    def tearDown(self):
        (L2.similarity.path, L2.read_documents) = self._saved
        self.temp.cleanup()

    def test_a_copy_missing_a_page_is_a_near_twin(self):
        full, short = self.copyright_page + self.body, self.body
        self.assertNotEqual(SIM.text_fingerprint(full, {'pages': 28}),
                            SIM.text_fingerprint(short, {'pages': 28}))
        self.assertGreaterEqual(
            SIM.sketch_overlap(SIM.text_sketch(full), SIM.text_sketch(short)),
            SIM.NEAR_TWIN_RATIO)

    def test_a_different_report_of_the_same_length_is_not(self):
        self.assertLess(
            SIM.sketch_overlap(SIM.text_sketch(self.body), SIM.text_sketch(self.other)),
            SIM.NEAR_TWIN_RATIO)

    def test_a_shared_front_matter_with_a_different_body_is_not(self):
        """同一模板的两份季报共用很长的开头，那不是副本。"""
        head = self.body[:2000]
        self.assertLess(
            SIM.sketch_overlap(SIM.text_sketch(head + self.body[2000:]),
                              SIM.text_sketch(head + self.other[2000:])),
            SIM.NEAR_TWIN_RATIO)

    def test_too_little_text_gets_no_sketch(self):
        self.assertEqual(SIM.text_sketch('目录'), [])

    def test_the_ledger_reports_who_it_overlaps_and_whether_it_was_read(self):
        sketch = SIM.text_sketch(self.copyright_page + self.body)
        L2.similarity.remember('a' * 64, 'deadbeef', SIM.text_sketch(self.body))
        found = L2.similarity.near_twins('b' * 64, sketch, L2.read_documents())
        self.assertEqual([t['sha256'] for t in found], ['a' * 64])
        self.assertFalse(found[0]['read'])
        self.read.add('a' * 64)
        self.assertTrue(L2.similarity.near_twins('b' * 64, sketch, L2.read_documents())[0]['read'])

    def test_a_document_is_never_its_own_near_twin(self):
        sketch = SIM.text_sketch(self.body)
        L2.similarity.remember('a' * 64, 'deadbeef', sketch)
        self.assertEqual(L2.similarity.near_twins('a' * 64, sketch, L2.read_documents()), [])

    def test_a_ledger_row_without_a_sketch_is_skipped_not_fatal(self):
        """#159 之前写进账本的行只有 text_md5，没有 sketch。"""
        L2.similarity.remember('a' * 64, 'deadbeef')
        self.assertEqual(L2.similarity.sketches(), {})
        self.assertEqual(L2.similarity.near_twins('b' * 64, SIM.text_sketch(self.body), L2.read_documents()), [])

    def test_an_empty_sketch_never_matches(self):
        self.assertEqual(SIM.sketch_overlap([], []), 0.0)
        self.assertEqual(SIM.sketch_overlap(['aa'], []), 0.0)


