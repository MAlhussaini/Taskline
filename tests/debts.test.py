"""Debt HTTP regressions, isolated stores only."""
import concurrent.futures
import runpy
import unittest
from pathlib import Path

helpers = runpy.run_path(str(Path(__file__).with_name('star-rules.test.py')))
app, base = helpers['app'], helpers['StarRules']
from accounts import COOKIE


class DebtTests(unittest.TestCase):
    setUp = base.setUp
    tearDown = base.tearDown
    request = base.request

    def enable(self):
        return self.request('PUT', '/api/settings', {'features': {'debts': True}})

    def create(self, title='صديقي', workspace='personal'):
        self.enable()
        return self.request('POST', '/api/debts', {'title': title}, workspace, 201)['id']

    def entry(self, list_id, amount, **fields):
        return self.request('POST', f'/api/debts/{list_id}/entries',
                            {'title': 'عملية', 'amount': amount, 'entry_date': '2026-11-10', **fields}, expected=201)

    def test_opt_in_footer_and_preservation(self):
        self.request('GET', '/api/debts', expected=403)
        enabled = self.enable()['settings']
        self.assertEqual(enabled['footer'][0], 'debts')
        lid = self.create()
        self.entry(lid, '20')
        off = self.request('PUT', '/api/settings', {'features': {'debts': False}})['settings']
        self.assertEqual(off['footer'][0], 'settings')
        self.request('DELETE', f'/api/debts/{lid}', expected=403)
        self.enable()
        self.assertEqual(self.request('GET', f'/api/debts/{lid}')['balance_cents'], 2000)
        app.initialize_database()
        self.assertEqual(len(self.request('GET', '/api/debts')), 1)

    def test_signed_precision_edit_delete_and_dates(self):
        lid = self.create()
        for amount in ('100.10', '-30.20', '0.10', '0.20'):
            result = self.entry(lid, amount)
        self.assertEqual((result['positive_cents'], result['negative_cents'], result['balance_cents']), (10040, -3020, 7020))
        e = result['entries'][0]
        edited = self.request('PUT', f'/api/debts/{lid}/entries/{e["id"]}',
                             {'title': 'تعديل', 'amount': '-10.15', 'entry_date': '2026-11-01'})
        self.assertEqual(edited['balance_cents'], -4005)
        self.assertEqual(edited['entries'][0]['entry_date'], '2026-11-01')
        deleted = self.request('DELETE', f'/api/debts/{lid}/entries/{e["id"]}')
        self.assertEqual(deleted['balance_cents'], -2990)

    def test_settle_both_directions_concurrently_and_undo(self):
        for amount in ('120.25', '-65.10'):
            lid = self.create()
            result = self.entry(lid, amount)
            payload = {'balance_cents': result['balance_cents'], 'entry_date': '2026-11-10'}
            with concurrent.futures.ThreadPoolExecutor() as pool:
                results = list(pool.map(lambda _: self.request('POST', f'/api/debts/{lid}/settle', payload), range(2)))
            self.assertTrue(all(r['balance_cents'] == 0 for r in results))
            self.assertEqual(len(results[-1]['entries']), 2)
            settlement = next(e for e in results[-1]['entries'] if e['kind'] == 'settlement')
            self.assertEqual(settlement['amount_cents'], -result['balance_cents'])
            undo = self.request('DELETE', f'/api/debts/{lid}/entries/{settlement["id"]}')
            self.assertEqual(undo['balance_cents'], result['balance_cents'])
            self.request('POST', f'/api/debts/{lid}/settle', {**payload, 'balance_cents': 1}, expected=400)

    def test_clear_and_delete_are_scoped(self):
        first, second = self.create(), self.create('البقالة')
        self.entry(first, '10')
        self.entry(second, '-20')
        self.request('DELETE', f'/api/debts/{first}/entries', workspace='work', expected=404)
        cleared = self.request('DELETE', f'/api/debts/{first}/entries')
        self.assertEqual((cleared['entries'], cleared['balance_cents']), ([], 0))
        self.assertEqual(self.request('GET', f'/api/debts/{second}')['balance_cents'], -2000)
        self.entry(first, '5')
        self.request('DELETE', f'/api/debts/{first}')
        with app.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM debt_entries WHERE list_id=?', (first,)).fetchone()[0], 0)
        self.request('GET', f'/api/debts/{first}', expected=404)

    def test_settlement_archives_old_entries_and_keeps_backdated_new_entries_current(self):
        lid = self.create()
        self.entry(lid, '10', entry_date='2026-12-20')
        before = self.entry(lid, '-3', entry_date='2026-12-21')
        result = self.request('POST', f'/api/debts/{lid}/settle',
                              {'balance_cents': 700, 'entry_date': '2026-11-13'})
        self.assertEqual((result['archive_count'], result['current_count']), (3, 0))
        self.assertTrue(all(e['archived'] for e in result['entries']))
        self.assertEqual(result['current_totals'], {'positive_cents': 0, 'negative_cents': 0, 'balance_cents': 0})
        self.assertEqual(result['archive_totals']['balance_cents'], 0)
        result = self.entry(lid, '2', entry_date='2020-01-01')
        self.assertEqual((result['archive_count'], result['current_count']), (3, 1))
        self.assertEqual(result['current_totals']['positive_cents'], 200)
        self.assertFalse(result['entries'][0]['archived'])
        result = self.request('POST', f'/api/debts/{lid}/settle',
                              {'balance_cents': 200, 'entry_date': '2026-11-13'})
        self.assertEqual((result['archive_count'], result['current_count']), (5, 0))
        # Repeated settlement is still idempotent, including after initialization/restart.
        app.initialize_database()
        result = self.request('POST', f'/api/debts/{lid}/settle',
                              {'balance_cents': 0, 'entry_date': '2026-11-13'})
        self.assertEqual(result['archive_count'], 5)
        cleared = self.request('DELETE', f'/api/debts/{lid}/entries')
        self.assertEqual((cleared['archive_count'], cleared['current_count']), (0, 0))

    def test_historical_edits_reopen_unpaid_entries_without_hiding_a_balance(self):
        lid = self.create()
        original = self.entry(lid, '10')['entries'][0]
        self.request('POST', f'/api/debts/{lid}/settle', {'balance_cents':1000, 'entry_date':'2026-11-13'})
        result = self.request('PUT', f'/api/debts/{lid}/entries/{original["id"]}',
                              {'title':'Changed amount', 'amount':'12', 'entry_date':'2026-11-10'})
        self.assertEqual((result['archive_count'], result['current_count'], result['balance_cents']), (0, 2, 200))
        self.assertEqual(result['current_totals']['balance_cents'], result['balance_cents'])
        result = self.request('POST', f'/api/debts/{lid}/settle', {'balance_cents':200, 'entry_date':'2026-11-13'})
        self.assertEqual((result['archive_count'], result['current_count']), (3, 0))
        payment = max(result['entries'], key=lambda e:e['id'])
        result = self.request('DELETE', f'/api/debts/{lid}/entries/{payment["id"]}')
        self.assertEqual((result['archive_count'], result['current_count'], result['balance_cents']), (0, 2, 200))

    def test_existing_settlements_are_archived_without_mutating_records(self):
        lid = self.create()
        with app.connect() as db:
            db.execute("INSERT INTO debt_entries(list_id,title,amount_cents,entry_date) VALUES(?, 'Legacy', -700, '2026-11-01')", (lid,))
            db.execute("INSERT INTO debt_entries(list_id,title,amount_cents,entry_date,kind) VALUES(?, 'Settlement', 700, '2026-11-02','settlement')", (lid,))
            before = [tuple(row) for row in db.execute('SELECT * FROM debt_entries ORDER BY id')]
        result = self.request('GET', f'/api/debts/{lid}')
        self.assertEqual((result['archive_count'], result['current_count']), (2, 0))
        with app.connect() as db:
            self.assertEqual([tuple(row) for row in db.execute('SELECT * FROM debt_entries ORDER BY id')], before)

    def test_validation_and_account_isolation(self):
        lid = self.create()
        for amount in [True, None, {}, 'NaN', 'Infinity', '0.001', '0', '1000000001', 'bad']:
            self.request('POST', f'/api/debts/{lid}/entries', {'title':'x', 'amount':amount, 'entry_date':'2026-11-10'}, expected=400)
        for value in ['2026-02-30', 'yesterday', None]:
            self.request('POST', f'/api/debts/{lid}/entries', {'title':'x', 'amount':'2', 'entry_date':value}, expected=400)
        self.assertEqual(self.request('GET', f'/api/debts/{lid}')['entries'], [])
        self.entry(lid, '40')
        store = app.ACCOUNT_STORE
        user_id = store.create_user({'email':'other@example.test', 'password':'fixture-password-for-tests'})
        original_cookie = self.cookie
        # Simulate an existing account whose database predates the finance feature.
        import sqlite3
        with sqlite3.connect(store.user_paths(user_id)[0]) as db:
            db.execute('DROP TABLE debt_entries')
            db.execute('DROP TABLE debt_lists')
        self.cookie = COOKIE + '=' + store.issue_session(user_id['id'], 'Debt isolation test')
        self.enable()
        self.assertEqual(self.request('GET', '/api/debts'), [])
        self.request('DELETE', f'/api/debts/{lid}', expected=404)
        self.cookie = original_cookie
        self.assertEqual(self.request('GET', f'/api/debts/{lid}')['balance_cents'], 4000)


del base, helpers
if __name__ == '__main__':
    unittest.main()
