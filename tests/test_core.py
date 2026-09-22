import sys,sqlite3,tempfile,unittest,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
import database as db
from services import backup
from services.bootstrap import ensure_defaults
from services.cash import open_session,close_session
from services.sales import complete_sale,create_return,hold_sale,resume_held,list_held
from services.pricing import resolve_unit_price,line_total
from services.inventory import apply_stock_movement
from services.purchases import receive_purchase
from services.catalog import search_products,scan_barcode
from services.security import current_user,hash_pin,verify_pin

class CoreTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();db.DB_PATH=Path(self.temp.name)/'todo.db'
  backup.DB_PATH=db.DB_PATH;backup.BASE=Path(self.temp.name)
  db.init_db();ensure_defaults()
  with db.connect() as c:self.uid=c.execute("SELECT id FROM users WHERE username='admin'").fetchone()[0]
  current_user.set(self.uid);self.session=open_session(self.uid,10000);self.pid=self.product()
 def tearDown(self):
  current_user.set(None);self.temp.cleanup()
 def product(self,name='Article',stock=20,fraction=0):
  with db.connect() as c:
   pid=c.execute('INSERT INTO products(name,sale_price_cents,purchase_price_cents,allow_fraction) VALUES(?,1000,300,?)',(name,fraction)).lastrowid
   apply_stock_movement(c,pid,stock,'OPENING',300,'product',pid,'Initial');return pid
 def sell(self,qty=1,price=1000,discount=0,pid=None):
  return complete_sale(self.session,self.uid,[dict(product_id=pid or self.pid,qty=qty,unit_price_cents=price)],'CASH',100000,discount)
 def item(self,sale):
  with db.connect() as c:return c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchone()[0]
 def stock(self):
  with db.connect() as c:return c.execute('SELECT stock_qty FROM products WHERE id=?',(self.pid,)).fetchone()[0]
 def test_mixed_cash_card_payment_tracks_only_cash_in_drawer(self):
  sale=complete_sale(self.session,self.uid,[dict(product_id=self.pid,qty=1,unit_price_cents=10000)],'CASH',10000,payments=[('CASH',3000),('CARD',7000)])
  with db.connect() as c:
   row=c.execute('SELECT payment_method,paid_cents,change_cents FROM sales WHERE id=?',(sale['id'],)).fetchone()
   self.assertEqual(tuple(row),('MIXED',10000,0))
   parts=[tuple(r) for r in c.execute('SELECT payment_method,amount_cents FROM sale_payments WHERE sale_id=? ORDER BY payment_method',(sale['id'],))]
   self.assertEqual(parts,[('CARD',7000),('CASH',3000)])
  self.assertEqual(close_session(self.session,13000)[:2],(13000,0))
 def test_invalid_mixed_payment_rolls_back(self):
  with self.assertRaises(ValueError):
   complete_sale(self.session,self.uid,[dict(product_id=self.pid,qty=1,unit_price_cents=10000)],'CASH',10000,payments=[('CASH',3000),('CARD',6000)])
  with db.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM sales').fetchone()[0],0)
 def test_sale_return_cash(self):
  sale=self.sell(2,450);self.assertEqual(self.stock(),18)
  ret=create_return(sale['id'],self.session,self.uid,[(self.item(sale),1)])
  self.assertEqual(ret['total_cents'],450);self.assertEqual(self.stock(),19)
  self.assertEqual(close_session(self.session,10450)[1],0)
 def test_discount_refund(self):
  sale=self.sell(discount=200)
  self.assertEqual(create_return(sale['id'],self.session,self.uid,[(self.item(sale),1)])['total_cents'],800)
 def test_partial_refunds_rounding(self):
  sale=self.sell(3,100,1)
  amounts=[create_return(sale['id'],self.session,self.uid,[(self.item(sale),1)])['total_cents'] for _ in range(3)]
  self.assertEqual(sum(amounts),299)
  with self.assertRaises(ValueError):create_return(sale['id'],self.session,self.uid,[(self.item(sale),1)])
 def test_duplicate_return_lines(self):
  sale=self.sell();item=self.item(sale)
  with self.assertRaises(ValueError):create_return(sale['id'],self.session,self.uid,[(item,1),(item,1)])
  self.assertEqual(self.stock(),19)
 def test_atomic_rollback(self):
  db.set_setting('allow_negative_stock','0')
  with self.assertRaises(ValueError):complete_sale(self.session,self.uid,[dict(product_id=self.pid,qty=15,unit_price_cents=100)]*2,'CASH',10000)
  self.assertEqual(self.stock(),20)
  with db.connect() as c:
   self.assertEqual(c.execute('SELECT count(*) FROM sales').fetchone()[0],0)
   self.assertEqual(c.execute("SELECT count(*) FROM stock_movements WHERE movement_type='SALE'").fetchone()[0],0)
 def test_negative_stock(self):
  self.assertEqual(db.get_setting('allow_negative_stock'),'1')
  self.sell(20);self.assertEqual(self.stock(),0)
  self.sell();self.assertEqual(self.stock(),-1)
  self.sell(2);self.assertEqual(self.stock(),-3)
  with db.connect() as c:
   movement=c.execute("SELECT old_qty,stock_after FROM stock_movements WHERE movement_type='SALE' ORDER BY id DESC LIMIT 1").fetchone()
   self.assertEqual(tuple(movement),(-1,-3))
 def test_negative_stock_policy_upgrade_once(self):
  with db.connect() as c:
   c.execute("DELETE FROM settings WHERE key='negative_stock_policy_v1'")
   c.execute("UPDATE settings SET value='0' WHERE key='allow_negative_stock'")
  db.init_db();self.assertEqual(db.get_setting('allow_negative_stock'),'1')
  db.set_setting('allow_negative_stock','0')
  db.init_db();self.assertEqual(db.get_setting('allow_negative_stock'),'0')
 def test_return_improves_negative_stock_with_strict_setting(self):
  sale=self.sell(25)
  db.set_setting('allow_negative_stock','0')
  create_return(sale['id'],self.session,self.uid,[(self.item(sale),1)])
  self.assertEqual(self.stock(),-4)
 def test_zero_price(self):self.assertEqual(self.sell(price=0)['total_cents'],0)
 def test_bundle_groups_remainder_and_refund(self):
  with db.connect() as c:
   c.execute("INSERT INTO quantity_prices(product_id,min_qty,unit_price_cents,pricing_mode) VALUES(?,3,2500,'BUNDLE')",(self.pid,))
  for qty,total in [(1,1000),(2,2000),(3,2500),(4,3500),(6,5000),(7,6000)]:
   self.assertEqual(line_total(resolve_unit_price(self.pid,qty),qty),total)
  sale=complete_sale(self.session,self.uid,[dict(product_id=self.pid,qty=3)],'CASH',2500)
  refunds=[create_return(sale['id'],self.session,self.uid,[(self.item(sale),1)])['total_cents'] for _ in range(3)]
  self.assertEqual(sum(refunds),2500)
 def test_invalid_discount(self):
  for d in [-1,1001]:
   with self.assertRaises(ValueError):self.sell(discount=d)
 def test_invalid_quantities(self):
  for q in [0,-1,float('nan'),float('inf'),0.5]:
   with self.assertRaises(ValueError):self.sell(qty=q)
 def test_fraction_product(self):
  pid=self.product(fraction=1);self.assertEqual(self.sell(qty=.125,pid=pid)['total_cents'],125)
 def test_quantity_and_pack_prices(self):
  with db.connect() as c:
   c.execute('INSERT INTO quantity_prices(product_id,min_qty,unit_price_cents) VALUES(?,2,1100)',(self.pid,))
   bid=c.execute("INSERT INTO product_barcodes(product_id,barcode,qty_multiplier,price_override_cents) VALUES(?,'PACK',12,11000)",(self.pid,)).lastrowid
   self.assertEqual(resolve_unit_price(self.pid,2,conn=c),1100)
   self.assertEqual(line_total(resolve_unit_price(self.pid,12,bid,c),12),11000)
  sale=complete_sale(self.session,self.uid,[dict(product_id=self.pid,qty=12,barcode_id=bid,barcode='PACK')],'CASH',11000)
  self.assertEqual(sale['total_cents'],11000)
 def test_hold_persists_discount(self):
  hid=hold_sale(self.uid,[dict(product_id=self.pid,qty=1,unit_price_cents=1000)],'Held',200)
  state=resume_held(hid);self.assertEqual(state['discount_cents'],200);self.assertEqual(len(list_held()),1)
  sale=complete_sale(self.session,self.uid,state['cart'],'CASH',800,200,hid)
  self.assertEqual(sale['total_cents'],800);self.assertEqual(len(list_held()),0)
  with self.assertRaises(ValueError):complete_sale(self.session,self.uid,state['cart'],'CASH',800,200,hid)
 def test_failed_held_kept(self):
  db.set_setting('allow_negative_stock','0')
  hid=hold_sale(self.uid,[dict(product_id=self.pid,qty=100,unit_price_cents=1000)])
  with self.assertRaises(ValueError):complete_sale(self.session,self.uid,resume_held(hid)['cart'],'CASH',100000,0,hid)
  self.assertEqual(len(list_held()),1)
 def test_closed_session(self):
  sale=self.sell();close_session(self.session,11000)
  with self.assertRaises(ValueError):self.sell()
  with self.assertRaises(ValueError):create_return(sale['id'],self.session,self.uid,[(self.item(sale),1)])
 def test_backup_live_wal(self):
  keeper=db.connect()
  try:
   keeper.execute('PRAGMA wal_autocheckpoint=0');keeper.execute("INSERT INTO settings VALUES('marker','present')");keeper.commit()
   saved=backup.create_backup();copy=sqlite3.connect(saved)
   try:self.assertEqual(copy.execute("SELECT value FROM settings WHERE key='marker'").fetchone()[0],'present')
   finally:copy.close()
  finally:keeper.close()
 def test_restore_and_invalid_backup(self):
  saved=backup.create_backup();self.sell();backup.restore_backup(saved);self.assertEqual(self.stock(),20)
  invalid=Path(self.temp.name)/'bad.db';invalid.write_bytes(b'not sqlite')
  with self.assertRaises((ValueError,sqlite3.Error)):backup.restore_backup(invalid)
  self.assertEqual(self.stock(),20)
 def test_search_and_ambiguity(self):
  second=self.product('Huile Olive')
  with db.connect() as c:
   c.execute("UPDATE products SET sku='REF-123',alias='زيت بلدي',supplier_code='SUP-789' WHERE id=?",(second,))
   c.executemany("INSERT INTO product_barcodes(product_id,barcode) VALUES(?,'SHARED')",[(self.pid,),(second,)])
  for q in ['Olive','live','REF-123','بلدي','SUP-789']:self.assertIn(second,[r['id'] for r in search_products(q)])
  self.assertEqual(len(scan_barcode('SHARED')),2)
 def test_stock_actor(self):
  with db.connect() as c:
   apply_stock_movement(c,self.pid,3,'ADJUSTMENT',note='Correction fiche')
   r=c.execute('SELECT * FROM stock_movements ORDER BY id DESC LIMIT 1').fetchone()
   self.assertEqual((r['old_qty'],r['stock_after'],r['user_id']),(20,23,self.uid))
 def test_cashier_permission(self):
  with db.connect() as c:uid=c.execute("INSERT INTO users(username,display_name,pin_hash,role) VALUES('cashier','Cashier',?,'cashier')",(hash_pin('5678'),)).lastrowid
  current_user.set(uid)
  with self.assertRaises(PermissionError):
   with db.connect() as c:apply_stock_movement(c,self.pid,1,'ADJUSTMENT',note='Test')
 def test_purchase(self):
  receive_purchase(None,'INV-1',[dict(product_id=self.pid,qty=3,unit_cost_cents=400)]);self.assertEqual(self.stock(),23)
 def test_migration_idempotent(self):
  sale=self.sell(discount=123);db.init_db();db.init_db()
  with db.connect() as c:self.assertEqual(c.execute('SELECT net_total_cents FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchone()[0],877)
 def test_pin_hash(self):
  a=hash_pin('1234');self.assertNotEqual(a,hash_pin('1234'));self.assertTrue(verify_pin('1234',a));self.assertFalse(verify_pin('4321',a))
  self.assertTrue(verify_pin('1234',hashlib.sha256(b'1234').hexdigest()))

 def test_legacy_migration_and_preupgrade_backup(self):
  old_path=db.DB_PATH;db.DB_PATH=Path(self.temp.name)/'legacy.db';backup.DB_PATH=db.DB_PATH
  c=sqlite3.connect(db.DB_PATH)
  c.executescript(db.SCHEMA)
  c.execute("INSERT INTO users(id,username,display_name,pin_hash) VALUES(1,'old','Old','hash')")
  c.execute('INSERT INTO cash_sessions(id,user_id) VALUES(1,1)')
  c.execute("INSERT INTO products(id,name,stock_qty) VALUES(1,'Legacy',9)")
  c.execute("INSERT INTO sales(id,sale_no,session_id,cashier_user_id,subtotal_cents,discount_cents,total_cents,paid_cents) VALUES(1,'OLD',1,1,1000,200,800,800)")
  c.execute("INSERT INTO sale_items(sale_id,product_id,name_snapshot,qty,unit_price_cents,line_total_cents) VALUES(1,1,'Legacy',1,1000,1000)")
  c.commit();c.close();db.init_db()
  with db.connect() as c:self.assertEqual(c.execute('SELECT net_total_cents FROM sale_items').fetchone()[0],800)
  self.assertEqual(create_return(1,1,1,[(1,1)])['total_cents'],800)
  self.assertTrue(list((db.DB_PATH.parent/'migration_backups').glob('*.db')))
  db.DB_PATH=old_path;backup.DB_PATH=old_path

 def test_line_and_ticket_discounts(self):
  sale=complete_sale(self.session,self.uid,[dict(product_id=self.pid,qty=1,unit_price_cents=1000,discount_cents=100),dict(product_id=self.pid,qty=1,unit_price_cents=1000)],'CASH',1800,100)
  with db.connect() as c:items=c.execute('SELECT id,net_total_cents FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchall()
  self.assertEqual(sum(i['net_total_cents'] for i in items),1800)
  refund=create_return(sale['id'],self.session,self.uid,[(i['id'],1) for i in items])
  self.assertEqual(refund['total_cents'],1800)

 def test_reports_follow_returns(self):
  from services.reports import today_summary
  sale=self.sell(discount=200);summary=today_summary()
  self.assertEqual((summary['net_sales'],summary['gross_margin']),(800,500))
  create_return(sale['id'],self.session,self.uid,[(self.item(sale),1)])
  summary=today_summary();self.assertEqual((summary['net_sales'],summary['gross_margin']),(0,0))

 def test_cash_movement_rejects_closed_session(self):
  from services.cash import record_cash
  record_cash(self.session,self.uid,200,'IN','Test')
  self.assertEqual(close_session(self.session,10200)[1],0)
  with self.assertRaises(ValueError):record_cash(self.session,self.uid,100,'OUT','Test')

 def test_github_pack_snapshot_and_return_policy(self):
  with db.connect() as c:
   bid=c.execute("INSERT INTO product_barcodes(product_id,barcode,qty_multiplier,price_override_cents) VALUES(?,'CARTON',6,2500)",(self.pid,)).lastrowid
  sale=complete_sale(self.session,self.uid,[dict(product_id=self.pid,qty=6,barcode_id=bid)],'CASH',2500,100)
  with db.connect() as c:row=c.execute('SELECT * FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchone()
  self.assertEqual((row['pricing_mode'],row['qty_multiplier'],row['unit_price_cents'],row['barcode_used']),('PACK',6,2500,'CARTON'))
  with self.assertRaises(ValueError):create_return(sale['id'],self.session,self.uid,[(row['id'],1)])
  self.assertEqual(create_return(sale['id'],self.session,self.uid,[(row['id'],6)])['total_cents'],2400)
  with self.assertRaises(ValueError):complete_sale(self.session,self.uid,[dict(product_id=self.pid,qty=7,barcode_id=bid)],'CASH',10000)

 def test_github_legacy_held_pack(self):
  with db.connect() as c:
   bid=c.execute("INSERT INTO product_barcodes(product_id,barcode,qty_multiplier,price_override_cents) VALUES(?,'CARTON',6,2500)",(self.pid,)).lastrowid
  hid=hold_sale(self.uid,[dict(product_id=self.pid,name='Article',qty=6,barcode_id=bid,unit_price_cents=2500,pricing_mode='PACK',qty_multiplier=6)])
  state=resume_held(hid)
  self.assertEqual(line_total(state['cart'][0]['unit_price_cents'],6),2500)

if __name__=='__main__':unittest.main()
