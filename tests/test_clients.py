import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
import database
from services.bootstrap import ensure_defaults
from services.security import current_user
from services.clients import save_client,get_client,add_payment,client_sales,credit_statement,list_payments
from services.cash import open_session,session_totals,close_session
from services.sales import complete_sale,create_return,hold_sale,resume_held
from services.catalog import search_products,set_product_categories

class ClientWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.old=database.DB_PATH
        database.DB_PATH=Path(self.tmp.name)/'test.db';database.init_db();ensure_defaults()
        with database.connect() as c:
            self.uid=c.execute('SELECT id FROM users').fetchone()[0]
            self.cat=c.execute("INSERT INTO categories(name) VALUES('Cats')").lastrowid
            self.pid=c.execute("INSERT INTO products(name,category_id,sale_price_cents) VALUES('Cat food',?,1000)",(self.cat,)).lastrowid
        self.token=current_user.set(self.uid)
        self.cid=save_client('Ahmed','0600000000');self.session=open_session(self.uid,0)
        self.cart=[dict(product_id=self.pid,qty=1,unit_price_cents=1000)]
    def tearDown(self):
        current_user.reset(self.token);database.DB_PATH=self.old;self.tmp.cleanup()
    def sale(self,method='CREDIT',paid=0):
        return complete_sale(self.session,self.uid,self.cart,method,paid,client_id=self.cid)
    def test_cash_and_card_are_not_debts(self):
        self.sale('CASH',1500);self.sale('CARD',1000)
        self.assertEqual(get_client(self.cid)['balance_cents'],0)
        self.assertEqual(credit_statement(),[])
    def test_credit_deposit_payment_and_close(self):
        sale=self.sale(paid=200)
        self.assertEqual(get_client(self.cid)['balance_cents'],800)
        add_payment(self.cid,300,'partial',sale['id'])
        self.assertEqual(client_sales(self.cid)[0]['balance_cents'],500)
        add_payment(self.cid,500,'final')
        self.assertEqual(get_client(self.cid)['balance_cents'],0)
        expected,diff,_=close_session(self.session,1000)
        self.assertEqual((expected,diff),(1000,0))
    def test_global_payment_allocates_oldest_and_rejects_excess(self):
        first=self.sale();self.sale()
        add_payment(self.cid,1500)
        self.assertEqual([r['balance_cents'] for r in client_sales(self.cid)],[0,500])
        self.assertEqual(len(list_payments(self.cid)),2)
        with self.assertRaises(ValueError):add_payment(self.cid,501)
        self.assertEqual(get_client(self.cid)['balance_cents'],500)
    def test_return_reduces_debt_before_refunding_cash(self):
        self.cart[0]['qty']=2
        sale=self.sale(paid=500)
        with database.connect() as c:item=c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchone()[0]
        first=create_return(sale['id'],self.session,self.uid,[(item,1)])
        self.assertEqual((first['refund_paid_cents'],get_client(self.cid)['balance_cents']),(0,500))
        second=create_return(sale['id'],self.session,self.uid,[(item,1)])
        self.assertEqual((second['refund_paid_cents'],get_client(self.cid)['balance_cents']),(500,0))
        self.assertEqual(close_session(self.session,0)[:2],(0,0))
    def test_settled_credit_return_refunds_receipts(self):
        sale=self.sale();add_payment(self.cid,1000)
        with database.connect() as c:item=c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchone()[0]
        result=create_return(sale['id'],self.session,self.uid,[(item,1)])
        self.assertEqual(result['refund_paid_cents'],1000)
        self.assertEqual(get_client(self.cid)['balance_cents'],0)
        self.assertEqual(close_session(self.session,0)[:2],(0,0))
    def test_hold_preserves_client_and_invalid_payments_rollback(self):
        hid=hold_sale(self.uid,self.cart,client_id=self.cid)
        self.assertEqual(resume_held(hid)['client_id'],self.cid)
        with self.assertRaises(ValueError):complete_sale(self.session,self.uid,self.cart,'CREDIT',0)
        self.sale()
        close_session(self.session,0)
        with self.assertRaises(ValueError):add_payment(self.cid,100)
        self.assertEqual(list_payments(self.cid),[])
    def test_search_and_category_assignments_survive_restart(self):
        self.assertEqual(search_products(category=self.cat)[0]['id'],self.pid)
        for q in ['Cat','Ca','food']:
            self.assertEqual(search_products(q)[0]['id'],self.pid)
        with database.connect() as c:
            c.execute("UPDATE products SET name='Cat_100% food' WHERE id=?",(self.pid,))
        self.assertEqual(search_products('_')[0]['id'],self.pid)
        self.assertEqual(search_products('%')[0]['id'],self.pid)
        with database.connect() as c:set_product_categories(c,self.pid,[])
        database.init_db()
        self.assertEqual(search_products(category=self.cat),[])
    def test_payment_requires_admin(self):
        self.sale()
        token=current_user.set(None)
        try:
            with self.assertRaises(PermissionError):add_payment(self.cid,100)
        finally:current_user.reset(token)

    def test_multiple_categories_keep_previous_primary_and_backup_upgrade(self):
        with database.connect() as c:
            second=c.execute("INSERT INTO categories(name) VALUES('Other')").lastrowid
            set_product_categories(c,self.pid,[second,self.cat])
            c.execute('PRAGMA user_version=110')
        database.init_db()
        self.assertEqual(search_products(category=self.cat)[0]['id'],self.pid)
        self.assertEqual(search_products(category=second)[0]['id'],self.pid)
        self.assertEqual(len(list((database.DB_PATH.parent/'migration_backups').glob('*.db'))),1)

    def test_photo_catalog_excludes_regular_products_before_limit(self):
        with database.connect() as c:
            c.executemany('INSERT INTO products(name,category_id) VALUES(?,?)',[(f'A{i:03}',self.cat) for i in range(100)])
            photo=c.execute("INSERT INTO products(name,category_id,image_path) VALUES('Z photo',?,'assets/test.png')",(self.cat,)).lastrowid
        self.assertNotIn(photo,[r['id'] for r in search_products()])
        self.assertEqual([r['id'] for r in search_products(images_only=True)],[photo])
        self.assertEqual(search_products(images_only=True,offset=1),[])
