"""Local accounts, revocable persistent sessions, and isolated SQLite stores."""
from __future__ import annotations

import contextvars
import functools
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from contextlib import contextmanager
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlparse

CURRENT_USER = contextvars.ContextVar('taskline_user', default=None)
COOKIE = '__Host-taskline-session'


def password_hash(password):
    if not isinstance(password, str) or not 6 <= len(password) <= 256:
        raise ValueError('Use a password of 6–256 characters / استخدم كلمة مرور من 6 إلى 256 حرفًا')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=131072, r=8, p=1, maxmem=256 * 1024 * 1024)
    return f'scrypt$131072$8$1${salt.hex()}${digest.hex()}'


def verify_password(password, encoded):
    if not isinstance(password, str) or len(password) > 256 or not encoded:
        return False
    try:
        kind, n, r, p, salt, digest = encoded.split('$')
        if kind != 'scrypt':
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p), maxmem=256 * 1024 * 1024)
        return hmac.compare_digest(actual.hex(), digest)
    except (ValueError, TypeError):
        return False


def email_value(value):
    value = str(value or '').strip().lower()
    if len(value) > 254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', value):
        raise ValueError('Invalid email / البريد الإلكتروني غير صالح')
    return value


def profile_fields(payload):
    full_name = str(payload.get('full_name', '')).strip()
    nickname = str(payload.get('nickname', '')).strip()
    if not 1 <= len(full_name) <= 120 or not 1 <= len(nickname) <= 60:
        raise ValueError('Full name and nickname are required / الاسم الكامل والاسم المستعار مطلوبان')
    return full_name, nickname, email_value(payload.get('email'))


def public_user(row):
    return {key: row[key] for key in ('id', 'full_name', 'nickname', 'email', 'role', 'active', 'is_owner', 'created_at')} | {'preferences': json.loads(row['preferences'])}


