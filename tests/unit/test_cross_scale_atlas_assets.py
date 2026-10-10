"""Read-only TA35 conservation/identity tests; no HTTP, renderer or product JS.

Run the tmp candidate with TA_CROSS_SCALE_SOURCE_ROOT=/absolute/checkout.
After installation under tests/unit, the default root is the repository root.
Saved evidence is checked structurally everywhere, and by bytes when its local
original exists. Missing host audit files do not make CI depend on /Users/m4.
Static path math is not a visual, upstream provenance or public-page verdict.
"""
import ast
import base64
import hashlib
import json
import math
import os
import re
import struct
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(os.environ.get('TA_CROSS_SCALE_SOURCE_ROOT', Path(__file__).resolve().parents[2]))
D = ROOT / 'docs/design/technical-atlas/TA-35'
ASSETS = ROOT / 'web/assets/technical-atlas'
NS = {'s': 'http://www.w3.org/2000/svg'}
MERGE = 'a379dbba9799c82b095843d87775271b0427686d'
HEAD = 'd8348ee3de523ae1a182cd0fb8fb7b9dbd21fe84'


def read(path):
    return json.loads(path.read_text())


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def png_size(raw):
    if raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR':
        raise ValueError('Expected native PNG IHDR')
    return struct.unpack('>II', raw[16:24])


def points(path):
    """This diagram deliberately uses absolute editable M/L paths only."""
    data = path.get('d', '')
    tokens = re.findall(r'[ML]|[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?', data)
    if re.sub(r'[ML\s,\d.eE+\-]', '', data):
        raise ValueError('Unexpected path command')
    result = []
    i = 0
    while i < len(tokens):
        if tokens[i] not in ('M', 'L') or i + 2 >= len(tokens):
            raise ValueError('Malformed editable line')
        result.append((float(tokens[i + 1]), float(tokens[i + 2])))
        i += 3
    if not all(math.isfinite(v) for p in result for v in p):
        raise ValueError('Non-finite SVG coordinate')
    return result


def distance_to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    t = max(0, min(1, ((p[0]-a[0])*dx + (p[1]-a[1])*dy) / (dx*dx + dy*dy))) if dx or dy else 0
    return math.hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(v for k, v in attrs if k in ('href', 'src') and v)


class CrossScaleAtlasAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = read(D / 'component-manifest-v1.json')
        cls.full = ET.parse(ASSETS / 'cross-scale-v1.svg').getroot()
        cls.preview = ET.parse(ASSETS / 'cross-scale-v1-preview.svg').getroot()

    def assertProof(self, row):
        self.assertRegex(row['sha256'], r'^[0-9a-f]{64}$')
        self.assertGreater(row['bytes'], 0)
        path = Path(row['path'])
        if path.is_file():
            raw = path.read_bytes()
            self.assertEqual(len(raw), row['bytes'], str(path))
            self.assertEqual(sha(raw), row['sha256'], str(path))

    def test_four_assets_native_dimensions_and_exact_embedded_rasters(self):
        manifest = read(D / 'asset-manifest-v1.json')['assets']
        acceptance = read(D / 'acceptance-v1.json')
        self.assertEqual(manifest, acceptance['artifacts'])
        self.assertEqual({Path(r['file']).suffix for r in manifest}, {'.png', '.svg', '.jpg'})
        self.assertEqual(len(manifest), 4)
        for row in manifest:
            raw = (ROOT / row['file']).read_bytes()
            self.assertEqual((len(raw), sha(raw)), (row['bytes'], row['sha256']))
        native = (ASSETS / 'cross-scale-v1.png').read_bytes()
        self.assertEqual(png_size(native), (1536, 1024))
        self.assertEqual(sha(native), read(D / 'generation-v1.json')['native_original_sha256'])
        for svg, name, mime in [(self.full, 'cross-scale-v1.png', 'png'), (self.preview, 'cross-scale-v1-preview.jpg', 'jpeg')]:
            self.assertEqual([float(v) for v in svg.get('viewBox').split()], [0, 0, 1536, 1024])
            images = svg.findall('.//s:image', NS)
            self.assertEqual(len(images), 1)
            image = images[0]
            self.assertEqual((image.get('width'), image.get('height')), ('1536', '1024'))
            prefix, encoded = image.get('href').split(',', 1)
            self.assertEqual(prefix, 'data:image/' + mime + ';base64')
            self.assertEqual(base64.b64decode(encoded, validate=True), (ASSETS / name).read_bytes())

    def test_six_adopted_originals_crop_contain_affine_and_source_anchors(self):
        rows = self.manifest['components']
        self.assertEqual({r['id'] for r in rows}, {'package', 'server', 'rack', 'facility', 'nic', 'switch'})
        self.assertEqual(len(rows), 6)
        # The independently adopted bytes, not values derived from TA35's own manifest.
        originals = {
            'chip-package-v1.png': '70a96800f1c0ef4e529d52b5c03adde027e05eb6e0f0e2ad39537d1c099e7721',
            'server-v1.png': 'abc8d42457216cf752fb6028c9c4251c50213e56c530ea99a005106bb15fdd15',
            'rack-overview-v1.png': 'd92ac021351375735f3b1ad93b3b6553aaecf84ad2a4bb1079ab20d03b89e49e',
            'campus-overview-v1.png': 'c8a1ca2ef4e4c08d93fe2626575f8482831f057dbefaf2e235a4d764c7e6191f',
            'nic-v1.png': 'a1262414eb704589eb1ec10bb290c6b238126b6b5dde574f28a4eb04ff24c151',
            'system/network-switch-v2.png': 'a6269fa55228a0a856e6924e98fed53ee2fccefc3c3bb07e215ae8f652643e61',
        }
        for row in rows:
            with self.subTest(component=row['id']):
                raw = (ASSETS / row['file']).read_bytes()
                self.assertEqual(sha(raw), originals[row['file']])
                self.assertEqual((sha(raw), len(raw)), (row['sha256'], row['bytes']))
                width, height = png_size(raw)
                x, y, w, h = row['crop']; bx, by, bw, bh = row['box']
                self.assertTrue(0 <= x < x+w <= width and 0 <= y < y+h <= height)
                self.assertTrue(w > 0 and h > 0 and bw > 0 and bh > 0)
                scale = min(bw/w, bh/h)
                translate = [bx+(bw-w*scale)/2-x*scale, by+(bh-h*scale)/2-y*scale]
                self.assertAlmostEqual(row['affine']['scale'], scale, places=12)
                for got, expected in zip(row['affine']['translate'], translate):
                    self.assertAlmostEqual(got, expected, places=10)
                ax, ay = row['source_anchor']
                self.assertTrue(x <= ax <= x+w and y <= ay <= y+h)
                expected = [ax*scale+translate[0], ay*scale+translate[1]]
                for got, want in zip(row['display_anchor'], expected):
                    self.assertAlmostEqual(got, want, delta=0.000051)
                self.assertTrue(bx <= expected[0] <= bx+bw and by <= expected[1] <= by+bh)
        self.assertFalse(self.manifest['originals_modified'])
        self.assertTrue(self.manifest['no_new_BOM_objects'])

    def test_licensed_original_fonts_embedded_subsets_and_editable_layer_parity(self):
        proof = read(D / 'font-subset-proof-v1.json')
        self.assertEqual(len(proof['fonts']), 3)
        self.assertFalse(proof['external_font_requests'])
        self.assertTrue(proof['license_texts_embedded_in_full_and_preview'])
        texts = lambda root: [''.join(e.itertext()) for e in root.findall('.//s:text', NS)]
        self.assertEqual(texts(self.full), texts(self.preview))
        actual_codepoints = {ord(c) for t in texts(self.full) for c in t}
        self.assertEqual(actual_codepoints, set(proof['text_codepoints']))
        cover = set()
        for svg in [self.full, self.preview]:
            license_meta = svg.find('s:metadata[@id="embedded-font-licenses"]', NS)
            self.assertIsNotNone(license_meta)
            license_texts = json.loads(license_meta.text)['licenses']
            self.assertEqual(set(license_texts), {r['license'] for r in proof['fonts']})
            for path, text in license_texts.items():
                self.assertEqual(text, (ROOT / path).read_text())
            css = ''.join(e.text or '' for e in svg.findall('.//s:style', NS))
            faces = re.findall(r'@font-face\{([^}]+)\}', css)
            self.assertEqual(len(faces), 3)
            for face, row in zip(faces, proof['fonts']):
                original = (ROOT / row['original_file']).read_bytes()
                self.assertEqual(sha(original), row['original_sha256'])
                self.assertIn('SIL OPEN FONT LICENSE', (ROOT / row['license']).read_text())
                embedded = re.search(r'data:font/woff2;base64,([A-Za-z0-9+/=]+)', face)
                self.assertIsNotNone(embedded)
                raw = base64.b64decode(embedded.group(1), validate=True)
                self.assertEqual((sha(raw), len(raw)), (row['subset_sha256'], row['bytes']))
                self.assertEqual(raw[:4], b'wOF2')
                self.assertEqual(struct.unpack('>I', raw[8:12])[0], len(raw))
                # Do not interpret chance U+ bytes inside the base64 font as CSS.
                declarations = re.sub(r'data:font/woff2;base64,[A-Za-z0-9+/=]+', '', face)
                declared = {int(v, 16) for v in re.findall(r'U\+([0-9A-F]+)', declarations)}
                self.assertEqual(declared, set(row['unicode_points']))
                cover.update(declared)
            self.assertNotRegex(css, r'url\(["\']?(?:https?:|//|/)')
        self.assertTrue(actual_codepoints <= cover)
        def vector_signature(root):
            return [(e.tag, sorted(e.attrib.items()), e.text) for e in root.iter() if e.tag.rsplit('}', 1)[-1] not in ('svg', 'style', 'image')]
        self.assertEqual(vector_signature(self.full), vector_signature(self.preview))

    def test_seven_editable_leaders_have_same_identity_and_mathematical_anchors(self):
        labels = read(D / 'labels-v1.json')['labels']
        self.assertEqual(labels, self.manifest['labels'])
        self.assertEqual({r['number'] for r in labels}, {f'{i:02}' for i in range(1, 8)})
        source_for = {'01': 'package', '02': 'server', '03': 'nic', '04': 'rack', '05': 'facility'}
        components = {r['id']: r for r in self.manifest['components']}
        groups = {g.get('data-label'): g for g in self.full.findall('.//s:g[@class="callout"]', NS)}
        self.assertEqual(set(groups), set(r['number'] for r in labels))
        for row in labels:
            group = groups[row['number']]
            self.assertEqual(group.get('data-object'), row['part_id'])
            paths = group.findall('s:path', NS); circles = group.findall('s:circle', NS)
            self.assertEqual((len(paths), len(circles)), (1, 1))
            anchor = tuple(row['display_anchor'])
            self.assertEqual(points(paths[0])[-1], anchor)
            self.assertEqual((float(circles[0].get('cx')), float(circles[0].get('cy'))), anchor)
            self.assertGreater(float(circles[0].get('r')), 0)
            if row['number'] in source_for:
                self.assertEqual(list(anchor), components[source_for[row['number']]]['display_anchor'])
            else:
                self.assertIn('logical', row['scope'])
        flows = {p.get('data-flow'): p for p in self.full.findall('.//s:path[@data-flow]', NS)}
        electric = points(flows['electric-power'])
        p = next(r['display_anchor'] for r in labels if r['number'] == '06')
        self.assertAlmostEqual(distance_to_segment(p, electric[0], electric[-1]), 0)

    def test_function_graph_separates_context_data_energy_and_two_fluid_loops(self):
        root_paths = self.full.findall('s:path', NS)
        flow = {p.get('data-flow'): p for p in root_paths if p.get('data-flow')}
        self.assertEqual(set(flow), {'context-location', 'host-pcie', 'external-network', 'electric-power', 'tcs-loop', 'fws-loop', 'heat-only'})
        arrowheads = [points(p) for p in root_paths if not p.get('data-flow') and len(points(p)) == 3]
        self.assertEqual(len(arrowheads), 8)
        tips = [p[1] for p in arrowheads]
        context = flow['context-location']; ends = points(context)
        self.assertIsNotNone(context.get('stroke-dasharray'))
        self.assertTrue(set(ends).isdisjoint(tips))
        self.assertTrue(all(context.get(k) is None for k in ['marker-start', 'marker-end']))
        for name in ['host-pcie', 'external-network']:
            a, b = points(flow[name])
            self.assertIn(a, tips); self.assertIn(b, tips)
            for endpoint, other in [(a, b), (b, a)]:
                head = next(p for p in arrowheads if p[1] == endpoint)
                # Wings remain inside the relation span: each tip points outwards.
                self.assertTrue(all((wing[0]-endpoint[0])*(other[0]-endpoint[0]) + (wing[1]-endpoint[1])*(other[1]-endpoint[1]) > 0 for wing in [head[0], head[2]]))
        loops = []
        for name in ['tcs-loop', 'fws-loop']:
            ps = points(flow[name]); self.assertEqual(ps[0], ps[-1])
            self.assertEqual(len(set(ps)), 4)
            self.assertTrue(all((a[0] == b[0]) != (a[1] == b[1]) for a, b in zip(ps, ps[1:])))
            self.assertGreater(abs(sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(ps, ps[1:]))), 0)
            loops.append((min(p[0] for p in ps), max(p[0] for p in ps), min(p[1] for p in ps), max(p[1] for p in ps)))
        left, right = loops
        self.assertLess(left[1], right[0])
        wall = next(points(p) for p in root_paths if not p.get('data-flow') and len(points(p)) == 4)
        self.assertEqual(wall[0][0], wall[1][0]); self.assertEqual(wall[2][0], wall[3][0])
        self.assertTrue(left[1] < wall[0][0] < wall[2][0] < right[0])
        heat = points(flow['heat-only']); self.assertEqual(heat[0][1], heat[1][1])
        for a, b in [wall[:2], wall[2:]]:
            self.assertTrue(heat[0][0] < a[0] < heat[1][0])
            self.assertTrue(min(a[1], b[1]) < heat[0][1] < max(a[1], b[1]))
        self.assertIsNotNone(flow['heat-only'].get('stroke-dasharray'))
        self.assertEqual(points(flow['electric-power'])[-1] in tips, True)
        self.assertNotEqual(flow['electric-power'].get('stroke'), flow['host-pcie'].get('stroke'))

    def test_binding_is_double_gated_and_complete_previous_atlas_bytes_survive(self):
        before = (D / 'technical-atlas-before-v1.js').read_text()
        actual = (ROOT / 'web/components/technical-atlas.js').read_text()
        start = actual.index('const crossScale=')
        end = actual.index('export function mountTechnicalAtlas', start)
        extension = actual[start:end]
        item = json.loads(extension.split('=', 1)[1].strip().removesuffix(';'))
        self.assertEqual(item['id'], 'TA-35')
        self.assertEqual(item['master'], '/assets/technical-atlas/cross-scale-v1.png')
        self.assertEqual(actual[:start], before[:before.index('export function mountTechnicalAtlas')])
        restored = actual[:start] + actual[end:]
        gate = re.compile(r"partId\s*===\s*'cross-scale'\s*&&\s*view\s*===\s*'cross-scale'\s*\?\s*crossScale\s*:\s*")
        self.assertEqual(len(gate.findall(restored)), 1)
        self.assertEqual(gate.sub('', restored, count=1), before)
        # Exact prior lookup/rendering bytes preclude injection into the old defaults.
        self.assertEqual(len(item['related']), 6)

    def test_visible_bom_link_only_geometry_conservation_and_real_public_routes(self):
        before = (D / 'bom-before-v1.html').read_text()
        actual = (ROOT / 'web/pages/bom.html').read_text()
        link = re.compile(r'^\s*<a\b[^\n]*\bdata-atlas-cross-scale>[^\n]*</a>\n', re.M)
        matches = link.findall(actual); self.assertEqual(len(matches), 1)
        self.assertIn('href="/cross-scale-atlas.html"', matches[0])
        self.assertNotIn('hidden', matches[0])
        self.assertEqual(link.sub('', actual), before)
        for row in read(ROOT / 'docs/design/technical-atlas/TA-29/baseline-v1.json')['unchanged_reuse']:
            raw = (ROOT / row['source']).read_bytes()
            self.assertEqual((sha(raw), len(raw)), (row['sha256'], row['bytes']))
        routes = read(ROOT / 'web/routes.json')
        page = ROOT / 'web/pages/cross-scale-atlas.html'
        self.assertEqual(routes['/cross-scale-atlas.html'], str(page.relative_to(ROOT)))
        for row in read(D / 'asset-manifest-v1.json')['assets']:
            url = '/' + row['file'].removeprefix('web/')
            self.assertEqual(routes[url], row['file']); self.assertTrue((ROOT / routes[url]).is_file())
        links = Links(); links.feed(page.read_text())
        links.urls += re.findall(r"from\s*['\"](/[^'\"]+)['\"]", page.read_text())
        for url in links.urls:
            if url.startswith('/') and not url.startswith('//'):
                path = urlsplit(url).path
                self.assertIn(path, routes, url); self.assertTrue((ROOT / routes[path]).is_file(), url)
        self.assertRegex(page.read_text(), r"mountTechnicalAtlas\([^;]+,'cross-scale',\{view:'cross-scale'\}\)")
        tree = ast.parse((ROOT / 'src/inresearch/interfaces/public.py').read_text())
        reader_pages = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'READER_PAGES' for t in n.targets))
        self.assertIn('/cross-scale-atlas.html', reader_pages)
        interface = read(ROOT / 'framework/interface_manifest.json')
        for key in ['static_pages', 'public_pages']:
            self.assertIn('cross-scale-atlas.html', interface[key])
        self.assertIn('cross-scale-atlas.html', interface['sections']['bom'])
        self.assertEqual(interface['page_sources']['cross-scale-atlas.html'], str(page.relative_to(ROOT)))

    def test_five_actual_publications_are_bound_and_progress_can_advance_to_35(self):
        q = read(ROOT / 'framework/visual_atlas_migration.json')
        items = {r['id']: r for r in q['items']}
        independent = read(ROOT / 'docs/design/technical-atlas/TA-30/publication-pack-independent-review-v4.json')
        binding = independent['binding']
        self.assertEqual((binding['head'], binding['merge']), (HEAD, MERGE))
        self.assertEqual((binding['health_sources'], binding['healthz']), (21, 200))
        self.assertEqual((independent['actual_primary_published'], independent['supplemental_published']), (34, 4))
        for n, object_id in zip(range(30, 35), ['server_nvme', 'server_gpu', 'server_storage', 'switch_tor', 'switch_ib']):
            folder = ROOT / f'docs/design/technical-atlas/TA-{n}'
            pub = read(folder / 'publication-20261010.json'); checks = read(folder / 'public-checks-v1.json')
            self.assertEqual((pub['figure_id'], pub['object_id']), (f'TA-{n}', object_id))
            self.assertEqual(items[f'TA-{n}']['status'], 'published')
            self.assertEqual(items[f'TA-{n}']['published_revision'], MERGE)
            self.assertEqual((pub['source_head'], pub['source_merge']), (HEAD, MERGE))
            self.assertEqual(pub['source_prs'][0]['headRefOid'], HEAD)
            self.assertEqual(pub['source_prs'][0]['mergeCommit']['oid'], MERGE)
            health = pub['final_fix_deployment']
            self.assertEqual((health['source_revision'], health['applied_revision']), (MERGE, MERGE))
            self.assertEqual(health['image'], health['applied_image'])
            self.assertEqual(health['image'], binding['exact_image'])
            self.assertEqual(health['container_state'], 'running/healthy')
            self.assertEqual(health['status'], 'HEALTHY: ' + MERGE)
            self.assertEqual(pub['actual_primary_published'], n)
            self.assertEqual(pub['supplemental_published'], 4)
            self.assertEqual(checks['counts']['batch_fault_records'], 15)
            self.assertEqual(checks['public_observation'], pub['public_checks_evidence'])
            self.assertEqual(checks['source_health'], pub['source_checks_evidence'])
            self.assertEqual(checks['owner_original_review'], pub['owner_original_review'])
            for key in ['original_source_deployment', 'public_checks_evidence', 'source_checks_evidence', 'owner_original_review', 'CI', 'final_closure_evidence']:
                self.assertProof(pub[key])
            ci_path = Path(pub['CI']['path'])
            if ci_path.is_file():
                ci = read(ci_path)
                self.assertEqual((ci['head'], ci['merge']), (HEAD, MERGE))
                self.assertTrue(ci['all_checks_success'] and ci['all_checks_on_exact_head'] and ci['normal_merge_no_admin_bypass'])
                self.assertTrue(ci['check_runs'])
                self.assertTrue(all(r['head_sha'] == HEAD and r['conclusion'] == 'success' for r in ci['check_runs']))
            health_path = Path(pub['source_checks_evidence']['path'])
            if health_path.is_file():
                observed = read(health_path)
                self.assertEqual(observed['source_head'], MERGE)
                self.assertEqual(observed['health']['status'], 200)
                self.assertTrue(observed['PASS'])
                self.assertEqual(len(observed['source_checks']), 21)
                self.assertTrue(all(r['match'] and r['status'] == 200 for r in observed['source_checks']))
            failures = checks['retained_failure_evidence']
            self.assertEqual([Path(r['path']).parent.name for r in failures], ['public-v1', 'public-v2', 'public-v3'])
            for row in failures:
                self.assertProof(row)
                if Path(row['path']).is_file():
                    self.assertEqual(read(Path(row['path']))['stage'], 'FAILED')
            self.assertTrue(any('cause remains unknown' in s for s in pub['boundaries']))
        # Saved per-item completion is stable; the global count may legitimately reach35.
        primary = [r for r in q['items'] if r.get('order', 999) <= 35]
        published = sum(r['status'] == 'published' for r in primary)
        self.assertEqual(q['primary_plan']['published'], published)
        self.assertGreaterEqual(published, 34)
        self.assertLessEqual(published, 35)
        acc = read(D / 'acceptance-v1.json'); current = items['TA-35']
        self.assertEqual(acc['object_id'], current['object_id'])
        if current['status'] in ('accepted', 'published'):
            self.assertTrue(acc['actual_new_public_execution'])
            self.assertTrue(acc['actual_public_receipt'])
            if current['status'] == 'published':
                pub = read(ROOT / current['publication_record'])
                self.assertEqual(pub['status'], 'published')
                self.assertEqual(pub['object_id'], 'cross-scale')
                self.assertEqual(pub['source_merge'], current['published_revision'])
        else:
            self.assertIn(current['status'], ('drafting', 'review'))
            self.assertFalse(acc['actual_new_public_execution'])
            self.assertEqual(acc['publication_status'], 'not_published')
            self.assertIsNone(current['published_revision'])


if __name__ == '__main__':
    unittest.main()
