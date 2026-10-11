"""Native benchmark support retains scope and needs an independent check."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inresearch.materials.demand_bindings import requirement_digest
from inresearch.workflow import quantitative_review as quantitative
from inresearch.workflow import research_review as review
from tests.unit.test_research_review import fixture, audit

ROOT = Path(__file__).resolve().parents[2]


def request():
    targets = json.loads((ROOT / 'framework/tco_targets.json').read_text())
    target, requirement = next((t, r) for t in targets['targets']
        for r in t['request']['requirements'] if r['model_input'] == 'tokens_per_gpu_sec')
    return dict(target_version=targets['version'], target_id=target['id'],
                requirement_id=requirement['id'], requirement_sha256=requirement_digest(requirement),
                question_id=requirement['question_ids'][0],
                scope_values={k: '8 H100; Llama2-70B; MLPerf Server; source-native run' for k in requirement['scope_fields']},
                purpose='Review a bounded benchmark reference; do not certify production throughput')


def scoped():
    packet, row = fixture()
    packet['items'][0]['candidate']['kind'] = 'observation'
    packet['quantitative_support_contract'] = quantitative.contract([request()], ROOT)
    row['quantitative_checks'] = {k: 'Native benchmark scope retained; unknown conditions remain unknown' for k in quantitative.CHECKS}
    r = packet['quantitative_support_contract']['requests'][0]
    packet['items'][0]['allowed_question_ids'] = [r['question_id']]
    packet['items'][0]['candidate']['question_ids'] = [r['question_id']]
    packet['research_context']['current_workorders'] = [{'wid':'Q-'+r['question_id']}]
    row['question_ids'] = [r['question_id']]
    packet['context_sha256'] = review.sha(packet['research_context'])
    row['parameter_assessments'] = [dict(requirement_id=r['requirement_id'], question_id=r['question_id'],
        status='usable_reference', rationale='Scoped run only, not a universal production rate', model_input_verified=False)]
    return packet, row


class QuantitativeReviewTests(unittest.TestCase):
    def test_explicit_request_is_resolved_but_not_certified(self):
        packet, row = scoped()
        self.assertEqual(review.validate_reviews(packet, {'reviews':[row]}), [row])
        self.assertIn('measured system', review.review_system(packet))
        self.assertEqual(packet['quantitative_support_contract']['requests'][0]['evidence_status'], 'unverified')
        bad = request(); bad['requirement_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'definition_changed'):
            quantitative.contract([bad], ROOT)

    def test_missing_scope_or_forged_fulfillment_cannot_pass(self):
        for field in quantitative.CHECKS:
            packet, row = scoped(); row['quantitative_checks'][field] = ''
            with self.assertRaisesRegex(ValueError, 'scope_checks'):
                review.validate_reviews(packet, {'reviews':[row]})
        for change in ({'model_input_verified':True}, {'requirement_id':'other'}, {'status':'verified'}):
            packet, row = scoped(); row['parameter_assessments'][0].update(change)
            with self.assertRaises(ValueError): review.validate_reviews(packet, {'reviews':[row]})
        packet, row = scoped(); row['parameter_assessments'] = []
        with self.assertRaisesRegex(ValueError, 'complete_parameter'):
            review.validate_reviews(packet, {'reviews':[row]})

    def test_every_observation_and_calculation_requires_second_check(self):
        packet, row = scoped(); eligible=[]
        for i in range(12):
            item=copy.deepcopy(packet['items'][0]); item['candidate']['id']='c'+str(i)
            item['candidate']['kind']='calculation' if i%2 else 'observation'
            if i == 0: packet['items']=[]
            packet['items'].append(item); eligible.append({'id':item['candidate']['id']})
        self.assertEqual(set(review.required_sample(packet, eligible)), {x['id'] for x in eligible})
        packet.pop('quantitative_support_contract')
        self.assertEqual(len(review.required_sample(packet, eligible)), 2)

    def test_existing_a_conditions_still_require_owner(self):
        packet, row = scoped(); packet['original_importance']=8
        with self.assertRaisesRegex(ValueError, 'c3_a'):
            review.validate_reviews(packet, {'reviews':[row]})
        row['decision']='needs_owner'
        self.assertEqual(review.validate_reviews(packet, {'reviews':[row]}), [row])

    def test_request_question_is_available_without_forcing_match(self):
        packet, row = scoped(); q=request()['question_id']
        tasks=[{'wid':'Q-'+q, 'title':'Actual parameter scope', 'object_ids':['unrelated-retrieval-tag']}]
        with patch.object(review.registry, 'current_tasks', return_value=tasks):
            matching=review.match_packet(ROOT, packet)
        self.assertEqual([x['id'] for x in matching['current_question_directory']], [q])
        self.assertIn('requested reading only', matching['request_relationship'])
        result={'matches':[{'id':row['id'], 'question_ids':[], 'context_terms':[], 'rationale':'No actual source support'}]}
        self.assertEqual(review.validate_matches(matching, result)[0]['question_ids'], [])

    def test_no_scoped_contract_cannot_adopt_a_measurement(self):
        packet, row = fixture(); packet['items'][0]['candidate']['kind']='observation'
        with self.assertRaisesRegex(ValueError, 'scoped_contract'):
            review.validate_reviews(packet, {'reviews':[row]})

    def test_publication_keeps_measurement_kind_and_parameter_limitations(self):
        packet, row = scoped()
        packet['research_context']['question_ids'] = row['question_ids']
        packet['context_sha256'] = review.sha(packet['research_context'])
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'data').mkdir(); (root/'framework').mkdir(); directory=root/'audit'; directory.mkdir()
            bundle=audit(directory, packet, row)
            from inresearch.materials.artifacts import atomic_json, read_json, digest_file
            first=read_json(directory/'request.json'); first['system']=review.review_system(packet)
            atomic_json(directory/'request.json', first); bundle['request_sha256']=digest_file(directory/'request.json')
            second=read_json(directory/'sampling-request.json'); second['system']=review.review_system(packet,sampling=True)
            atomic_json(directory/'sampling-request.json', second)
            graph=json.loads((ROOT/'framework/research_graph.json').read_text())
            atomic_json(root/'framework/research_graph.json', graph)
            atomic_json(root/'framework/research_questions.json', {'records':[{'id':row['question_ids'][0],
                'object_ids':['root'], 'acceptance':'Independent validation', 'evidence_requirements':['Native original']}]})
            atomic_json(root/'data/research_knowledge.json', {'documents':[], 'evidence':[], 'statements':[], 'answers':[]})
            with patch.object(review, 'context', return_value=packet['research_context']):
                result=review.promote(root,bundle,directory)
            value=read_json(root/'data/research_knowledge.json')
            self.assertEqual(result['closed_questions_added'],0)
            self.assertEqual(value['answers'],[])
            self.assertEqual(value['statements'][0]['kind'],'observation')
            self.assertEqual(value['statements'][0]['parameter_assessments'],row['parameter_assessments'])
            self.assertFalse(value['statements'][0]['parameter_assessments'][0]['model_input_verified'])
            self.assertFalse((root/'data/datacenter_model.json').exists())

    def test_missing_second_measurement_check_blocks_entire_publication(self):
        packet,row=scoped()
        packet['items'].append(copy.deepcopy(packet['items'][0]))
        packet['items'][1]['candidate']['id']='second-observation'
        row2=copy.deepcopy(row);row2['id']='second-observation'
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'data').mkdir();directory=root/'audit';directory.mkdir()
            bundle=audit(directory,packet,row)
            bundle['reviews']=[row,row2]
            with patch.object(review,'verify_audit',return_value=True), patch.object(review,'current_context',return_value=packet['research_context']):
                with self.assertRaisesRegex(ValueError,'fixed_cohort'):
                    review._checked_adoption(root,bundle,directory,{'statements':[]})

    def test_discovery_reopens_only_old_type_deferrals_and_keeps_other_guards(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock
        for importance in [7, 8, 3]:
            with self.subTest(importance=importance), tempfile.TemporaryDirectory() as td:
                store=review.ReviewStore(td)
                doc={'doc_id':'doc-'+'a'*64,'revision_id':'rev-test','report_sha256':'b'*64,'sha256':'a'*64}
                report={'importance':importance,'explicit_research_requests':[request()]}
                packet,row=fixture(); claims=[]
                for kind in ['observation','calculation','unverified','author_claim']:
                    c=copy.deepcopy(packet['items'][0]['candidate']); c['id']='candidate:'+kind;c['kind']=kind;claims.append(c)
                if importance==7:
                    store.disposition(claims[0]['id'],doc,'needs_specialist','initial lane covers attributed claims/forecasts')
                conn=MagicMock(); conn.execute.return_value.fetchall.return_value=[doc]
                with patch.object(review.DocumentScope,'ids',return_value=[doc['doc_id']]), \
                     patch.object(review,'ro',return_value=conn), \
                     patch.object(review.ReadingArtifacts,'verify_seal',return_value=report), \
                     patch.object(review,'project_document',return_value={'statements':claims}), \
                     patch.object(review,'supplied_sources',return_value={doc['sha256']:{'research_requests':[request()]}}):
                    store.discover(ROOT,Path(td)/'scope.json')
                    before=[tuple(x) for x in store.db.execute('SELECT * FROM dispositions ORDER BY id')]
                    store.discover(ROOT,Path(td)/'scope.json')
                    self.assertEqual(before,[tuple(x) for x in store.db.execute('SELECT * FROM dispositions ORDER BY id')])
                states=dict(store.db.execute('SELECT id,state FROM dispositions'))
                expected='queued' if importance==7 else 'needs_owner' if importance==8 else 'background'
                self.assertEqual(states['candidate:observation'],expected)
                self.assertEqual(states['candidate:calculation'],expected)
                self.assertEqual(states['candidate:unverified'],'needs_specialist' if importance==7 else expected)
                if importance==7:
                    self.assertEqual(store.db.execute('SELECT count(*) FROM routing_history').fetchone()[0],1)