class Accounts:
    def __init__(self, database, state_dir, owner_email, initialize_tenant):
        self.database, self.state_dir = Path(database), Path(state_dir)
        self.initialize_tenant = initialize_tenant
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_dir, 0o700)
        self.setup_file = self.state_dir / 'owner-setup-code.txt'
        self.dummy_hash = password_hash(secrets.token_urlsafe(32))
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS auth_users (
                    id INTEGER PRIMARY KEY, full_name TEXT NOT NULL, nickname TEXT NOT NULL,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT,
                    role TEXT NOT NULL CHECK(role IN ('Admin','User')), active INTEGER NOT NULL DEFAULT 1,
                    is_owner INTEGER NOT NULL DEFAULT 0, data_key TEXT NOT NULL UNIQUE,
                    preferences TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX IF NOT EXISTS auth_one_owner ON auth_users(is_owner) WHERE is_owner = 1;
                CREATE TABLE IF NOT EXISTS auth_sessions (
                    id TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE, user_id INTEGER NOT NULL,
                    user_agent TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    last_used TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, revoked INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES auth_users(id)
                );
                CREATE TABLE IF NOT EXISTS auth_config (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS auth_attempts (key TEXT NOT NULL, attempted REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS auth_attempt_time ON auth_attempts(key, attempted);
                CREATE TABLE IF NOT EXISTS auth_identities (
                    provider TEXT NOT NULL, subject TEXT NOT NULL, user_id INTEGER NOT NULL,
                    PRIMARY KEY(provider,subject), FOREIGN KEY(user_id) REFERENCES auth_users(id)
                );
            ''')
            owner = db.execute('SELECT * FROM auth_users WHERE is_owner = 1').fetchone()
            if owner is None:
                db.execute("INSERT INTO auth_users(full_name,nickname,email,role,is_owner,data_key) VALUES('Owner','Owner',?,'Admin',1,'primary')", (email_value(owner_email),))
                owner = db.execute('SELECT * FROM auth_users WHERE is_owner = 1').fetchone()
            if os.environ.get('RENDER') == 'true' and not owner['password_hash'] and len(os.environ.get('TASKLINE_SETUP_TOKEN', '')) < 32:
                raise RuntimeError('Set a random TASKLINE_SETUP_TOKEN of at least 32 characters before activating the owner on Render')

    def connect(self):
        db = sqlite3.connect(self.database, timeout=30)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def token_hash(token):
        return hashlib.sha256(token.encode()).hexdigest()

    def user_paths(self, user):
        if user['is_owner']:
            return self.database, self.database.parent / 'uploads'
        directory = self.state_dir / 'users' / user['data_key']
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        return directory / 'tasks.db', directory / 'uploads'

    def issue_session(self, user_id, agent):
        token, session_id = secrets.token_urlsafe(32), uuid.uuid4().hex
        with self.connect() as db:
            db.execute('INSERT INTO auth_sessions(id,token_hash,user_id,user_agent) VALUES(?,?,?,?)', (session_id, self.token_hash(token), user_id, agent[:300]))
        return token

    def resolve(self, token):
        if not token or len(token) > 100:
            return None
        with self.connect() as db:
            row = db.execute('''SELECT u.*, s.id AS session_id FROM auth_sessions s JOIN auth_users u ON u.id=s.user_id
                                WHERE s.token_hash=? AND s.revoked=0 AND u.active=1''', (self.token_hash(token),)).fetchone()
            if row:
                db.execute('UPDATE auth_sessions SET last_used=CURRENT_TIMESTAMP WHERE id=?', (row['session_id'],))
                return dict(row)

    def rate_limit(self, email, address):
        keys = [(self.token_hash('email:' + email), 12), (self.token_hash('ip:' + address), 60)]
        with self.connect() as db:
            db.execute('DELETE FROM auth_attempts WHERE attempted < ?', (time.time() - 900,))
            for key, limit in keys:
                if db.execute('SELECT COUNT(*) FROM auth_attempts WHERE key=?', (key,)).fetchone()[0] >= limit:
                    raise ValueError('Too many attempts; try again later / محاولات كثيرة، حاول لاحقًا')
            db.executemany('INSERT INTO auth_attempts VALUES(?,?)', [(key, time.time()) for key, _ in keys])

    def create_user(self, payload, role='User'):
        email = email_value(payload.get('email'))
        default_name = email.split('@', 1)[0]
        full_name, nickname, email = profile_fields({
            'full_name': default_name[:120], 'nickname': default_name[:60], **payload,
        })
        encoded = password_hash(payload.get('password'))
        if role not in ('Admin', 'User'):
            raise ValueError('Invalid role')
        key = uuid.uuid4().hex
        with self.connect() as db:
            cursor = db.execute('INSERT INTO auth_users(full_name,nickname,email,password_hash,role,data_key) VALUES(?,?,?,?,?,?)', (full_name,nickname,email,encoded,role,key))
            row = dict(db.execute('SELECT * FROM auth_users WHERE id=?', (cursor.lastrowid,)).fetchone())
            self.initialize_tenant(row)
        return row

    def route(self, handler, path, user):
        method = handler.command
        data = handler.read_json() if method in ('POST','PUT') else {}
        if not isinstance(data, dict):
            raise ValueError('Expected a JSON object')
        agent = handler.headers.get('User-Agent', '')
        if path == '/api/auth/status' and method == 'GET':
            with self.connect() as db:
                pending = not db.execute('SELECT password_hash FROM auth_users WHERE is_owner=1').fetchone()[0]
            handler.send_json({'user': public_user(user) if user else None, 'setup_required': pending, 'setup_token_required': pending and os.environ.get('RENDER') == 'true', 'registration_enabled': os.environ.get('RENDER') != 'true', 'google_login': False})
            return
        if path in ('/api/auth/setup','/api/auth/login','/api/auth/register') and method == 'POST':
            email = email_value(data.get('email'))
            self.rate_limit(email, handler.client_address[0])
            with self.connect() as db:
                owner = db.execute('SELECT * FROM auth_users WHERE is_owner=1').fetchone()
                if path.endswith('/setup'):
                    if owner['password_hash'] or email != owner['email']:
                        raise ValueError('Invalid activation account / بيانات التفعيل غير صحيحة')
                    if os.environ.get('RENDER') == 'true':
                        supplied = data.get('setup_token')
                        expected = os.environ.get('TASKLINE_SETUP_TOKEN', '')
                        if not isinstance(supplied, str) or len(expected) < 32 or not hmac.compare_digest(supplied.encode(), expected.encode()):
                            raise ValueError('Invalid activation account / بيانات التفعيل غير صحيحة')
                    db.execute('UPDATE auth_users SET password_hash=? WHERE id=?', (password_hash(data.get('password')),owner['id']))
                    db.execute("DELETE FROM auth_config WHERE key='setup_hash'")
                    user_id = owner['id']
                elif not owner['password_hash']:
                    raise ValueError('The owner must activate the app first / يجب تفعيل حساب المالك أولًا')
                elif path.endswith('/login'):
                    row = db.execute('SELECT * FROM auth_users WHERE email=?', (email,)).fetchone()
                    valid = verify_password(data.get('password'), row['password_hash'] if row else self.dummy_hash)
                    if not row or not row['active'] or not valid:
                        handler.send_json({'error':'Invalid email or password / البريد أو كلمة المرور غير صحيحة'}, 401)
                        return
                    user_id = row['id']
                else:
                    if os.environ.get('RENDER') == 'true':
                        raise ValueError('Registration is disabled / التسجيل غير متاح')
                    user_id = None
            if path.endswith('/setup'):
                self.setup_file.unlink(missing_ok=True)
            if user_id is None:
                user_id = self.create_user(data)['id']
            handler._session_token = self.issue_session(user_id, agent)
            handler.send_json({'user':public_user(self.resolve(handler._session_token))}, 201 if path.endswith('/register') else 200)
            return
        if not user:
            handler.send_json({'error':'Sign in required / يرجى تسجيل الدخول'}, 401)
            return
        if path == '/api/auth/logout' and method == 'POST':
            with self.connect() as db:
                db.execute('UPDATE auth_sessions SET revoked=1 WHERE id=?', (user['session_id'],))
            handler._session_token = ''
            handler.send_json({'ok': True})
            return
        if path == '/api/auth/renew' and method == 'POST':
            # Explicit rotation; normal requests refresh cookie persistence without expiring sessions.
            with self.connect() as db:
                db.execute('UPDATE auth_sessions SET revoked=1 WHERE id=?', (user['session_id'],))
            handler._session_token = self.issue_session(user['id'], agent)
            handler.send_json({'ok': True})
            return
        if path == '/api/auth/profile' and method in ('GET','PUT'):
            if method == 'PUT':
                name, nick, email = profile_fields(data)
                password = data.get('new_password')
                if (email != user['email'] or password) and not verify_password(data.get('current_password'), user['password_hash']):
                    raise ValueError('Current password required / أدخل كلمة المرور الحالية')
                prefs = data.get('preferences', json.loads(user['preferences']))
                if not isinstance(prefs, dict) or set(prefs) - {'theme','language'} or prefs.get('theme','system') not in ('system','light','dark') or prefs.get('language','ar') not in ('ar','en'):
                    raise ValueError('Invalid preferences')
                with self.connect() as db:
                    db.execute('UPDATE auth_users SET full_name=?,nickname=?,email=?,preferences=? WHERE id=?', (name,nick,email,json.dumps(prefs),user['id']))
                    if password:
                        db.execute('UPDATE auth_users SET password_hash=? WHERE id=?', (password_hash(password),user['id']))
                    if password or email != user['email']:
                        db.execute('UPDATE auth_sessions SET revoked=1 WHERE user_id=?', (user['id'],))
                if password or email != user['email']:
                    handler._session_token = self.issue_session(user['id'], agent)
                user = self.resolve(handler._session_token)
            handler.send_json({'user': public_user(user)})
            return
        if path == '/api/auth/sessions' and method == 'GET':
            with self.connect() as db:
                rows = db.execute('SELECT id,user_agent,created_at,last_used FROM auth_sessions WHERE user_id=? AND revoked=0 ORDER BY created_at DESC', (user['id'],)).fetchall()
            handler.send_json([dict(row) | {'current':row['id']==user['session_id']} for row in rows])
            return
        match = re.fullmatch('/api/auth/sessions/([a-f0-9]{32})', path)
        if match and method == 'DELETE':
            with self.connect() as db:
                db.execute('UPDATE auth_sessions SET revoked=1 WHERE id=? AND user_id=?', (match[1],user['id']))
            if match[1] == user['session_id']:
                handler._session_token = ''
            handler.send_json({'ok': True})
            return
        if path.startswith('/api/admin/'):
            if user['role'] != 'Admin':
                handler.send_json({'error':'Admin access required'}, 403)
                return
            if path == '/api/admin/backups' and method == 'GET':
                handler.send_json(self.backups.list())
                return
            if path == '/api/admin/backups' and method == 'POST':
                handler.send_json(self.backups.create('manual'),201)
                return
            backup_match = re.fullmatch(r'/api/admin/backups/([0-9TZ-]+[a-z-]*)/(verify|restore)', path)
            if backup_match and method == 'POST':
                identity,action = backup_match.groups()
                if action == 'restore':
                    if not user['is_owner'] or not verify_password(data.get('password'),user['password_hash']):
                        raise ValueError('Owner password required to restore / الاستعادة تتطلب كلمة مرور المالك')
                    result=self.backups.restore(identity)
                    handler._session_token=''
                else:
                    result=self.backups.verify(identity)
                handler.send_json(result)
                return
            if path == '/api/admin/users' and method == 'GET':
                with self.connect() as db:
                    handler.send_json([public_user(row) for row in db.execute('SELECT * FROM auth_users ORDER BY id')])
                return
            if path == '/api/admin/users' and method == 'POST':
                handler.send_json({'user':public_user(self.create_user(data, data.get('role','User')))}, 201)
                return
            match = re.fullmatch('/api/admin/users/(\d+)', path)
            if match and method == 'PUT':
                with self.connect() as db:
                    target = db.execute('SELECT * FROM auth_users WHERE id=?', (int(match[1]),)).fetchone()
                    if not target:
                        handler.send_json({'error':'User not found'}, 404)
                        return
                    name,nick,email = profile_fields(data)
                    role,active = data.get('role',target['role']), data.get('active',bool(target['active']))
                    if role not in ('Admin','User') or type(active) is not bool:
                        raise ValueError('Invalid role or status')
                    if target['is_owner'] and (role != 'Admin' or not active):
                        raise ValueError('The owner must remain an active Admin')
                    if target['is_owner'] and target['id'] != user['id']:
                        raise ValueError('Only the owner may change the owner account')
                    db.execute('UPDATE auth_users SET full_name=?,nickname=?,email=?,role=?,active=? WHERE id=?', (name,nick,email,role,int(active),target['id']))
                    if data.get('password'):
                        db.execute('UPDATE auth_users SET password_hash=? WHERE id=?', (password_hash(data['password']),target['id']))
                    if data.get('password') or not active or role != target['role'] or email != target['email']:
                        db.execute('UPDATE auth_sessions SET revoked=1 WHERE user_id=?', (target['id'],))
                    updated = db.execute('SELECT * FROM auth_users WHERE id=?', (target['id'],)).fetchone()
                handler.send_json({'user':public_user(updated)})
                return
        handler.send_json({'error':'Not found'}, 404)


def protected(method):
    @functools.wraps(method)
    def wrapper(handler):
        path = urlparse(handler.path).path
        handler._session_token = None
        if not (path.startswith('/api/') or path.startswith('/uploads/')):
            return method(handler)
        from local_backup import operation_lock
        store = handler.account_store()
        with operation_lock(store.state_dir):
            if handler.command not in ('GET','HEAD'):
                origin = handler.headers.get('Origin')
                origin_url = urlparse(origin) if origin else None
                if (origin_url and origin_url.netloc != handler.headers.get('Host')) or handler.headers.get('Sec-Fetch-Site') == 'cross-site':
                    handler.send_json({'error':'Cross-origin request rejected'}, 403)
                    return
                if handler.command in ('POST','PUT') and handler.headers.get('Content-Type','').split(';')[0] != 'application/json':
                    handler.send_json({'error':'JSON required'}, 415)
                    return
            cookie = SimpleCookie()
            try:
                cookie.load(handler.headers.get('Cookie',''))
                token = cookie[COOKIE].value if COOKIE in cookie else ''
            except Exception:
                token = ''
            user = store.resolve(token)
            handler._session_token = token if user else None
            expected = handler.headers.get('X-Taskline-Account')
            if user and expected and expected != str(user['id']):
                handler.send_json({'error':'Account changed; reload the page'},409)
                return
            try:
                if path.startswith(('/api/auth/','/api/admin/')):
                    return store.route(handler,path,user)
                if not user:
                    handler.send_json({'error':'Sign in required / يرجى تسجيل الدخول'}, 401)
                    return
                context = CURRENT_USER.set(user)
                try:
                    return method(handler)
                finally:
                    CURRENT_USER.reset(context)
            except sqlite3.IntegrityError:
                handler.send_json({'error':'Account already exists or invalid data / الحساب موجود أو البيانات غير صالحة'}, 400)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                handler.send_json({'error':str(error)}, 400)
    return wrapper


def security_headers(handler):
    handler.send_header('X-Content-Type-Options','nosniff')
    handler.send_header('X-Frame-Options','DENY')
    handler.send_header('Referrer-Policy','same-origin')
    handler.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
    if handler.path.startswith(('/api/','/uploads/')):
        handler.send_header('Cache-Control','no-store')
    token = getattr(handler, '_session_token', None)
    if token is not None:
        handler.send_header('Set-Cookie', f'{COOKIE}={token}; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age={34560000 if token else 0}')
