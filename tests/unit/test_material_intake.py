import io
import os
import tempfile
import unittest
from unittest.mock import patch
from inresearch.materials import inbox as m

class IntakeTests(unittest.TestCase):
    def test_complete_duplicate_and_ack(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'INRESEARCH_INTAKE_ROOT':d}):
            a=m.receive(io.BytesIO(b'hello'),5,{'name':'../../报告.txt','topic':'泰国'},'tester')
            b=m.receive(io.BytesIO(b'hello'),5,{'name':'报告.txt'},'tester')
            self.assertNotEqual(a['id'],b['id'])
            self.assertEqual(a['sha256'],b['sha256'])
            self.assertEqual(a['name'],'报告.txt')
            with self.assertRaises(ValueError):m.acknowledge(a['id'],'wrong')
            self.assertEqual(m.acknowledge(a['id'],a['sha256'])['status'],'archived')
    def test_partial_not_visible(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {'INRESEARCH_INTAKE_ROOT':d}):
            with self.assertRaises(ValueError):m.receive(io.BytesIO(b'x'),5,{},'tester')
            self.assertEqual(m.records(),[])
            with self.assertRaises(ValueError):m.record_path('../escape')
            with self.assertRaises(ValueError):m.receive(io.BytesIO(),m.MAX_BYTES+1,{},'tester')
if __name__=='__main__':unittest.main()
