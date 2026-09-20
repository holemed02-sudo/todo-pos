"""Business acceptance: isolated purchase, sale, stock and printable PDF."""
import sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'todo'))
import database
from services import bootstrap, cash, purchases, sales, receipts
from services.security import current_user

class PurchaseToReceiptTest(unittest.TestCase):
    def test_purchase_sale_pdf(self):
        old = database.DB_PATH
        old_user = current_user.get()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                database.DB_PATH = Path(tmp) / 'test.db'
                database.init_db()
                bootstrap.ensure_defaults()
                with database.connect() as c:
                    uid = c.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
                    pid = c.execute("INSERT INTO products(name,sale_price_cents) VALUES('Test rice',300)").lastrowid
                current_user.set(uid)
                session = cash.open_session(uid, 10000)
                purchase, total = purchases.receive_purchase(None, 'TEST-001', [dict(product_id=pid,qty=5,unit_cost_cents=200)])
                self.assertEqual(total, 1000)
                with database.connect() as c:
                    self.assertEqual(c.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0],5)
                result = sales.complete_sale(session,uid,[dict(product_id=pid,qty=2,unit_price_cents=300)],'CASH',1000,100)
                self.assertEqual(result['total_cents'],500)
                self.assertEqual(result['change_cents'],500)
                with database.connect() as c:
                    self.assertEqual(c.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0],3)
                    self.assertEqual(c.execute('SELECT COUNT(*) FROM stock_movements WHERE product_id=?',(pid,)).fetchone()[0],2)
                    self.assertEqual(c.execute('SELECT SUM(net_total_cents-qty*cost_price_cents) FROM sale_items WHERE sale_id=?',(result['id'],)).fetchone()[0],100)
                receipt = receipts.build_receipt(result['id'])
                self.assertIn(result['sale_no'],receipt)
                self.assertIn('5.00',receipt)
                pdf=receipts.export_receipt_pdf(result['id'],Path(tmp)/'receipt.pdf')
                self.assertTrue(pdf.read_bytes().startswith(b'%PDF-'))
                self.assertGreater(pdf.stat().st_size,500)
            finally:
                current_user.set(old_user)
                database.DB_PATH=old
