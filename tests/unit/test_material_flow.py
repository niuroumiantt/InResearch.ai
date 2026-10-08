"""Read-only aggregates, authority boundaries and missing measurements."""
import copy
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from inresearch.delivery import material_measurements as measurements
from inresearch.interfaces import material_flow


def measured_fixture():
    # Explicit UI fixture; these figures do not certify production measurements.
    return {'schema_version':1,'generated':'2026-10-08T04:01:00+00:00',
        'received_at':'2026-10-08T03:57:58+00:00','stale':False,
        'measurements':{'schema_version':1,'measured_at':'2026-10-08T04:01:00+00:00',
            'archive':{'state':'observed','measured_at':'2026-10-08T04:00:00+00:00',
                'allocated_bytes':447653093376,'directories':{'raw-materials':268057616384,
                'originals':106770440192,'incoming':48288755712,'extracted':16665784320,
                'backups':198000000},'other_bytes':7672496768},
            'catalog':{'files':36047,'content_identities':36047,'size_bytes':106543438635,
                'types':[{'suffix':'.pdf','files':12728,'size_bytes':10},
                         {'suffix':'.txt','files':12770,'size_bytes':10},
                         {'suffix':'.dwg','files':3947,'size_bytes':10}],
                'states':{'complete':137,'queued':11689,'blocked':24211,'failed':10}},
            'candidates':{'scope':'current_batch','documents':135,'statements':16028,'evidence':17347},
            'databases':{'reader':{'state':'observed','file_bytes':209285120,'wal_bytes':4391952,
                                    'shm_bytes':32768,'index_bytes':73175040},
                'acquisition':{'state':'observed','file_bytes':60862464,'wal_bytes':0,'shm_bytes':0,'index_bytes':6705152},
                'review':{'state':'observed','file_bytes':9617408,'wal_bytes':4000552,'shm_bytes':32768,'index_bytes':0}}},
        'execution_scope':{'documents':135,'counts':{'complete':135},'types':{'.pdf':71,'.html':64},
            'chunks_read':2474,'chunks_total':2474,'complete_with_gaps':17,'unread_gap_pages':18,
            'skipped_image_pages':1063,'text_layer_empty_pages':3},
        'review':{'state':'observed','candidates':{'queued':9819,'reviewing':12,'review_ready':7,'background':6161,'published':10,'already_adopted':19}},
        'formal':{'statements':29,'projects':126,'contracts':8},
        'website':{'measured_at':'2026-10-08T04:01:00+00:00','allocated_bytes':227868672,
            'candidate_snapshot_bytes':78715015,'product_database_bytes':138280960}}


class MaterialMeasurementsTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def test_sql_catalog_counts_and_database_sizes_do_not_write(self):
        path=self.root/'catalog/catalog.sqlite';path.parent.mkdir()
        db=sqlite3.connect(path);self.addCleanup(db.close)
        db.executescript('CREATE TABLE documents(sha256 TEXT,size_bytes INTEGER,suffix TEXT);'
                         'CREATE TABLE current_readings(state TEXT);'
                         'CREATE INDEX sha ON documents(sha256);')
        db.executemany('INSERT INTO documents VALUES(?,?,?)',[('a',100,'.pdf'),('a',100,'.pdf'),('b',20,'.txt')])
        db.executemany('INSERT INTO current_readings VALUES(?)',[('complete',),('blocked',),('queued',)])
        db.commit();before=path.read_bytes();mtime=path.stat().st_mtime_ns
        with patch.object(measurements,'directory_sizes',return_value={'state':'unavailable'}):
            result=measurements.spark_snapshot(db,self.root)
        self.assertEqual(result['catalog']['files'],3)
        self.assertEqual(result['catalog']['content_identities'],2)
        # SUM sizes covers registered rows, not the directory nor a unique-original archive.
        self.assertEqual(result['catalog']['size_bytes'],220)
        self.assertEqual(result['catalog']['states'],{'complete':1,'blocked':1,'queued':1})
        size=result['databases']['reader']
        self.assertEqual(size['file_bytes'],len(before));self.assertGreater(size['index_bytes'],0)
        self.assertLessEqual(size['index_bytes'],size['file_bytes'])
        self.assertEqual((path.read_bytes(),path.stat().st_mtime_ns),(before,mtime))
        missing=self.root/'absent.sqlite'
        self.assertEqual(measurements.database_sizes(missing),{'state':'unavailable'})
        self.assertFalse(missing.exists())

    def test_directory_cache_records_observation_time_and_failure_is_stale(self):
        state=self.root/'state';state.mkdir();data=self.root/'data';data.mkdir()
        output=f'200\t{data}/raw-materials\n100\t{data}/originals\n450\t{data}\n'
        with patch.object(measurements.subprocess,'run',return_value=subprocess.CompletedProcess([],0,output)) as call:
            first=measurements.directory_sizes(data,state,now=1000)
            cached=measurements.directory_sizes(data,state,now=1100)
        self.assertEqual(call.call_count,1);self.assertEqual(cached,first)
        self.assertEqual(first['other_bytes'],150)
        with patch.object(measurements.subprocess,'run',side_effect=subprocess.TimeoutExpired('du',15)):
            stale=measurements.directory_sizes(data,state,now=5000)
        self.assertEqual(stale['state'],'stale');self.assertEqual(stale['measured_at'],first['measured_at'])
        self.assertEqual(stale['allocated_bytes'],450)
        (state/'material-directory-measurements.json').write_text('[]')
        with patch.object(measurements.subprocess,'run',side_effect=OSError()):
            self.assertEqual(measurements.directory_sizes(data,state)['state'],'unavailable')
        # An empty/malformed du reply must never interrupt the existing publisher.
        with patch.object(measurements.subprocess,'run',return_value=subprocess.CompletedProcess([],0,'')):
            self.assertEqual(measurements.directory_sizes(data)['state'],'unavailable')

    def test_receiver_only_preserves_whitelisted_aggregates(self):
        raw=measured_fixture()['measurements'];raw['private_path']='/secret/material.pdf'
        raw['databases']['unknown']={'password':'secret'}
        raw['archive']['directories']['secret-name']=123
        clean=measurements.sanitize(raw)
        self.assertNotIn('secret',json.dumps(clean))
        self.assertEqual(clean['catalog']['files'],36047)
        self.assertEqual(clean['candidates']['documents'],135)
        for bad in (None,[],{}, {'schema_version':1,'measured_at':'bad'}, {'schema_version':1,'measured_at':True}):
            self.assertEqual(measurements.sanitize(bad),{'state':'unavailable'})
        raw['catalog']['files']=-1
        self.assertNotIn('catalog',measurements.sanitize(raw))
        raw['archive']['allocated_bytes']=True
        self.assertEqual(measurements.sanitize(raw)['archive']['state'],'unavailable')
        scope=measured_fixture()['execution_scope'];scope.update(executor={'secret':'key'},original_path='/private')
        self.assertNotIn('secret',json.dumps(measurements.sanitize_scope(scope)))
        self.assertEqual(measurements.sanitize_scope(scope)['documents'],135)

    def test_projection_uses_supported_formal_records_not_ready_queue(self):
        root=self.root
        (root/'data').mkdir()
        for name in ('projects','contracts'):(root/'data'/(name+'.json')).write_text('{"records":[]}')
        curated={'statements':[{'id':'adopted'},{'id':'invalid'}]}
        reader={'execution_scope':measured_fixture()['execution_scope'],
                'research_verification':{'state':'observed','active_batches':0,'candidates':{'review_ready':700}},
                'material_measurements':measured_fixture()['measurements']}
        material_flow._CACHE.clear()
        with patch.object(material_flow.registry,'_snapshot_inputs',return_value=({}, {},curated,{},{})), \
             patch.object(material_flow.registry,'_reader_state',return_value=reader), \
             patch.object(material_flow.registry,'supported_adoption',side_effect=lambda s,k:s['id']=='adopted'), \
             patch.object(material_flow,'website_sizes',return_value={}):
            result=material_flow.snapshot(root)
        self.assertEqual(result['formal']['statements'],1)
        self.assertEqual(result['review']['candidates']['review_ready'],700)
        self.assertEqual(result['execution_scope']['documents'],135)

    def test_missing_web_files_are_unknown_without_creating_databases(self):
        with patch.object(material_flow,'workspace_path',return_value=self.root/'data/research_runtime.json'), \
             patch.object(material_flow.subprocess,'run',side_effect=OSError()):
            result=material_flow.website_sizes(self.root)
        self.assertIsNone(result['candidate_snapshot_bytes'])
        self.assertIsNone(result['product_database_bytes'])
        self.assertIsNone(result['allocated_bytes'])
        self.assertFalse((self.root/'data').exists())


if __name__=='__main__':unittest.main()
