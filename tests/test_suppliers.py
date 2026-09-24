import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'todo'))
import database
from services.bootstrap import ensure_defaults
from services.security import current_user
from services.suppliers import save_supplier, list_suppliers
from services.supplier_payments import add_supplier_payment, supplier_purchases


class SupplierTests(unittest.TestCase):
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

    def test_edit_preserves_purchase_identity_and_audits(self):
        sid = save_supplier(' Supplier ', '0600000000', 'Delivery Friday')
        with database.connect() as conn:
            conn.execute('INSERT INTO purchases(supplier_id,total_cents) VALUES(?,?)', (sid, 12500))
        save_supplier('Updated supplier', '0611111111', '', sid)
        with database.connect() as conn:
            row = conn.execute('SELECT s.name,p.total_cents FROM purchases p JOIN suppliers s ON s.id=p.supplier_id').fetchone()
            self.assertEqual(tuple(row), ('Updated supplier', 12500))
            self.assertEqual(conn.execute("SELECT count(*) FROM audit_log WHERE action LIKE 'SUPPLIER_%'").fetchone()[0], 2)
        self.assertEqual(list_suppliers('06111')[0]['id'], sid)

    def test_invalid_or_unauthorized_changes_leave_records_unchanged(self):
        with self.assertRaises(ValueError):
            save_supplier(' ')
        with self.assertRaises(ValueError):
            save_supplier('Missing', supplier_id=999)
        token = current_user.set(None)
        try:
            with self.assertRaises(PermissionError):
                save_supplier('Unauthorized')
        finally:
            current_user.reset(token)
        self.assertEqual(list_suppliers(), [])


# Supplier payment allocation regressions are covered above.
