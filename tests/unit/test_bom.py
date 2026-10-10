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
        self.assertEqual([s['id'] for s in self.bom['scales']], ['S1', 'S2', 'S3', 'S4', 'S5'])
        self.assertEqual([s['name'] for s in self.bom['scales']], ['园区', '建筑', '机房', '机柜', '部件'])

    def test_kind_and_scale(self):
        scales = {s['id'] for s in self.bom['scales']}
        for p in self.bom['parts']:
            self.assertIn(p['kind'], self.bom['kinds'], p['id'])
            self.assertIn(p['system'], self.bom['systems'], p['id'])
            self.assertIn(p['status'], ('mature', 'tight', 'transition', 'emerging'), p['id'])
            if p['kind'] == 'part':
                self.assertIn(p['scale'], scales, p['id'])
            else:
                self.assertIsNone(p['scale'], p['id'])
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
        # 一个骨架：五个系统，IT 三分、存储再分；系统内按能量流链路排；部件只挂叶子系统
        systems = self.bom['systems']
        top = [sid for sid, s in systems.items() if not s.get('parent')]
        self.assertEqual([systems[s]['name'] for s in sorted(top, key=lambda s: systems[s]['order'])], ['设施', '水与散热', '电', 'IT设施', '控制与软件'])
        self.assertEqual(sorted(sid for sid, s in systems.items() if s.get('parent') == 'it'), ['compute', 'network', 'storage-group'])
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

    def test_graph_parts_follow_chain_order(self):
        # 图谱 3.0 由骨架生成：部件对象按系统顺序 × 链路顺序 × chain_order 排
        systems = self.bom['systems']
        def key(o):
            from inresearch.knowledge.skeleton import system_key
            return (system_key(systems, o['system']), systems[o['system']]['chains'].index(o['chain']), o['chain_order'])
        keys = [key(o) for o in self.graph['objects'] if o['kind'] == 'part']
        self.assertEqual(keys, sorted(keys))

    def test_user_classification_of_2026_10_10(self):
        systems = self.bom['systems']
        self.assertEqual(systems['memory']['parent'], 'storage-group')
        self.assertEqual(systems['storage']['parent'], 'storage-group')
        self.assertEqual(systems['storage']['name'], 'IT · 持久存储')
        groups = systems['compute']['processor_groups']
        self.assertEqual([g['name'] for g in groups], ['CPU', 'GPU', '其他'])
        self.assertEqual([g['parts'] for g in groups], [['cpu'], ['gpu'], ['ai-asic', 'fpga']])
        partition = [pid for g in groups for pid in g['parts']] + systems['compute']['support_parts']
        self.assertEqual(sorted(partition), sorted(p['id'] for p in self.parts.values() if p['system']=='compute'))
        self.assertEqual(self.objects['system:memory']['parent'], 'system:storage-group')
        self.assertEqual(self.objects['system:storage-group']['parent'], 'system:it')

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

    def test_graph_is_the_skeleton_and_old_ids_are_aliases(self):
        # 每个部件、权利、系统一个对象；被重切的旧 ID 是目标对象的别名，不再是隐藏节点
        for pid in self.parts:
            self.assertEqual(self.objects['part:' + pid]['kind'], 'part', pid)
        for rid in self.rights:
            self.assertEqual(self.objects['site:' + rid]['kind'], 'site_right', rid)
        for sid in self.bom['systems']:
            self.assertEqual(self.objects['system:' + sid]['kind'], 'system', sid)
        for old, target in self.bom['aliases'].items():
            node = self.objects[target if target.startswith('site:') else 'part:' + target]
            self.assertIn('part:' + old, node['aliases'], old)
            self.assertNotIn('part:' + old, self.objects, old)
        for key in ('hardware_domains', 'navigation', 'views', 'research_topics'):
            self.assertNotIn(key, self.graph, key)

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
            self.assertIn(rec.get('bom_layer'), {s['id'] for s in self.bom['scales']}, rec['product_line'])


if __name__ == '__main__':
    unittest.main()
