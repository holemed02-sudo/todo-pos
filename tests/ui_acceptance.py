"""Exercise real Tk controls against an isolated database, including geometry."""
import os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
temp=tempfile.TemporaryDirectory()
os.environ['TODO_DB_PATH']=str(Path(temp.name)/'ui.db')
from app import ToDoApp
from database import connect
from screens.products import ProductEditor
from screens.payment import PaymentDialog
from services.cash import open_session
from services.receipts import export_receipt_pdf

def fail(title,message,**kwargs):
    raise AssertionError(str(title)+': '+str(message))
def descendants(w):
    for child in w.winfo_children():
        yield child
        yield from descendants(child)
def button(w, label):
    return next(x for x in descendants(w) if x.winfo_class() in ('TButton','Button') and label in str(x.cget('text')))
def visible(w):
    app.update()
    assert w.winfo_viewable(), str(w)
    top=w.winfo_toplevel()
    assert w.winfo_rooty()+w.winfo_height() <= top.winfo_rooty()+top.winfo_height(), str(w.cget('text'))
    assert w.winfo_rootx()+w.winfo_width() <= top.winfo_rootx()+top.winfo_width(), str(w.cget('text'))

with patch('tkinter.messagebox.showerror',fail), patch('tkinter.messagebox.showwarning',fail), patch('tkinter.messagebox.showinfo',lambda *a,**k:None):
    app=ToDoApp()
    app.report_callback_exception=lambda t,v,tb: fail('Tk callback',v)
    app.login_pin.set('1234');app.login()
    app.geometry('1100x640');app.update()
    done=__import__('tkinter').BooleanVar(value=False)
    app.after(200,lambda:done.set(True));app.wait_variable(done)
    app.show('stock');app.update()
    button(app.current,'Articles').invoke()
    app.update()
    editor=ProductEditor(app)
    editor.name.set('TEST - Rice')
    editor.cat.set('Test groceries')
    editor.buy.set('2');editor.sell.set('3')
    editor.bar.set('TEST123')
    button(editor,'Enregistrer').invoke();app.update()
    with connect() as c:
        pid=c.execute("SELECT id FROM products WHERE name='TEST - Rice'").fetchone()[0]
        assert c.execute('SELECT category_id FROM products WHERE id=?',(pid,)).fetchone()[0]
    app.show('purchases');app.update()
    purchase=app.current
    purchase.supplier.set('TEST Supplier');purchase.invoice.set('TEST-001')
    purchase.prod.selection_set(purchase.prod.get_children()[0])
    with patch('tkinter.simpledialog.askfloat',side_effect=[5,2]):
        purchase.addline()
    confirm=button(purchase,'VALIDER');visible(confirm);confirm.invoke();app.update()
    with connect() as c:assert c.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0]==5
    open_session(app.user['id'],10000)
    app.show('sale');app.update()
    sale=app.current
    assert str(pid) in sale.products.get_children(), 'Products without images must be searchable'
    assert len(sale.card_inner.winfo_children())==0, 'Photo grid must exclude products without images'
    sale.query.set('TEST123');sale.confirm_search();sale.change(1)
    with patch('tkinter.simpledialog.askfloat',return_value=1):sale.discount()
    assert sale.totals()[1]==500
    for label in ['SOLDER avec','SOLDER sans','Fonctions']:visible(button(sale,label))
    def finish_payment():
        dialog=next(w for w in descendants(app) if isinstance(w,PaymentDialog))
        visible(dialog.confirm_button)
        dialog.amount.set('10.00')
        dialog.confirm_button.invoke()
    app.after(150,finish_payment)
    button(sale,'SOLDER avec').invoke();app.update()
    assert not sale.cart
    receipt=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    visible(button(receipt,'PDF'))
    with connect() as c:
        row=c.execute('SELECT * FROM sales').fetchone()
        assert row['total_cents']==500 and row['change_cents']==500
        assert c.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0]==3
    output=Path(os.environ.get('TODO_TEST_OUTPUT',str(Path(temp.name)/'receipt.pdf')))
    with patch('tkinter.filedialog.asksaveasfilename',return_value=str(output)):
        button(receipt,'PDF').invoke()
    assert output.read_bytes().startswith(b'%PDF-')
    receipt.destroy()
    app.show('journal');app.update()
    print('PASS: UI product/category -> purchase confirmation -> stock 5 -> scan/qty/discount -> visible SOLDER/VALIDER at 1100x640 -> sale 5 DH -> stock 3 -> receipt PDF -> journal',flush=True)
    if os.environ.get('TODO_REVIEW_UI'):
        app.show('sale')
        app.title('ToDo POS - isolated acceptance test')
        app.mainloop()
    else:app.destroy()
temp.cleanup()
