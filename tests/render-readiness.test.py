"""Exercise persistent paths and the Render launch guard without touching live data."""
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

class RenderReadiness(unittest.TestCase):
    def test_runtime_paths_restart_and_sqlite_wal_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / 'disk'
            env = dict(os.environ, TASKLINE_DATA_DIR=str(data), TASKLINE_OWNER_EMAIL='owner@example.test', TASKLINE_HOST='0.0.0.0')
            env.pop('RENDER', None)
            for key in ('TASKLINE_DB', 'TASKLINE_STATE_DIR', 'TASKLINE_BACKUP_DIR'):
                env.pop(key, None)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                env['PORT'] = str(sock.getsockname()[1])
            command = 'TASKLINE_HOST=0.0.0.0 TASKLINE_PORT=$PORT python3 app.py'
            def start():
                proc = subprocess.Popen(command, shell=True, executable='/bin/bash', cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
                for _ in range(100):
                    try:
                        with urllib.request.urlopen('http://127.0.0.1:'+env['PORT']+'/api/auth/status', timeout=1) as response:
                            return proc, json.load(response)
                    except OSError:
                        if proc.poll() is not None:
                            self.fail(proc.stderr.read().decode())
                        time.sleep(.1)
                proc.terminate()
                self.fail('server did not start')
            proc, status = start()
            try:
                self.assertTrue(status['setup_required'])
                self.assertTrue((data/'tasks.db').exists())
                self.assertTrue((data/'uploads').is_dir())
                self.assertTrue((data/'private-data').is_dir())
                with sqlite3.connect(data/'tasks.db') as db:
                    self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone()[0], 'wal')
                    db.execute('CREATE TABLE wal_marker(value TEXT)')
                    db.execute("INSERT INTO wal_marker VALUES('present')")
                    db.commit()
                    self.assertTrue((data/'tasks.db-wal').exists())
                    self.assertTrue((data/'tasks.db-shm').exists())
                    result = subprocess.run(['python3','local_backup.py','create'], cwd=ROOT, env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    backup_id = json.loads(result.stdout)['id']
                    subprocess.run(['python3','local_backup.py','verify',backup_id], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
                    with sqlite3.connect(data/'backups'/backup_id/'primary'/'tasks.db') as backup:
                        self.assertEqual(backup.execute('SELECT value FROM wal_marker').fetchone()[0], 'present')
                with sqlite3.connect(data/'tasks.db') as db:
                    db.execute("UPDATE wal_marker SET value='changed'")
                subprocess.run(['python3','local_backup.py','restore',backup_id], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
                with sqlite3.connect(data/'tasks.db') as db:
                    self.assertEqual(db.execute('SELECT value FROM wal_marker').fetchone()[0], 'present')
            finally:
                proc.terminate(); proc.wait(timeout=10); proc.stderr.close()
            proc, _ = start()
            try:
                with sqlite3.connect(data/'tasks.db') as db:
                    self.assertEqual(db.execute('SELECT value FROM wal_marker').fetchone()[0], 'present')
            finally:
                proc.terminate(); proc.wait(timeout=10); proc.stderr.close()

    def test_render_rejects_unmounted_data_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            env = dict(os.environ, RENDER='true', TASKLINE_DATA_DIR=temp, TASKLINE_OWNER_EMAIL='owner@example.test')
            result = subprocess.run(['python3','app.py'], cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('persistent disk mount', result.stderr)
            self.assertFalse((Path(temp)/'tasks.db').exists())

if __name__ == '__main__':
    unittest.main()
