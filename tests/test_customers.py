import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'todo'))
import database
from services.bootstrap import ensure_defaults
from services.security import current_user
from services.customers import save_customer, list_customers


class CustomerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / 'test.db'
        database.init_db()
        ensure_defaults()
        with database.connect() as conn:
            uid = conn.execute('SELECT id FROM users').fetchone()[0]
        self.token = current_user.set(uid)

    def tearDown(self):
        current_user.reset(self.token)
        database.DB_PATH = self.old
        self.temp.cleanup()

    def test_create_search_and_edit_audits(self):
        cid = save_customer(' Client ', '0600000000', 'Habitué du quartier')
        self.assertEqual(list_customers('06000')[0]['id'], cid)
        save_customer('Client fidèle', '0611111111', '', cid)
        with database.connect() as conn:
            row = conn.execute('SELECT name,phone FROM customers WHERE id=?', (cid,)).fetchone()
            self.assertEqual(tuple(row), ('Client fidèle', '0611111111'))
            self.assertEqual(conn.execute("SELECT count(*) FROM audit_log WHERE action LIKE 'CUSTOMER_%'").fetchone()[0], 2)

    def test_invalid_or_unauthorized_changes_leave_records_unchanged(self):
        with self.assertRaises(ValueError):
            save_customer(' ')
        with self.assertRaises(ValueError):
            save_customer('Missing', customer_id=999)
        token = current_user.set(None)
        try:
            with self.assertRaises(PermissionError):
                save_customer('Unauthorized')
        finally:
            current_user.reset(token)
        self.assertEqual(list_customers(), [])
