import os,sys,tempfile,json
from pathlib import Path
sys.dont_write_bytecode=True
project=Path(__file__).resolve().parents[1]
temp=tempfile.TemporaryDirectory()
os.environ['TODO_DB_PATH']=str(Path(temp.name)/'ui.db')
sys.path.insert(0,str(project/'todo'))
from app import ToDoApp
from database import connect
from services.security import current_user
from services.inventory import apply_stock_movement
from screens.products import ProductEditor
from tkinter import messagebox
def unexpected_dialog(title,message,**kwargs):
 raise AssertionError(f'{title}: {message}')
messagebox.showerror=unexpected_dialog
messagebox.showwarning=unexpected_dialog
app=ToDoApp()
app.withdraw()
app.login_pin.set('1234');app.login();app.withdraw();app.update_idletasks()
app.show('sale');app.update_idletasks()
with connect() as c:
 pid=c.execute("INSERT INTO products(name,sale_price_cents) VALUES('UI Smoke',1200)").lastrowid
 apply_stock_movement(c,pid,10,'OPENING',note='UI test')
 c.execute("INSERT INTO product_barcodes(product_id,barcode) VALUES(?,'123456')",(pid,))
sale=app.sale_frame
sale.query.set('123456');sale.confirm_search();app.update_idletasks()
assert len(sale.cart)==1
assert sale.totals()==(1200,1200)
sale.change(1);assert sale.cart[0]['qty']==2
for key in ['home','products','cash','stock','purchases','returns','journal','settings','sale']:
 app.show(key);app.update_idletasks()
assert app.sale_frame.cart[0]['qty']==2
editor=ProductEditor(app,product_id=pid)
editor.withdraw();editor.update_idletasks()
assert str(editor.e_stock.cget('state'))!='disabled'
editor.stock.set('15');editor.save();app.update_idletasks()
with connect() as c:
 assert c.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0]==15
 row=c.execute('SELECT * FROM stock_movements ORDER BY id DESC LIMIT 1').fetchone()
 assert row['old_qty']==10 and row['stock_after']==15 and row['user_id']==app.user['id']
editor=ProductEditor(app)
editor.withdraw();editor.name.set('Photo only');editor.sell.set('7.50');editor.cat.set('New family')
editor.offer_rows[0][0].set('3');editor.offer_rows[0][1].set('20');editor.offer_rows[0][2].set('Lot')
editor.save();app.update_idletasks()
with connect() as c:
 photo=c.execute("SELECT id FROM products WHERE name='Photo only'").fetchone()[0]
 assert not c.execute('SELECT 1 FROM product_barcodes WHERE product_id=?',(photo,)).fetchone()
sale.render_products();assert 'New family' in sale.categories
sale.add_product(photo);assert len(sale.cart)==2
sale.add_product(photo);sale.add_product(photo)
assert sale.cart[-1]['qty']==3 and sale.totals()[0]==4400
sale.query.set('987654321999999');sale.confirm_search();app.update_idletasks()
import tkinter as tk
dialogs=[w for w in app.winfo_children() if isinstance(w,tk.Toplevel)]
unknown=next(w for w in dialogs if 'Produit inconnu' in w.title())
assert unknown.cget('bg')=='#DC2626'
app.tk.call(unknown.protocol('WM_DELETE_WINDOW'))
app.update_idletasks();assert len(sale.cart)==2 and sale.query.get()==''
sale.functions();app.update_idletasks()
for w in sale.winfo_children():
 if isinstance(w,tk.Toplevel):w.destroy()
from screens.payment import PaymentDialog
payment=PaymentDialog(sale,2200)
payment.amount.set('50');assert '28.00' in payment.change.cget('text')
payment.amount.set('20');payment.confirm();assert payment.result is None
payment.amount.set('50');payment.confirm();assert payment.result==('CASH',5000,False)
payment=PaymentDialog(sale,2200)
payment.choose_method('CARD');payment.confirm();assert payment.result==('CARD',2200,False)
from services.cash import open_session
open_session(app.user['id'],0)
def accept_payment():
 dialogs=[w for w in app.winfo_children() if isinstance(w,PaymentDialog)]
 assert len(dialogs)==1
 dialogs[0].set_amount(100);dialogs[0].confirm()
app.after(200,accept_payment)
sale.checkout();assert not sale.cart
with connect() as c:
 last=c.execute('SELECT total_cents,paid_cents,change_cents FROM sales ORDER BY id DESC LIMIT 1').fetchone()
 assert tuple(last)==(4400,10000,5600)
sale.scan_quantity.set('3');sale.add_product(photo)
assert sale.cart[-1]['qty']==3 and sale.scan_quantity.get()=='1'
app.destroy();temp.cleanup()
print('UI SMOKE PASSED: login, scan, quantity, navigation, all screens, direct stock edit with ledger')
