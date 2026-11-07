# Local accounts and recovery

The running Python app remains the existing Taskline app. There is no cloud database, email service, analytics, remote font request, or active Google login. Google identities have a reserved local table only; no OAuth flow is enabled.

## Storage and migration

- The primary owner uses the original `tasks.db` and `uploads/` without copying, renumbering or rewriting task records. Account/session tables are added to that same database. The immutable owner flag binds this data to the owner account even if its email later changes.
- New users get their own `TASKLINE_STATE_DIR/users/<random-key>/tasks.db` and `uploads/`. Every task API and uploaded image request resolves its database and folder from the authenticated session, never a user-supplied ID. Settings and routine generation run in that same store.
- Account passwords use salted scrypt (`N=131072, r=8, p=1`). Session cookies contain random tokens; only SHA-256 token hashes are stored on disk. Login attempts are rate limited locally. Profile email/password changes and admin security changes revoke old sessions. Disabled users retain all data.
- Profile and feature settings are persisted locally. Browser preferences are namespaced by account. The owner's old browser preferences migrate once without removing the old keys. Requests from a tab holding a different account ID are rejected, preventing cross-account writes after switching accounts in another tab.
- `tasks.db` was tracked before this feature. It is removed from the index, not the disk; new commits exclude databases, uploads, credentials and backups. Existing Git history is intentionally preserved locally, not rewritten or pushed.

## Configuration and first activation

Production uses `/home/core/.config/taskline/server.env` (mode 0600), outside Git:

```ini
TASKLINE_OWNER_EMAIL=owner@example.test
TASKLINE_STATE_DIR=/home/core/.local/share/taskline
TASKLINE_BACKUP_DIR=/home/core/.local/state/taskline-backups
```

The email above is an example, not a default account. On the first start, Taskline reserves that owner account with the Admin role. Open `/account.html` and enter only the configured email and a new password of at least 6 characters. Activation is allowed once; no preset password or setup code is used. Keep the deployment private and activate it before granting others access: knowing the reserved email is not proof of mailbox ownership, and anyone with access before activation could claim it. Existing profile names are preserved. Registration also needs only email and password, with initial names derived from the email; names can be edited later in Profile. Registration becomes available after activation and always creates a User; an Admin can create or manage users on the account page. The owner cannot be demoted or disabled. Users are disabled rather than deleted. Any legacy setup-code file is removed after activation.

Main app Settings links to Profile, sessions, logout and (for Admins) user and backup management. Use HTTPS for normal access. Cookies are `__Host-`, `Secure`, `HttpOnly`, `SameSite=Strict`. API and upload responses use `Cache-Control: no-store`; only the public interface shell is available offline.

## Persistent sessions

There is no server-side idle or absolute session timeout, and sessions survive server restarts. Each authenticated response renews the cookie's browser persistence; `/api/auth/renew` explicitly rotates the token. Logout, device-session revocation, account disabling, password/email security changes and database restore invalidate sessions.

Browsers impose their own storage limits: persistent cookies are set for 400 days and refreshed on use. Clearing browser data, removing the app, or leaving it unopened beyond the browser's cookie retention limit requires signing in again. The server does not impose inactivity logout. Session secrets are never placed in localStorage.

## Local backups

`taskline-backup.timer` runs every six hours with catch-up after downtime. Each dated directory contains online SQLite snapshots of the original database and every user store, uploaded files, and a SHA-256 manifest. Creation validates all checksums and SQLite integrity before publishing the backup directory. All backup/state directories are private to the service user. No automatic deletion or external upload is performed.

Install the files in `deploy/` as the systemd service/timer and the app service drop-in, using the paths in those files. Enable with `systemctl enable --now taskline-backup.timer`. Check with `systemctl list-timers taskline-backup.timer` and `journalctl -u taskline-backup.service`.

Admins can create, list and verify backups on `/account.html`. Only the primary owner can restore through the UI, and must re-enter their password. Restore validates the entire snapshot first and automatically creates a `before-restore` backup. Application reads/writes and backup operations share an OS lock to prevent partial concurrent writes. Restoring revokes every session, requiring a new login. Extra files created after the snapshot are retained on disk but unreferenced by restored accounts, allowing recovery without deletion.

For terminal operations, run as the service user with the same environment:

```bash
set -a
. /home/core/.config/taskline/server.env
set +a
python3 local_backup.py list
python3 local_backup.py create
python3 local_backup.py verify BACKUP_ID
python3 local_backup.py restore BACKUP_ID
```

After a terminal restore, restart `taskline.service`. If the restored snapshot predates owner activation, activate the reserved owner again with its email and a new password, keeping access private until that is done. On any interrupted restore, retain the `before-restore` directory and restore it after resolving the disk/service issue; no backup is removed automatically.

## Verification

Tests use temporary databases and temporary Chrome profiles. `tests/auth-backup.test.py` exercises activation, account roles, login/logout, session revocation/renewal, isolation (including uploads), profile/settings persistence, checksum rejection and real restore. `tests/auth-browser-smoke.py` exercises the UI and a real browser + server restart. `tests/verify-existing-data.py PATH_TO_DB` copies an existing database, compares every legacy row before/after migration, and restores the copy to verify exact preservation; it never modifies the source. The existing UI/API and frontend suites cover prior application behavior under authentication.

The unrelated starter-render test `tests/rendered-html.test.mjs` requires the unused JavaScript starter's `dist/server/index.js`; it is not part of the deployed Python runtime and cannot run without that separate build.

Password/session implementation references: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [OWASP session management](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html). Taskline deliberately omits server session timeouts per the requested persistent-session policy.
