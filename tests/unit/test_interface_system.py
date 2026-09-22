"""UI coverage and authentication boundary regression; Python standard library only."""

from inresearch.paths import project_root
import http.client
import json
import threading
import unittest
from unittest.mock import patch
from inresearch.interfaces import auth as auth
from inresearch.interfaces import pages
from inresearch.interfaces import http as serve

ROOT = project_root()

class InterfaceContractTests(unittest.TestCase):
    def test_all_html_classified_and_application_hooks(self):
        manifest = json.loads((ROOT/'framework/interface_manifest.json').read_text())
        # Only tracked project HTML, excluding development/runtime artifacts.
        import subprocess
        files = set(subprocess.check_output(['git','ls-files','*.html'],cwd=ROOT,text=True).splitlines())
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

    def test_only_skin_resources_are_public(self):
        with patch.object(serve,'AUTH_ON',True), patch.object(auth,'session_user',return_value=None):
            server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler)
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True)
            thread.start()
            try:
                cases={'/assets/site-skin.css':200,'/assets/site-skin.js?v=1':200,
                       '/assets/fonts/fonts.css':200,'/assets/fonts/noto-sans-sc-1.woff2':200,'/assets/fonts/LICENSE-NotoSansSC.txt':200,
                       '/assets/fonts/manifest.json':200,'/assets/fonts/../research.css':302,'/assets/InterVariable.woff2':302,'/assets/other.woff2':302,
                       '/login':200,'/assets/research.css':302,'/framework/research_graph.json':302,
                       '/api/research':401,'/data/users.json':404,'/assets/.hub_secret':404,
                       '/assets/site-skin.css/../../data/research_runtime.json':404}
                for method in ['GET','HEAD']:
                    for path,expected in cases.items():
                        if method=='HEAD' and path=='/login':continue
                        con=http.client.HTTPConnection(*server.server_address,timeout=3)
                        try:
                            con.request(method,path);response=con.getresponse();response.read()
                            self.assertEqual(response.status,expected,(method,path))
                        finally:con.close()
            finally:
                server.shutdown();server.server_close();thread.join(timeout=2)

if __name__=='__main__':unittest.main()
