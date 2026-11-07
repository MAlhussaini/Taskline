"""Real HTTP authentication, isolation and local restore regressions."""
import json
import os
import runpy
import unittest
from unittest.mock import patch
import urllib.request
import urllib.error
from pathlib import Path

helpers=runpy.run_path(str(Path(__file__).with_name('star-rules.test.py')))
app,base=helpers['app'],helpers['StarRules']
PASSWORD='a-strong-local-test-password'


class AuthBackupTests(unittest.TestCase):
    setUp=base.setUp
    tearDown=base.tearDown

    def call(self,method,path,data=None,cookie=None,status=200,headers=None):
        request=urllib.request.Request(self.origin+path,data=None if data is None else json.dumps(data).encode(),method=method,
            headers={'Content-Type':'application/json','Cookie':self.cookie if cookie is None else cookie,**(headers or {})})
        try: response=urllib.request.urlopen(request)
        except urllib.error.HTTPError as error: response=error
        with response:
            raw=response.read()
            result=json.loads(raw) if response.headers.get('Content-Type','').startswith('application/json') else raw
            self.assertEqual(response.status,status,result)
            session=response.headers.get('Set-Cookie','').split(';')[0]
            return result,session,response.headers

    def register(self,email='user@example.test'):
        return self.call('POST','/api/auth/register',{'email':email,'password':PASSWORD,'role':'Admin'},cookie='',status=201)

    def test_render_activation_requires_token_and_disables_registration(self):
        with app.ACCOUNT_STORE.connect() as db:
            db.execute('UPDATE auth_users SET password_hash=NULL WHERE is_owner=1')
        token='test-only-activation-token-at-least-32-characters'
        with patch.dict(os.environ, {'RENDER':'true', 'TASKLINE_SETUP_TOKEN':token}):
            status,_,_=self.call('GET','/api/auth/status',cookie='')
            self.assertTrue(status['setup_token_required'])
            self.assertFalse(status['registration_enabled'])
            payload={'email':'owner@example.test','password':'123456'}
            self.call('POST','/api/auth/setup',payload,cookie='',status=400)
            self.call('POST','/api/auth/setup',{**payload,'setup_token':'wrong'},cookie='',status=400)
            self.call('POST','/api/auth/setup',{**payload,'setup_token':token},cookie='')
            self.call('POST','/api/auth/register',{'email':'new@example.test','password':PASSWORD},cookie='',status=400)

    def test_setup_claim_and_registration_roles(self):
        store=app.ACCOUNT_STORE
        with store.connect() as db:
            db.execute('UPDATE auth_users SET password_hash=NULL WHERE is_owner=1')
            db.execute('UPDATE auth_sessions SET revoked=1')
        payload={'email':'not-owner@example.test','password':PASSWORD}
        self.call('POST','/api/auth/setup',payload,cookie='',status=400)
        self.call('POST','/api/auth/register',payload,cookie='',status=400)
        payload['email']='owner@example.test'
        self.call('POST','/api/auth/setup',{**payload,'password':'short'},cookie='',status=400)
        payload['password']='123456'
        result,cookie,headers=self.call('POST','/api/auth/setup',payload,cookie='')
        self.assertEqual(result['user']['role'],'Admin')
        self.assertTrue(result['user']['is_owner'])
        self.assertEqual(result['user']['full_name'],'Owner')
        self.assertEqual(result['user']['nickname'],'Owner')
        self.assertFalse(store.setup_file.exists())
        self.call('POST','/api/auth/setup',payload,cookie='',status=400)
        self.call('POST','/api/auth/register',{'email':'short@example.test','password':'12345'},cookie='',status=400)
        user,_,_=self.call('POST','/api/auth/register',{'email':'user@example.test','password':'123456'},cookie='',status=201)
        self.assertEqual(user['user']['role'],'User')
        self.assertEqual(user['user']['full_name'],'user')
        self.assertEqual(user['user']['nickname'],'user')
        self.assertNotIn('password_hash',user['user'])
        self.assertIn('HttpOnly',headers['Set-Cookie'])
        self.assertIn('Secure',headers['Set-Cookie'])
        self.assertIn('SameSite=Strict',headers['Set-Cookie'])

    def test_persistent_sessions_rotation_logout_and_security_checks(self):
        result,cookie,_=self.register()
        with app.ACCOUNT_STORE.connect() as db:
            db.execute("UPDATE auth_sessions SET last_used='1970-01-01', created_at='1970-01-01'")
        old=app.ACCOUNT_STORE
        app.initialize_accounts('owner@example.test',old.state_dir,old.backups.directory)
        self.call('GET','/api/tasks?date=2030-01-01',cookie=cookie)
        self.call('POST','/api/tasks',{'title':'x'},cookie=cookie,headers={'Origin':'https://evil.example'},status=403)
        self.call('GET','/api/tasks',cookie=cookie,headers={'X-Taskline-Account':'999'},status=409)
        _,renewed,_=self.call('POST','/api/auth/renew',{},cookie=cookie)
        self.call('GET','/api/tasks',cookie=cookie,status=401)
        self.call('POST','/api/auth/logout',{},cookie=renewed)
        self.call('GET','/api/tasks',cookie=renewed,status=401)
        self.call('POST','/api/auth/login',{'email':'user@example.test','password':'wrong'},cookie='',status=401)
        _,again,_=self.call('POST','/api/auth/login',{'email':'USER@example.test','password':PASSWORD},cookie='')
        self.call('GET','/api/auth/profile',cookie=again)
        self.call('GET','/api/admin/users',cookie=again,status=403)

    def test_data_settings_and_uploads_are_isolated(self):
        owner_task,_,_=self.call('POST','/api/tasks',{'title':'Private owner task','task_date':'2030-01-01'},status=201)
        owner_list,_,_=self.call('POST','/api/lists',{'title':'Private owner list'},status=201)
        app.UPLOAD_DIR.joinpath('private.png').write_bytes(b'private-upload')
        user,cookie,_=self.register()
        for path in ('/api/tasks?date=2030-01-01','/api/lists','/api/routines','/api/dreams'):
            data,_,_=self.call('GET',path,cookie=cookie)
            self.assertEqual(data,[])
        self.call('PUT',f"/api/tasks/{owner_task['id']}",{'title':'Stolen'},cookie=cookie,status=404)
        self.call('DELETE',f"/api/lists/{owner_list['id']}",cookie=cookie,status=404)
        self.call('GET','/uploads/private.png',cookie=cookie,status=404)
        self.call('GET','/uploads/private.png',cookie='',status=401)
        self.call('GET','/uploads/private.png')
        self.call('POST','/api/tasks',{'title':'Separate user task','task_date':'2030-01-01'},cookie=cookie,status=201)
        self.call('PUT','/api/settings',{'features':{'stars':False}},cookie=cookie)
        owner_settings,_,_=self.call('GET','/api/settings')
        self.assertTrue(owner_settings['settings']['features']['stars'])
        own,_,_=self.call('GET','/api/tasks?date=2030-01-01')
        self.assertEqual([task['title'] for task in own],['Private owner task'])
        profile={**user['user'],'full_name':'Updated Name','nickname':'Changed','preferences':{'theme':'dark','language':'ar'}}
        updated,_,_=self.call('PUT','/api/auth/profile',profile,cookie=cookie)
        self.assertEqual(updated['user']['full_name'],'Updated Name')
        self.assertEqual(updated['user']['preferences'],profile['preferences'])
        self.assertNotEqual(app.ACCOUNT_STORE.user_paths(app.ACCOUNT_STORE.resolve(cookie.split('=',1)[1]))[0],app.DB_PATH)

    def test_admin_disables_user_and_password_change_revokes_other_sessions(self):
        user,cookie,_=self.register()
        _,second,_=self.call('POST','/api/auth/login',{'email':'user@example.test','password':PASSWORD},cookie='')
        payload={**user['user'],'current_password':PASSWORD,'new_password':'a-new-strong-local-password'}
        _,replacement,_=self.call('PUT','/api/auth/profile',payload,cookie=cookie)
        self.call('GET','/api/tasks',cookie=second,status=401)
        self.call('GET','/api/tasks',cookie=cookie,status=401)
        self.call('GET','/api/tasks',cookie=replacement)
        self.call('PUT',f"/api/admin/users/{user['user']['id']}",{**user['user'],'active':False})
        self.call('GET','/api/tasks',cookie=replacement,status=401)
        self.call('POST','/api/auth/login',{'email':'user@example.test','password':'a-new-strong-local-password'},cookie='',status=401)

    def test_backup_restore_all_tenants_uploads_and_integrity(self):
        _,cookie,_=self.register()
        self.call('POST','/api/tasks',{'title':'Owner before','task_date':'2030-01-01'},status=201)
        self.call('POST','/api/tasks',{'title':'User before','task_date':'2030-01-01'},cookie=cookie,status=201)
        app.UPLOAD_DIR.joinpath('proof.png').write_bytes(b'original image')
        backup,_,_=self.call('POST','/api/admin/backups',{},status=201)
        self.call('POST',f"/api/admin/backups/{backup['id']}/verify",{})
        self.call('POST','/api/admin/backups',{},cookie=cookie,status=403)
        self.call('POST','/api/tasks',{'title':'After','task_date':'2030-01-01'},status=201)
        app.UPLOAD_DIR.joinpath('proof.png').write_bytes(b'changed image')
        result,_,_=self.call('POST',f"/api/admin/backups/{backup['id']}/restore",{'password':'fixture-password-for-tests'})
        self.assertTrue(result['sessions_revoked'])
        self.assertTrue(app.ACCOUNT_STORE.backups.path(result['safety_backup']).is_dir())
        self.call('GET','/api/tasks',cookie=cookie,status=401)
        self.call('GET','/api/tasks',status=401)
        self.assertEqual(app.UPLOAD_DIR.joinpath('proof.png').read_bytes(),b'original image')
        _,owner_cookie,_=self.call('POST','/api/auth/login',{'email':'owner@example.test','password':'fixture-password-for-tests'},cookie='')
        rows,_,_=self.call('GET','/api/tasks?date=2030-01-01',cookie=owner_cookie)
        self.assertEqual([row['title'] for row in rows],['Owner before'])
        _,new_cookie,_=self.call('POST','/api/auth/login',{'email':'user@example.test','password':PASSWORD},cookie='')
        rows,_,_=self.call('GET','/api/tasks?date=2030-01-01',cookie=new_cookie)
        self.assertEqual([row['title'] for row in rows],['User before'])
        path=app.ACCOUNT_STORE.backups.path(backup['id'])/'primary/uploads/proof.png'
        path.write_bytes(b'tampered')
        self.call('POST',f"/api/admin/backups/{backup['id']}/restore",{'password':'fixture-password-for-tests'},cookie=owner_cookie,status=400)
        rows,_,_=self.call('GET','/api/tasks?date=2030-01-01',cookie=owner_cookie)
        self.assertEqual([row['title'] for row in rows],['Owner before'])


del base,helpers
if __name__=='__main__':unittest.main()
