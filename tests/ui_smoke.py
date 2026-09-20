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
app.destroy();temp.cleanup()
print('UI SMOKE PASSED: login, scan, quantity, navigation, all screens, direct stock edit with ledger')
