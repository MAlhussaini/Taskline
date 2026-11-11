"""Per-account, per-workspace debt ledgers. Money is stored in integer cents."""
import re
from datetime import date
from decimal import Decimal, InvalidOperation

MAX_CENTS = 100_000_000_000


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS debt_lists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        workspace TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS debt_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id INTEGER NOT NULL REFERENCES debt_lists(id),
        title TEXT NOT NULL,
        amount_cents INTEGER NOT NULL,
        entry_date TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT 'transaction' CHECK(kind IN ('transaction', 'settlement')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")
    db.execute('CREATE INDEX IF NOT EXISTS debt_entries_list ON debt_entries(list_id, id)')


def title_value(payload):
    title = payload.get('title')
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= 280:
        raise ValueError('Enter a name between 1 and 280 characters')
    return title.strip()


def date_value(payload):
    value = payload.get('entry_date')
    if not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('Enter a valid date')
    return date.fromisoformat(value).isoformat()


def amount_value(payload):
    value = payload.get('amount')
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ValueError('Enter a signed amount with up to two decimal places')
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or abs(amount) > MAX_CENTS / 100:
            raise ValueError('Amount is out of range')
        cents = amount * 100
        if cents != cents.to_integral_value() or cents == 0:
            raise ValueError('Enter a non-zero amount with up to two decimal places')
        return int(cents)
    except InvalidOperation:
        raise ValueError('Enter a valid amount') from None


def ledger(db, list_id):
    row = dict(db.execute('SELECT * FROM debt_lists WHERE id=?', (list_id,)).fetchone())
    row['entries'] = [dict(entry) for entry in db.execute(
        'SELECT * FROM debt_entries WHERE list_id=? ORDER BY entry_date, id', (list_id,))]
    row['positive_cents'] = sum(e['amount_cents'] for e in row['entries'] if e['amount_cents'] > 0)
    row['negative_cents'] = sum(e['amount_cents'] for e in row['entries'] if e['amount_cents'] < 0)
    row['balance_cents'] = row['positive_cents'] + row['negative_cents']
    return row


def handle(handler, method, path, workspace, connect, read_settings):
    """Called only inside the authenticated handler and its account context."""
    if not path.startswith('/api/debts'):
        return False
    match = re.fullmatch(r'/api/debts(?:/(\d+)(?:/(entries|settle)(?:/(\d+))?)?)?', path)
    if not match:
        handler.send_json({'error': 'Not found'}, 404)
        return True
    list_id, action, entry_id = match.groups()
    try:
        with connect() as db:
            if method != 'GET':
                db.execute('BEGIN IMMEDIATE')
            if not read_settings(db)['features']['debts']:
                handler.send_json({'error': 'Enable financial transactions in Settings first'}, 403)
                return True
            # Existing users and restored stores receive the additive tables on first use.
            initialize(db)
            payload = handler.read_json() if method in ('POST', 'PUT') else {}
            if not isinstance(payload, dict):
                raise ValueError('Invalid request')
            if list_id is None:
                if method == 'GET':
                    result = [ledger(db, row['id']) for row in db.execute(
                        'SELECT id FROM debt_lists WHERE workspace=? ORDER BY id DESC', (workspace,))]
                elif method == 'POST':
                    cursor = db.execute('INSERT INTO debt_lists(title, workspace) VALUES(?, ?)',
                                        (title_value(payload), workspace))
                    result = ledger(db, cursor.lastrowid)
                else:
                    handler.send_json({'error': 'Method not allowed'}, 405)
                    return True
            else:
                existing = db.execute('SELECT id FROM debt_lists WHERE id=? AND workspace=?',
                                      (list_id, workspace)).fetchone()
                if not existing:
                    handler.send_json({'error': 'List not found'}, 404)
                    return True
                if action == 'entries' and entry_id:
                    entry = db.execute('SELECT * FROM debt_entries WHERE id=? AND list_id=?',
                                       (entry_id, list_id)).fetchone()
                    if not entry:
                        handler.send_json({'error': 'Entry not found'}, 404)
                        return True
                    if method == 'DELETE':
                        db.execute('DELETE FROM debt_entries WHERE id=?', (entry_id,))
                    elif method == 'PUT':
                        db.execute('UPDATE debt_entries SET title=?, amount_cents=?, entry_date=? WHERE id=?',
                                   (title_value(payload), amount_value(payload), date_value(payload), entry_id))
                    else:
                        handler.send_json({'error': 'Method not allowed'}, 405)
                        return True
                elif action == 'settle' and not entry_id and method == 'POST':
                    balance = ledger(db, list_id)['balance_cents']
                    # A second/concurrent settlement is a no-op once the balance is zero.
                    if balance:
                        if payload.get('balance_cents') != balance:
                            handler.send_json({'error': 'Balance changed. Refresh the list and try again.'}, 400)
                            return True
                        db.execute("INSERT INTO debt_entries(list_id,title,amount_cents,entry_date,kind) VALUES(?,?,?,?,'settlement')",
                                   (list_id, 'Settlement', -balance, date_value(payload)))
                elif action == 'entries' and not entry_id and method == 'POST':
                    db.execute('INSERT INTO debt_entries(list_id,title,amount_cents,entry_date) VALUES(?,?,?,?)',
                               (list_id, title_value(payload), amount_value(payload), date_value(payload)))
                elif action == 'entries' and not entry_id and method == 'DELETE':
                    db.execute('DELETE FROM debt_entries WHERE list_id=?', (list_id,))
                elif action is None and method == 'PUT':
                    db.execute('UPDATE debt_lists SET title=? WHERE id=?', (title_value(payload), list_id))
                elif action is None and method == 'DELETE':
                    db.execute('DELETE FROM debt_entries WHERE list_id=?', (list_id,))
                    db.execute('DELETE FROM debt_lists WHERE id=?', (list_id,))
                elif not (action is None and method == 'GET'):
                    handler.send_json({'error': 'Method not allowed'}, 405)
                    return True
                result = {'ok': True} if method == 'DELETE' and action is None else ledger(db, list_id)
                if result.get('balance_cents') is not None and any(
                    abs(result[key]) > MAX_CENTS for key in ('positive_cents', 'negative_cents', 'balance_cents')
                ):
                    raise ValueError('List total is out of range')
        handler.send_json(result, 201 if method == 'POST' and action != 'settle' else 200)
    except (ValueError, TypeError) as error:
        handler.send_json({'error': str(error)}, 400)
    return True
