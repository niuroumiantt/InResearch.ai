"""Content conservation and hostile-input boundaries for the public PPT utility."""
from http.client import HTTPConnection
from io import BytesIO
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from inresearch.delivery import presentation_layout as layout
from inresearch.interfaces import http, public
from inresearch.interfaces import presentation_layout as endpoint

ROOT = Path(__file__).resolve().parents[2]


def shape(sid, value, title=False):
    ph = '<p:ph type="title"/>' if title else '<p:ph type="body" idx="1"/>'
    return f'''<p:sp><p:nvSpPr><p:cNvPr id="{sid}" name="原始对象{sid}"/><p:cNvSpPr/><p:nvPr>{ph}</p:nvPr></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="100000" y="{sid * 1000000}"/><a:ext cx="9000000" cy="2000000"/></a:xfrm></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:pPr/><a:r><a:rPr b="1" sz="2400"><a:hlinkClick r:id="rIdLink"/></a:rPr><a:t xml:space="preserve">{escape(value)}</a:t></a:r><a:br/><a:r><a:rPr sz="1800"/><a:t>第二行 Evidence 12.50%</a:t></a:r><a:endParaRPr/></a:p></p:txBody></p:sp>'''


def fixture(extra='', value='正文：“GPU” 128 GB；−12.5% —— 原文不改。', pages=1):
    header = f'xmlns:p="{layout.P}" xmlns:a="{layout.A}" xmlns:r="{layout.R}"'
    rels = f'xmlns="{layout.REL}"'
    slide = f'<p:sld {header}><p:cSld><p:spTree><p:nvGrpSpPr/><p:grpSpPr/>{shape(2,"研究 Research",True)}{shape(3,value)}{extra}</p:spTree></p:cSld></p:sld>'
    members = {
        '[Content_Types].xml': b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/></Types>',
        'ppt/presentation.xml': f'<p:presentation {header}><p:sldIdLst>' + ''.join(f'<p:sldId id="{256+i}" r:id="s{i}"/>' for i in range(pages)) + '</p:sldIdLst><p:sldSz cx="15240000" cy="8572500"/></p:presentation>',
        'ppt/_rels/presentation.xml.rels': f'<Relationships {rels}>' + ''.join(f'<Relationship Id="s{i}" Type="{layout.R}/slide" Target="slides/slide{i+1}.xml"/>' for i in range(pages)) + '</Relationships>',
        'ppt/slideLayouts/slideLayout1.xml': f'<p:sldLayout {header}><p:cSld><p:spTree/></p:cSld></p:sldLayout>',
        'ppt/slideLayouts/_rels/slideLayout1.xml.rels': f'<Relationships {rels}><Relationship Id="m" Type="{layout.R}/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>',
        'ppt/slideMasters/slideMaster1.xml': f'<p:sldMaster {header}><p:cSld><p:spTree/></p:cSld></p:sldMaster>',
        'ppt/media/image1.png': b'\x89PNG\r\noriginal-evidence-image',
        'ppt/charts/chart1.xml': '<chart><value>12.500</value><formula>Sheet1!B2</formula></chart>',
        'ppt/embeddings/workbook.xlsx': b'unchanged-embedded-workbook',
        'ppt/notesSlides/notesSlide1.xml': '<notes>保留原备注、来源及保密提示</notes>',
    }
    for i in range(pages):
        members[f'ppt/slides/slide{i+1}.xml'] = slide
        members[f'ppt/slides/_rels/slide{i+1}.xml.rels'] = f'<Relationships {rels}><Relationship Id="l" Type="{layout.R}/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rIdLink" Type="{layout.R}/hyperlink" Target="https://example.test/evidence?q=1" TargetMode="External"/></Relationships>'
    return package(members)


def package(members):
    out = BytesIO()
    with ZipFile(out, 'w', ZIP_DEFLATED) as z:
        for name, value in members.items():
            z.writestr(name, value)
    return out.getvalue()


def replace(raw, name, value):
    with ZipFile(BytesIO(raw)) as z:
        items = {n: z.read(n) for n in z.namelist()}
    items[name] = value
    return package(items)


