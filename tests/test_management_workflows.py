import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
import database
from services.bootstrap import ensure_defaults
from services.security import current_user
from services.inventory import apply_physical_counts,apply_stock_movement
from services.supplier_payments import add_supplier_payment,supplier_purchases,supplier_credit_statement

class ManagementTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=database.DB_PATH
  database.DB_PATH=Path(self.tmp.name)/'test.db';database.init_db();ensure_defaults()
  with database.connect() as c:
   self.uid=c.execute('SELECT id FROM users').fetchone()[0]
   self.pids=[c.execute('INSERT INTO products(name,stock_qty) VALUES(?,10)',(name,)).lastrowid for name in ['A','B']]
   self.supplier=c.execute("INSERT INTO suppliers(name) VALUES('Supplier')").lastrowid
   self.other=c.execute("INSERT INTO suppliers(name) VALUES('Other')").lastrowid
   self.invoices=[c.execute('INSERT INTO purchases(supplier_id,total_cents) VALUES(?,1000)',(self.supplier,)).lastrowid for _ in range(2)]
  self.token=current_user.set(self.uid)
 def tearDown(self):
  current_user.reset(self.token);database.DB_PATH=self.old;self.tmp.cleanup()
 def test_counts_atomic_and_stale_stock_rejected(self):
  a,b=self.pids
  with database.connect() as c:apply_stock_movement(c,b,-1,'SALE')
  with self.assertRaises(ValueError):apply_physical_counts({a:7,b:8},{a:10,b:10})
  with database.connect() as c:self.assertEqual(c.execute('SELECT stock_qty FROM products WHERE id=?',(a,)).fetchone()[0],10)
  self.assertEqual(apply_physical_counts({a:7,b:8},{a:10,b:9}),2)
  with database.connect() as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM stock_movements WHERE movement_type='INVENTORY'").fetchone()[0],2)
 def test_invalid_counts_and_permissions(self):
  for value in [-1,float('nan'),1.5]:
   with self.assertRaises(ValueError):apply_physical_counts({self.pids[0]:value},{self.pids[0]:10})
  token=current_user.set(None)
  try:
   with self.assertRaises(PermissionError):add_supplier_payment(self.supplier,100)
   with database.connect() as c:
    with self.assertRaises(PermissionError):apply_stock_movement(c,self.pids[0],-1,'SORTIE',note='loss')
  finally:current_user.reset(token)
 def test_supplier_allocation_and_rejections(self):
  add_supplier_payment(self.supplier,1500)
  self.assertEqual([r['paid'] for r in supplier_purchases(self.supplier)],[500,1000])
  self.assertEqual(supplier_credit_statement()[0]['balance_cents'],500)
  with self.assertRaises(ValueError):add_supplier_payment(self.supplier,501)
  with self.assertRaises(ValueError):add_supplier_payment(self.other,1,purchase_id=self.invoices[0])
  add_supplier_payment(self.supplier,500,purchase_id=self.invoices[1])
  self.assertEqual(supplier_credit_statement(),[])
 def test_legacy_global_payment_is_allocated(self):
  with database.connect() as c:c.execute('INSERT INTO supplier_payments(supplier_id,amount_cents) VALUES(?,1200)',(self.supplier,))
  self.assertEqual([r['paid'] for r in supplier_purchases(self.supplier)],[200,1000])
  add_supplier_payment(self.supplier,800)
  self.assertEqual(supplier_credit_statement(),[])
