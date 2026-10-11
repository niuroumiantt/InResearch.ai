"""Local evidence is reusable before a full reading, with exact identity seals."""
import copy
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from inresearch.workflow import targeted_research as excerpts
from inresearch.knowledge import registry, industry, site_timeline


class TargetedResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = Path(self.tmp.name)
        (self.data/'catalog').mkdir()
        (self.data/'data').mkdir()
        (self.data/'data/projects.json').write_text(json.dumps({'records': [{'site_id': 'campus'}]}))
        self.text = 'Campus used 1–2 GWh during 2025. Scope: campus electricity consumption.\n'
        self.original = self.data/'source.txt'
        self.original.write_text(self.text)
        self.sha = hashlib.sha256(self.original.read_bytes()).hexdigest()
        with sqlite3.connect(self.data/'catalog/catalog.sqlite') as db:
            db.execute('CREATE TABLE documents(sha256 TEXT, original_rel TEXT)')
            db.execute('INSERT INTO documents VALUES (?,?)', (self.sha, 'source.txt'))
        self.source = {'source_url': 'https://example.org/source', 'source_provenance': {},
                       'research_requests': [{'target_id': 'site-grid', 'scope': 'campus'}]}
        self.addCleanup(patch.stopall)
        patch.object(excerpts, 'supplied_sources', return_value={self.sha: self.source}).start()
        patch.object(excerpts, 'resolve_requests', side_effect=lambda rows, root: copy.deepcopy(rows)).start()
        patch.object(excerpts, '_first_received', return_value={'at': None, 'provenance': 'unknown'}).start()
        self.selection = [{'sha256': self.sha, 'pages': [1]}]

    def context(self):
        return excerpts.prepare(self.data, self.data, self.selection, 'campus')

    def proposal(self):
        return {'project': {'site_id': 'campus'}, 'targeted_sources': self.selection,
                'target_ids': ['site-grid'], 'source_version': self.context()['source_version'],
                'assertions': [{'source_sha256': self.sha, 'locator': 'excerpt:page:1', 'quote': self.text.strip()}]}

    def test_native_excerpt_has_no_reader_completion_or_model_dependency(self):
        before = (self.data/'data/projects.json').read_bytes()
        with patch('inresearch.adapters.reader_model.ModelClient', side_effect=AssertionError('no model')):
            context = excerpts.resolve(self.data, self.data, self.proposal())
        ref = context['document_refs'][0]
        self.assertFalse(ref['coverage']['complete'])
        self.assertEqual(ref['coverage']['mode'], 'targeted')
        self.assertEqual(context['first_received'][self.sha]['at'], None)
        self.assertEqual((self.data/'data/projects.json').read_bytes(), before)
        self.assertEqual(context['source_pages'][self.sha][1], self.text)

    def test_quotes_pages_bindings_identity_and_original_are_revalidated(self):
        p = self.proposal()
        for failure in ('page', 'quote', 'site', 'target', 'seal'):
            bad = copy.deepcopy(p)
            if failure == 'page': bad['assertions'][0]['locator'] = 'excerpt:page:2'
            if failure == 'quote': bad['assertions'][0]['quote'] = 'Campus used 100 GWh.'
            if failure == 'site': bad['project']['site_id'] = 'neighbour'
            if failure == 'target': bad['target_ids'] = ['other']
            if failure == 'seal': bad['source_version'] = '0'*64
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                excerpts.resolve(self.data, self.data, bad)
        self.source['research_requests'][0]['scope'] = 'region'
        with self.assertRaisesRegex(ValueError, 'binding_changed'):
            excerpts.resolve(self.data, self.data, p)
        self.original.write_text('Changed source bytes')
        with self.assertRaisesRegex(ValueError, 'hash_changed'):
            self.context()

    def test_partial_coverage_only_supports_exact_reviewed_context(self):
        coverage = self.context()['document_refs'][0]['coverage']
        doc = {'id': 'doc-'+self.sha, 'content_sha256': self.sha, 'coverage': coverage}
        span = coverage['reviewed_spans'][0]
        evidence = {'page_index': 0, 'locator': span['locator'], 'context_sha256': span['text_sha256']}
        self.assertFalse(registry.coverage_complete(doc))
        self.assertTrue(registry.coverage_supports_evidence(doc, evidence))
        for key, value in [('page_index', 1), ('locator', 'excerpt:page:2'), ('context_sha256', 'f'*64)]:
            self.assertFalse(registry.coverage_supports_evidence(doc, dict(evidence, **{key: value})))

    def test_bounded_statement_does_not_claim_whole_question_is_answered(self):
        from test_research import adopted_knowledge
        knowledge = adopted_knowledge()
        doc = knowledge['documents'][0]
        coverage = self.context()['document_refs'][0]['coverage']
        doc.update(id='doc-'+self.sha, content_sha256=self.sha, coverage=coverage)
        ev = knowledge['evidence'][0]
        ev.update(document_id=doc['id'], page_index=0, locator='excerpt:page:1',
                  context_sha256=coverage['reviewed_spans'][0]['text_sha256'])
        self.assertTrue(registry.supported_adoption(knowledge['statements'][0], knowledge))
        self.assertFalse(registry.supported_adoption(knowledge['answers'][0], knowledge))
        self.assertEqual(registry.completed_questions(knowledge), set())
        ev['context_sha256'] = '0'*64
        self.assertFalse(registry.supported_adoption(knowledge['statements'][0], knowledge))

    def test_local_energy_interval_passes_existing_site_writer_and_keeps_partial_label(self):
        from inresearch.workflow import project_review
        project = {'site_id': 'campus', 'name': 'Campus', 'country': 'US', 'region': 'north-america',
                   'location': 'One fixed plot', 'status': 'L8', 'verified_date': '2026-10-10',
                   'notes': 'Registered physical site', 'sources': [{'url': self.source['source_url'], 'grade': 'company'}]}
        (self.data/'data/projects.json').write_text(json.dumps({'records': [project]}))
        (self.data/'framework').mkdir()
        (self.data/'framework/tco_targets.json').write_text(json.dumps({'targets': [{'id': 'site-grid'}]}))
        proposal = self.proposal()
        metric = {'value_range': [1, 2], 'unit': 'GWh', 'basis': 'native reported interval',
                  'period_start': '2025-01-01', 'period_end': '2025-12-31',
                  'boundary': 'whole campus electricity consumption', 'measurement_kind': 'reported'}
        proposal.update(source_kind='targeted_excerpt', baseline_sha256=project_review.digest(project),
            fields=['electricity_consumption_mwh'], scope='Campus electricity in 2025',
            project=dict(project, verified_date='2026-10-11', electricity_consumption_mwh=metric),
            observation={'effective_at': '2025-12-31', 'kind': 'reported', 'scope': 'whole_site', 'basis': 'native interval'},
            review={'by': 'fixture reviewer', 'at': '2026-10-11T00:00:00Z', 'score': 8, 'tier': 'A',
                'authority': 'delegated_reviewer', 'decision': 'adopted', 'rationale': 'test-only native context review',
                'delegation': {'delegate': 'fixture reviewer', 'granted_by': 'fixture owner', 'granted_at': '2026-10-11',
                    'reference': 'test-only delegation', 'scope': 'new_or_supplemental_research'}})
        proposal['assertions'][0].update(metric='electricity_consumption_mwh', quantity=metric)
        project_review.apply(self.data, self.data, proposal)
        record = json.loads((self.data/'data/projects.json').read_text())['records'][0]
        self.assertEqual(record['observations'][0]['fields']['electricity_consumption_mwh'], metric)
        public = site_timeline.public_timeline(record)[0]
        self.assertEqual(public['source_reading'][0]['mode'], 'targeted')
        self.assertFalse(public['source_reading'][0]['complete'])