class LayoutTests(unittest.TestCase):
    def test_content_resources_relationships_notes_and_order_are_preserved(self):
        raw = fixture(pages=2)
        output, report = layout.transform(raw)
        self.assertEqual(report['counts'], {'reflowed': 2})
        self.assertFalse(report['model_used'])
        with ZipFile(BytesIO(raw)) as before, ZipFile(BytesIO(output)) as after:
            self.assertEqual(before.namelist(), after.namelist())
            for name in before.namelist():
                if not name.startswith('ppt/slides/slide'):
                    self.assertEqual(before.read(name), after.read(name), name)
                else:
                    old, new = ET.fromstring(before.read(name)), ET.fromstring(after.read(name))
                    for a, b in zip(old.iter('{'+layout.A+'}p'), new.iter('{'+layout.A+'}p')):
                        self.assertEqual(''.join(a.itertext()), ''.join(b.itertext()))
                    links = list(new.iter('{'+layout.A+'}hlinkClick'))
                    self.assertTrue(links)
                    self.assertTrue(all(n.get('{'+layout.R+'}id') == 'rIdLink' for n in links))
                    for r in new.iter('{'+layout.A+'}r'):
                        val = r.find('{'+layout.A+'}t').text or ''
                        props = r.find('{'+layout.A+'}rPr')
                        if any(c in val for c in '中文研究正文第二行“”—'):
                            self.assertEqual(props.find('{'+layout.A+'}latin').get('typeface'), 'FangSong')
                            self.assertEqual(props.get('b'), '0')
                            self.assertEqual(props.get('i'), '0')

    def test_fonts_only_keeps_all_geometry_and_dense_page_is_not_forced(self):
        for raw, mode in ((fixture(), 'fonts'), (fixture(value='拥挤内容 ' * 3000), 'layout')):
            out, report = layout.transform(raw, mode=mode)
            self.assertEqual(report['counts'], {'fonts_only': 1})
            with ZipFile(BytesIO(raw)) as a, ZipFile(BytesIO(out)) as b:
                for tag in ('off', 'ext'):
                    old = ET.fromstring(a.read('ppt/slides/slide1.xml')).iter('{'+layout.A+'}'+tag)
                    new = ET.fromstring(b.read('ppt/slides/slide1.xml')).iter('{'+layout.A+'}'+tag)
                    self.assertEqual([n.attrib for n in old], [n.attrib for n in new])

    def test_graphics_and_animations_keep_layout_and_payload(self):
        extra = '<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="5" name="chart"/></p:nvGraphicFramePr><a:graphic><a:graphicData uri="chart"/></a:graphic></p:graphicFrame>'
        raw = fixture(extra=extra)
        out, report = layout.transform(raw)
        self.assertEqual(report['counts'], {'fonts_only': 1})
        with ZipFile(BytesIO(out)) as z:
            self.assertIn(extra.encode(), z.read('ppt/slides/slide1.xml'))

    def test_template_round_trip_preserves_all_binary_assets_and_slide_count(self):
        path = next((ROOT / 'web/assets/marketing').glob('*模板*.pptx'))
        raw = path.read_bytes()
        result, report = layout.transform(raw)
        with ZipFile(BytesIO(raw)) as a, ZipFile(BytesIO(result)) as b:
            slides = [n for n in a.namelist() if n.startswith('ppt/slides/slide') and n.endswith('.xml')]
            self.assertEqual(report['slides'], len(slides))
            for n in a.namelist():
                if n not in slides:
                    self.assertEqual(a.read(n), b.read(n), n)

    def test_rejects_invalid_bombs_macro_signature_entities_and_excess_pages(self):
        bad = [b'not pptx', b'%PDF-1.7', fixture(pages=101),
               replace(fixture(), 'ppt/vbaProject.bin', b'macro'),
               replace(fixture(), '_xmlsignatures/sig1.xml', b'signed'),
               replace(fixture(), '../escape', b'payload'),
               replace(fixture(), 'bomb.bin', b'A' * (1024 * 1024)),
               replace(fixture(), 'ppt/slides/slide1.xml', '<!DOCTYPE x [<!ENTITY a "secret">]><x>&a;</x>')]
        for raw in bad:
            with self.subTest(size=len(raw)), self.assertRaises(layout.LayoutError):
                layout.transform(raw)

    def test_bundle_contains_pptx_machine_and_readable_report(self):
        raw, report = layout.bundle(fixture())
        with ZipFile(BytesIO(raw)) as z:
            self.assertEqual(set(z.namelist()), {'inresearch-formatted.pptx', 'layout-report.json', '排版说明.txt'})
            self.assertEqual(json.loads(z.read('layout-report.json')), report)


class LayoutHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = http.ThreadingHTTPServer(('127.0.0.1', 0), http.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(lambda: (self.server.shutdown(), self.thread.join(), self.server.server_close()))
        endpoint.REQUESTS.clear()

    def request(self, raw, headers=None):
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=45)
        fields = {'Content-Type': layout.PPTX_MIME, 'X-Requested-With': 'presentation-layout'}
        fields.update(headers or {})
        conn.request('POST', '/api/presentation-layout', raw, fields)
        response = conn.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        conn.close()
        return result

    def test_anonymous_and_customer_receive_private_download_without_storage(self):
        for actor in (None, 'customer'):
            with patch.object(http, 'AUTH_ON', True), patch.object(http.auth, 'session_user', return_value=actor), patch.object(http.auth, 'user_role', return_value='customer'), patch.object(http, 'workspace_path', side_effect=AssertionError('no persistence')):
                status, headers, raw = self.request(fixture())
            self.assertEqual(status, 200, raw[:200])
            self.assertIn('no-store', headers['Cache-Control'])
            self.assertEqual(headers['X-Layout-Slides'], '1')
            with ZipFile(BytesIO(raw)) as z:
                self.assertIn('inresearch-formatted.pptx', z.namelist())

    def test_rejects_cross_origin_invalid_and_busy_without_leaking_content(self):
        self.assertEqual(self.request(b'x', {'Origin': 'https://evil.test'})[0], 403)
        self.assertEqual(self.request(b'x', {'X-Requested-With': ''})[0], 403)
        self.assertEqual(self.request(b'x', {'Content-Type': 'text/plain'})[0], 415)
        self.assertEqual(self.request(b'PRIVATE CORRUPT INPUT')[0], 422)
        self.assertEqual(self.request(b'x', {'X-Layout-Mode': 'shell'})[0], 400)
        with patch.object(endpoint.SLOT, 'acquire', return_value=False):
            self.assertEqual(self.request(b'x')[0], 503)

    def test_rate_limit_and_expiry(self):
        with patch.object(endpoint.time, 'monotonic', return_value=1000):
            self.assertTrue(all(endpoint.rate_allowed('test') for _ in range(5)))
            self.assertFalse(endpoint.rate_allowed('test'))
        with patch.object(endpoint.time, 'monotonic', return_value=1301):
            self.assertTrue(endpoint.rate_allowed('test'))

    def test_cloudfront_host_rewrite_allows_only_the_exact_public_origin(self):
        status, _, body = self.request(fixture(), {'Host': 'origin.inresearch.ai', 'Origin': 'https://inresearch.ai', 'Sec-Fetch-Site': 'same-origin'})
        self.assertEqual(status, 200, body[:200])
        for origin in ('https://evil.test', 'https://inresearch.ai.evil.test', 'http://inresearch.ai'):
            self.assertEqual(self.request(b'x', {'Host': 'origin.inresearch.ai', 'Origin': origin})[0], 403)
        self.assertEqual(self.request(b'x', {'Host': 'another-origin.test', 'Origin': 'https://inresearch.ai'})[0], 403)

    def test_customer_can_open_the_tool_and_its_exact_public_assets_only(self):
        import re
        page = (ROOT / 'web/pages/marketing.html').read_text()
        assets = set(re.findall(r'(?:src|href)="(/assets/marketing/[^\"]+)"', page))
        for path in ['/marketing.html', *assets]:
            self.assertTrue(public.customer_allowed(ROOT, path), path)
        self.assertTrue(public.customer_allowed(ROOT, '/api/presentation-layout', method='POST'))
        self.assertFalse(public.customer_allowed(ROOT, '/assets/marketing/unregistered-private.pptx'))
        self.assertFalse(public.customer_allowed(ROOT, '/api/research'))
        conn = HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        with patch.object(http, 'AUTH_ON', True), patch.object(http.auth, 'session_user', return_value='customer'), patch.object(http.auth, 'user_role', return_value='customer'):
            conn.request('GET', '/marketing.html'); response = conn.getresponse()
            self.assertEqual(response.status, 200); self.assertIn(b'ppt-layout-form', response.read())
        conn.close()


if __name__ == '__main__':
    unittest.main()
