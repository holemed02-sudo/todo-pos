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
from services.cash import open_session, close_session


class SupplierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = database.DB_PATH
        database.DB_PATH = Path(self.temp.name) / 'test.db'
        database.init_db()
        ensure_defaults()
        with database.connect() as conn:
            uid = conn.execute('SELECT id FROM users').fetchone()[0]
        self.uid = uid
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


    def test_supplier_payment_allocates_oldest_open_invoices(self):
        sid = save_supplier('Supplier')
        with database.connect() as conn:
            p1 = conn.execute("INSERT INTO purchases(supplier_id,supplier_invoice,total_cents) VALUES(?,?,?)",(sid,'F1',1000)).lastrowid
            p2 = conn.execute("INSERT INTO purchases(supplier_id,supplier_invoice,total_cents) VALUES(?,?,?)",(sid,'F2',2000)).lastrowid
        add_supplier_payment(sid, 1500)
        rows = {r['id']: r for r in supplier_purchases(sid)}
        self.assertEqual(rows[p1]['paid'], 1000)
        self.assertEqual(rows[p2]['paid'], 500)
        with self.assertRaises(ValueError):
            add_supplier_payment(sid, 1600)

    def test_supplier_payment_rejects_wrong_invoice_and_overpayment(self):
        s1 = save_supplier('Supplier 1')
        s2 = save_supplier('Supplier 2')
        with database.connect() as conn:
            p1 = conn.execute("INSERT INTO purchases(supplier_id,total_cents) VALUES(?,?)",(s1,1000)).lastrowid
            p2 = conn.execute("INSERT INTO purchases(supplier_id,total_cents) VALUES(?,?)",(s2,1000)).lastrowid
        with self.assertRaises(ValueError):
            add_supplier_payment(s1, 100, purchase_id=p2)
        with self.assertRaises(ValueError):
            add_supplier_payment(s1, 1001, purchase_id=p1)
        add_supplier_payment(s1, 400, purchase_id=p1)
        with self.assertRaises(ValueError):
            add_supplier_payment(s1, 601, purchase_id=p1)

    def test_supplier_payment_requires_admin_and_leaves_balance_unchanged(self):
        sid = save_supplier('Protected Supplier')
        with database.connect() as conn:
            pid = conn.execute("INSERT INTO purchases(supplier_id,total_cents) VALUES(?,?)",(sid,1000)).lastrowid
            cashier = conn.execute("INSERT INTO users(username,display_name,pin_hash,role) VALUES('pay_cashier','Pay Cashier','x','cashier')").lastrowid
        token = current_user.set(cashier)
        try:
            with self.assertRaises(PermissionError):
                add_supplier_payment(sid, 300, purchase_id=pid)
        finally:
            current_user.reset(token)
        rows = supplier_purchases(sid)
        self.assertEqual(rows[0]['paid'], 0)
        with database.connect() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM supplier_payments WHERE supplier_id=?",(sid,)).fetchone()[0],0)

    def test_cash_supplier_payment_reduces_expected_drawer_cash(self):
        sid = save_supplier('Cash Supplier')
        with database.connect() as conn:
            pid = conn.execute("INSERT INTO purchases(supplier_id,total_cents) VALUES(?,?)",(sid,1000)).lastrowid
        session = open_session(self.uid, 2000)
        add_supplier_payment(sid, 500, purchase_id=pid, payment_method='CASH')
        expected, diff, totals = close_session(session, 1500)
        self.assertEqual((expected, diff), (1500, 0))
        self.assertEqual(totals['cash_out'], 500)

    def test_card_supplier_payment_does_not_reduce_drawer_cash(self):
        sid = save_supplier('Card Supplier')
        with database.connect() as conn:
            pid = conn.execute("INSERT INTO purchases(supplier_id,total_cents) VALUES(?,?)",(sid,1000)).lastrowid
        session = open_session(self.uid, 2000)
        add_supplier_payment(sid, 500, purchase_id=pid, payment_method='CARD')
        expected, diff, totals = close_session(session, 2000)
        self.assertEqual((expected, diff), (2000, 0))
        self.assertEqual(totals['cash_out'], 0)
