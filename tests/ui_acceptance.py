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
    with patch('screens.products.simpledialog.askstring',return_value='Test groceries'):
        editor.add_category()
    editor.buy.set('2');editor.sell.set('3')
    editor.bar.set('TEST123')
    button(editor,'Enregistrer').invoke();app.update()
    with connect() as c:
        pid=c.execute("SELECT id FROM products WHERE name='TEST - Rice'").fetchone()[0]
        assert c.execute('SELECT category_id FROM products WHERE id=?',(pid,)).fetchone()[0]
    app.show('purchases');app.update()
    purchase=app.current
    from screens.suppliers import SupplierEditor, SuppliersFrame
    button(purchase,'+').invoke();app.update()
    supplier_editor=next(w for w in descendants(app) if isinstance(w,SupplierEditor))
    supplier_editor.name.set('TEST Supplier');supplier_editor.phone.set('0600000000')
    button(supplier_editor,'Enregistrer').invoke();app.update()
    assert purchase.supplier_id is not None
    supplier_id=purchase.supplier_id
    purchase.invoice.set('TEST-001')
    purchase.prod.selection_set(purchase.prod.get_children()[0])
    with patch('tkinter.simpledialog.askfloat',side_effect=[5,2]):
        purchase.addline()
    confirm=button(purchase,'VALIDER');visible(confirm);confirm.invoke();app.update()
    with connect() as c:
        assert c.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0]==5
        assert c.execute('SELECT supplier_id FROM purchases').fetchone()[0]==supplier_id
    app.show('management');app.update()
    supplier_cards=[w for w in descendants(app.current) if w.winfo_class()=='Label' and w.cget('text')=='Fournisseurs']
    assert len(supplier_cards)==1
    supplier_cards[0].event_generate('<Button-1>');app.update()
    assert isinstance(app.current,SuppliersFrame)
    app.current.tree.selection_set(str(supplier_id))
    button(app.current,'Modifier').invoke();app.update()
    supplier_editor=next(w for w in descendants(app) if isinstance(w,SupplierEditor))
    supplier_editor.name.set('TEST Supplier updated');button(supplier_editor,'Enregistrer').invoke()
    button(app.current,'Réceptions du fournisseur').invoke();app.update()
    history=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    history_tree=next(w for w in descendants(history) if w.winfo_class()=='Treeview')
    assert len(history_tree.get_children())==1
    assert 'TEST-001' in history_tree.item(history_tree.get_children()[0],'values')
    history.destroy()
    open_session(app.user['id'],10000)
    app.show('sale');app.update()
    sale=app.current
    sale.entry.focus_set();app.update()
    button(app,'Clavier').invoke();app.update()
    from screens.virtual_keyboard import VirtualKeyboard
    assert VirtualKeyboard._instance and VirtualKeyboard._instance.winfo_exists()
    VirtualKeyboard._instance._close()
    assert str(pid) in sale.products.get_children(), 'Products without images must be searchable'
    # Photo-only products saved through the real editor receive a stable TODO-* internal barcode.
    photo_editor=ProductEditor(app)
    photo_editor.name.set('TEST Photo Internal')
    photo_editor.sell.set('4')
    photo_editor.img_rel='missing-test-image.jpg'
    button(photo_editor,'Enregistrer').invoke();app.update()
    with connect() as c:
        photo_internal_pid=c.execute("SELECT id FROM products WHERE name='TEST Photo Internal'").fetchone()[0]
        internal_barcode=c.execute("SELECT barcode FROM product_barcodes WHERE product_id=?",(photo_internal_pid,)).fetchone()[0]
        assert internal_barcode==f'TODO-{photo_internal_pid:08d}'
        c.execute("INSERT INTO products(name,sale_price_cents,active,image_path) VALUES('TEST Photo Regular',500,1,'missing-test-image-2.jpg')")
        photo_regular_pid=c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute("INSERT INTO product_barcodes(product_id,barcode,qty_multiplier) VALUES(?,?,1)",(photo_regular_pid,'REGULAR123'))
    sale.render_products();app.update()
    tactile_names=[w.cget('text') for w in descendants(sale.card_inner) if w.winfo_class()=='Label']
    assert 'TEST - Rice' not in tactile_names, 'Products without images must stay out of tactile grid'
    assert 'TEST Photo Internal' in tactile_names, 'Image-only products with TODO internal barcode must remain in tactile grid'
    assert 'TEST Photo Regular' not in tactile_names, 'Products with a real barcode must stay out of tactile grid'
    sale.query.set('TEST123');sale.handle_scan_input()
    assert sale.scan_submit_job is not None, 'Known barcode typing must schedule the 500 ms auto-submit'
    sale.confirm_search()
    assert sale.scan_submit_job is None, 'Scanner Enter must cancel pending auto-submit to prevent double lines'
    assert len(sale.cart)==1 and sale.cart[0]['qty']==1
    sale.change(1)
    # Invoke reference menu actions while preserving the current ticket.
    sale.functions();app.update()
    menu=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    for label in ['Duplicata','Modifier quantité','Modifier prix','Supprimer','Grille de prix','Clôture','Dépenses','Rapport','Raccourcis']:
        visible(button(menu,label))
    with patch('tkinter.simpledialog.askstring',return_value='4.00'):
        button(menu,'Modifier prix').invoke()
    assert sale.totals()[1]==800
    # End-to-end PRIX_1: grid price is selectable from the sale UI.
    with connect() as c:
        gid=c.execute("INSERT INTO price_grids(name,active) VALUES('TEST PRO',1)").lastrowid
        c.execute("INSERT INTO product_grid_prices(product_id,grid_id,unit_price_cents) VALUES(?,?,?)",(pid,gid,250))
    sale.restore_price()
    sale.cart[0].pop('manual_unit_price',None)
    sale.functions();app.update()
    menu=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    button(menu,'Grille de prix').invoke();app.update()
    grid_dialog=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    button(grid_dialog,'TEST PRO').invoke();app.update()
    assert sale.price_grid_id==gid
    assert sale.totals()[1]==500
    # Return to the normal grid so later acceptance scenarios are isolated.
    sale.price_grid_id=None;sale.price_grid_name=sale.tr('Normal','عادي')
    sale.cart[0].pop('manual_unit_price',None)
    sale.restore_price()
    assert sale.totals()[1]==600
    with patch('tkinter.simpledialog.askstring',return_value='Test held ticket'):
        sale.hold()
    assert not sale.cart
    sale.show_held();app.update()
    held=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    tree=next(w for w in descendants(held) if w.winfo_class()=='Treeview')
    tree.selection_set(tree.get_children()[0]);button(held,'Reprendre').invoke()
    assert sale.cart[0]['qty']==2
    saved=list(sale.cart)
    app.lock_cashier();app.update()
    lock=app.lock_window
    app.show('products');assert app.current is sale
    lock.pin.set('9999');lock.unlock();assert app.lock_window is lock
    lock.pin.set('1234');lock.unlock();assert app.lock_window is None
    assert sale.cart==saved
    sale.calculator();app.update()
    calc=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    calc.expression.set('12,5 * 2');button(calc,'=').invoke()
    assert calc.expression.get()=='25'
    button(calc,'Fermer').invoke()
    app.choose_theme();app.update()
    theme=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    button(theme,'Vert').invoke()
    from database import get_setting
    assert get_setting('theme')=='Vert' and app.theme_color=='#15803D'
    assert sale.cart==saved
    sale.add_misc();app.update()
    misc=next(w for w in descendants(app) if hasattr(w,'misc_price_var'))
    misc.misc_name_var.set('TEST supplement')
    misc.misc_price_var.set('2.50')
    misc.misc_qty_var.set('1')
    misc.misc_confirm.invoke();app.update()
    assert sale.cart[-1]['is_misc'] and sale.totals()[1]==850
    sale.remove();assert sale.totals()[1]==600
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
    assert sale.last_sale_snapshot and sale.ticket.get_children()
    # Checkout stays inline: no automatic receipt popup. Cashier focus returns
    # to the barcode/search field and the compact blue reminder shows the result.
    assert not any(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    assert sale.focus_get() is sale.entry
    reminder=sale.last_sale_summary.cget('text')
    assert 'PAYÉ' in reminder and 'RENDU' in reminder
    with connect() as c:
        row=dict(c.execute('SELECT * FROM sales').fetchone())
        assert row['total_cents']==500 and row['change_cents']==500
        assert c.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0]==3
    # Receipt/PDF remains available on demand, but is never forced after checkout.
    sale.show_receipt(row);app.update()
    receipt=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    visible(button(receipt,'PDF'))
    output=Path(os.environ.get('TODO_TEST_OUTPUT',str(Path(temp.name)/'receipt.pdf')))
    with patch('tkinter.filedialog.asksaveasfilename',return_value=str(output)):
        button(receipt,'PDF').invoke()
    assert output.read_bytes().startswith(b'%PDF-')
    receipt.destroy()
    # Logica-compatible behavior: completed ticket remains visible until the next article.
    sale.query.set('TEST123');sale.confirm_search();app.update()
    assert sale.cart and sale.last_sale_snapshot is None
    assert len(sale.ticket.get_children())==1
    sale.clear()
    sale.cash_tools();app.update()
    cash_window=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    with patch('tkinter.simpledialog.askstring',return_value='TEST expense'), patch('tkinter.simpledialog.askfloat',return_value=1):
        button(cash_window,'Dépense').invoke()
    with connect() as c:
        assert c.execute('SELECT amount_cents FROM expenses').fetchone()[0]==100
    # Closing uses the real denomination counter instead of askfloat.
    def finish_cash_count():
        counter=next(w for w in descendants(app) if w.winfo_class()=='Toplevel' and 'Comptage' in str(w.title()))
        for value,count in ((100,1),(2,2)):
            for _ in range(count):button(counter,f'+ {value:g} DH').invoke()
        button(counter,'Valider le comptage').invoke()
    app.after(150,finish_cash_count)
    button(cash_window,'Clôturer').invoke()
    with connect() as c:
        closing=c.execute('SELECT * FROM cash_sessions').fetchone()
        assert closing['status']=='CLOSED' and closing['actual_cash_cents']==10400 and closing['difference_cents']==0
    cash_window.destroy()
    app.show('journal');app.update()
    # Complete a customer credit sale and settlement through actual Tk controls.
    from screens.clients import ClientEditor, PaymentsWindow
    from services.clients import get_client
    from services.cash import close_session
    open_session(app.user['id'],0)
    app.show('clients');app.update()
    button(app.current,'Nouveau').invoke();app.update()
    customer_editor=next(w for w in descendants(app) if isinstance(w,ClientEditor))
    customer_editor.name.set('TEST credit customer')
    button(customer_editor,'Enregistrer').invoke();app.update()
    with connect() as c:cid=c.execute("SELECT id FROM clients WHERE name='TEST credit customer'").fetchone()[0]
    app.show('sale');app.update();sale=app.current
    button(sale,'F6 Client').invoke();app.update()
    picker=next(w for w in descendants(app) if w.winfo_class()=='Toplevel')
    customer_tree=next(w for w in descendants(picker) if w.winfo_class()=='Treeview')
    customer_tree.selection_set(str(cid));button(picker,'Choisir').invoke()
    assert sale.client_id==cid
    sale.query.set('TEST123');sale.confirm_search()
    def credit_payment():
        dialog=next(w for w in descendants(app) if isinstance(w,PaymentDialog))
        dialog.choose_method('CREDIT');dialog.amount.set('1.00');app.update()
        visible(dialog.confirm_button)
        assert not dialog.confirm_button.instate(['disabled'])
        dialog.confirm_button.invoke()
    app.after(150,credit_payment)
    button(sale,'SOLDER sans').invoke();app.update()
    assert get_client(cid)['balance_cents']==200 and sale.client_id is None
    app.show('clients');app.update()
    app.current.tree.selection_set(str(cid));button(app.current,'Règlements').invoke();app.update()
    payments=next(w for w in descendants(app) if isinstance(w,PaymentsWindow))
    with patch('tkinter.simpledialog.askstring',side_effect=['2.00','CASH','TEST settlement']):
        button(payments,'Ajouter un règlement').invoke()
    assert get_client(cid)['balance_cents']==0
    payments.destroy()
    assert close_session(__import__('services.cash',fromlist=['get_open_session']).get_open_session()['id'],300)[:2]==(300,0)
    app.show('settings');app.update()
    settings=app.current
    with patch('services.printers.installed_printers',return_value=['Receipt Test']):
        button(settings,'Actualiser imprimantes').invoke()
    assert 'Receipt Test' in settings.printer_choice['values']
    settings.printer.set('Receipt Test');settings.print_mode.set('never')
    settings.drawer_enabled.set(True);settings.drawer_pin.set('1')
    button(settings,'Enregistrer impression').invoke()
    assert get_setting('printer_name')=='Receipt Test'
    assert get_setting('drawer_enabled')=='1' and get_setting('drawer_pin')=='1'
    # New Logica-compatible switches must persist through the real Settings UI save path.
    settings.credit_enabled.set(False)
    settings.closure_enabled.set(False)
    settings.sans_ticket_enabled.set(False)
    settings.payment_window_enabled.set(False)
    settings.customer_enabled.set(False)
    button(settings,'Enregistrer').invoke();app.update()
    assert get_setting('credit_enabled')=='0'
    assert get_setting('closure_enabled')=='0'
    assert get_setting('sans_ticket_enabled')=='0'
    assert get_setting('payment_window_enabled')=='0'
    assert get_setting('customer_display_enabled')=='0'
    print('PASS: UI product/category -> purchase confirmation -> stock 5 -> scan/qty/discount -> visible SOLDER/VALIDER at 1100x640 -> sale 5 DH -> stock 3 -> receipt PDF -> journal',flush=True)
    if os.environ.get('TODO_REVIEW_UI'):
        app.show('sale')
        app.title('ToDo POS - isolated acceptance test')
        app.mainloop()
    else:app.destroy()
temp.cleanup()
