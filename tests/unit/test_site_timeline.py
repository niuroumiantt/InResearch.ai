import copy
import unittest
from inresearch.knowledge import site_timeline


class SiteTimelineTests(unittest.TestCase):
    def observation(self, ident='new', when='2026-10-01', **fields):
        return dict(id=ident, effective_at=when, recorded_at='2026-10-11T00:00:00Z',
                    scope='whole_site', kind='disclosed', basis='source review',
                    fields=fields or {'tenant': ['new-user']}, adoption={'review_id': ident})

    def test_newer_effective_time_wins_even_when_older_event_arrives_last(self):
        baseline={'site_id':'fixed-land', 'location':'same block', 'tenant':['old-user']}
        newer=self.observation();older=self.observation('old', '2026-09-01',tenant=['intermediate'])
        row,_=site_timeline.append(baseline,newer);row,_=site_timeline.append(row,older)
        projected=site_timeline.current(row, '2026-10-11')
        self.assertEqual(projected['tenant'], ['new-user'])
        self.assertEqual(row['tenant'],['old-user']);self.assertEqual(row['location'],baseline['location'])
        self.assertEqual(site_timeline.append(row,newer),(row,True))
        changed=copy.deepcopy(newer);changed['fields']['tenant']=[]
        with self.assertRaisesRegex(ValueError,'id_conflict'):site_timeline.append(row,changed)

    def test_future_forecast_and_equal_time_conflict_do_not_silently_replace_current(self):
        row={'tenant':['baseline']}
        rows=[self.observation(),self.observation('disagreement',tenant=['another']),
              self.observation('future','2026-12-01',tenant=['future'])]
        rows[-1]['kind']='forecast';row['observations']=rows
        result=site_timeline.current(row,'2026-10-11')
        self.assertEqual(result['tenant'],['baseline'])
        self.assertEqual(result['tracking']['forecasts'],1)
        self.assertEqual(result['tracking']['conflicts'][0]['field'],'tenant')

    def test_estimated_small_change_accepted_and_it_bundle_does_not_mix_dates(self):
        row={'capacity_it_mw':None,'capacity_it_mw_by_status':{'L8':421}}
        observation=self.observation(capacity_it_mw=421.25,capacity_it_mw_by_status={},capacity_assessment=None)
        observation.update(kind='estimated',assumptions=['satellite cooling estimate'])
        row,_=site_timeline.append(row,observation)
        result=site_timeline.current(row,'2026-10-11')
        self.assertEqual(result['capacity_it_mw'],421.25)
        self.assertEqual(result['capacity_it_mw_by_status'],{})
        self.assertEqual(result['capacity_assessment']['as_of'],'2026-10-01')
        bad=self.observation(capacity_it_mw=422)
        with self.assertRaisesRegex(ValueError,'bundle'):site_timeline.append(row,bad)
        bad=self.observation(location='different block')
        with self.assertRaisesRegex(ValueError,'fields'):site_timeline.append(row,bad)

    def test_source_paths_and_review_private_data_are_not_public(self):
        observation=self.observation();observation['adoption']['private_path']='/secret'
        observation['sources']=[{'url':'https://example.org/original','private_path':'/secret'}]
        result=site_timeline.public_timeline({'observations':[observation]})
        self.assertNotIn('/secret',str(result));self.assertNotIn('adoption',result[0])

    def test_pause_keeps_capacity_history_but_excludes_active_supply(self):
        from inresearch.knowledge.industry import project, totals
        row={'site_id':'same-land','status':'L8','capacity_it_mw':200}
        row,_=site_timeline.append(row,self.observation(lifecycle='paused'))
        view=project(row)
        self.assertEqual(view['capacity']['operating'],200)
        self.assertEqual(totals([view])['operating'],0)
        self.assertEqual(totals([view])['inactive_sites'],1)

    def test_unknown_and_month_only_times_can_be_saved_without_inventing_day(self):
        row={'tenant':['baseline']}
        for ident,when in [('unknown',None),('month','2026-10')]:
            row,_=site_timeline.append(row,self.observation(ident,when))
        result=site_timeline.current(row,'2026-10-11')
        self.assertEqual(result['tenant'],['baseline'])
        self.assertEqual(result['tracking']['imprecise_times'],2)
        self.assertEqual(row['observations'][1]['effective_at'],'2026-10')

    def test_recheck_refreshes_only_reviewed_field_without_rewriting_event_date(self):
        row={'tenant':['old-user'],'status':'L8','verified_date':'2025-01-01'}
        observation=self.observation(when='2026-01-01')
        row,_=site_timeline.append(row,observation)
        result=site_timeline.current(row,'2026-10-11')
        self.assertNotIn('tenant',result['tracking']['review_due_fields'])
        self.assertIn('status',result['tracking']['review_due_fields'])
        self.assertEqual(result['tracking']['fields']['tenant']['effective_at'],'2026-01-01')
        self.assertEqual(row['verified_date'],'2025-01-01')
