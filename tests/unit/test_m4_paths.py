#!/usr/bin/env python3
"""Redirecting a run must redirect its books too, or two corpora share one ledger."""
import os
from pathlib import Path
import tempfile
import unittest

from inresearch.materials import paths as P

VARS = ('INRESEARCH_SOURCE', 'INRESEARCH_LIBRARY', 'INRESEARCH_DATASET')


class PathTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: os.environ.get(k) for k in VARS}
        for k in VARS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._saved.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v

    def test_defaults_reproduce_the_original_run(self):
        self.assertEqual(str(P.source()), P.DEFAULT_SOURCE)
        self.assertEqual(str(P.library()), P.DEFAULT_LIBRARY)
        self.assertEqual(P.data().name, 'm4-triage')
        self.assertEqual(P.state().name, 'm4-triage')

    def test_source_and_library_follow_the_environment(self):
        os.environ['INRESEARCH_SOURCE'] = '/Volumes/NAS/资料'
        os.environ['INRESEARCH_LIBRARY'] = '/Volumes/NAS/资料库'
        self.assertEqual(str(P.source()), '/Volumes/NAS/资料')
        self.assertEqual(str(P.library()), '/Volumes/NAS/资料库')

    def test_a_second_corpus_gets_its_own_ledgers(self):
        os.environ['INRESEARCH_DATASET'] = 'nas'
        self.assertEqual(P.data().name, 'nas')
        self.assertEqual(P.state().name, 'nas')
        os.environ['INRESEARCH_DATASET'] = 'm4-triage'
        self.assertNotEqual(P.data().name, 'nas')

    def test_an_empty_value_falls_back_to_the_default(self):
        os.environ['INRESEARCH_SOURCE'] = ''
        self.assertEqual(str(P.source()), P.DEFAULT_SOURCE)

    def test_a_dataset_name_with_a_slash_is_refused(self):
        for bad in ('a/b', '..', '.', '', '   '):
            os.environ['INRESEARCH_DATASET'] = bad
            with self.assertRaises(SystemExit):
                P.data()

    def test_volume_of_resolves_a_library_that_does_not_exist_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            here = Path(tmp)
            unborn = here / 'not' / 'created' / 'yet'
            self.assertFalse(unborn.exists())
            self.assertEqual(P.volume_of(unborn), P.volume_of(here))

    def test_same_volume_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'src'; src.mkdir()
            lib = Path(tmp) / 'lib'
            P.require_same_volume(src, lib)   # must not raise

    def test_different_volumes_are_refused_before_anything_moves(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'src'; src.mkdir()
            lib = Path(tmp) / 'lib'
            real = P.volume_of
            P.volume_of = lambda p: 1 if Path(p) == src else 2
            try:
                with self.assertRaises(SystemExit) as caught:
                    P.require_same_volume(src, lib)
                self.assertIn('different volumes', str(caught.exception))
            finally:
                P.volume_of = real


if __name__ == '__main__':
    unittest.main()
