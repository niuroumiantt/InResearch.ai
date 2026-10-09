import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from inresearch.adapters import editorial_sync as e
from inresearch.paths import project_root
from inresearch.workflow import research_match

class EditorialSyncTests(unittest.TestCase):
    def test_outbox_seal_requires_matching_completed_render(self):
        import runpy
        outbox=runpy.run_path(str(project_root()/'scripts/editorial-outbox.py'))
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);folder=base/'2026-10-09-example';(folder/'checks').mkdir(parents=True)
            (folder/'article.md').write_text('# Title\n\nData center grid TCO')
            (folder/'sources.json').write_text('{"records":[]}')
            hashes={}
            for name in ('wechat','full','lite'):
                body=(name+' rendered').encode();(folder/(name+'.html')).write_bytes(body);hashes[name]=hashlib.sha256(body).hexdigest()
            p=folder/'checks/browser.json';p.write_text(json.dumps({'pass':True,'input_sha256':hashes}))
            dest=outbox['seal'](folder,base/'outbox');self.assertEqual(e.load_bundle(dest/'manifest.json')['title'],'Title')
            (folder/'full.html').write_text('changed after checking')
            with self.assertRaises(ValueError):outbox['seal'](folder,base/'outbox')

    def item(self, **kw):
        return {'id':'inews-column-9','title':'机房用电','source_role':'authored_analysis',
                'url':'https://inews.today/c/9','text':'# 机房用电\n\n数据中心电网接入电价 power electricity TCO cost $100.',
                'references':[{'url':'https://www.eia.gov/electricity/','title':'原件'}],**kw}

    def test_dedup_revisions_scope_and_reindex_preserve_authorship(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data';scope=Path(tmp)/'scope.json'
            scope.write_text(json.dumps({'schema_version':1,'doc_ids':['doc-'+'f'*64],'include_daily_deliveries':True}))
            first=e.receive(self.item(),data,project_root(),scope)
            self.assertFalse(first['duplicate']);self.assertTrue(first['scope_enrolled'])
            self.assertTrue(e.receive(self.item(),data,project_root(),scope)['duplicate'])
            v=json.loads(scope.read_text());self.assertEqual(len(v['doc_ids']),2);self.assertTrue(v['include_daily_deliveries'])
            revised=e.receive(self.item(text=self.item()['text']+'\n改稿'),data,project_root(),scope)
            self.assertNotEqual(revised['article_sha256'],first['article_sha256'])
            self.assertEqual(len(json.loads(scope.read_text())['doc_ids']),3)
            doc=next(r for r in research_match.projection(data)['records'] if r['sha256']==first['article_sha256'])
            self.assertEqual(doc['source_role'],'authored_analysis');self.assertEqual(len(doc['editorial_references']),1)
            from inresearch.delivery.reader_export import supplied_sources
            exported=supplied_sources(data)[first['article_sha256']]
            self.assertEqual(exported['source_role'],'authored_analysis')
            self.assertEqual(exported['source_url'],'https://inews.today/c/9')
            blob=data/'acquisition/blobs'/first['article_sha256'][:2]/(first['article_sha256']+'.md')
            research_match.ingest(blob,data,project_root())
            doc=next(r for r in research_match.projection(data)['records'] if r['sha256']==first['article_sha256'])
            self.assertEqual(doc['source_role'],'authored_analysis');self.assertFalse(doc['full_read'])

    def test_broken_scope_fails_without_claiming_delivered_then_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data';scope=Path(tmp)/'scope.json';scope.write_text('{}')
            with self.assertRaises(ValueError):e.receive(self.item(),data,project_root(),scope)
            self.assertFalse((data/'material-reviews/editorial-deliveries.json').exists())
            scope.write_text('{"schema_version":1,"doc_ids":[]}')
            self.assertTrue(e.receive(self.item(),data,project_root(),scope)['scope_enrolled'])

    def test_bundle_tampering_and_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);body=self.item()['text'].encode();(base/'article.md').write_bytes(body)
            manifest={ 'schema':'editorial-delivery-v1','id':'longform','title':'研究','article':'article.md',
                'source_role':'authored_analysis','files':[{'path':'article.md','bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}]}
            p=base/'manifest.json';p.write_text(json.dumps(manifest))
            self.assertEqual(e.load_bundle(p)['text'],body.decode())
            (base/'article.md').write_bytes(body+b'x')
            with self.assertRaises(ValueError):e.load_bundle(p)
            with self.assertRaises(ValueError):e.validate(self.item(source_role='primary_source'))
            with self.assertRaises(ValueError):e.validate(self.item(url='file:///secret'))

    def test_polling_restarts_at_zero_for_changed_old_articles_and_rejects_bad_cursor(self):
        with tempfile.TemporaryDirectory() as tmp:
            data=Path(tmp)/'data'
            page={'schema':'inews-editorial-feed-v1','items':[self.item()],'next_after':None}
            first=e.sync(data,project_root(),'https://inews.today/api/feeds/columns',fetch=lambda _:page)
            self.assertEqual(first['received'],1)
            self.assertEqual(e.sync(data,project_root(),'https://inews.today/api/feeds/columns',fetch=lambda _:page)['unchanged'],1)
            page['next_after']='0'
            with self.assertRaises(ValueError):e.sync(data,project_root(),'https://inews.today/api/feeds/columns',fetch=lambda _:page)
