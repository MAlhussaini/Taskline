"""Verify migration/restore on an isolated copy of an existing Taskline database."""
import importlib.util
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from local_backup import sqlite_copy


def snapshot(path, tables=None):
    with sqlite3.connect(f'file:{path}?mode=ro',uri=True) as db:
        tables=list(tables) if tables is not None else [row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'auth_%'")]
        return {name:[list(row) for row in db.execute('SELECT * FROM "'+name+'" ORDER BY rowid')] for name in tables}


def main(source):
    spec=importlib.util.spec_from_file_location('verify_existing',ROOT/'app.py')
    app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
    with tempfile.TemporaryDirectory(prefix='taskline-migration-audit-') as temporary:
        root=Path(temporary);app.DB_PATH=root/'tasks.db';app.UPLOAD_DIR=root/'uploads'
        sqlite_copy(source,app.DB_PATH)
        if (source.parent/'uploads').exists():shutil.copytree(source.parent/'uploads',app.UPLOAD_DIR)
        before=snapshot(app.DB_PATH)
        app.initialize_database()
        store=app.initialize_accounts('migration-owner@example.test',root/'state',root/'backups')
        assert snapshot(app.DB_PATH, before)==before,'Existing rows changed during migration'
        with store.connect() as db:
            owner=dict(db.execute('SELECT * FROM auth_users WHERE is_owner=1').fetchone())
        assert store.user_paths(owner)[0]==app.DB_PATH
        backup=store.backups.create('migration-test')
        with app.connect() as db:
            db.execute("UPDATE tasks SET title='Isolated restore test' WHERE id=(SELECT MIN(id) FROM tasks)")
        store.backups.restore(backup['id'])
        assert snapshot(app.DB_PATH, before)==before,'Restore did not reproduce existing rows exactly'
        print(json.dumps({'migration':'all existing rows identical','restore':'all existing rows identical','tables':{name:len(rows) for name,rows in before.items()}},indent=2))


if __name__=='__main__':main(Path(sys.argv[1]).resolve())
