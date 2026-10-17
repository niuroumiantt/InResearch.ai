"""Real HTTP authorization tests over isolated accounts, originals and grants."""
from http.client import HTTPConnection
import io
import base64
import time
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import quote
import uuid

from inresearch.interfaces import auth, http, project_access as access
from inresearch.materials import inbox, batch_review


class ProjectAccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        (root/'runtime').mkdir()
        self.patches = [patch.object(auth, 'USERS_FILE', root/'users.json'),
                        patch.object(auth, 'SECRET_FILE', root/'.secret'),
                        patch.object(http, 'AUTH_ON', True),
                        patch.dict(os.environ, {'INRESEARCH_RUNTIME_ROOT':str(root/'runtime'),
                                               'INRESEARCH_INTAKE_ROOT':str(root/'inbox'),
                                               'INRESEARCH_MATERIAL_APPROVER':'owner'})]
        for value in self.patches:
            value.start(); self.addCleanup(value.stop)
        auth.add_user('owner', 'owner-password', 'admin')
        for name in ('alice', 'bob', 'reviewer'):
            auth.add_user(name, 'temporary-password', 'collaborator')
            auth.set_password(name, 'account-password')
            self.grant(name, submit=['dc-census-cn'] if name != 'reviewer' else [],
                       approve=['dc-census-cn'] if name == 'reviewer' else [])
        self.server = http.ThreadingHTTPServer(('127.0.0.1', 0), http.Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown(); self.thread.join(); self.server.server_close()

    def grant(self, name, submit=(), approve=(), **changes):
        mission, _ = access.catalog()
        user = auth.load_users()[name]
        value = {'enabled':True, 'expires_at':None, 'frontend':True,
                 'submit_packages':list(submit), 'approve_packages':list(approve)}
        value.update(changes)
        return access.update({'username':name,'expected_revision':user.get('access_revision',0),
                              'display_name':name.upper(),'disabled':False,
                              'project_id':mission['id'],'grant':value},'owner')

    def req(self, path, actor=None, data=None, method=None, headers=None):
        headers = dict(headers or {})
        if actor:
            headers['Cookie'] = actor if actor.startswith('hub_session=') else auth.make_cookie(actor).split(';')[0]
        if isinstance(data, dict):
            data = json.dumps(data).encode();headers['Content-Type']='application/json'
        connection = HTTPConnection('127.0.0.1',self.server.server_port)
        connection.request(method or ('POST' if data is not None else 'GET'),path,body=data,headers=headers)
        response = connection.getresponse(); body = response.read();status=response.status
        connection.close()
        try: body=json.loads(body)
        except (ValueError, UnicodeDecodeError): pass
        return status,body

    def upload(self, name='alice', package='dc-census-cn', **metadata):
        values={'name':'source.txt','submitter':'FORGED OWNER','project_name':'Test material','package_id':package,
                'owner_id':'forged','project_id':'wrong',**metadata}
        return self.req('/api/task-uploads',name,b'original text',headers={
            'X-Requested-With':'task-upload','X-Material-Metadata':quote(json.dumps(values))})

    def action(self, item, actor='reviewer', action='approve', **extra):
        return self.req('/api/materials/review',actor,{
            'id':item['id'],'sha256':item['sha256'],'expected_revision':item['revision'],
            'operation_id':str(uuid.uuid4()),'action':action,**extra},headers={'X-Requested-With':'material-intake'})

    def test_existing_legacy_session_gets_stable_identity_before_upload(self):
        users=auth.load_users()
        users['alice'].pop('id');users['alice'].pop('session_version')
        auth.save_users(users)
        payload=f"alice:{int(time.time())+600}"
        token=base64.urlsafe_b64encode(f"{payload}:{auth._sign(payload)}".encode()).decode()
        cookie='hub_session='+token
        self.assertEqual(auth.session_user(cookie),'alice')
        status,work=self.req('/api/project-work',cookie)
        self.assertEqual(status,200);self.assertTrue(work['user_id'])
        self.assertEqual(auth.session_user(cookie),'alice')
        self.assertEqual(self.req('/api/project-work',cookie)[1]['user_id'],work['user_id'])
        self.assertEqual(self.upload(cookie)[1]['item']['owner_id'],work['user_id'])

    def test_new_upload_requires_login_and_server_assigns_identity(self):
        self.assertEqual(self.upload(None)[0],401)
        status,result=self.upload();self.assertEqual(status,201,result)
        item=result['item'];user=auth.load_users()['alice']
        self.assertEqual(item['user'],'alice');self.assertEqual(item['submitter'],'ALICE')
        self.assertEqual(item['owner_id'],user['id']);self.assertEqual(item['project_id'],access.catalog()[0]['id'])
        self.assertEqual(inbox.pending(),[])
        self.assertEqual(self.upload('alice','dc-census-eu')[0],404)

    def test_personal_records_downloads_and_receipts_do_not_cross_accounts(self):
        _,result=self.upload();item=result['item']
        self.assertEqual(self.req('/api/project-work','alice')[1]['items'][0]['id'],item['id'])
        self.assertEqual(self.req('/api/project-work','bob')[1]['items'],[])
        for method in ('GET','HEAD'):
            self.assertEqual(self.req('/api/materials/content/'+item['id'],'alice',method=method)[0],200)
            self.assertEqual(self.req('/api/materials/content/'+item['id'],'bob',method=method)[0],404)
        receipt={'id':item['id'],'receipt':result['receipt']}
        self.assertEqual(self.req('/api/task-uploads/receipt','bob',receipt)[0],404)
        self.assertEqual(self.req('/api/task-uploads/receipt',None,receipt)[0],404)
        self.assertEqual(self.req('/api/task-uploads/receipt','alice',receipt)[0],200)

    def test_scoped_approval_and_self_approval(self):
        _,result=self.upload();item=result['item']
        self.assertEqual(self.action(item,'bob')[0],403)
        self.grant('alice',submit=['dc-census-cn'],approve=['dc-census-cn'])
        self.assertEqual(self.action(item,'alice')[0],403)
        self.assertEqual(self.action(item)[0],200)
        self.assertEqual(inbox.load(item['id'])['approval']['by'],'reviewer')
        self.assertEqual(len(inbox.pending()),1)
        self.grant('bob',submit=['dc-census-eu'])
        _,other=self.upload('bob','dc-census-eu')
        self.assertEqual(self.action(other['item'])[0],403)
        rows=self.req('/api/materials','reviewer')[1]['items']
        self.assertNotIn(other['item']['id'],[r['id'] for r in rows])

    def test_batch_ownership_recovery_and_scoped_joint_approval(self):
        bid, token=str(uuid.uuid4()),str(uuid.uuid4());rows=[]
        for i in range(2):
            status,result=self.upload(batch_id=bid,batch_token=token,batch_total=2,batch_index=i)
            self.assertEqual(status,201,result);rows.append(result)
        payload={'batch_id':bid,'batch_token':token}
        self.assertEqual(self.req('/api/task-uploads/batch-status','bob',payload)[0],404)
        self.assertEqual(self.req('/api/task-uploads/batch-status','alice',payload)[1]['batch']['received'],2)
        sealed={'batch_id':bid,'items':[{'id':r['item']['id'],'receipt':r['receipt']} for r in rows]}
        self.assertEqual(self.req('/api/task-uploads/batch','bob',sealed)[0],404)
        self.assertEqual(self.req('/api/task-uploads/batch','alice',sealed)[0],200)
        batch={'operation_id':str(uuid.uuid4()),'action':'approve_and_analyze','note':'verified',
               'items':[{'id':r['item']['id'],'sha256':r['item']['sha256'],'expected_revision':0} for r in rows]}
        self.assertEqual(self.req('/api/materials/review-batch','bob',batch,headers={'X-Requested-With':'material-intake'})[0],403)
        self.assertEqual(self.req('/api/materials/review-batch','reviewer',batch,headers={'X-Requested-With':'material-intake'})[0],200)
        self.assertTrue(all(batch_review.review_ready(inbox.load(r['item']['id'])) for r in rows))

    def test_batch_with_unauthorized_item_has_no_partial_approval(self):
        bid=str(uuid.uuid4())
        _,first=self.upload(batch_id=bid)
        self.grant('bob',submit=['dc-census-eu'])
        _,second=self.upload('bob','dc-census-eu',batch_id=bid)
        payload={'operation_id':str(uuid.uuid4()),'action':'approve_and_analyze','note':'',
                 'items':[{'id':r['item']['id'],'sha256':r['item']['sha256'],'expected_revision':0}
                          for r in (first,second)]}
        self.assertEqual(self.req('/api/materials/review-batch','reviewer',payload,
                                 headers={'X-Requested-With':'material-intake'})[0],403)
        for row in (first,second):
            record=inbox.load(row['item']['id'])
            self.assertEqual(record['status'],'pending_approval')
            self.assertFalse(record.get('approval'))
            self.assertFalse(record.get('review_batch_id'))
        self.assertEqual(inbox.pending(),[])

    def test_password_and_permission_changes_revoke_existing_sessions(self):
        cookie=auth.make_cookie('alice').split(';')[0]
        self.assertEqual(self.req('/api/project-work',cookie)[0],200)
        auth.set_password('alice','another-password')
        self.assertIsNone(auth.session_user(cookie))
        cookie=auth.make_cookie('alice').split(';')[0]
        self.grant('alice',enabled=False)
        self.assertIsNone(auth.session_user(cookie))
        self.assertFalse(self.req('/api/project-work','alice')[1]['member'])
        self.assertEqual(self.upload()[0],404)

    def test_expiry_enforced_without_cookie_rotation(self):
        cookie=auth.make_cookie('alice').split(';')[0]
        users=auth.load_users();users['alice']['projects'][access.catalog()[0]['id']]['expires_at']='2000-01-01T00:00:00+00:00';auth.save_users(users)
        self.assertEqual(auth.session_user(cookie),'alice')
        self.assertFalse(self.req('/api/project-work',cookie)[1]['member'])
        self.assertEqual(self.req('/projects.html',cookie)[0],403)

    def test_identity_survives_rename_and_same_name_recreation_does_not_claim_history(self):
        _,result=self.upload();identity=result['item']['owner_id']
        old_cookie=auth.make_cookie('alice').split(';')[0]
        auth.rename_user('alice','alice-new')
        self.assertEqual(auth.load_users()['alice-new']['id'],identity)
        self.assertEqual(len(self.req('/api/project-work','alice-new')[1]['items']),1)
        auth.add_user('alice','new-password','collaborator');auth.set_password('alice','another-password')
        self.grant('alice',submit=['dc-census-cn'])
        self.assertEqual(self.req('/api/project-work','alice')[1]['items'],[])
        self.assertIsNone(auth.session_user(old_cookie))

    def test_frontstage_read_grant_never_grants_operational_or_source_access(self):
        for path in ('/ops.html','/api/status','/data/facts.json','/src/inresearch/interfaces/auth.py','/admin/company.html','/admin/project-access.html','/api/project-access','/api/site-search?scope=all'):
            for method in ('GET','HEAD'):
                self.assertEqual(self.req(path,'alice',method=method)[0],403,(path,method))
        self.assertEqual(self.req('/projects.html','alice')[0],200)
        self.assertFalse(self.req('/api/research-task-examples','alice')[1]['authenticated'])
        self.assertEqual(self.req('/api/navigation?page=/tasks.html','alice')[1]['active']['area'],'backstage')
        self.assertEqual(self.req('/api/navigation?page=/projects.html','alice')[1]['active']['area'],'delivery')
        self.assertEqual(self.req('/api/navigation?page=/admin/project-access.html','owner')[1]['active']['section'],'production')
        self.assertEqual(self.req('/task-reviews.html','alice')[0],403)
        self.assertEqual(self.req('/task-reviews.html','reviewer')[0],200)
        self.assertEqual(self.req('/api/materials','alice',b'bad',headers={'X-Requested-With':'material-intake'})[0],403)

    def test_first_password_change_gate_and_disabled_account(self):
        auth.add_user('fresh','initial-password','collaborator')
        cookie=auth.make_cookie('fresh').split(';')[0]
        self.assertEqual(self.req('/api/project-work',cookie)[0],403)
        status,result=self.req('/api/passwd',cookie,{'old_password':'initial-password','new_password':'chosen-password'})
        self.assertEqual(status,200,result);self.assertEqual(result['next'],'/tasks.html')
        users=auth.load_users();users['fresh']['disabled']=True;auth.save_users(users)
        self.assertFalse(auth.verify_password('fresh','chosen-password'))
        self.assertIsNone(auth.session_user(auth.make_cookie('fresh')))
        self.assertIsNone(auth.session_user(cookie))

    def test_intern_login_opens_personal_work_and_never_inherits_approval(self):
        auth.add_user('isaac', 'intern-password', 'intern')
        mission, _ = access.catalog()
        users = auth.load_users()
        users['isaac']['projects'] = {mission['id']:{'enabled':True, 'expires_at':None,
            'frontend':True, 'submit_packages':['dc-census-cn'],
            'approve_packages':['dc-census-cn']}}
        auth.save_users(users)
        status, result = self.req('/api/login', data={'username':'isaac','password':'intern-password'})
        self.assertEqual(status, 200, result)
        self.assertEqual(result['next'], '/tasks.html')
        work = self.req('/api/project-work', 'isaac')[1]
        self.assertTrue(work['member'])
        self.assertFalse(work['can_approve'])
        self.assertFalse(access.can_review('isaac'))
        self.assertEqual(self.req('/task-reviews.html', 'isaac')[0], 403)

    def test_collaborator_cannot_modify_team_assignments_or_feedback(self):
        _,result=self.upload();item=result['item']
        self.assertEqual(self.req('/api/research-tasks','alice',{'action':'update'})[0],403)
        self.assertEqual(self.action(item,'reviewer','feedback',text='bad',result='accepted')[0],403)

    def test_concurrent_owner_grants_conflict_instead_of_overwrite(self):
        mission,_=access.catalog()
        current=auth.load_users()['alice']
        payload={'username':'alice','expected_revision':current['access_revision'],
                 'display_name':'ALICE','disabled':False,'project_id':mission['id'],
                 'grant':current['projects'][mission['id']]}
        self.grant('alice',submit=['dc-census-eu'])
        self.assertEqual(self.req('/api/project-access','owner',payload,headers={'X-Requested-With':'project-access'})[0],400)
        self.assertEqual(access.grant('alice')['submit_packages'],['dc-census-eu'])

    def test_legacy_anonymous_records_not_claimed_by_matching_name(self):
        item,receipt=inbox.receive(io.BytesIO(b'old'),3,{'name':'old.txt','submitter':'ALICE','project_name':'old'},'anonymous',public=True)
        self.assertEqual(self.req('/api/project-work','alice')[1]['items'],[])
        self.assertEqual(self.req('/api/task-uploads/receipt',None,{'id':item['id'],'receipt':receipt})[0],200)
        self.assertEqual(self.action(item,'reviewer')[0],403)
        self.assertEqual(self.action(item,'owner')[0],200)

    def test_owner_api_and_stale_grants(self):
        self.assertEqual(self.req('/api/project-access','owner')[0],200)
        for actor,expected in [('owner',(True,True,True)),('alice',(False,False,False)),('reviewer',(False,False,True))]:
            status,view=self.req('/api/project-work',actor)
            self.assertEqual(status,200)
            self.assertEqual((view['can_admin'],view['can_manage'],view['can_approve']),expected)
        auth.add_user('other-admin','admin-password','admin')
        status,view=self.req('/api/project-work','other-admin')
        self.assertEqual((view['can_admin'],view['can_manage'],view['can_approve']),(True,False,False))
        self.assertEqual(self.req('/api/project-access','other-admin')[0],403)
        self.assertEqual(self.req('/api/project-access','alice',{'action':'create','username':'evil'},headers={'X-Requested-With':'project-access'})[0],403)
        self.assertEqual(self.req('/api/project-access','owner',{'action':'create','username':'charlie'},headers={'X-Requested-With':'project-access'})[0],200)
        self.assertFalse(access.member('charlie'))
        self.assertFalse(access.can_review('charlie'))
