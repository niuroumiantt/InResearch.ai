"""Daily event links use current scoped observations, without changing the register."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from inresearch.materials import daily_events
from inresearch.paths import project_root


class DailyEventProjectionTests(unittest.TestCase):
    def project(self, site):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'data').mkdir();(root/'acquisition').mkdir()
            register=root/'data/projects.json'
            register.write_text(json.dumps({'records':[site]}))
            before=register.read_bytes()
            event={'id':'fixture-event','body':'project report','matched_site_id':site['site_id'],
                   'sources':[{'urls':['https://example.org/report']}], 'reported_stage':'operating',
                   'capacity_observations':[], 'site_candidates':[],
                   'document_refs':[{'sha256':'f'*64,'report_date':'2026-10-11'}]}
            (root/'acquisition/daily-events.json').write_text(json.dumps({'records':{event['id']:event}}))
            with patch('inresearch.paths.project_root',return_value=root):
                result=daily_events.projection(root)['records'][0]['registered_project']
            self.assertEqual(register.read_bytes(),before)
            return result

    def test_real_abilene_current_estimate_keeps_forecast_and_legacy_baseline_separate(self):
        register=project_root()/'data/projects.json';before=register.read_bytes()
        site=next(s for s in json.loads(before)['records'] if s['site_id']=='us-tx-abilene')
        baseline=copy.deepcopy(site)
        self.assertEqual(site['capacity_it_mw_by_status'],{'L8':421,'L6':422})
        result=self.project(site)
        self.assertEqual(result['capacity_it_mw'],421)
        self.assertEqual(result['capacity_it_mw_by_status'],{})
        self.assertEqual(result['quantity_fields']['capacity_it_mw'],421)
        self.assertEqual(result['capacity_assessment']['as_of'],'2026-07-28')
        self.assertEqual(result['tracking']['fields']['capacity_it_mw']['kind'],'estimated')
        self.assertEqual(result['tracking']['latest_effective_at'],'2026-07-28')
        self.assertEqual(result['tracking']['forecasts'],1)
        self.assertEqual(site,baseline)
        self.assertEqual(register.read_bytes(),before)

    def test_native_range_and_effective_date_survive_registered_project_projection(self):
        reviewed='2026-10-11T00:00:00Z'
        quantity={'value_range':[.4,.5],'unit':'GW','assumptions':['test-only cooling interval']}
        observation={'id':'fixture-range','schema_version':2,'effective_at':'2026-07-28',
                     'recorded_at':reviewed,'reviewed_at':reviewed,'scope':'whole_site','kind':'estimated',
                     'basis':'test-only cooling estimate','assumptions':['test-only cooling interval'],
                     'fields':{'capacity_it_mw':quantity,'capacity_it_mw_by_status':{},'capacity_assessment':None},
                     'source_versions':[{'source_sha256':'a'*64,'published_at':None,'first_received_at':None,
                        'published_at_precision':'unknown','first_received_at_precision':'unknown',
                        'published_at_provenance':'test-only unknown date','first_received_at_provenance':'test-only unknown receipt'}],
                     'adoption':{'review_id':'fixture-review','source_kind':'reader_report','source_id':'fixture-report',
                        'source_version':'b'*64,'document_refs':[{'sha256':'a'*64}],'target_ids':['fixture-demand'],
                        'assertions':[{'source_sha256':'a'*64,'quote':'test-only native interval','locator':'fixture:1'}],
                        'review':{'by':'fixture reviewer','at':reviewed,'tier':'A','score':8,'authority':'delegated_reviewer',
                            'decision':'adopted','rationale':'test-only reviewed estimate',
                            'delegation':{'delegate':'fixture reviewer','granted_by':'fixture owner','granted_at':'2026-10-11',
                                'reference':'test-only delegation','scope':'new_or_supplemental_research'}}}}
        result=self.project({'site_id':'fixture-range','status':'L8','capacity_it_mw':999,
                             'capacity_it_mw_by_status':{'L8':999},'observations':[observation]})
        self.assertIsNone(result['capacity_it_mw'])
        self.assertEqual(result['capacity_it_mw_by_status'],{})
        self.assertEqual(result['quantity_fields']['capacity_it_mw'],quantity)
        self.assertEqual(result['capacity_assessment']['as_of'],'2026-07-28')
        self.assertEqual(result['tracking']['fields']['capacity_it_mw']['kind'],'estimated')