class CampusRegisterTests(unittest.TestCase):
    def test_structured_geography_filters_do_not_require_a_street_or_capacity(self):
        from inresearch.paths import project_root
        root = project_root()
        view = industry.snapshot(root, {'country': 'CN', 'province': '河北'})
        self.assertEqual([p['site_id'] for p in view['rows']], ['cn-hebei-zhangjiakou'])
        p = view['rows'][0]
        self.assertEqual(p['geography']['regional_address'], '张家口')
        self.assertEqual(p['geography']['identity_scope'], 'cluster')
        self.assertIsNone(p['geography']['street_address'])
        self.assertIn('张家口', view['geographic_filters']['addresses'])
        self.assertEqual(industry.snapshot(root, {'country': 'IN', 'province': '河北'})['rows'], [])
        filtered = industry.snapshot(root, {'country': 'IN', 'province': 'Telangana', 'address': 'Hyderabad'})
        self.assertTrue(filtered['rows'])
        self.assertTrue(all(p['country'] == 'IN' and p['geography']['province'] == 'Telangana' for p in filtered['rows']))

    def test_geography_backfill_keeps_source_description_identity_and_review_dates(self):
        from inresearch.paths import project_root
        root = project_root()
        audit = json.loads((root/'docs/reviews/2026-10-11/research-remediation/explicit-location-backfill.json').read_text())
        records = {r['site_id']: r for r in json.loads((root/'data/projects.json').read_text())['records']}
        for change in audit['records']:
            current = records[change['site_id']]
            self.assertEqual(current['location'], change['location_description'])
            self.assertNotIn('verified_date', change['after'])
            self.assertTrue(all(current[key] == value for key, value in change['after'].items()))
            self.assertEqual([s.get('url') for s in current['sources']], change['source_urls'])

    def test_missing_address_not_guessed_and_roles_not_inferred(self):
        row = {'site_id': 'physical-campus', 'country': 'US', 'location': 'Texas, Abilene',
               'status': 'L8', 'developer': ['selfbuilder'], 'end_user': ['selfbuilder'],
               'lender': ['bank'], 'sources': [{'url': 'file:///secret'}]}
        p = industry.project(row)
        self.assertIsNone(p['geography']['province'])
        self.assertIsNone(p['geography']['street_address'])
        self.assertEqual({r['role'] for r in p['participants']}, {'developer', 'end_user', 'lender'})
        self.assertTrue(all(not r['sources'] for r in p['participants']))
        self.assertNotIn('owner', {r['role'] for r in p['participants']})

    def test_stage_capacities_do_not_invent_planned_total_or_fact_date(self):
        p = industry.project({'site_id': 'campus', 'status': 'L8', 'verified_date': '2026-10-11',
                              'capacity_it_mw_by_status': {'L8': 100, 'L6': 200, 'L2': 300}})
        self.assertIsNone(p['capacity_register']['planned']['quantity'])
        self.assertIsNone(p['capacity_register']['operating']['effective_at'])
        self.assertEqual(p['capacity_register']['operating']['reviewed_at'], '2026-10-11')
        self.assertEqual(p['total_mw'], 600)

    def test_explicit_plan_is_separate_and_never_added_to_operating_total(self):
        p = industry.project({'site_id': 'campus', 'status': 'L8', 'capacity_it_mw': 100,
                              'capacity_planned_it_mw': {'value_range': [1, 2], 'unit': 'GW', 'basis': 'campus design'}})
        self.assertEqual(p['total_mw'], 100)
        self.assertEqual(p['capacity_register']['planned']['quantity']['value_range'], [1, 2])
