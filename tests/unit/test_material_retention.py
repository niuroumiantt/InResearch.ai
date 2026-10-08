import hashlib
import json
import sqlite3
import shutil
import tempfile
import unittest
from pathlib import Path
from inresearch.paths import project_root
from inresearch.materials.retention import audit


class RetentionTests(unittest.TestCase):
    def test_backup_live_wal_and_missing_original_are_reported_without_deletion(self):
        with tempfile.TemporaryDirectory() as t:
            data=Path(t);(data/'acquisition').mkdir();p=data/'acquisition/catalog.sqlite'
            db=sqlite3.connect(p);db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE observations(relative_path TEXT)')
            original=data/'source.txt';original.write_text('raw original')
            db.executemany('INSERT INTO observations VALUES(?)',[('source.txt',),('missing.txt',)])
            db.commit();before=hashlib.sha256(original.read_bytes()).hexdigest()
            try:
                result=audit(data,project_root(),True)
                self.assertEqual(result['catalogs']['acquisition/catalog.sqlite']['missing'],1)
                saved=next((data/'material-reviews/retention').rglob('*.sqlite'))
                backup=sqlite3.connect(saved)
                self.assertEqual(backup.execute('SELECT count(*) FROM observations').fetchone()[0],2)
                self.assertEqual(backup.execute('PRAGMA journal_mode').fetchone()[0],'delete');backup.close()
                portable=data/'portable.sqlite';shutil.copyfile(saved,portable)
                readonly=sqlite3.connect(portable.as_uri()+'?mode=ro',uri=True)
                try:self.assertEqual(readonly.execute('SELECT count(*) FROM observations').fetchone()[0],2)
                finally:readonly.close()
                self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0],'wal')
                self.assertFalse(result['automatic_deletion'])
                self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(),before)
            finally:db.close()
