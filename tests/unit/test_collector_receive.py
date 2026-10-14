import copy
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from inresearch.materials.collector_receive import receive
from tests.unit.test_collector_handoff import example


class LocalCollectorReceiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.package = example.build(self.root/'input', 'fetchstat')
        self.sandbox = self.root/'sandbox'

    def counts(self):
        with sqlite3.connect(self.sandbox/'receipts.sqlite3') as db:
            return {t: db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('deliveries','originals','items','observations','delivery_observations')}

    def mutate_delivery(self, identifier):
        p=self.package/'manifest.json'; m=json.loads(p.read_text());m['delivery_id']=identifier;p.write_text(json.dumps(m))

    def test_replay_preserves_receipt_clocks_counts_and_input_bytes(self):
        before={str(p.relative_to(self.package)):p.read_bytes() for p in self.package.rglob('*') if p.is_file()}
        first=receive(self.package,self.sandbox); counts=self.counts()
        again=receive(self.package,self.sandbox)
        self.assertEqual(first['first_received_at'],again['first_received_at'])
        self.assertTrue(again['replayed']);self.assertEqual(counts,self.counts())
        self.assertEqual(again['current_receive_counts']['new_candidates'],0)
        self.assertFalse(again['formal_adoption']);self.assertTrue(again['local_only'])
        self.assertEqual(before,{str(p.relative_to(self.package)):p.read_bytes() for p in self.package.rglob('*') if p.is_file()})

    def test_same_delivery_changed_metadata_is_collision(self):
        receive(self.package,self.sandbox); counts=self.counts()
        p=self.package/'manifest.json';m=json.loads(p.read_text());m['generated_at']='2026-10-14T03:00:00Z';p.write_text(json.dumps(m))
        with self.assertRaisesRegex(ValueError,'delivery ID collision'):receive(self.package,self.sandbox)
        self.assertEqual(counts,self.counts())

    def test_new_delivery_can_reference_same_candidate_without_duplicate(self):
        a=receive(self.package,self.sandbox)
        self.mutate_delivery('new-envelope')
        b=receive(self.package,self.sandbox)
        self.assertEqual(b['counts']['new_candidates'],0)
        self.assertEqual(b['counts']['new_originals'],0)
        self.assertEqual(self.counts()['deliveries'],2)
        self.assertEqual(self.counts()['observations'],1)
        with sqlite3.connect(self.sandbox/'receipts.sqlite3') as db:
            self.assertEqual(db.execute('SELECT first_received_at FROM observations').fetchone()[0],a['first_received_at'])

    def test_changed_observation_id_payload_rolls_back_whole_package(self):
        receive(self.package,self.sandbox);counts=self.counts()
        self.mutate_delivery('collision-in-new-envelope')
        p=self.package/'observations.jsonl';r=json.loads(p.read_text());r['scope'] += '; tampered scope'
        p.write_text(json.dumps(r)+'\n')
        with self.assertRaisesRegex(ValueError,'observation ID collision'):receive(self.package,self.sandbox)
        self.assertEqual(counts,self.counts())

    def test_invalid_candidate_and_native_sha_tamper_do_not_receive(self):
        p=self.package/'observations.jsonl';good=p.read_bytes();r=json.loads(good);r['adopted']=True;p.write_text(json.dumps(r)+'\n')
        with self.assertRaises(ValueError):receive(self.package,self.sandbox)
        self.assertFalse(self.sandbox.exists())
        p.write_bytes(good)
        next((self.package/'originals').iterdir()).write_bytes(b'tampered')
        with self.assertRaises(ValueError):receive(self.package,self.sandbox)
        self.assertFalse(self.sandbox.exists())

    def test_all_four_provider_namespaces_stay_independent(self):
        receive(self.package,self.sandbox)
        for team in ('fetchfilings','fetchreports','fetchquotes'):
            p=example.build(self.root/team,team);result=receive(p,self.sandbox)
            self.assertEqual(result['provider_id'],team)
        self.assertEqual(self.counts()['deliveries'],4)
        self.assertEqual(self.counts()['observations'],4)

    def test_unmarked_existing_directory_is_not_a_database_target(self):
        self.sandbox.mkdir();(self.sandbox/'important.sqlite3').write_bytes(b'unique')
        with self.assertRaisesRegex(ValueError,'unmarked'):receive(self.package,self.sandbox)
        self.assertEqual((self.sandbox/'important.sqlite3').read_bytes(),b'unique')

    def test_archive_tamper_is_not_healed_by_replay(self):
        result=receive(self.package,self.sandbox)
        stored=self.sandbox/'packages'/result['package_sha256']/'observations.jsonl';stored.write_text('tampered\n')
        with self.assertRaisesRegex(ValueError,'archive changed'):receive(self.package,self.sandbox)
        self.assertEqual(stored.read_text(),'tampered\n')

    def test_new_source_version_keeps_both_originals_and_candidates(self):
        receive(self.package,self.sandbox)
        import hashlib
        mpath=self.package/'manifest.json'; m=json.loads(mpath.read_text());item=m['items'][0]; oldpath=self.package/item['path']
        data=oldpath.read_bytes()+b'\nnew source version';sha=hashlib.sha256(data).hexdigest();newpath='originals/'+sha+'.html'
        (self.package/newpath).write_bytes(data);oldid=item['item_id'];item.update(item_id='new-source-item',sha256=sha,path=newpath,version_of=oldid)
        m['delivery_id']='new-version';mpath.write_text(json.dumps(m));(self.package/'SHA256SUMS').write_text(sha+'  '+newpath+'\n')
        p=self.package/'observations.jsonl';r=json.loads(p.read_text());oldobs=r['observation_id'];r.update(observation_id='new-observation',source_item_id=item['item_id'],revision_of=oldobs);p.write_text(json.dumps(r)+'\n')
        result=receive(self.package,self.sandbox)
        self.assertEqual(result['counts']['new_originals'],1)
        self.assertEqual(self.counts()['originals'],2)
        self.assertEqual(self.counts()['observations'],2)

if __name__=='__main__':unittest.main()
