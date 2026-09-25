"""Actual Tk category persistence and statistics controls after integration."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
temp=tempfile.TemporaryDirectory();os.environ['TODO_DB_PATH']=str(Path(temp.name)/'ui.db')
from app import ToDoApp
from database import connect
from screens.products import ProductEditor
from screens.settings import CategoryEditor
from screens.statistics import StatisticsFrame
from services.catalog import get_product_categories
from services.cash import open_session
from services.sales import complete_sale,create_return

def fail(*args,**kwargs):raise AssertionError(str(args))
def descendants(w):
    for child in w.winfo_children():
        yield child;yield from descendants(child)
def button(w,label):
    return next(c for c in descendants(w) if c.winfo_class() in ('Button','TButton') and c.cget('text')==label)
with patch('tkinter.messagebox.showerror',fail):
    app=ToDoApp();app.report_callback_exception=lambda t,v,tb:fail(v)
    app.login_pin.set('1234');app.login();app.geometry('1100x640');app.update()
    with connect() as c:
        ids=[c.execute('INSERT INTO categories(name) VALUES(?)',(f'Family {i:02}',)).lastrowid for i in range(30)]
    editor=ProductEditor(app);editor.name.set('TEST multi family');editor.sell.set('15');editor.buy.set('8')
    editor.cat_vars[ids[0]][0].set(True);editor.cat_vars[ids[-1]][0].set(True)
    with patch('tkinter.simpledialog.askstring',return_value='Added inline'):button(editor,'+ Famille').invoke()
    assert editor.cat_vars[ids[0]][0].get() and editor.cat_vars[ids[-1]][0].get()
    button(editor,'Enregistrer').invoke();app.update()
    with connect() as c:
        pid=c.execute("SELECT id FROM products WHERE name='TEST multi family'").fetchone()[0]
        added=c.execute("SELECT id FROM categories WHERE name='Added inline'").fetchone()[0]
    assert set(get_product_categories(pid))=={ids[0],ids[-1],added}
    editor=ProductEditor(app,pid);app.update()
    assert {cid for cid,(v,_) in editor.cat_vars.items() if v.get()}=={ids[0],ids[-1],added}
    editor.cat_vars[ids[0]][0].set(False)
    with connect() as c:cat=dict(c.execute('SELECT * FROM categories WHERE id=?',(ids[-1],)).fetchone())
    editor.edit_category(cat);app.update()
    category=next(w for w in descendants(editor) if isinstance(w,CategoryEditor))
    category.name_var.set('Cats updated');category._pick('#16A34A');category.icon_var.set('🐟')
    button(category,'Enregistrer').invoke();app.update()
    assert editor.cat_vars[ids[-1]][0].get() and not editor.cat_vars[ids[0]][0].get()
    button(editor,'Enregistrer').invoke();app.update()
    assert set(get_product_categories(pid))=={ids[-1],added}
    app.show('sale');app.update()
    family=button(app.sale_frame,'🐟 Cats updated');assert family.cget('bg')=='#16A34A'
    family.invoke();app.update();assert app.sale_frame.cat.get()=='Cats updated'
    session=open_session(app.user['id'],0)
    sale=complete_sale(session,app.user['id'],[dict(product_id=pid,qty=2,unit_price_cents=1500)],'CASH',2500,discount_cents=500)
    with connect() as c:item=c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sale['id'],)).fetchone()[0]
    create_return(sale['id'],session,app.user['id'],[(item,1)])
    app.show('statistics');app.update();stats=app.current;assert isinstance(stats,StatisticsFrame)
    for key,btn in stats._period_btns.items():
        btn.invoke();app.update()
        assert sum(stats.evo_chart._values)==1250
        assert stats.top_chart._items[0][1]==1250
        assert stats.cat_chart._items[0][1]==1250
        assert stats.cashier_chart._items[0][1]==1250
    with connect() as c:c.execute("UPDATE sales SET created_at='2000-01-01 12:00:00'")
    stats.refresh();app.update();assert sum(stats.evo_chart._values)==-1250
    for _ in range(3):
        app.show('sale');app.update();app.show('statistics');app.update()
    app.destroy()
temp.cleanup()
print('PASS: 30 families, inline addition, multi-select save/reopen/remove, colour/icon editor, sale family button, 3 statistics periods, discounts/returns, negative chart, navigation')
