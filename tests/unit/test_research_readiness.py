"""Readiness counts preserve authority and denominator boundaries."""
import unittest
from inresearch.knowledge.research_readiness import summarize


class ResearchHealthTests(unittest.TestCase):
    def health(self, acquisition=None, **kw):
        rows = [dict(id='P.gpu.news', team='inews', team_state='connected', status='needed',
                     request={'question_ids':['q', 'unknown']}, feeds_primary=['power'], model_inputs=['power']),
                dict(id='P.gpu.spec', team='fetchspec', team_state='connected', status='delivered',
                     request={'question_ids':[]}, feeds_primary=[], model_inputs=[]),
                dict(id='P.gpu.price', team='fetchquotes', team_state='not_connected', status='needed',
                     request={'question_ids':[]}, feeds_primary=[], model_inputs=[])]
        return summarize({'targets':rows}, [{'id':'q'}], {'answers':[{'id':'unreviewed'}]},
            {'inputs':{'power':1}, 'evidence':{'power':{'status':'assumed'}},
             'sensitivity_drivers':[{'key':'power','label':'功率'}]}, {'relations':[{'type':'part_of'}]},
            acquisition=acquisition, **kw)

    def test_unavailable_runtime_and_support_are_unknown(self):
        h=self.health()
        self.assertIsNone(h['questions']['answered'])
        self.assertIsNone(h['formal']['supported_statements'])
        self.assertTrue(all(p['runtime_observed_targets'] is None for p in h['providers']))
        self.assertEqual(h['model']['unresolved'],1)
        self.assertEqual(h['model']['critical_inputs'][0]['target_id'],'P.gpu.news')

    def test_receipts_do_not_adopt_or_change_git_and_scopes_stay_separate(self):
        h=self.health({'news_feed':{'by_target':{'P.gpu.news':3}},
                       'fetchspec_feed':{'by_target':{'P.gpu.spec':{'received_items':7}}}},
                      completed_question_ids={'q','unknown'},supported_statement_ids=[])
        teams={p['team']:p for p in h['providers']}
        self.assertEqual(h['questions']['answered'],1)
        self.assertEqual(h['questions']['with_exact_target_link'],1)
        self.assertEqual(h['questions']['targets_without_exact_question'],2)
        self.assertEqual(teams['inews']['runtime_received_git_needed'],1)
        self.assertEqual(teams['fetchspec']['runtime_received_git_needed'],0)
        self.assertNotEqual(teams['inews']['runtime_scope'],teams['fetchspec']['runtime_scope'])
        self.assertEqual(h['reconciliation'],[{'target_id':'P.gpu.news','team':'inews','git_status':'needed'}])
        self.assertEqual(h['formal']['answers'],1)  # a record alone never closes q

    def test_bad_runtime_counts_are_not_positive_receipts(self):
        for value in (True, -1, '3', 10**10, {'received_items':2}):
            self.assertEqual(self.health({'news_feed':{'by_target':{'P.gpu.news':value}}})['reconciliation'],[])
