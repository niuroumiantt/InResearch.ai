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
            self.assertNotIn('prefers-color-scheme',html,name)
            self.assertNotIn(':root',html,name)
            self.assertNotIn('border-radius: 0 !important',html,name)
        for name in manifest['dynamic_pages']['src/inresearch/interfaces/pages.py']:
            html=getattr(pages,name)
            self.assertIn('src="/assets/site-skin.js"',html)
            self.assertIn('href="/assets/site-skin.css"',html)
            self.assertIn('class="ui-auth"',html)

    def test_only_skin_resources_are_public(self):
        with patch.object(serve,'AUTH_ON',True), patch.object(auth,'session_user',return_value=None):
            server=serve.ThreadingHTTPServer(('127.0.0.1',0),serve.Handler)
            thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True)
            thread.start()
            try:
                cases={'/assets/site-skin.css':200,'/assets/site-skin.js?v=1':200,
                       '/assets/InterVariable.woff2':200,'/assets/Inter-LICENSE.txt':200,'/assets/other.woff2':302,
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
