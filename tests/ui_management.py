"""Focused management UI regression; isolated data only."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
tmp=tempfile.TemporaryDirectory();os.environ['TODO_DB_PATH']=str(Path(tmp.name)/'ui.db')
from app import ToDoApp
from database import connect
from screens.management import GROUPS
from screens.inventory import InventaireFrame,SortiesFrame
from screens.supplier_payments import SupplierReglementFrame,SupplierCreditStateWindow
def fail(*args,**kwargs):raise AssertionError(str(args))
with patch('tkinter.messagebox.showerror',fail),patch('tkinter.messagebox.showinfo'):
 app=ToDoApp();app.report_callback_exception=lambda t,v,tb:fail(v)
 app.login_pin.set('1234');app.login();app.update()
 with connect() as c:
  a=c.execute("INSERT INTO products(name,stock_qty) VALUES('Apple',10)").lastrowid
  b=c.execute("INSERT INTO products(name,stock_qty) VALUES('Banana',10)").lastrowid
 routes={label:route for group in GROUPS for _,label,route,*rest in group}
 for label,cls in [('Inventaire',InventaireFrame),('Sorties',SortiesFrame),('Règlements fournisseurs',SupplierReglementFrame)]:
  app.show('management');app.current._activate(routes[label],label);app.update()
  assert isinstance(app.current,cls)
 app.show('inventory');frame=app.current
 for pid,count in [(a,7),(b,8)]:
  frame.tree.selection_set(str(pid))
  with patch('tkinter.simpledialog.askfloat',return_value=count):frame._edit_cell(None)
 frame.query.set('Apple');frame.refresh();frame.apply_all();app.update()
 with connect() as c:
  assert c.execute('SELECT stock_qty FROM products WHERE id=?',(a,)).fetchone()[0]==7
  assert c.execute('SELECT stock_qty FROM products WHERE id=?',(b,)).fetchone()[0]==8
 app.show('stock_exits');frame=app.current;frame.tree.selection_set(str(a))
 with patch('tkinter.simpledialog.askfloat',return_value=2),patch('tkinter.simpledialog.askstring',return_value=None):frame.add_exit()
 with connect() as c:assert c.execute('SELECT stock_qty FROM products WHERE id=?',(a,)).fetchone()[0]==7
 with patch('tkinter.simpledialog.askfloat',return_value=2),patch('tkinter.simpledialog.askstring',return_value='Casse TEST'):frame.add_exit()
 with connect() as c:assert c.execute('SELECT stock_qty FROM products WHERE id=?',(a,)).fetchone()[0]==5
 app.show('management');app.current._activate('supplier_credits','Crédits');app.update()
 assert any(isinstance(w,SupplierCreditStateWindow) for w in app.winfo_children())
 app.destroy()
tmp.cleanup()
print('PASS management navigation, filtered multi-product inventory, cancelled/confirmed stock exit, supplier credits')
