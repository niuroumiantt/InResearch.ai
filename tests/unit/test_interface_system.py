"""UI coverage and authentication boundary regression; Python standard library only."""

from inresearch.paths import project_root
import http.client
import json
import re
import threading
import unittest
from unittest.mock import patch
from inresearch.interfaces import auth as auth
from inresearch.interfaces import pages
from inresearch.interfaces import http as serve

ROOT = project_root()

class InterfaceContractTests(unittest.TestCase):
    def test_mutable_static_entries_revalidate_without_disabling_conditional_reads(self):
        with patch.object(serve, 'AUTH_ON', True), patch.object(auth, 'session_user', return_value=None):
            server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
            thread.start()
            try:
                for path in ('/bom.html', '/rack3d.html', '/assets/part-dossier.js?v=20261008.15', '/assets/site-skin.css'):
                    for method in ('GET', 'HEAD'):
                        connection = http.client.HTTPConnection(*server.server_address, timeout=3)
                        try:
                            connection.request(method, path)
                            response = connection.getresponse(); response.read()
                            self.assertEqual(response.status, 200, (method, path))
                            self.assertEqual(response.getheader('Cache-Control'), 'no-cache')
                            modified = response.getheader('Last-Modified')
                            self.assertIsNotNone(modified)
                            connection.request(method, path, headers={'If-Modified-Since': modified})
                            response = connection.getresponse(); response.read()
                            self.assertEqual(response.status, 304)
                            self.assertEqual(response.getheader('Cache-Control'), 'no-cache')
                        finally:
                            connection.close()
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_all_html_classified_and_application_hooks(self):
        manifest = json.loads((ROOT/'framework/interface_manifest.json').read_text())
        # Only tracked project HTML, excluding development/runtime artifacts.
        import subprocess
        files = set(subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','*.html'],cwd=ROOT,text=True).splitlines())
        self.assertEqual(files,set(manifest['page_sources'].values()) | set(manifest['excluded_pages']) | set(manifest['template_fragments']))
        for name in manifest['static_pages']:
            html=(ROOT/manifest['page_sources'][name]).read_text()
            self.assertEqual(html.count('src="/assets/site-skin.js"'),1,name)
            self.assertEqual(html.count('href="/assets/site-skin.css"'),1,name)
            self.assertEqual(html.count('href="/assets/fonts/fonts.css"'),1,name)
            self.assertLess(html.index('href="/assets/fonts/fonts.css"'),html.index('href="/assets/site-skin.css"'),name+': 字体包要在共享外观之前加载')
            self.assertNotIn('PingFang',html,name+': 页面不再自带字体栈')
            self.assertNotIn('prefers-color-scheme',html,name)
            self.assertNotIn(':root',html,name)
            self.assertNotIn('border-radius: 0 !important',html,name)
        for name in manifest['dynamic_pages']['src/inresearch/interfaces/pages.py']:
            html=getattr(pages,name)
            self.assertIn('src="/assets/site-skin.js"',html)
            self.assertIn('href="/assets/site-skin.css"',html)
            self.assertIn('href="/assets/fonts/fonts.css"',html)
            self.assertIn('class="ui-auth"',html)

    def test_shared_appearance_has_one_skin_and_bundled_fonts(self):
        skin=(ROOT/'web/themes/site-skin.css').read_text()
        self.assertNotIn('attio',skin.lower(),'2026-09-22 起只有一套视觉')
        self.assertNotIn('--crm-',skin,'令牌由本仓库自己定义, 不再内嵌 infra CRM 块')
        self.assertNotIn('@font-face',skin,'字体只由 /assets/fonts/fonts.css 声明')
        shell=(ROOT/'web/components/site-shell.js').read_text()
        self.assertNotIn('data-ui-choice',shell)
        self.assertNotIn('ui-skin-choices',shell)
        # 字体包必须与自己的 manifest 一致 (infra scripts/sync_fonts.py --check 的本地版)
        import hashlib
        fonts=ROOT/'web/assets/fonts'
        manifest=json.loads((fonts/'manifest.json').read_text())
        self.assertGreaterEqual(len(manifest['files']),6)
        routes=json.loads((ROOT/'web/routes.json').read_text())
        for name,meta in manifest['files'].items():
            self.assertEqual(hashlib.sha256((fonts/name).read_bytes()).hexdigest(),meta['sha256'],name)
            self.assertEqual(routes.get('/assets/fonts/'+name),'web/assets/fonts/'+name,name)
        self.assertNotIn('/assets/InterVariable.woff2',routes)
        css=(fonts/'fonts.css').read_text()
        self.assertIn('--font-sans:',css);self.assertIn('"Noto Sans SC"',css)

    def test_pages_declare_a_directory_section(self):
        from inresearch.interfaces import public
        manifest = json.loads((ROOT/'framework/interface_manifest.json').read_text())
        listed = {page: section for section, pages in manifest['sections'].items() for page in pages}
        self.assertEqual(set(listed), set(manifest['static_pages']), 'every application page belongs to exactly one directory entry')
        self.assertEqual(list(manifest['sections']), ['industry', 'datacenter', 'ledger', 'bom', 'acquisition', 'results', 'admin'])
        # 研究目录 ↔ 四问：行业总览与管理不对应任何一问，其余每一问至少被一项覆盖
        questions = manifest['section_questions']
        self.assertEqual(list(questions), list(manifest['sections']))
        for section, qs in questions.items():
            self.assertEqual(qs, sorted(set(qs)), section)
            self.assertTrue(set(qs) <= {1, 2, 3, 4}, section)
        self.assertEqual(questions['admin'], [])
        self.assertEqual({q for s, qs in questions.items() if s != 'admin' for q in qs}, {1, 2, 3, 4})
        for name in manifest['static_pages']:
            html = (ROOT/manifest['page_sources'][name]).read_text()
            declared = re.search(r'<inresearch-shell data-section="([a-z]+)"', html).group(1)
            self.assertEqual(declared, listed[name], name)
        self.assertEqual({'/' + p for p in manifest['public_pages']} | {'/'}, set(public.READER_PAGES) | {'/index.html'})
        for entry in ('datacenter', 'ledger', 'bom', 'acquisition', 'results', 'admin'):
            self.assertIn(f"['{entry}'", (ROOT/'web/components/site-shell.js').read_text(), entry)
        routes = json.loads((ROOT/'web/routes.json').read_text())
        for url, rel in routes.items():
            self.assertTrue((ROOT/rel).exists(), f'{url} -> {rel} is a dead route')
        self.assertEqual(routes['/data/datacenter_model.json'], 'data/datacenter_model.json')

    def test_public_read_only_boundary(self):
        with patch.object(serve,'AUTH_ON',True), patch.object(auth,'session_user',return_value=None):
            server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler)
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True)
            thread.start()
            try:
                # 公开只读（reader，2026-09-28）：目录三项、账本与它们的数据不登录可 GET；采集、管理、事实层、任务板与一切写接口不公开。
                cases={'/assets/site-skin.css':200,'/assets/site-skin.js?v=1':200,
                       '/assets/fonts/fonts.css':200,'/assets/fonts/noto-sans-sc-1.woff2':200,'/assets/fonts/LICENSE-NotoSansSC.txt':200,
                       '/assets/fonts/manifest.json':200,'/assets/fonts/../research.css':200,'/assets/InterVariable.woff2':404,'/assets/other.woff2':404,
                       '/login':200,'/assets/research.css':200,'/framework/research_graph.json':302,
                       '/api/research':401,'/data/users.json':404,'/assets/.hub_secret':404,
                       '/assets/site-skin.css/../../data/research_runtime.json':404,
                       '/':200,'/index.html':200,'/node.html':200,'/ledger.html':200,'/bom.html':200,'/bom3d.html':200,'/server-plan.html':200,'/rack-atlas.html':200,'/rack-exploded.html':200,'/chip-atlas.html':200,
                       '/assets/chip-package-assembly.js':200,'/assets/chip-package-generator.js':200,
                       '/assets/technical-atlas/chip-package-v1.png':200,'/assets/technical-atlas/chip-package-v1.svg':200,'/assets/technical-atlas/chip-package-v1-preview.svg':200,
                       '/assets/rack-exploded-generator.js':200,'/assets/rack-exploded-view.js':200,'/assets/technical-atlas/rack-exploded-v1.png':200,
                       '/assets/technical-atlas/rack-exploded-v1.svg':200,'/assets/technical-atlas/rack-exploded-v1-preview.svg':200,'/report.html':200,
                       '/data/dashboard.json':200,'/data/tco_targets.json':200,'/data/datacenter_model.json':200,'/api/whoami':200,
                       '/supply.html':302,'/team.html':302,'/ops.html':302,'/materials.html':302,'/company.html':302,'/doc.html':302,'/research.html':302,
                       '/data/facts.json':302,'/framework/part_fetch.json':302,'/api/tasks':401,'/api/supply':401,'/api/users':401}
                for method in ['GET','HEAD']:
                    for path,expected in cases.items():
                        if method=='HEAD' and path in ('/login','/api/whoami'):continue  # dynamic pages answer GET only
                        con=http.client.HTTPConnection(*server.server_address,timeout=3)
                        try:
                            con.request(method,path);response=con.getresponse();response.read()
                            self.assertEqual(response.status,expected,(method,path))
                        finally:con.close()
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2)

    def test_company_workspace_requires_admin_for_get_and_head(self):
        server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
        thread.start()
        try:
            for enabled in (True, False):
                for role, expected in ((None, 302), ('member', 403), ('intern', 403), ('admin', 200)):
                    with patch.object(serve, 'AUTH_ON', enabled), patch.object(auth, 'session_user', return_value=role), patch.object(auth, 'user_role', return_value=role):
                        for method in ('GET', 'HEAD'):
                            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
                            try:
                                connection.request(method, '/admin/company.html?c=nvidia')
                                response = connection.getresponse(); body = response.read()
                                self.assertEqual(response.status, expected, (enabled, role, method))
                                self.assertEqual(response.getheader('Cache-Control'), 'private, no-store')
                                if role == 'admin' and method == 'GET':
                                    self.assertIn('来源与版本记录', body.decode())
                                if role is None:
                                    self.assertTrue(response.getheader('Location').startswith('/login'))
                            finally:
                                connection.close()
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)

    def test_company_alias_preserves_query_after_auth_gate(self):
        from urllib.parse import parse_qs, urlsplit
        with patch.object(serve, 'AUTH_ON', False):
            server = serve.ThreadingHTTPServer(('127.0.0.1', 0), serve.Handler)
            thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': .01}, daemon=True)
            thread.start()
            try:
                for method in ('GET', 'HEAD'):
                    connection = http.client.HTTPConnection(*server.server_address, timeout=3)
                    try:
                        connection.request(method, '/company.html?c=supermicro&q=SYS+GPU&product_id=one&group=servers')
                        response = connection.getresponse()
                        response.read()
                        self.assertEqual(response.status, 302)
                        target = urlsplit(response.getheader('Location'))
                        self.assertEqual(target.path, '/product-catalog.html')
                        self.assertEqual(parse_qs(target.query), {'c':['supermicro'], 'q':['SYS GPU'], 'product_id':['one'], 'group':['servers']})
                    finally:
                        connection.close()
            finally:
                server.shutdown(); server.server_close(); thread.join(timeout=2)

if __name__=='__main__':unittest.main()
