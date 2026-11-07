"""Local, checksummed backups and verified restores; no networking."""
from __future__ import annotations

import argparse
import contextvars
import fcntl
import hashlib
import json
import os
import re
import shutil
import sqlite3
import tempfile
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path

_held = contextvars.ContextVar('backup_lock', default=None)


@contextmanager
def operation_lock(state):
    state = Path(state).resolve()
    if _held.get() == state:
        yield
        return
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(state / 'operation.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        token = _held.set(state)
        try:
            yield
        finally:
            _held.reset(token)
            fcntl.flock(lock, fcntl.LOCK_UN)


def sqlite_copy(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with closing(sqlite3.connect(f'file:{source}?mode=ro', uri=True)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('SQLite integrity check failed')
    os.chmod(destination, 0o600)


class Backups:
    def __init__(self, database, state, uploads, directory):
        self.database, self.state, self.uploads, self.directory = map(Path, (database,state,uploads,directory))

    def list(self):
        if not self.directory.exists():
            return []
        return sorted([{'id':p.name, 'created_at':json.loads((p/'manifest.json').read_text())['created_at']}
                       for p in self.directory.iterdir() if p.is_dir() and not p.name.startswith('.') and (p/'manifest.json').is_file()], key=lambda item:item['id'], reverse=True)

    def create(self, label='scheduled'):
        with operation_lock(self.state):
            self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            os.chmod(self.directory,0o700)
            created = datetime.now(timezone.utc)
            identity = created.strftime('%Y%m%dT%H%M%S%fZ') + '-' + label
            pending = Path(tempfile.mkdtemp(prefix='.pending-',dir=self.directory))
            sqlite_copy(self.database,pending/'primary/tasks.db')
            self.copy_uploads(self.uploads,pending/'primary/uploads')
            if (self.state/'users').exists():
                for user_dir in (self.state/'users').iterdir():
                    if re.fullmatch('[a-f0-9]{32}',user_dir.name) and (user_dir/'tasks.db').is_file():
                        sqlite_copy(user_dir/'tasks.db',pending/'users'/user_dir.name/'tasks.db')
                        self.copy_uploads(user_dir/'uploads',pending/'users'/user_dir.name/'uploads')
            files = {str(p.relative_to(pending)):hashlib.sha256(p.read_bytes()).hexdigest() for p in pending.rglob('*') if p.is_file()}
            (pending/'manifest.json').write_text(json.dumps({'format':1,'created_at':created.isoformat(),'files':files},indent=2))
            self.verify_directory(pending)
            pending.rename(self.directory/identity)
            return {'id':identity,'files':len(files)}

    @staticmethod
    def copy_uploads(source,destination):
        if not source.exists():
            return
        for file in source.rglob('*'):
            if file.is_symlink():
                raise ValueError('Symlinks are not supported in backup data')
            if file.is_file():
                target=destination/file.relative_to(source)
                target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                shutil.copy2(file,target)
                os.chmod(target,0o600)

    def path(self,identity):
        if not re.fullmatch(r'[0-9]{8}T[0-9]{12}Z-[a-z-]+',identity):
            raise ValueError('Invalid backup identifier')
        path=self.directory/identity
        if not path.is_dir() or path.is_symlink():
            raise ValueError('Backup not found')
        return path

    @staticmethod
    def verify_directory(path):
        manifest=json.loads((path/'manifest.json').read_text())
        if manifest.get('format') != 1 or 'primary/tasks.db' not in manifest.get('files',{}):
            raise ValueError('Invalid backup manifest')
        for name,digest in manifest['files'].items():
            relative=Path(name)
            if relative.is_absolute() or '..' in relative.parts or not re.fullmatch(r'(primary|users/[a-f0-9]{32})/(tasks\.db|uploads/[^/]+)',name):
                raise ValueError('Unsafe backup path')
            source=path/relative
            if source.is_symlink() or not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest()!=digest:
                raise ValueError('Backup checksum mismatch: '+name)
            if name.endswith('/tasks.db'):
                with closing(sqlite3.connect(f'file:{source}?mode=ro',uri=True)) as db:
                    if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                        raise ValueError('Invalid backup database: '+name)
        return manifest

    def verify(self,identity):
        manifest=self.verify_directory(self.path(identity))
        return {'ok':True,'files':len(manifest['files'])}

    def restore(self,identity):
        with operation_lock(self.state):
            source=self.path(identity)
            manifest=self.verify_directory(source)
            safety=self.create('before-restore')
            # Validate all files before replacing any; retain a recoverable pre-restore snapshot.
            for name in manifest['files']:
                if name.startswith('primary/'):
                    destination=self.database if name=='primary/tasks.db' else self.uploads/Path(name).name
                else:
                    destination=self.state/name
                if name.endswith('/tasks.db'):
                    sqlite_copy(source/name,destination)
                else:
                    destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                    shutil.copy2(source/name,destination)
                    os.chmod(destination,0o600)
            with sqlite3.connect(self.database) as db:
                if db.execute("SELECT 1 FROM sqlite_master WHERE name='auth_sessions'").fetchone():
                    db.execute('UPDATE auth_sessions SET revoked=1')
            return {'ok':True,'safety_backup':safety['id'],'sessions_revoked':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('create','list','verify','restore'))
    parser.add_argument('backup',nargs='?')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    data=Path(os.environ['TASKLINE_DATA_DIR']) if os.environ.get('TASKLINE_DATA_DIR') else None
    backups=Backups(os.environ.get('TASKLINE_DB',(data or root)/'tasks.db'),os.environ.get('TASKLINE_STATE_DIR',(data or root)/'private-data'),(data or root)/'uploads',os.environ.get('TASKLINE_BACKUP_DIR',data/'backups' if data else root.parent/'Taskline-backups'))
    if args.action in ('verify','restore') and not args.backup:
        parser.error('A backup identifier is required')
    result=getattr(backups,args.action)(args.backup) if args.backup else getattr(backups,args.action)()
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
