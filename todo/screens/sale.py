import tkinter as tk
import math
from tkinter import ttk, messagebox, simpledialog, filedialog
from decimal import Decimal
from database import connect, get_setting
from services.catalog import search_products, scan_barcode, list_categories
from services.pricing import resolve_unit_price, line_total
from services.sales import complete_sale, hold_sale, list_held, resume_held
from services.cash import get_open_session
from services.money import fmt, to_cents, allocate
from services.images import abs_image
from services.receipts import build_receipt, print_receipt_windows, export_receipt_pdf
from screens.payment import PaymentDialog
try:
    from PIL import Image, ImageTk
except ImportError:
    Image=ImageTk=None


class SaleFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=16)
        self.app=app
        self.client_id=None
        self.cart=[]
        self.ticket_discount_cents=0
        self.held_id=None
        self.payment='CASH'
        self.category=None
        self.photo_offset=0
        self.photo_filter=None
        self.currency=get_setting('currency','DH')
        self.images={}
        self.search_job=None
        self.busy=False
        self.bindings=[]
        top=ttk.Frame(self)
        top.pack(fill='x',pady=(0,12))
        ttk.Label(top,text='Vente / البيع',style='Title.TLabel').pack(side='left')
        self.payment_label=ttk.Label(top,text='Paiement : CASH',style='Accent.TLabel')
        self.payment_label.pack(side='right')
        self.client_button=ttk.Button(top,text='F6 Client : passage',command=self.choose_client)
        self.client_button.pack(side='left',padx=18)
        searchbar=ttk.Frame(self,style='Card.TFrame',padding=12)
        searchbar.pack(fill='x',pady=(0,12))
        ttk.Label(searchbar,text='⌕  Scanner ou rechercher',style='Card.TLabel').pack(side='left',padx=(0,12))
        self.query=tk.StringVar()
        self.entry=ttk.Entry(searchbar,textvariable=self.query,font=('Segoe UI',16))
        self.entry.pack(side='left',fill='x',expand=True)
        ttk.Label(searchbar,text='Qté / الكمية').pack(side='left',padx=(12,4))
        self.scan_quantity=tk.StringVar(value='1')
        self.quantity_entry=ttk.Entry(searchbar,textvariable=self.scan_quantity,width=6,font=('Segoe UI',16))
        self.quantity_entry.pack(side='left')
        self.quantity_entry.bind('<Return>',lambda e:self.focus_search())
        self.entry.bind('<Return>',self.confirm_search)
        self.entry.bind('<KeyRelease>',self.schedule_search)
        self.entry.bind('<Down>',self.focus_catalog)
        body=ttk.Panedwindow(self,orient='horizontal')
        body.pack(fill='both',expand=True)
        right=ttk.Frame(body,style='Card.TFrame',padding=14);body.add(right,weight=4)
        left=ttk.Frame(body,padding=(12,0,0,0));body.add(left,weight=6)
        filters=ttk.Frame(left);filters.pack(fill='x',pady=(0,8))
        with connect() as conn:
            categories=conn.execute('SELECT id,name FROM categories WHERE active=1 ORDER BY sort_order,name').fetchall()
        self.categories={'Tous':None,**{r['name']:r['id'] for r in categories}}
        self.cat=tk.StringVar(value='Tous')
        self.family_canvas=tk.Canvas(filters,height=42,highlightthickness=0)
        self.family_canvas.pack(fill='x',expand=True)
        family_scroll=ttk.Scrollbar(filters,orient='horizontal',command=self.family_canvas.xview)
        family_scroll.pack(fill='x')
        self.family_canvas.configure(xscrollcommand=family_scroll.set)
        self.category_buttons=ttk.Frame(self.family_canvas)
        self.family_canvas.create_window((0,0),window=self.category_buttons,anchor='nw')
        self.category_buttons.bind('<Configure>',lambda e:self.family_canvas.configure(scrollregion=self.family_canvas.bbox('all')))
        self.catalog_tabs=ttk.Notebook(left)
        self.list_page=ttk.Frame(self.catalog_tabs);self.photo_page=ttk.Frame(self.catalog_tabs)
        self.catalog_tabs.add(self.photo_page,text='Photos / بيع بدون باركود');self.catalog_tabs.add(self.list_page,text='Liste')
        self.catalog_tabs.pack(fill='both',expand=True)
        self.products=ttk.Treeview(self.list_page,columns=('price','stock'),show='tree headings',selectmode='browse',style='Catalog.Treeview')
        self.products.heading('#0',text='PRODUIT');self.products.column('#0',width=240,minwidth=160)
        for key,label in [('price','PRIX'),('stock','STOCK')]:
            self.products.heading(key,text=label);self.products.column(key,width=85,stretch=False,anchor='e')
        self.products.pack(fill='both',expand=True)
        photo_nav=ttk.Frame(self.photo_page);photo_nav.pack(side='bottom',fill='x')
        ttk.Button(photo_nav,text='Précédent',command=lambda:self.photo_next(-1)).pack(side='left')
        self.photo_more=ttk.Button(photo_nav,text='Suivant',command=lambda:self.photo_next(1));self.photo_more.pack(side='right')
        self.card_canvas=tk.Canvas(self.photo_page,background='#F6F7FB',highlightthickness=0)
        self.card_scroll=ttk.Scrollbar(self.photo_page,orient='vertical',command=self.card_canvas.yview)
        self.card_inner=ttk.Frame(self.card_canvas)
        self.card_inner.bind('<Configure>',lambda e:self.card_canvas.configure(scrollregion=self.card_canvas.bbox('all')))
        self.card_canvas.create_window((0,0),window=self.card_inner,anchor='nw')
        self.card_canvas.configure(yscrollcommand=self.card_scroll.set)
        self.card_canvas.bind('<Configure>',self.layout_cards)
        self.card_canvas.pack(side='left',fill='both',expand=True);self.card_scroll.pack(side='right',fill='y')
        self.products.bind('<Double-1>',self.add_selected_product)
        self.products.bind('<Return>',self.add_selected_product)
        ttk.Button(left,text='Ajouter le produit sélectionné  ↵',command=self.add_selected_product).pack(fill='x',pady=(8,0))
        checkout_area=ttk.Frame(right,style='Card.TFrame')
        checkout_area.pack(side='bottom',fill='x')
        actions=ttk.Frame(checkout_area,style='Card.TFrame');actions.pack(fill='x',pady=8)
        ttk.Button(checkout_area,text='Fonctions / الوظائف',command=self.functions).pack(fill='x',pady=4)
        for label,command in [('−',lambda:self.change(-1)),('+',lambda:self.change(1)),('Qté F8',self.set_qty),('Remise ligne',self.line_discount),('Suppr.',self.remove)]:
            ttk.Button(actions,text=label,command=command).pack(side='left',expand=True,fill='x',padx=2)
        self.subtotal_label=ttk.Label(checkout_area,text='',style='Card.TLabel');self.subtotal_label.pack(anchor='e')
        self.total_label=ttk.Label(checkout_area,text='',style='Total.TLabel');self.total_label.pack(anchor='e',pady=8)
        ttk.Button(checkout_area,text='SOLDER avec ticket  F5',style='Primary.TButton',command=lambda:self.checkout(True)).pack(fill='x',ipady=8,pady=(2,2))
        ttk.Button(checkout_area,text='SOLDER sans ticket',command=lambda:self.checkout(False)).pack(fill='x',ipady=6)
        ttk.Label(right,text='Ticket en cours',style='CardTitle.TLabel').pack(anchor='w',pady=(0,8))
        self.ticket=ttk.Treeview(right,columns=('qty','price','discount','total'),show='tree headings',selectmode='browse',style='Cart.Treeview')
        self.ticket.heading('#0',text='ARTICLE');self.ticket.column('#0',width=170,minwidth=100)
        for key,label,width in [('qty','QTÉ',55),('price','P.U.',70),('discount','REMISE',75),('total','NET',85)]:
            self.ticket.heading(key,text=label);self.ticket.column(key,width=width,minwidth=40,anchor='e')
        self.ticket.tag_configure('offer',background='#DCFCE7',foreground='#166534')
        self.ticket.pack(fill='both',expand=True)
        self.ticket.bind('<Delete>',lambda e:self.remove())
        footer=ttk.Frame(self);footer.pack(fill='x',pady=(12,0))
        for label,command in [('F2 Espèces',lambda:self.set_payment('CASH')),('F3 Carte',lambda:self.set_payment('CARD')),('F4 Attente',self.hold),('Liste attente',self.show_held),('F7 Remise',self.discount),('ESC Annuler',self.cancel)]:
            ttk.Button(footer,text=label,command=command).pack(side='left',padx=3)
        self.status=ttk.Label(self,text='Scanner prêt · Ctrl+F Rechercher · Entrée Ajouter')
        self.status.pack(anchor='w',pady=(8,0))
        commands={'<F2>':lambda:self.set_payment('CASH'),'<F3>':lambda:self.set_payment('CARD'),'<F4>':self.hold,'<F5>':lambda:self.checkout(True),'<F6>':self.choose_client,'<F7>':self.discount,'<F8>':self.set_qty,'<Escape>':self.cancel,'<Control-f>':self.focus_search}
        for sequence,command in commands.items():
            binding=app.bind(sequence,lambda e,c=command:self.shortcut(e,c),add='+')
            self.bindings.append((sequence,binding))
        self.render_products();self.refresh();self.after_idle(self.focus_search)

    def shortcut(self,event,command):
        if self.winfo_viewable() and event.widget.winfo_toplevel()==self.app:
            command();return 'break'

    def destroy(self):
        if self.search_job:
            self.after_cancel(self.search_job)
        for sequence,binding in self.bindings:
            self.app.unbind(sequence,binding)
        super().destroy()

    def focus_search(self):
        self.entry.focus_set();self.entry.selection_range(0,'end')

    def focus_catalog(self,event=None):
        self.catalog_tabs.select(self.list_page)
        rows=self.products.get_children()
        if rows:
            self.products.focus_set();self.products.selection_set(rows[0]);self.products.focus(rows[0])
        return 'break'

    def layout_cards(self,event=None):
        columns=max(1,self.card_canvas.winfo_width()//167)
        for index,card in enumerate(self.card_inner.winfo_children()):
            card.grid_configure(row=index//columns,column=index%columns)

    def functions(self):
        window=tk.Toplevel(self);window.title('Fonctions / الوظائف')
        window.transient(self.winfo_toplevel());window.grab_set()
        def run(command):
            window.destroy();command()
        commands=[('Duplicata / نسخة التيكي',self.duplicate_receipt),
                  ('Divers / منتوج أو مبلغ إضافي',self.add_misc),
                  ('Modifier quantité / الكمية',self.set_qty),
                  ('Modifier prix / الثمن',self.set_price),
                  ('Remise ticket / تخفيض',self.discount),
                  ('Remise ligne',self.line_discount),
                  ('Supprimer ligne / حذف السطر',self.remove),
                  ('PRIX 1 / الثمن العادي',self.restore_price),
                  ('Compter la caisse / الصندوق',self.cash_tools),
                  ('Clôture / إغلاق الصندوق',lambda:self.cash_tools('close')),
                  ('Dépenses / المصاريف',lambda:self.cash_tools('expense')),
                  ('Rapport / التقارير',lambda:self.app.show('journal')),
                  ('Raccourcis / الاختصارات',self.show_shortcuts),
                  ('Calculatrice / الحاسبة',self.calculator),
                  ('Lock / قفل الصندوق',self.app.lock_cashier),
                  ('Thème / الألوان',self.app.choose_theme),
                  ('Tiroir / درج النقود',self.open_drawer),
                  ('Attente / انتظار',self.hold),
                  ("Liste d’attente / المعلقات",self.show_held)]
        for index,(label,command) in enumerate(commands):
            ttk.Button(window,text=label,command=lambda c=command:run(c)).grid(row=index//3,column=index%3,padx=6,pady=6,ipadx=4,ipady=10,sticky='ew')
        ttk.Button(window,text='Fermer / رجوع',command=lambda:run(self.focus_search)).grid(row=(len(commands)+2)//3,column=0,columnspan=3,pady=12)
        window.bind('<Escape>',lambda e:run(self.focus_search))

    def restore_price(self):
        index=self.selected()
        if index is None:return
        line=self.cart[index]
        if line.get('is_misc'):return
        with connect() as conn:
            product=conn.execute('SELECT sale_price_cents FROM products WHERE id=?',(line['product_id'],)).fetchone()
        line['unit_price_cents']=str(product['sale_price_cents'])
        line['manual_unit_price']=True
        line['discount_cents']=min(line.get('discount_cents',0),line_total(line['unit_price_cents'],line['qty']))
        self.ticket_discount_cents=min(self.ticket_discount_cents,self.totals()[0])
        self.refresh(index);self.focus_search()

    def calculator(self):
        from screens.cashier_tools import Calculator
        Calculator(self)

    def open_drawer(self):
        from services.printers import open_drawer
        try:
            open_drawer();self.status.config(text='Commande envoyée au tiroir.')
        except Exception as error:messagebox.showerror('Tiroir',str(error),parent=self)

    def add_misc(self):
        from services.misc import misc_line
        name=simpledialog.askstring('Divers','Libellé / اسم المنتوج أو المبلغ:',parent=self)
        if name is None:return
        price=simpledialog.askstring('Divers','Prix unitaire (DH) / الثمن:',parent=self)
        if price is None:return
        quantity=simpledialog.askstring('Divers','Quantité / الكمية:',initialvalue='1',parent=self)
        if quantity is None:return
        try:
            self.cart.append(misc_line(name,price,quantity));self.refresh(len(self.cart)-1)
        except (ValueError,ArithmeticError) as error:messagebox.showerror('Divers',str(error),parent=self)
        self.focus_search()

    def cash_tools(self,action=None):
        from screens.cashdesk import CashFrame
        window=tk.Toplevel(self);window.title('Caisse / الصندوق')
        window.transient(self.app);window.grab_set()
        frame=CashFrame(window,self.app);frame.pack(fill='both',expand=True)
        ttk.Button(window,text='Retour à la vente',command=window.destroy).pack(pady=8)
        window.bind('<Escape>',lambda e:window.destroy())
        if action in ('close','expense'):
            window.after_idle(getattr(frame,action))

    def show_shortcuts(self):
        messagebox.showinfo('Raccourcis',
            'F2 : Espèces\nF3 : Carte\nF4 : Attente\nF5 : Solder\nF7 : Remise\nF8 : Quantité\nCtrl+F : Recherche\nEntrée : Ajouter / Confirmer\nSuppr : Supprimer ligne\nÉchap : Annuler',parent=self)

    def duplicate_receipt(self):
        with connect() as conn:
            rows=conn.execute('SELECT id,sale_no,total_cents,created_at FROM sales ORDER BY id DESC LIMIT 100').fetchall()
        window=tk.Toplevel(self);window.title('Duplicata — choisir un ticket')
        window.transient(self.winfo_toplevel());window.grab_set()
        tree=ttk.Treeview(window,columns=('number','date','total'),show='headings',height=12)
        for key,label in [('number','Ticket'),('date','Date'),('total','Total')]:tree.heading(key,text=label)
        tree.pack(fill='both',expand=True,padx=12,pady=12)
        for row in rows:tree.insert('','end',iid=str(row['id']),values=(row['sale_no'],row['created_at'],fmt(row['total_cents'],self.currency)))
        def choose(event=None):
            if not tree.selection():return
            sid=int(tree.selection()[0]);row=next(r for r in rows if r['id']==sid)
            window.destroy();self.show_receipt(row)
        ttk.Button(window,text='Voir / Imprimer',command=choose).pack(pady=10)
        tree.bind('<Return>',choose);tree.bind('<Double-1>',choose)
        window.bind('<Escape>',lambda e:window.destroy())
        if rows:tree.selection_set(str(rows[0]['id']));tree.focus_set()

    def schedule_search(self,event=None):
        if event and event.keysym in ('Return','Down','Up','Escape'):return
        if self.search_job:self.after_cancel(self.search_job)
        self.search_job=self.after(120,self.render_products)

    def thumbnail(self,row,size=40):
        key=(row['id'],row['image_path'],size)
        if key not in self.images and Image:
            path=abs_image(row['image_path']) if row['image_path'] else None
            if path:
                try:
                    with Image.open(path) as source:
                        im=source.copy();im.thumbnail((size,size))
                    self.images[key]=ImageTk.PhotoImage(im,master=self)
                except (OSError,ValueError):pass
        return self.images.get(key,'')

    def photo_next(self,direction):
        self.photo_offset=max(0,self.photo_offset+direction*60);self.render_products()
        self.card_canvas.yview_moveto(0)

    def render_products(self):
        self.search_job=None
        with connect() as conn:
            categories=conn.execute('SELECT id,name FROM categories WHERE active=1 ORDER BY sort_order,name').fetchall()
        self.categories={'Tous':None,**{r['name']:r['id'] for r in categories}}
        if self.cat.get() not in self.categories:self.cat.set('Tous')
        for child in self.category_buttons.winfo_children(): child.destroy()
        category_rows=list_categories()
        # Default colours for "Tous" and fallback
        all_colors = {'Tous': ('#1e293b', '#ffffff')}
        for cat_row in category_rows:
            bg = cat_row['color'] or '#2563EB'
            # compute a readable text colour (white or black) based on luminance
            try:
                r2,g2,b2 = int(bg[1:3],16), int(bg[3:5],16), int(bg[5:7],16)
                lum = (0.299*r2 + 0.587*g2 + 0.114*b2)
                fg = '#ffffff' if lum < 140 else '#1e293b'
            except Exception:
                fg = '#ffffff'
            all_colors[cat_row['name']] = (bg, fg)
        active = self.cat.get()
        for name, (bg, fg) in all_colors.items():
            if name not in self.categories:
                continue
            icon = ''
            for cat_row in category_rows:
                if cat_row['name'] == name:
                    icon = (cat_row['icon'] + ' ') if cat_row['icon'] else ''
                    break
            label = icon + name
            is_active = (name == active)
            border  = '#f59e0b' if is_active else bg
            relief  = 'solid'   if is_active else 'flat'
            btn = tk.Button(
                self.category_buttons,
                text=label,
                bg=bg, fg=fg,
                activebackground=bg, activeforeground=fg,
                relief=relief, bd=2 if is_active else 0,
                highlightbackground=border,
                font=('Segoe UI', 9, 'bold' if is_active else 'normal'),
                padx=10, pady=6, cursor='hand2',
                command=lambda n=name: self.choose_category(n)
            )
            btn.pack(side='left', padx=3, pady=2)
        rows=search_products(self.query.get(),self.categories[self.cat.get()])
        self.products.delete(*self.products.get_children())
        for child in self.card_inner.winfo_children():child.destroy()
        self.product_rows={str(r['id']):r for r in rows}
        columns=max(1,self.card_canvas.winfo_width()//167)
        for row in rows:
            self.products.insert('', 'end',iid=str(row['id']),text=row['name'],image=self.thumbnail(row),values=(fmt(row['sale_price_cents'],''),f"{row['stock_qty']:g}"))
        photo_filter=(self.query.get(),self.categories[self.cat.get()])
        if photo_filter!=self.photo_filter:self.photo_offset=0;self.photo_filter=photo_filter
        photo_rows=search_products(*photo_filter,limit=61,images_only=True,offset=self.photo_offset)
        self.photo_more.configure(state='normal' if len(photo_rows)>60 else 'disabled')
        photo_rows=photo_rows[:60]
        for index,row in enumerate(photo_rows):
            card=tk.Frame(self.card_inner,bg='white',bd=1,relief='solid',width=155,height=150,cursor='hand2')
            card.grid(row=index//columns,column=index%columns,padx=6,pady=6);card.grid_propagate(False)
            thumb=self.thumbnail(row,90)
            picture=tk.Label(card,image=thumb or '',text='' if thumb else '📦',bg='white',font=('Segoe UI',26));picture.pack(fill='both',expand=True)
            tk.Label(card,text=row['name'],bg='white',font=('Segoe UI',9,'bold'),wraplength=140).pack()
            tk.Label(card,text=fmt(row['sale_price_cents'],self.currency),bg='white',fg='#2563EB').pack()
            for widget in [card,*card.winfo_children()]:
                widget.bind('<Button-1>',lambda e,pid=row['id']:self.add_product(pid))

    def choose_category(self,name):
        self.cat.set(name)
        self.render_products()

    def confirm_search(self,event=None):
        if self.search_job:
            self.after_cancel(self.search_job);self.search_job=None
        code=self.query.get().strip()
        if not code:return 'break'
        rows=scan_barcode(code)
        if len(rows)==1:
            r=rows[0];self.add_product(r['id'],r['barcode_id'],r['qty_multiplier'],r['barcode'])
        elif len(rows)>1:self.pick_barcode(rows)
        else:
            rows=search_products(code,limit=2)
            if len(rows)==1:self.add_product(rows[0]['id'])
            else:
                self.render_products();self.focus_catalog()
                self.status.config(text='Choisissez un produit puis Entrée.' if rows else 'Aucun produit trouvé.')
                if not rows:self.unknown_product(code)
        return 'break'

    def unknown_product(self,code):
        from services.security import require_admin
        from screens.products import ProductEditor
        window=tk.Toplevel(self)
        window.title('منتوج غير معروف — Produit inconnu')
        window.configure(bg='#DC2626');window.geometry('640x340')
        window.transient(self.winfo_toplevel());window.grab_set()
        self.bell()
        tk.Label(window,text='!  منتوج غير معروف',bg='#DC2626',fg='white',font=('Segoe UI',30,'bold')).pack(pady=(28,8))
        tk.Label(window,text='Produit inconnu',bg='#DC2626',fg='white',font=('Segoe UI',18)).pack()
        tk.Label(window,text=code,bg='#DC2626',fg='white',font=('Segoe UI',20),wraplength=580).pack(pady=18)
        def close():
            window.destroy();self.query.set('');self.render_products();self.after_idle(self.focus_search)
        def create():
            try:
                with connect() as conn:require_admin(conn)
            except PermissionError as error:
                messagebox.showerror('ToDo',str(error),parent=window);return
            window.destroy()
            editor=ProductEditor(self,on_saved=self.render_products)
            editor.bar.set(code)
            self.wait_window(editor)
            self.query.set('');self.render_products();self.focus_search()
        buttons=tk.Frame(window,bg='#DC2626');buttons.pack(pady=12)
        ttk.Button(buttons,text='إضافة المنتوج / Ajouter',command=create).pack(side='left',padx=8,ipady=10)
        back=ttk.Button(buttons,text='رجوع للبيع / Retour',command=close)
        back.pack(side='left',padx=8,ipady=10);back.focus_set()
        window.protocol('WM_DELETE_WINDOW',close)
        window.bind('<Escape>',lambda e:close())
        window.bind('<Return>',lambda e:close())

    def pick_barcode(self,rows):
        w=tk.Toplevel(self);w.title('Choisir le produit / اختار المنتوج');w.transient(self);w.grab_set()
        tree=ttk.Treeview(w,columns=('pack','price'),show='tree headings',height=8)
        tree.heading('#0',text='Produit');tree.heading('pack',text='Unités');tree.heading('price',text='Prix sélection')
        tree.pack(fill='both',expand=True,padx=12,pady=12)
        with connect() as conn:
            for i,r in enumerate(rows):
                price=resolve_unit_price(r['id'],r['qty_multiplier'],r['barcode_id'],conn)
                tree.insert('','end',iid=str(i),text=r['name'],values=(r['qty_multiplier'],fmt(line_total(price,r['qty_multiplier']))))
        def choose(event=None):
            if not tree.selection():return
            r=rows[int(tree.selection()[0])];w.destroy()
            self.add_product(r['id'],r['barcode_id'],r['qty_multiplier'],r['barcode'])
        tree.bind('<Return>',choose);tree.bind('<Double-1>',choose)
        ttk.Button(w,text='Choisir',command=choose).pack(pady=8)
        tree.selection_set('0');tree.focus('0');tree.focus_set()

    def add_selected_product(self,event=None):
        if self.products.selection():self.add_product(int(self.products.selection()[0]))
        return 'break'

    def add_product(self,pid,barcode_id=None,qty=1,barcode=''):
        try:
            qty=float(qty)*float(self.scan_quantity.get().replace(',','.'))
            if not math.isfinite(float(qty)) or float(qty)<=0:
                raise ValueError('Quantité invalide')
            with connect() as conn:
                p=conn.execute('SELECT * FROM products WHERE id=? AND active=1',(pid,)).fetchone()
                if not p:raise ValueError('Article introuvable')
                if not p['allow_fraction'] and not float(qty).is_integer():raise ValueError('Quantité entière requise')
                index=next((i for i,x in enumerate(self.cart) if x['product_id']==pid and x.get('barcode_id')==barcode_id),None)
                new_qty=float(qty)+(self.cart[index]['qty'] if index is not None else 0)
                unit=resolve_unit_price(pid,new_qty,barcode_id,conn)
                if index is not None and self.cart[index].get('manual_unit_price'):
                    unit=Decimal(self.cart[index]['unit_price_cents'])
                barcode_row=conn.execute('SELECT qty_multiplier,price_override_cents FROM product_barcodes WHERE id=?',(barcode_id,)).fetchone() if barcode_id else None
                step=barcode_row['qty_multiplier'] if barcode_row and barcode_row['price_override_cents'] is not None else 1
                if index is None:
                    self.cart.append(dict(product_id=pid,name=p['name'],qty=new_qty,barcode_id=barcode_id,barcode=barcode,unit_price_cents=str(unit),qty_multiplier=step,base_price_cents=p['sale_price_cents'],image_path=p['image_path'],allow_fraction=p['allow_fraction'],discount_cents=0))
                    index=len(self.cart)-1
                else:self.cart[index].update(qty=new_qty,unit_price_cents=str(unit))
            self.query.set('');self.scan_quantity.set('1');self.refresh(index);self.focus_search()
            self.status.config(text=f"Ajouté : {p['name']}")
        except Exception as e:messagebox.showerror('ToDo',str(e),parent=self)

    def selected(self):
        selected=self.ticket.selection()
        return int(selected[0]) if selected else (len(self.cart)-1 if self.cart else None)

    def totals(self):
        sub=sum(line_total(x['unit_price_cents'],x['qty'])-int(x.get('discount_cents',0)) for x in self.cart)
        return sub,max(0,sub-self.ticket_discount_cents)

    def refresh(self,index=None):
        if index is None:index=self.selected()
        self.ticket.delete(*self.ticket.get_children())
        sub,total=self.totals()
        weights=[line_total(x['unit_price_cents'],x['qty'])-int(x.get('discount_cents',0)) for x in self.cart]
        nets=allocate(total,weights)
        for i,(x,net) in enumerate(zip(self.cart,nets)):
            gross=line_total(x['unit_price_cents'],x['qty'])
            offer=Decimal(str(x['unit_price_cents']))<x.get('base_price_cents',0) or gross>net
            thumb=self.thumbnail({'id':x['product_id'],'image_path':x.get('image_path','')})
            step=x.get('qty_multiplier',1)
            name=x['name']+(f' · pack ×{step:g}' if step!=1 else '')
            quantity=f"{x['qty']/step:g}p" if step!=1 else f"{x['qty']:g}"
            price=fmt(line_total(x['unit_price_cents'],step),'')
            self.ticket.insert('','end',iid=str(i),text=name,image=thumb,values=(quantity,price,fmt(gross-net,''),fmt(net,'')),tags=('offer',) if offer else ())
        if self.cart:
            chosen=str(min(index if index is not None else len(self.cart)-1,len(self.cart)-1))
            self.ticket.selection_set(chosen);self.ticket.see(chosen)
        self.subtotal_label.config(text=f'Sous-total {fmt(sub,self.currency)}  ·  Remise ticket {fmt(self.ticket_discount_cents,self.currency)}')
        self.total_label.config(text=fmt(total,self.currency))
        self.app.update_customer_display(self.cart,total)

    def update_quantity(self,index,qty):
        if not math.isfinite(float(qty)):
            messagebox.showerror('ToDo','Quantité invalide.',parent=self);return
        x=self.cart[index]
        if qty<=0:self.cart.pop(index)
        else:
            if not x.get('allow_fraction',False) and not float(qty).is_integer():
                messagebox.showerror('ToDo','Quantité entière requise.',parent=self);return
            try:unit=Decimal(x['unit_price_cents']) if x.get('manual_unit_price') else resolve_unit_price(x['product_id'],qty,x.get('barcode_id'))
            except ValueError as e:
                messagebox.showerror('ToDo',str(e),parent=self);return
            x.update(qty=qty,unit_price_cents=str(unit))
            x['discount_cents']=min(x.get('discount_cents',0),line_total(unit,qty))
        self.ticket_discount_cents=min(self.ticket_discount_cents,self.totals()[0])
        self.refresh(index);self.focus_search()

    def change(self,delta):
        index=self.selected()
        if index is not None:self.update_quantity(index,self.cart[index]['qty']+delta*self.cart[index].get('qty_multiplier',1))

    def set_qty(self):
        index=self.selected()
        if index is None:return
        step=self.cart[index].get('qty_multiplier',1)
        qty=simpledialog.askfloat('Quantité','Nombre de packs:' if step!=1 else 'Nouvelle quantité:',initialvalue=self.cart[index]['qty']/step,parent=self,minvalue=0.001)
        if qty is not None:self.update_quantity(index,qty*step)
        self.focus_search()

    def remove(self):
        index=self.selected()
        if index is not None:self.update_quantity(index,0)

    def discount(self):
        if not self.cart:return
        amount=simpledialog.askfloat('Remise ticket','Montant de la remise:',parent=self,minvalue=0,maxvalue=self.totals()[0]/100)
        if amount is not None:self.ticket_discount_cents=to_cents(amount);self.refresh()
        self.focus_search()

    def line_discount(self):
        index=self.selected()
        if index is None:return
        x=self.cart[index]
        amount=simpledialog.askfloat('Remise ligne','Montant de la remise:',parent=self,minvalue=0,maxvalue=line_total(x['unit_price_cents'],x['qty'])/100)
        if amount is not None:
            x['discount_cents']=to_cents(amount)
            self.ticket_discount_cents=min(self.ticket_discount_cents,self.totals()[0]);self.refresh(index)
        self.focus_search()

    def set_price(self):
        index=self.selected()
        if index is None:return
        line=self.cart[index]
        if line.get('qty_multiplier',1)!=1:
            messagebox.showinfo('ToDo','Pour un pack, utilisez la remise ligne.',parent=self);return
        amount=simpledialog.askstring('Modifier prix',f"{line['name']}\nNouveau prix unitaire (DH) :",initialvalue=f"{Decimal(line['unit_price_cents'])/100:.2f}",parent=self)
        if amount is None:return
        try:
            price=to_cents(amount)
            if price<0:raise ValueError('Prix invalide')
            line['unit_price_cents']=str(price)
            line['manual_unit_price']=True
            line['discount_cents']=min(line.get('discount_cents',0),line_total(price,line['qty']))
            self.ticket_discount_cents=min(self.ticket_discount_cents,self.totals()[0])
            self.refresh(index)
        except Exception as error:messagebox.showerror('ToDo',str(error),parent=self)
        self.focus_search()

    def choose_client(self):
        from services.clients import list_clients
        window=tk.Toplevel(self);window.title('Choisir client / الزبون');window.geometry('580x460')
        window.transient(self.app);window.grab_set()
        query=tk.StringVar();entry=ttk.Entry(window,textvariable=query);entry.pack(fill='x',padx=12,pady=12)
        buttons=ttk.Frame(window);buttons.pack(side='bottom',fill='x',padx=12,pady=12)
        tree=ttk.Treeview(window,columns=('name','phone'),show='headings')
        tree.heading('name',text='Client');tree.heading('phone',text='Téléphone');tree.pack(fill='both',expand=True,padx=12)
        def refresh(*args):
            tree.delete(*tree.get_children())
            for row in list_clients(query.get()):tree.insert('','end',iid=str(row['id']),values=(row['name'],row['phone']))
        def select(clear=False):
            if not clear and not tree.selection():return
            self.client_id=None if clear else int(tree.selection()[0])
            self.update_client_label();window.destroy();self.focus_search()
        ttk.Button(buttons,text='Choisir',command=select).pack(side='left')
        ttk.Button(buttons,text='Client de passage',command=lambda:select(True)).pack(side='left',padx=10)
        tree.bind('<Double-1>',lambda e:select());entry.bind('<KeyRelease>',refresh);refresh();entry.focus_set()

    def update_client_label(self):
        from services.clients import get_client
        name=get_client(self.client_id)['name'] if self.client_id is not None else 'passage'
        self.client_button.configure(text='F6 Client : '+name[:30])

    def set_payment(self,method):
        self.payment=method;self.payment_label.config(text='Paiement : '+method);self.focus_search()

    def clear(self):
        self.cart=[];self.ticket_discount_cents=0;self.held_id=None;self.client_id=None;self.payment='CASH';self.payment_label.config(text='Paiement : CASH');self.update_client_label();self.refresh();self.focus_search()

    def cancel(self):
        if self.cart and not messagebox.askyesno('Annuler','Vider le ticket en cours ? Un ticket en attente reste sauvegardé.',parent=self):return
        self.clear()

    def hold(self):
        if not self.cart:return
        label=simpledialog.askstring('Attente','Nom ou numéro du ticket:',parent=self)
        if label is None:return
        try:
            hold_sale(self.app.user['id'],self.cart,label,self.ticket_discount_cents,self.held_id,client_id=self.client_id)
            self.clear();self.status.config(text='Ticket et remise sauvegardés.')
        except Exception as e:messagebox.showerror('ToDo',str(e),parent=self)

    def show_held(self):
        if self.cart:
            messagebox.showinfo('ToDo','Mettez le ticket actuel en attente avant de reprendre un autre.',parent=self);return
        rows=list_held()
        if not rows:
            messagebox.showinfo('ToDo','Aucun ticket en attente.',parent=self);return
        w=tk.Toplevel(self);w.title('Tickets en attente');w.transient(self);w.grab_set()
        tree=ttk.Treeview(w,columns=('date','discount'),show='tree headings')
        tree.heading('#0',text='Ticket');tree.heading('date',text='Date');tree.heading('discount',text='Remise')
        tree.pack(fill='both',expand=True,padx=12,pady=12)
        for r in rows:tree.insert('','end',iid=str(r['id']),text=r['label'],values=(r['created_at'],fmt(r['discount_cents'])))
        def resume(event=None):
            if not tree.selection():return
            state=resume_held(int(tree.selection()[0]))
            self.cart=state['cart'];self.ticket_discount_cents=state['discount_cents'];self.held_id=state['held_id']
            self.client_id=state.get('client_id');self.update_client_label()
            self.refresh();w.destroy();self.focus_search()
        tree.bind('<Return>',resume);tree.bind('<Double-1>',resume)
        ttk.Button(w,text='Reprendre',command=resume).pack(pady=8)

    def checkout(self, print_ticket=True):
        if not self.cart or self.busy:return
        session=get_open_session()
        if not session:
            messagebox.showinfo('ToDo','Ouvrez la caisse avant de vendre.',parent=self);return
        self.busy=True
        try:
            total=self.totals()[1]
            from services.clients import get_client
            client_name=get_client(self.client_id)['name'] if self.client_id is not None else None
            dialog=PaymentDialog(self,total,self.currency,self.payment,client_name=client_name)
            mode=get_setting('print_mode','ask')
            dialog.print_ticket.set(print_ticket and mode=='always')
            self.wait_window(dialog)
            if dialog.result is None:return
            self.payment,paid,dialog_print=dialog.result
            self.payment_label.config(text='Paiement : '+self.payment)
            result=complete_sale(session['id'],self.app.user['id'],self.cart,self.payment,paid,self.ticket_discount_cents,self.held_id,client_id=self.client_id)
            # Clear immediately after commit, before receipt/UI work, to prevent a duplicate sale on display failure.
            self.clear()
            self.status.config(text=f"Dernière vente : {fmt(total,self.currency)} · Reçu : {fmt(paid,self.currency)} · Monnaie : {fmt(result['change_cents'],self.currency)} · {result['sale_no']}")
            try:
                if print_ticket:
                    self.show_receipt(result)
                if print_ticket and mode!='never' and (mode=='always' or dialog_print):print_receipt_windows(result['id'])
            except Exception as e:messagebox.showwarning('ToDo',f"Vente enregistrée : {result['sale_no']}\nTicket indisponible : {e}",parent=self)
            self.render_products()
        except Exception as e:messagebox.showerror('ToDo',str(e),parent=self)
        finally:self.busy=False;self.focus_search()

    def show_receipt(self,result):
        w=tk.Toplevel(self);w.title(result['sale_no']);w.geometry('450x560');w.transient(self)
        buttons=ttk.Frame(w);buttons.pack(side='bottom',fill='x')
        def save_pdf():
            path=filedialog.asksaveasfilename(parent=w,defaultextension='.pdf',filetypes=[('PDF','*.pdf')],initialfile=result['sale_no']+'.pdf')
            if path:export_receipt_pdf(result['id'],path)
        ttk.Button(buttons,text='PDF / حفظ الفاتورة',command=save_pdf).pack(side='left',padx=8,pady=8)
        text=tk.Text(w,font=('Consolas',11),padx=16,pady=16)
        text.pack(fill='both',expand=True);text.insert('1.0',build_receipt(result['id']));text.config(state='disabled')
        ttk.Button(buttons,text='Imprimer',command=lambda:print_receipt_windows(result['id'])).pack(side='left',padx=12,pady=12)
        ttk.Button(buttons,text='Fermer',command=w.destroy).pack(side='right',padx=12,pady=12)
        w.bind('<Escape>',lambda e:w.destroy())
