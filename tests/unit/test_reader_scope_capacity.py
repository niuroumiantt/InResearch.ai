"""Explicit large user batches remain bounded and fail closed."""
import json
import tempfile
import unittest
from pathlib import Path
from inresearch.workflow.reader_scope import DocumentScope

class ScopeCapacityTests(unittest.TestCase):
    def test_large_explicit_batch_preserves_every_content_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'scope.json'
            ids=['doc-'+format(i,'064x') for i in range(10000)]
            path.write_text(json.dumps({'schema_version':1,'doc_ids':ids}))
            self.assertLess(path.stat().st_size,1024*1024)
            self.assertEqual(DocumentScope(path,Path(tmp)).ids(),ids)
            path.write_text(json.dumps({'schema_version':1,'doc_ids':ids+['doc-'+format(10000,'064x')]}))
            with self.assertRaises(ValueError):DocumentScope(path,Path(tmp))

    def test_bad_large_batch_does_not_open_the_whole_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'scope.json'
            ids=['doc-'+format(i,'064x') for i in range(5500)]
            ids[-1]='doc-not-a-content-identity'
            path.write_text(json.dumps({'schema_version':1,'doc_ids':ids}))
            with self.assertRaises(ValueError):DocumentScope(path,Path(tmp))
            path.write_bytes(b' '* (1024*1024+1))
            with self.assertRaises(ValueError):DocumentScope(path,Path(tmp))

if __name__=='__main__':unittest.main()
