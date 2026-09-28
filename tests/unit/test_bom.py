"""BOM 2.0 (2026-09-28 部件重切) 的结构约束：kind、尺度、系统、别名、站点权利与下游引用互相闭合。"""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding='utf-8'))


class BomStructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bom = load('framework/bom.json')
        cls.parts = {p['id']: p for p in cls.bom['parts']}
        cls.rights = {r['id']: r for r in load('framework/site_rights.json')['rights']}
        cls.companies = {r['company_id'] for r in load('data/companies.json')['records']}
        cls.graph = load('framework/research_graph.json')
        cls.objects = {o['id']: o for o in cls.graph['objects']}

    def test_scales_are_s1_to_s5(self):
        self.assertEqual([s['id'] for s in self.bom['layers']], ['S1', 'S2', 'S3', 'S4', 'S5'])
        self.assertEqual([s['name'] for s in self.bom['layers']], ['园区', '建筑', '机房', '机柜', '部件'])

    def test_kind_and_scale(self):
        scales = {s['id'] for s in self.bom['layers']}
        for p in self.bom['parts']:
            self.assertIn(p['kind'], self.bom['kinds'], p['id'])
            self.assertIn(p['system'], self.bom['systems'], p['id'])
            self.assertIn(p['status'], ('mature', 'tight', 'transition', 'emerging'), p['id'])
            if p['kind'] == 'part':
                self.assertIn(p['layer'], scales, p['id'])
            else:
                self.assertIsNone(p['layer'], p['id'])
            for c in p['companies']:
                self.assertIn(c, self.companies, f"{p['id']} → {c}")
        kinds = {k: sum(1 for p in self.bom['parts'] if p['kind'] == k) for k in self.bom['kinds']}
        self.assertEqual(kinds, {'part': 61, 'software': 1, 'archetype': 1})

    def test_user_decisions_of_2026_09_28(self):
        # 通用服务器与加速器服务器分两行；BMC、CXL 内存单列；小型堆登记为 emerging；配电条并入 PDU
        self.assertIn('general-server', self.parts)
        self.assertIn('server', self.parts)
        self.assertIn('bmc', self.parts)
        self.assertIn('cxl-memory', self.parts)
        self.assertEqual(self.parts['smr']['status'], 'emerging')
        self.assertNotIn('rack-pdu', self.parts)
        self.assertEqual(self.parts['dcim']['kind'], 'software')
        self.assertEqual(self.parts['modular-dc']['kind'], 'archetype')

    def test_one_skeleton_systems_and_chains(self):
        # 一个骨架：五个系统，IT 再分四个；系统内按能量流链路排；部件只挂叶子系统
        systems = self.bom['systems']
        top = [sid for sid, s in systems.items() if not s.get('parent')]
        self.assertEqual([systems[s]['name'] for s in sorted(top, key=lambda s: systems[s]['order'])], ['设施', '电力', '冷却', 'IT', '控制与软件'])
        self.assertEqual(sorted(sid for sid, s in systems.items() if s.get('parent') == 'it'), ['compute', 'memory', 'network', 'storage'])
        self.assertEqual(systems['power']['chains'], ['电网接入', '变电', '发电与储能', 'UPS', '配电', '机柜与板级供电'])
        self.assertEqual(systems['thermal']['chains'], ['排热', '冷水与 CDU', '机房与机柜', '芯片级'])
        slots = set()
        for p in self.bom['parts']:
            self.assertNotEqual(p['system'], 'it', p['id'])
            self.assertIn(p['chain'], systems[p['system']]['chains'], p['id'])
            key = (p['system'], p['chain'], p['chain_order'])
            self.assertNotIn(key, slots, p['id']); slots.add(key)
        # 边界件按能量流位置（用户 2026-09-28）
        self.assertEqual(self.parts['bess']['chain'], '发电与储能')
        for pid in ('power-shelf', 'psu', 'vrm', 'bbu'):
            self.assertEqual(self.parts[pid]['chain'], '机柜与板级供电', pid)
        self.assertEqual(self.parts['coldplate']['chain'], '芯片级')
        for pid in ('manifold', 'quick-disconnect'):
            self.assertEqual(self.parts[pid]['chain'], '机房与机柜', pid)
        self.assertEqual(self.parts['fuel-storage']['chain'], '发电与储能')

    def test_graph_domains_follow_chain_order(self):
        for d in self.graph['hardware_domains']:
            chains = self.bom['systems'][d['id']]['chains']
            keys = [(chains.index(self.parts[o[5:]]['chain']), self.parts[o[5:]]['chain_order']) for o in d['object_ids'] if o[5:] in self.parts]
            self.assertEqual(keys, sorted(keys), d['id'])

    def test_build_stages(self):
        # 03「骨架的三个补充」第 1 条：建设阶段是部件的第二个属性，六段有序；站点权利同
        stages = [s['id'] for s in self.bom['stages']]
        self.assertEqual(stages, ['rights', 'grid', 'shell', 'mep', 'it', 'commissioning'])
        self.assertEqual([s['name'] for s in self.bom['stages']], ['权利与审批', '并网与外线', '土建与壳', '机电', 'IT 进场', '调试与上架'])
        for p in self.bom['parts']:
            self.assertIn(p['stage'], stages, p['id'])
            if p['system'] in ('compute', 'memory', 'storage', 'network'):
                self.assertEqual(p['stage'], 'it', p['id'])
        for pid in ('hv-switchyard', 'transformer', 'mv-switchgear'):
            self.assertEqual(self.parts[pid]['stage'], 'grid', pid)
        self.assertEqual(self.parts['shell']['stage'], 'shell')
        self.assertEqual(self.parts['dcim']['stage'], 'commissioning')
        for r in self.rights.values():
            self.assertEqual(r['stage'], 'grid' if r['id'] == 'grid' else 'rights', r['id'])

    def test_aliases_resolve(self):
        for old, target in self.bom['aliases'].items():
            self.assertNotIn(old, self.parts, old)
            if target.startswith('site:'):
                self.assertIn(target[5:], self.rights, old)
            else:
                self.assertIn(target, self.parts, old)
        for r in self.rights.values():
            if r['from_bom_part']:
                self.assertEqual(self.bom['aliases'].get(r['from_bom_part']), 'site:' + r['id'], r['id'])

    def test_site_rights(self):
        self.assertEqual(sorted(self.rights), ['gas-supply', 'grid', 'land', 'network-access', 'permits', 'water-rights'])
        for r in self.rights.values():
            self.assertTrue(set(r['variable_classes']) <= {1, 2, 3, 4, 5} and r['variable_classes'], r['id'])
            self.assertEqual(r['scale'], 'S1', r['id'])
            for c in r['companies']:
                self.assertIn(c, self.companies, r['id'])

    def test_graph_has_a_node_per_part_and_hidden_nodes_redirect(self):
        for pid in self.parts:
            node = self.objects.get('part:' + pid)
            self.assertIsNotNone(node, pid)
            if node.get('navigation_hidden'):  # 例如 ssd 早已转向 ssd-drive：隐藏节点必须有去处
                self.assertIn(node.get('redirect_to'), self.objects, pid)
        for old, target in self.bom['aliases'].items():
            node = self.objects.get('part:' + old)
            if target.startswith('site:'):
                self.assertIsNotNone(node, old)  # 权利保留研究节点，3D 场景仍按旧 ID 打开
            else:
                self.assertTrue(node and node.get('navigation_hidden') and node.get('redirect_to') == 'part:' + target, old)
        for domain in self.graph['hardware_domains']:
            for oid in domain['object_ids']:
                self.assertFalse(self.objects[oid].get('navigation_hidden'), oid)

    def test_factor_tree_and_products_reference_current_ids(self):
        factors = load('framework/tco_factors.json')['factors']
        hooked = set()
        for f in factors:
            for pid in f.get('bom_parts', []):
                self.assertIn(pid, self.parts, f['id'])
                hooked.add(pid)
            for rid in f.get('site_rights', []):
                self.assertIn(rid, self.rights, f['id'])
        unhooked = {pid for pid, p in self.parts.items() if p['kind'] == 'part'} - hooked
        self.assertEqual(unhooked, {'bbu'}, '每个物理部件都应归入某个因子（bbu 待电芯档案后归入）')
        self.assertTrue({r for f in factors for r in f.get('site_rights', [])} >= set(self.rights) - {'network-access'})
        for rec in load('data/products.json')['records']:
            for pid in rec.get('bom_parts') or []:
                self.assertIn(pid, self.parts, rec['product_line'])
            self.assertIn(rec.get('bom_layer'), {s['id'] for s in self.bom['layers']}, rec['product_line'])


if __name__ == '__main__':
    unittest.main()
