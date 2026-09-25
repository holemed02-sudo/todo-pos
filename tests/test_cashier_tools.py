import sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
from screens.cashier_tools import calculate
from services.misc import misc_line
from services.bootstrap import ensure_defaults
from services.cash import open_session
from services.sales import complete_sale,create_return,hold_sale,resume_held
from services.catalog import search_products
from services.security import current_user
from services.receipts import build_receipt
import database

class CashierToolsTest(unittest.TestCase):
    def test_calculator(self):
        self.assertEqual(calculate('(0,1 + 0,2) × 3'),'0.9')
        self.assertEqual(calculate('-10 / 4'),'-2.5')
        for expression in ['1/0','2**1000','__import__("os")','[1]','True','9'*170]:
            with self.assertRaises((ValueError,SyntaxError,ArithmeticError)):calculate(expression)

    def test_misc_sale_hold_and_return_without_stock(self):
        old=database.DB_PATH;token=current_user.set(None)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                database.DB_PATH=Path(tmp)/'db.sqlite';database.init_db();ensure_defaults()
                with database.connect() as conn:uid=conn.execute('SELECT id FROM users').fetchone()[0]
                current_user.set(uid);session=open_session(uid,0)
                a=misc_line('Produit non enregistré','12.50','2')
                b=misc_line('Supplément','3.00')
                hid=hold_sale(uid,[a,b]);cart=resume_held(hid)['cart']
                self.assertEqual(search_products('Divers'),[])
                sale=complete_sale(session,uid,cart,'CASH',3000,held_id=hid)
                self.assertEqual(sale['total_cents'],2800)
                receipt=build_receipt(sale['id'])
                self.assertIn('Produit non enregistré',receipt);self.assertIn('Supplément',receipt)
                with database.connect() as conn:
                    rows=conn.execute('SELECT id,qty FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchall()
                refund=create_return(sale['id'],session,uid,[(r['id'],r['qty']) for r in rows])
                self.assertEqual(refund['total_cents'],2800)
                with database.connect() as conn:
                    self.assertEqual(conn.execute('SELECT COUNT(*) FROM stock_movements').fetchone()[0],0)
                    self.assertEqual(conn.execute('SELECT stock_qty FROM products WHERE is_misc=1').fetchone()[0],0)
            finally:database.DB_PATH=old;current_user.reset(token)

    def test_flash_payment_sources_separate_cash_card_and_credit(self):
        old=database.DB_PATH;token=current_user.set(None)
        with tempfile.TemporaryDirectory() as tmp:
            try:
                database.DB_PATH=Path(tmp)/'db.sqlite';database.init_db();ensure_defaults()
                with database.connect() as conn:
                    uid=conn.execute('SELECT id FROM users').fetchone()[0]
                    pid=conn.execute("SELECT id FROM products WHERE is_misc=1").fetchone()[0]
                    cid=conn.execute("INSERT INTO clients(name,active) VALUES('Flash credit',1)").lastrowid
                current_user.set(uid);session=open_session(uid,0)
                for method,price,paid,client in [('CASH',1000,1000,None),('CARD',2000,2000,None),('CREDIT',3000,0,cid)]:
                    line=dict(product_id=pid,name=method+' item',qty=1,unit_price_cents=price,discount_cents=0)
                    complete_sale(session,uid,[line],method,paid,client_id=client)
                with database.connect() as conn:
                    totals={row['payment_method']:row['amount'] for row in conn.execute(
                        "SELECT payment_method,SUM(amount_cents) amount FROM sale_payments GROUP BY payment_method")}
                self.assertEqual(totals.get('CASH'),1000)
                self.assertEqual(totals.get('CARD'),2000)
                self.assertEqual(totals.get('CREDIT'),0)
            finally:database.DB_PATH=old;current_user.reset(token)
