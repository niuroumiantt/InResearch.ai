"""System publications stay atomic, private and independent of application images."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from inresearch.interfaces import repository_pages, static
from inresearch.paths import project_root
from test_repository_pages import RepositoryPageTests

ROOT=project_root()
spec=importlib.util.spec_from_file_location('publisher',ROOT/'scripts/publish_repository_pages.py')
publisher=importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def bundle(folder):
    for name in publisher.FILES:
        path=folder/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('<!doctype html><p>Daily runtime projection</p>')
    (folder/'repo-content/manifest.json').write_text(json.dumps({key:{'synced_at':'2026-10-08',
        'sources':[{'sha256':'a'*64}]} for key in publisher.KEYS}))


class RepositoryProjectionTests(unittest.TestCase):
    def test_incomplete_or_symlink_bundle_cannot_replace_previous_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'source';dest=root/'dest'
            bundle(source);publisher.activate(source,dest)
            old=(dest/'current').resolve()
            (source/'repos.html').unlink()
            with self.assertRaises(ValueError):publisher.activate(source,dest)
            self.assertEqual((dest/'current').resolve(),old)
            (source/'repos.html').symlink_to(old/'repos.html')
            with self.assertRaises(ValueError):publisher.activate(source,dest)
            self.assertEqual((dest/'current').resolve(),old)

    def test_only_registered_private_routes_use_runtime_and_escape_falls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            runtime=Path(temp)/'runtime';source=Path(temp)/'bundle'
            dest=runtime/'data/raw/repository-pages'
            bundle(source);publisher.activate(source,dest)
            with patch.dict(os.environ,{'INRESEARCH_RUNTIME_ROOT':str(runtime)}):
                self.assertIn('Daily runtime projection',static.source_path('/admin/aimailrepo.html').read_text())
                self.assertEqual(static.source_path('/admin/repo-content/manifest.json').parent.name,'repo-content')
                self.assertEqual(static.source_path('/data/raw/repository-pages/current/repos.html').name,'.not-served')
                self.assertIsNone(repository_pages.runtime_source('/admin/repo-content/unregistered.json',ROOT))
                (dest/'current').unlink();(dest/'current').symlink_to(source)
                self.assertEqual(static.source_path('/admin/aimailrepo.html'),ROOT/'web/pages/admin/aimailrepo.html')

    def test_published_runtime_status_and_pages_require_real_admin(self):
        case=RepositoryPageTests()
        try:
            case.setUp()
            with tempfile.TemporaryDirectory() as temp:
                runtime=Path(temp)/'runtime';source=Path(temp)/'bundle'
                dest=runtime/'data/raw/repository-pages'
                bundle(source);publisher.activate(source,dest)
                (dest/'status.json').write_text(json.dumps({'state':'failed','last_success_at':'2026-10-03'}))
                with patch.dict(os.environ,{'INRESEARCH_RUNTIME_ROOT':str(runtime)}):
                    for path in ('/admin/agentrepo.html','/admin/repo-content/job-status.json'):
                        for method in ('GET','HEAD'):
                            self.assertEqual(case.request(method,path)[0],302)
                            self.assertEqual(case.request(method,path,'member')[0],403)
                            code,headers,body=case.request(method,path,'admin')
                            self.assertEqual(code,200)
                            self.assertEqual(headers['Cache-Control'],'private, no-store')
                    self.assertEqual(json.loads(case.request('GET','/admin/repo-content/job-status.json','admin')[2])['state'],'failed')
        finally:
            case.doCleanups()
