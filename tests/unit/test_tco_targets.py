"""The five-variable-class target list is generated; it must equal its inputs, reference only things that exist,
route every row to a registered team and host, and cover every non-user TCO input."""
import json
import unittest
from pathlib import Path

from inresearch.knowledge import targets as targets_mod

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class TcoTargetListTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = load('framework/tco_targets.json')
        cls.targets = cls.doc['targets']
        cls.factors = {f['id']: f for f in load('framework/tco_factors.json')['factors']}
        cls.parts = {p['id']: p for p in load('framework/bom.json')['parts']}
        cls.rights = {r['id']: r for r in load('framework/site_rights.json')['rights']}
        cls.series = {r['series_id'] for r in load('data/prices.json')['records']}
        cls.indicators = {i['id'] for i in load('framework/indicators.json')['indicators']}
        model = load('data/datacenter_model.json')
        cls.inputs = set(model['inputs'])
        cls.evidence = model['evidence']
        contract = load('framework/supply_contract.json')
        cls.providers = {p['id'] for p in contract['providers']}
        cls.provider_rows = {p['id']: p for p in contract['providers']}
        cls.hosts = {p['host'] for p in contract['execution_policy'].values() if isinstance(p, dict) and 'host' in p}

    def test_file_is_generated_from_its_inputs(self):
        built = targets_mod.build(ROOT, self.doc['updated'])
        self.assertEqual(targets_mod.render(built), (ROOT / targets_mod.TARGETS).read_text(encoding='utf-8'),
                         'framework/tco_targets.json is stale; run python3 manage.py targets --refresh')

    def test_classification_update_does_not_move_deadlines(self):
        bom = load('framework/bom.json')
        self.assertLess(bom['schedule_updated'], bom['updated'])
        implicit = targets_mod.build(ROOT)
        explicit = targets_mod.build(ROOT, bom['schedule_updated'])
        self.assertEqual({r['id']:r['next_due'] for r in implicit['targets']}, {r['id']:r['next_due'] for r in explicit['targets']})

    def test_ids_unique_and_fields_complete(self):
        ids = [t['id'] for t in self.targets]
        self.assertEqual(len(ids), len(set(ids)))
        for t in self.targets:
            self.assertIn(t['variable_class'], (1, 2, 3, 4, 5), t['id'])
            self.assertNotIn('layer', t, f"{t['id']}: layer key retired 2026-09-29; scale is bom's, variable_class is ours")
            self.assertIn(t['origin'], ('factor', 'part', 'software', 'archetype', 'site_right'), t['id'])
            self.assertTrue(t['id'].startswith({'factor': 'F.', 'site_right': 'S.'}.get(t['origin'], 'P.')), t['id'])
            self.assertIn(t['data_class'], self.doc['data_classes'], t['id'])
            self.assertIn(t['mechanism'], self.doc['mechanisms'], t['id'])
            self.assertIn(t['status'], ('sourced', 'assumed', 'delivered', 'needed'), t['id'])
            for key in ('disclosure_type', 'publisher_category', 'calendar', 'team_state'):
                self.assertTrue(t.get(key), f"{t['id']} missing {key}")
            self.assertIn(t['team_state'], ('connected', 'not_connected'), t['id'])
            self.assertEqual(bool(t.get('next_due')), t['team_state'] == 'connected', f"{t['id']} due dates only for connected teams")
            self.assertEqual(t.get('sourced_by'), {'sourced': 'registry', 'delivered': 'delivery'}.get(t['status']), t['id'])
            self.assertTrue(t['instances'], t['id'])

    def test_every_part_and_right_is_covered(self):
        by_part = {}
        for t in self.targets:
            if t['part_id']:
                by_part.setdefault(t['part_id'], set()).add(t['id'].rsplit('.', 1)[1])
        for pid, p in self.parts.items():
            want = {'part': {'spec', 'operation', 'price', 'lead_time'}, 'software': {'spec', 'price'}, 'archetype': {'spec'}}[p['kind']]
            if p['kind'] == 'part' and p['status'] != 'mature':
                want = want | {'news'}
            self.assertEqual(by_part.get(pid), want, pid)
        for rid, r in self.rights.items():
            classes = {t['variable_class'] for t in self.targets if t['site_right_id'] == rid}
            self.assertEqual(classes, set(r['variable_classes']), rid)
        self.assertEqual(self.doc['counts']['total'], len(self.targets))

    def test_part_rows_carry_curated_sources(self):
        # 第 4 步的人工部分：每个物理部件的规格、价格、交期三行都有登记的出版方、实例与日历（framework/part_fetch.json）
        for t in self.targets:
            if t['origin'] == 'part' and t['id'].rsplit('.', 1)[1] in ('spec', 'price', 'lead_time'):
                self.assertTrue(t['curated'], f"{t['id']} still uses template sources")
                self.assertTrue(t['instances'] and t['publisher_category'] and t['calendar'], t['id'])

    def test_references_exist(self):
        for t in self.targets:
            self.assertTrue(t['factor_ids'] or t['origin'] != 'factor', t['id'])
            for fid in t['factor_ids']:
                self.assertIn(fid, self.factors, f"{t['id']} → factor {fid}")
            self.assertEqual(t['factor_id'], t['factor_ids'][0] if t['factor_ids'] else None, t['id'])
            if t['part_id']:
                self.assertIn(t['part_id'], self.parts, t['id'])
            if t['site_right_id']:
                self.assertIn(t['site_right_id'], self.rights, t['id'])
            for key in t['model_inputs']:
                self.assertIn(key, self.inputs, f"{t['id']} → input {key}")
            for sid in t['series']:
                self.assertIn(sid, self.series, f"{t['id']} → series {sid}")
            for sid in t['planned_series']:
                self.assertNotIn(sid, self.series, f"{t['id']} planned series already exists: {sid}")
            for iid in t['indicators']:
                self.assertIn(iid, self.indicators, f"{t['id']} → indicator {iid}")

    def test_team_and_host_registered(self):
        for t in self.targets:
            self.assertIn(t['team'], self.providers, f"{t['id']} → team {t['team']}")
            self.assertIn(t['team'], self.doc['teams'], t['id'])
            self.assertIn(t['host'], self.hosts, f"{t['id']} → host {t['host']}")
            # inews only produces event cards and pointers; originals belong to the other teams.
            if t['team'] == 'inews':
                self.assertEqual(t['mechanism'], 'rss', t['id'])
                self.assertEqual(t['data_class'], 'material', t['id'])
            if t['mechanism'] in ('pdf_registered', 'js_page'):
                self.assertEqual(t['host'], 'macmini', f"{t['id']} assisted mechanism must run on macmini")
            else:  # 2026-09-29：主执行机按供应方登记（fetchspec 在 macmini），不再一律 aws
                self.assertEqual(t['host'], self.provider_rows[t['team']].get('host_default', 'aws'), f"{t['id']} host follows the provider's host_default")

    def test_every_fed_input_has_exactly_one_primary_row(self):
        # 2026-09-29：55/77 个被喂的输入由多行喂；账本只回链主行，因子行优先
        primary = {}
        for t in self.targets:
            self.assertTrue(set(t['feeds_primary']) <= set(t['model_inputs']), t['id'])
            for k in t['feeds_primary']:
                self.assertNotIn(k, primary, f"{k} has two primary rows: {primary.get(k)} and {t['id']}")
                primary[k] = t['id']
        covered = {k for t in self.targets for k in t['model_inputs']}
        self.assertEqual(set(primary), covered)
        factor_rows = {t['id'] for t in self.targets if t['origin'] == 'factor'}
        for k, tid in primary.items():
            if any(k in t['model_inputs'] for t in self.targets if t['origin'] == 'factor'):
                self.assertIn(tid, factor_rows, f"{k}: a factor row exists, so the primary must be a factor row")

    def test_every_non_user_input_has_a_target(self):
        covered = {k for t in self.targets for k in t['model_inputs']}
        expected = {k for k, v in self.evidence.items() if v.get('status') != 'input'}
        self.assertEqual(expected - covered, set(), f"inputs without a target: {sorted(expected - covered)}")

    def test_status_is_not_more_optimistic_than_the_model(self):
        for t in self.targets:
            statuses = {self.evidence[k]['status'] for k in t['model_inputs'] if k in self.evidence}
            if t['status'] == 'sourced':
                self.assertIn('sourced', statuses, f"{t['id']} claims sourced but model evidence is {statuses}")
                self.assertTrue(statuses <= {'sourced', 'input'}, t['id'])
                self.assertTrue(t['series'] or t['indicators'] or t['data_class'] == 'reference', t['id'])
            if t['origin'] != 'factor' and not (t['series'] or t['indicators']):
                self.assertIn(t['status'], ('needed', 'delivered'), f"{t['id']} generated row without data must stay needed or delivered")

    def test_requests_expose_real_links_and_provider_boundaries(self):
        questions = {q['id']: q for q in load('framework/research_questions.json')['records']}
        profiles = self.doc['request_contract']['profiles']
        for target in self.targets:
            request = target['request']
            self.assertIn(request['profile'], profiles)
            self.assertTrue(request['scope_required'])
            for qid in request['question_ids']:
                self.assertEqual(questions[qid]['node'], request['node'])
                self.assertEqual(questions[qid]['variable_class'], target['variable_class'])
            if target['id'].endswith('.operation'):
                self.assertEqual(request['profile'], 'vendor_operation')
                self.assertNotIn('利用率', target['disclosure_type'])
        self.assertTrue(any(not t['request']['question_ids'] for t in self.targets))

    def test_skeleton_additions_of_2026_09_28(self):
        # 运行行、建设时间线因子、建设阶段（03「骨架的三个补充」）
        stages = {s['id'] for s in load('framework/bom.json')['stages']}
        ops = [t for t in self.targets if t['id'].endswith('.operation')]
        self.assertEqual(len(ops), sum(1 for p in self.parts.values() if p['kind'] == 'part'))
        for t in ops:
            self.assertEqual((t['variable_class'], t['data_class']), (2, 'reference'), t['id'])
        build = [t for t in self.targets if t['factor_id'] == 'time.build']
        self.assertEqual(sorted(t['id'] for t in build), ['F.time.build.duration', 'F.time.build.permit', 'F.time.build.queue'])
        for t in build:
            self.assertEqual(t['variable_class'], 4, t['id'])
        self.assertTrue({'construction_years', 'gate_wait_years', 'permit_months'} <= {k for t in build for k in t['model_inputs']})
        for t in self.targets:
            if t['part_id'] or t['site_right_id']:
                self.assertIn(t['stage'], stages, t['id'])
            else:
                self.assertIsNone(t['stage'], t['id'])

    def test_team_state_follows_the_supply_contract(self):
        contract = load('framework/supply_contract.json')
        connected = {p['id'] for p in contract['providers'] if p.get('connection') != 'not_connected'}
        for t in self.targets:
            self.assertEqual(t['team_state'], 'connected' if t['team'] in connected else 'not_connected', t['id'])

    def test_delivered_needs_a_git_carrier(self):
        """delivered is only claimed when a carrier inside Git holds the delivery: the docs plan (doc_id / source_url),
        an event card with origin_pointer, or a price record with target_id. Runtime-only deliveries never count."""
        import csv
        self.assertEqual(set(self.doc['statuses']), {'sourced', 'assumed', 'delivered', 'needed'})
        self.assertTrue(self.doc['carriers'])
        with (ROOT / targets_mod.DOCS_PLAN).open(encoding='utf-8', newline='') as fh:
            plan_parts = {r['part_id'] for r in csv.DictReader(fh) if r.get('status', 'todo') != 'todo' and (r.get('doc_id') or r.get('source_url'))}
        cards_path = ROOT / targets_mod.EVENT_CARDS
        cards = json.loads(cards_path.read_text(encoding='utf-8')).get('records', []) if cards_path.exists() else []
        # a card bound to a target row holds only that row; part/right widen target-less cards only
        card_targets = {c.get('target_id') for c in cards if c.get('origin_pointer')}
        price_targets = {r.get('target_id') for r in load('data/prices.json')['records'] if r.get('target_id')}
        for t in self.targets:
            if t['status'] != 'delivered':
                continue
            kind = t['id'].rsplit('.', 1)[1]
            held = (t['id'] in price_targets or t['id'] in card_targets
                    or (kind == 'spec' and t['part_id'] in plan_parts))
            self.assertTrue(held, f"{t['id']} is delivered without a Git carrier")


    def test_target_bound_card_delivers_only_its_own_row(self):
        """A Fetchspec spec card for P.server.spec must not mark the inews row P.server.news delivered."""
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rel in ('framework', 'data'):
                shutil.copytree(ROOT / rel, root / rel)
            cards = {'version': '1.0', 'records': [
                {'target_id': 'P.server.spec', 'part_id': 'server', 'site_right_id': None, 'team': 'fetchspec',
                 'origin_pointer': 'https://www.supermicro.com/en/products/system/gpu/8u/sys-821ge-tnhr', 'pointer_kind': 'url'},
                {'target_id': None, 'part_id': 'gpu', 'site_right_id': None, 'team': 'inews',
                 'origin_pointer': 'https://example.com/press/gpu', 'pointer_kind': 'url'}]}
            (root / targets_mod.EVENT_CARDS).write_text(json.dumps(cards), encoding='utf-8')
            status = {t['id']: t['status'] for t in targets_mod.build(root)['targets']}
        self.assertEqual(status['P.server.spec'], 'delivered')
        self.assertEqual(status['P.server.news'], 'needed')
        self.assertEqual(status['P.server.operation'], 'needed')
        self.assertEqual(status['P.gpu.news'], 'needed')  # an unbound old card cannot certify a current demand

if __name__ == '__main__':
    unittest.main()
