import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from database import connect, get_setting
from services.inventory import apply_stock_movement
from services.security import require_admin, audit
import math
from services.money import to_cents
from services.images import import_image, abs_image
from screens.common import labeled_entry
from services.catalog import list_categories, get_product_categories, set_product_categories
try:
    from PIL import Image,ImageTk
    PIL=True
except Exception:
    PIL=False

class ProductEditor(tk.Toplevel):
    def __init__(self,master,product_id=None,on_saved=None):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.pid=product_id; self.on_saved=on_saved
        self.loaded_stock=0
        self.img_source="";self.img_rel="";self.img_ref=None
        self.title('ToDo — '+self.tr('Article','المنتوج'));self.geometry("1100x900");self.resizable(True,True);self.transient(master)
        # Do not grab the whole application: a modal grab prevents the global
        # virtual keyboard (another Toplevel) from receiving mouse/touch events.
        # The editor remains transient, while its own embedded keyboard works
        # entirely inside this window.
        self.sku=tk.StringVar();self.alias=tk.StringVar();self.supplier_code=tk.StringVar();self.fraction=tk.BooleanVar();self.stock_note=tk.StringVar()
        self.bar=tk.StringVar();self.name=tk.StringVar();self.cat=tk.StringVar()
        self.barcode_rows=[]
        self.buy=tk.StringVar(value="0");self.sell=tk.StringVar(value="0");self.stock=tk.StringVar(value="0");self.alert=tk.StringVar(value="0")
        root=ttk.Frame(self,padding=15);root.pack(fill="both",expand=True)
        self._keyboard_target = None
        self.bind_all('<FocusIn>', self._remember_keyboard_target, add='+')
        left=ttk.Frame(root);left.pack(side="left",fill="both",expand=True,padx=(0,18))
        right=ttk.LabelFrame(root,text=self.tr('Image produit','صورة المنتوج'),padding=8);right.pack(side="right",fill="y")
        self.e_bar=labeled_entry(left,self.tr('CODE-BARRES','الباركود'),self.bar,0,bold=True)
        self.e_name=labeled_entry(left,self.tr('Article','المنتوج'),self.name,1)
        ttk.Label(left,text=self.tr('Familles','العائلات')).grid(row=2,column=0,sticky='nw',pady=4)
        cat_outer=ttk.Frame(left);cat_outer.grid(row=2,column=1,columnspan=2,sticky='ew',pady=4)
        ttk.Button(cat_outer,text=self.tr('+ Famille','+ عائلة'),command=self.add_category).pack(side='bottom',anchor='w',pady=(4,0))
        cat_canvas=tk.Canvas(cat_outer,height=100,highlightthickness=0)
        cat_canvas.pack(side='left',fill='x',expand=True)
        scrollbar=ttk.Scrollbar(cat_outer,orient='vertical',command=cat_canvas.yview)
        scrollbar.pack(side='right',fill='y');cat_canvas.configure(yscrollcommand=scrollbar.set)
        self.cat_scroll_frame=tk.Frame(cat_canvas,bg='white')
        cat_canvas.create_window((0,0),window=self.cat_scroll_frame,anchor='nw')
        self.cat_scroll_frame.bind('<Configure>',lambda e:cat_canvas.configure(scrollregion=cat_canvas.bbox('all')))
        self.cat_vars={}
        self.refresh_categories()
        self.e_buy=labeled_entry(left,"Prix achat",self.buy,3)
        self.e_sell=labeled_entry(left,"Prix vente",self.sell,4)
        self.e_stock=labeled_entry(left,"Stock",self.stock,5)
        self.e_alert=labeled_entry(left,"Alerte stock",self.alert,6)
        left.columnconfigure(1,weight=1)
        self.e_bar.bind("<Return>",lambda e:self.e_name.focus_set())
        chain=[(self.e_name,self.e_buy),(self.e_buy,self.e_sell),(self.e_sell,self.e_stock),(self.e_stock,self.e_alert)]
        for a,b in chain:a.bind("<Return>",lambda e,n=b:n.focus_set())
        ttk.Label(left,text="Codes-barres / Packs",font=("Segoe UI",10,"bold")).grid(row=7,column=0,columnspan=2,sticky="w",pady=(14,4))
        self.barcodes_frame=ttk.Frame(left);self.barcodes_frame.grid(row=8,column=0,columnspan=2,sticky="ew")
        ttk.Button(left,text="+ Ajouter barcode / pack",command=self.add_barcode_row).grid(row=9,column=0,columnspan=2,sticky="w",pady=4)
        ttk.Label(left,text="Carton/pack : multiplicateur + prix total optionnel.",wraplength=520).grid(row=10,column=0,columnspan=2,sticky="w")
        ttk.Label(left,text="Promotions et prix par quantité",font=("Segoe UI",10,"bold")).grid(row=11,column=0,columnspan=2,sticky="w",pady=(10,4))
        self.offer_rows=[]
        self.offers_frame=ttk.Frame(left);self.offers_frame.grid(row=12,column=0,columnspan=2,sticky="ew")
        self.add_offer_row()
        ttk.Button(left,text="+ Ajouter une offre",command=self.add_offer_row).grid(row=13,column=0,columnspan=2,sticky="w",pady=4)
        ttk.Label(left,text="Prix/unité : dès la quantité indiquée.\nLot : groupes complets, reste au prix normal.\nSi plusieurs offres : le plus grand seuil atteint s'applique.",wraplength=440).grid(row=14,column=0,columnspan=2,sticky="w",pady=6)
        b=ttk.Frame(left);b.grid(row=15,column=0,columnspan=2,sticky="e",pady=16)
        ttk.Button(b,text="Enregistrer",command=self.save).pack(side="left",padx=4)
        ttk.Button(b,text="Annuler",command=self.destroy).pack(side="left")
        ttk.Button(b,text="⌨ Clavier",command=self.toggle_embedded_keyboard).pack(side="left",padx=(10,0))
        self.preview=tk.Label(right,text="Aucune image",bg="white",relief="groove",width=25,height=13);self.preview.pack()
        ttk.Button(right,text="Choisir image",command=self.choose_image).pack(fill="x",pady=8)
        fields=ttk.LabelFrame(right,text='Recherche',padding=8);fields.pack(fill='x',pady=10)
        for label,variable in [('Référence',self.sku),('Code fournisseur',self.supplier_code),('Alias',self.alias)]:
            ttk.Label(fields,text=label).pack(anchor='w')
            ttk.Entry(fields,textvariable=variable,width=27).pack(fill='x',pady=(0,5))
        ttk.Checkbutton(fields,text='Vente au poids / fraction',variable=self.fraction).pack(anchor='w',pady=5)
        ttk.Label(fields,text='Note stock (facultatif)').pack(anchor='w')
        ttk.Entry(fields,textvariable=self.stock_note).pack(fill='x')
        if self.pid:
            self.load()

        # Embedded touch keyboard: same ProductEditor window, hidden by default.
        self.keyboard_frame = tk.Frame(self, bg='#1E293B', padx=6, pady=6)
        self.keyboard_visible = False
        self._build_embedded_keyboard()
        self.after(100,lambda: self.e_bar.focus_force() if self.e_bar.winfo_exists() else None)

    def _is_text_input(self, widget):
        try:
            return widget is not None and widget.winfo_exists() and widget.winfo_class() in (
                'Entry', 'TEntry', 'Text', 'Spinbox', 'TSpinbox', 'TCombobox'
            )
        except tk.TclError:
            return False

    def _remember_keyboard_target(self, event):
        if self._is_text_input(event.widget) and event.widget.winfo_toplevel() is self:
            self._keyboard_target = event.widget

    def toggle_embedded_keyboard(self):
        if self.keyboard_visible:
            self.keyboard_frame.pack_forget()
            self.keyboard_visible = False
            self.after_idle(lambda: self.e_bar.focus_set() if self.e_bar.winfo_exists() else None)
            return
        target = self.focus_get()
        if self._is_text_input(target) and target.winfo_toplevel() is self:
            self._keyboard_target = target
        if not self._is_text_input(self._keyboard_target):
            self._keyboard_target = self.e_bar
        self.keyboard_frame.pack(side='bottom', fill='x')
        self.keyboard_visible = True
        self.after_idle(lambda: self._keyboard_target.focus_set() if self._is_text_input(self._keyboard_target) else None)

    def _build_embedded_keyboard(self):
        rows = [
            ['1','2','3','4','5','6','7','8','9','0','⌫'],
            ['a','z','e','r','t','y','u','i','o','p'],
            ['q','s','d','f','g','h','j','k','l','m'],
            ['w','x','c','v','b','n',',','.','-','_'],
            ['Espace','@','/','Effacer','Entrée','Fermer'],
        ]
        for keys in rows:
            row = tk.Frame(self.keyboard_frame, bg='#1E293B')
            row.pack(fill='x', pady=2)
            for key in keys:
                tk.Button(
                    row, text=key, font=('Segoe UI', 11, 'bold'),
                    bg='#334155', fg='white', activebackground='#475569',
                    activeforeground='white', relief='flat', bd=0,
                    padx=8, pady=7,
                    command=lambda k=key: self._keyboard_press(k)
                ).pack(side='left', fill='x', expand=True, padx=2)

    def _keyboard_press(self, key):
        w = self._keyboard_target
        if not self._is_text_input(w):
            w = self.focus_get()
        if not self._is_text_input(w) or w.winfo_toplevel() is not self:
            w = self.e_bar
            self._keyboard_target = w
        if key == 'Fermer':
            self.toggle_embedded_keyboard()
            return
        if key == '⌫':
            w.event_generate('<BackSpace>')
        elif key == 'Entrée':
            w.event_generate('<Return>')
        elif key == 'Effacer':
            try:
                w.delete(0, tk.END)
            except tk.TclError:
                w.delete('1.0', tk.END)
        else:
            char = ' ' if key == 'Espace' else key
            try:
                w.insert(tk.INSERT, char)
            except tk.TclError:
                pass
        self._keyboard_target = w
        self.after_idle(w.focus_set)

    def add_barcode_row(self, barcode="", multiplier="1", price=""):
        row=ttk.Frame(self.barcodes_frame);row.pack(fill="x",pady=2)
        code=tk.StringVar(value=str(barcode));mult=tk.StringVar(value=str(multiplier));pack=tk.StringVar(value=str(price))
        ttk.Entry(row,textvariable=code,width=22).pack(side="left",padx=3);ttk.Label(row,text="×").pack(side="left");ttk.Entry(row,textvariable=mult,width=7).pack(side="left",padx=3);ttk.Label(row,text="Prix pack").pack(side="left");ttk.Entry(row,textvariable=pack,width=10).pack(side="left",padx=3)
        item=[code,mult,pack,row]
        def remove():
            row.destroy()
            if item in self.barcode_rows:self.barcode_rows.remove(item)
        ttk.Button(row,text="×",width=3,command=remove).pack(side="left")
        self.barcode_rows.append(item)

    def read_barcodes(self):
        result=[];seen=set();primary=self.bar.get().strip()
        if primary:seen.add(primary);result.append((primary,1.0,None))
        for code,mult,pack,_ in self.barcode_rows:
            value=code.get().strip()
            if not value:continue
            if value in seen:raise ValueError("Code-barres répété dans la même fiche.")
            qty=float((mult.get() or "1").replace(",", "."));price=to_cents(pack.get()) if pack.get().strip() else None
            if not math.isfinite(qty) or qty<=0 or (price is not None and price<0):raise ValueError("Barcode / pack invalide")
            seen.add(value);result.append((value,qty,price))
        return result

    def add_offer_row(self, minimum="", price="", mode="UNIT"):
        row=ttk.Frame(self.offers_frame);row.pack(fill="x",pady=2)
        minimum_var=tk.StringVar(value=str(minimum));price_var=tk.StringVar(value=str(price))
        mode_var=tk.StringVar(value='Lot' if mode=='BUNDLE' else 'Prix/unité')
        ttk.Combobox(row,textvariable=mode_var,values=['Prix/unité','Lot'],state='readonly',width=10).pack(side='left')
        ttk.Label(row,text="Qté").pack(side="left")
        ttk.Entry(row,textvariable=minimum_var,width=9).pack(side="left",padx=4)
        ttk.Label(row,text="Prix DH").pack(side="left")
        ttk.Entry(row,textvariable=price_var,width=12).pack(side="left",padx=4)
        def remove():
            row.destroy();self.offer_rows.remove((minimum_var,price_var,mode_var))
        ttk.Button(row,text="×",width=3,command=remove).pack(side="left")
        self.offer_rows.append((minimum_var,price_var,mode_var))

    def read_offers(self):
        values=[]
        for minimum_var,price_var,mode_var in self.offer_rows:
            if not minimum_var.get().strip() and not price_var.get().strip():continue
            q=float(minimum_var.get().replace(',','.'));price=to_cents(price_var.get())
            if not math.isfinite(q) or q<=0 or price<0:raise ValueError("Offre invalide")
            if any(v[0]==q for v in values):raise ValueError('Une seule offre par quantité.')
            values.append((q,price,'BUNDLE' if mode_var.get()=='Lot' else 'UNIT'))
        return values

    def choose_image(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("Images","*.png *.jpg *.jpeg *.webp *.bmp"),("Tous","*.*")])
        if p:self.img_source=p;self.preview_image(p)

    def add_category(self):
        name=simpledialog.askstring("Famille","Nom de la nouvelle famille :",parent=self)
        if not name or not name.strip():return
        name=name.strip()
        try:
            with connect() as conn:
                require_admin(conn)
                conn.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)",(name,));conn.commit()
            self.refresh_categories()
            for var, label in self.cat_vars.values():
                if label==name:var.set(True)
            self.e_buy.focus_set()
        except Exception as error:
            messagebox.showerror("ToDo",str(error),parent=self)

    def refresh_categories(self):
        selected={cid for cid,(var,_) in self.cat_vars.items() if var.get()}
        for w in self.cat_scroll_frame.winfo_children():
            w.destroy()
        self.cat_vars.clear()
        for cat in list_categories():
            var = tk.BooleanVar(value=cat['id'] in selected)
            bg  = cat['color'] or '#2563EB'
            try:
                r2,g2,b2 = int(bg[1:3],16),int(bg[3:5],16),int(bg[5:7],16)
                fg = '#ffffff' if (0.299*r2+0.587*g2+0.114*b2)<140 else '#1e293b'
            except Exception:
                fg = '#ffffff'
            icon = (cat['icon']+' ') if cat['icon'] else ''
            row  = tk.Frame(self.cat_scroll_frame, bg='white')
            row.pack(fill='x', padx=4, pady=1)
            cb = tk.Checkbutton(row, text=icon+cat['name'],
                variable=var, bg='white', activebackground='white',
                selectcolor=bg, font=('Segoe UI',9))
            cb.pack(side='left')
            swatch = tk.Label(row, bg=bg, text=icon or ' ', fg=fg,
                width=3, font=('Segoe UI',8,'bold'), relief='flat')
            swatch.pack(side='left', padx=4)
            swatch.configure(cursor='hand2')
            swatch.bind('<Button-1>',lambda e,c=dict(cat):self.edit_category(c))
            self.cat_vars[cat['id']] = (var, cat['name'])

    def edit_category(self,category):
        from screens.settings import CategoryEditor
        def saved():
            self.refresh_categories();self.grab_set()
        CategoryEditor(self,category,on_saved=saved)

    def preview_image(self,p):
        if not PIL:return
        try:
            im=Image.open(p);im.thumbnail((230,230));self.img_ref=ImageTk.PhotoImage(im);self.preview.config(image=self.img_ref,text="",width=230,height=230)
        except:pass

    def load(self):
        selected=get_product_categories(self.pid)
        for cid,(var,_) in self.cat_vars.items():var.set(cid in selected)
        with connect() as c:
            p=c.execute("""SELECT p.*,COALESCE(cat.name,'') category FROM products p LEFT JOIN categories cat ON cat.id=p.category_id WHERE p.id=?""",(self.pid,)).fetchone()
            b=c.execute("SELECT barcode FROM product_barcodes WHERE product_id=? ORDER BY id LIMIT 1",(self.pid,)).fetchone()
            bars=c.execute("SELECT barcode,qty_multiplier,price_override_cents FROM product_barcodes WHERE product_id=? ORDER BY id",(self.pid,)).fetchall()
            rs=c.execute("SELECT min_qty,unit_price_cents,pricing_mode FROM quantity_prices WHERE product_id=? ORDER BY min_qty",(self.pid,)).fetchall()
        self.sku.set(p["sku"]);self.alias.set(p["alias"]);self.supplier_code.set(p["supplier_code"]);self.fraction.set(bool(p["allow_fraction"]))
        self.bar.set(b["barcode"] if b else "");self.name.set(p["name"]);self.cat.set(p["category"])
        for child in self.barcodes_frame.winfo_children():child.destroy()
        self.barcode_rows=[]
        for extra in bars[1:]:
            price="" if extra["price_override_cents"] is None else f"{extra['price_override_cents']/100:.2f}"
            self.add_barcode_row(extra["barcode"],f"{extra['qty_multiplier']:g}",price)
        self.buy.set(f"{p['purchase_price_cents']/100:.2f}");self.sell.set(f"{p['sale_price_cents']/100:.2f}")
        self.stock.set(f"{p['stock_qty']:g}");self.alert.set(f"{p['alert_qty']:g}");self.img_rel=p["image_path"] or ""
        self.loaded_stock=float(p['stock_qty'])
        for child in self.offers_frame.winfo_children():child.destroy()
        self.offer_rows=[]
        for r in rs:self.add_offer_row(r['min_qty'],f"{r['unit_price_cents']/100:.2f}",r['pricing_mode'])
        if not self.offer_rows:self.add_offer_row()
        q=abs_image(self.img_rel)
        if q:self.preview_image(q)

    def save(self):
        try:
            barcode=self.bar.get().strip();name=self.name.get().strip()
            if not name:raise ValueError("اسم المنتوج إجباري.")
            buy=to_cents(self.buy.get());sell=to_cents(self.sell.get());stock=float(self.stock.get() or 0);alert=float(self.alert.get() or 0)
            if not all(math.isfinite(x) for x in (stock,alert)) or min(buy,sell,alert)<0:
                raise ValueError('Valeurs invalides')
            selected_cats=[cid for cid,(var,_) in self.cat_vars.items() if var.get()]
            cat=next((name for cid,(_,name) in self.cat_vars.items() if cid in selected_cats),'Général') if selected_cats else 'Général'
            rules=self.read_offers()
            barcodes=self.read_barcodes()
            img=self.img_rel
            if self.img_source:img=import_image(self.img_source)
            with connect() as c:
                c.execute("BEGIN IMMEDIATE")
                require_admin(c)
                c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)",(cat,))
                catid=c.execute("SELECT id FROM categories WHERE name=?",(cat,)).fetchone()["id"]
                if self.pid:
                    c.execute("""UPDATE products SET name=?,category_id=?,purchase_price_cents=?,sale_price_cents=?,alert_qty=?,image_path=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                              (name,catid,buy,sell,alert,img,self.pid));pid=self.pid
                else:
                    cur=c.execute("""INSERT INTO products(name,category_id,purchase_price_cents,sale_price_cents,stock_qty,alert_qty,image_path) VALUES(?,?,?,?,?,?,?)""",
                                  (name,catid,buy,sell,0,alert,img));pid=cur.lastrowid
                set_product_categories(c,pid,selected_cats or [catid])
                old=c.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0]
                if abs(stock-self.loaded_stock)>1e-9 and abs(stock-old)>1e-9:
                    apply_stock_movement(c,pid,stock-old,'ADJUSTMENT' if self.pid else 'OPENING',buy,'product',pid,self.stock_note.get().strip() or ('Correction depuis la fiche produit' if self.pid else 'Stock initial'))
                c.execute('UPDATE products SET sku=?,alias=?,supplier_code=?,allow_fraction=? WHERE id=?',(self.sku.get().strip(),self.alias.get().strip(),self.supplier_code.get().strip(),int(self.fraction.get()),pid))
                audit(c,'PRODUCT_SAVE',pid)
                c.execute("DELETE FROM product_barcodes WHERE product_id=?",(pid,))
                c.executemany("INSERT INTO product_barcodes(product_id,barcode,qty_multiplier,price_override_cents) VALUES(?,?,?,?)",[(pid,code,mult,price) for code,mult,price in barcodes])
                c.execute("DELETE FROM quantity_prices WHERE product_id=?",(pid,))
                c.executemany("INSERT INTO quantity_prices(product_id,min_qty,unit_price_cents,pricing_mode) VALUES(?,?,?,?)",[(pid,q,p,m) for q,p,m in rules])
                c.commit()
            if self.on_saved:self.on_saved()
            self.destroy()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)

class ProductsFrame(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=10)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.page=0
        top=ttk.Frame(self);top.pack(fill="x",pady=(0,8))
        ttk.Label(top,text=self.tr('Articles','المنتجات'),font=("Segoe UI",20,"bold")).pack(side="left")
        ttk.Label(self,text=self.tr('Fiche article, codes-barres, images, prix et offres.','بطاقة المنتوج، الباركودات، الصور، الأثمنة والعروض.'),foreground="#475569").pack(anchor="w",pady=(0,8))
        self.q=tk.StringVar();e=ttk.Entry(top,textvariable=self.q,width=28);e.pack(side="left",padx=15);e.bind("<KeyRelease>",lambda x:self.go_page(0))
        self.filter=tk.StringVar(value="Tous")
        ttk.Combobox(top,textvariable=self.filter,values=["Tous","Alertes stock","Stock négatif","Promotions"],state="readonly",width=16).pack(side="left",padx=4)
        self.filter.trace_add("write",lambda *_:self.go_page(0))
        ttk.Button(top,text=self.tr('+ Nouveau','+ جديد'),command=self.new).pack(side="right",padx=3)
        ttk.Button(top,text=self.tr('Importer Excel','استيراد Excel'),command=self.import_excel).pack(side="right",padx=3)
        ttk.Button(top,text=self.tr('Exporter catalogue','تصدير الكتالوج'),command=self.export_catalogue).pack(side="right",padx=3)
        ttk.Button(top,text=self.tr('Étiquette PDF','ملصق PDF'),command=self.label_pdf).pack(side="right",padx=3)
        ttk.Button(top,text=self.tr('Modifier','تعديل'),command=self.edit).pack(side="right",padx=3)
        cols=("id","barcode","name","cat","buy","sell","stock","alert","img")
        self.t=ttk.Treeview(self,columns=cols,show="headings")
        cfg=[("id","ID",50),("barcode","Barcode",145),("name","Article",260),("cat","Famille",130),("buy","Achat",85),("sell","Vente",85),("stock","Stock",80),("alert","Alerte",80),("img","Img",45)]
        for c,h,w in cfg:self.t.heading(c,text=h);self.t.column(c,width=w,anchor="center")
        self.t.pack(fill="both",expand=True);self.t.bind("<Double-1>",lambda e:self.edit())
        self.kpi_bar=tk.Frame(self,bg='#F6F7FB');self.kpi_bar.pack(fill='x',pady=(8,2))
        self.kpi_values=[]
        for title,color in [('Articles','#DC2626'),('Alertes stock','#F59E0B'),('Prix quantité','#E07B00'),('Valeur stock achat','#2563EB'),('Stock négatif','#16A34A')]:
            card=tk.Frame(self.kpi_bar,bg=color,height=72);card.pack(side='left',fill='x',expand=True,padx=3);card.pack_propagate(False)
            value=tk.Label(card,text='0',bg=color,fg='white',font=('Segoe UI',18,'bold'));value.pack(anchor='w',padx=12,pady=(7,0))
            tk.Label(card,text=title,bg=color,fg='white',font=('Segoe UI',9)).pack(anchor='w',padx=12)
            self.kpi_values.append(value)
        pages=ttk.Frame(self);pages.pack(fill='x',pady=6)
        ttk.Button(pages,text='Précédent',command=lambda:self.go_page(max(0,self.page-1))).pack(side='left')
        ttk.Button(pages,text='Suivant',command=lambda:self.go_page(self.page+1)).pack(side='left',padx=8)
        self.page_label=ttk.Label(pages);self.page_label.pack(side='right')
        self.refresh()
    def go_page(self,page):
        self.page=page;self.refresh()
    def refresh(self):
        q=f"%{self.q.get().strip()}%"
        with connect() as c:
            extra=""
            if self.filter.get()=="Alertes stock":extra=" AND p.stock_qty<=p.alert_qty"
            elif self.filter.get()=="Stock négatif":extra=" AND p.stock_qty<0"
            elif self.filter.get()=="Promotions":extra=" AND EXISTS(SELECT 1 FROM quantity_prices qp WHERE qp.product_id=p.id AND qp.active=1)"
            sql="""SELECT p.*,COALESCE(cat.name,'') category,
                (SELECT barcode FROM product_barcodes b WHERE b.product_id=p.id ORDER BY id LIMIT 1) barcode
                FROM products p LEFT JOIN categories cat ON cat.id=p.category_id
                WHERE p.active=1 AND (p.name LIKE ? OR cat.name LIKE ? OR EXISTS(SELECT 1 FROM product_barcodes b2 WHERE b2.product_id=p.id AND b2.barcode LIKE ?))"""+extra+""" ORDER BY p.name LIMIT 200 OFFSET ?"""
            rows=c.execute(sql,(q,q,q,self.page*200)).fetchall()
            stats=c.execute("SELECT COUNT(*),COALESCE(SUM(stock_qty*purchase_price_cents),0),COALESCE(SUM(CASE WHEN stock_qty<0 THEN 1 ELSE 0 END),0),COALESCE(SUM(CASE WHEN stock_qty<=alert_qty THEN 1 ELSE 0 END),0) FROM products WHERE active=1").fetchone()
            promos=c.execute("SELECT COUNT(*) FROM quantity_prices WHERE active=1").fetchone()[0]
        self.kpi_values[0].config(text=str(stats[0]));self.kpi_values[1].config(text=str(stats[3]));self.kpi_values[2].config(text=str(promos));self.kpi_values[3].config(text=f"{stats[1]/100:.2f}");self.kpi_values[4].config(text=str(stats[2]))
        self.page_label.config(text=f'Page {self.page+1} · {len(rows)} produits · 200 par page')
        self.t.delete(*self.t.get_children())
        for r in rows:self.t.insert("", "end",values=(r["id"],r["barcode"] or "",r["name"],r["category"],f"{r['purchase_price_cents']/100:.2f}",f"{r['sale_price_cents']/100:.2f}",f"{r['stock_qty']:g}",f"{r['alert_qty']:g}","✓" if r["image_path"] else ""))
    def label_pdf(self):
        pid=self.sel()
        if not pid:
            messagebox.showinfo("Étiquette","Sélectionnez un article.",parent=self);return
        copies=simpledialog.askinteger("Étiquette","Nombre d'étiquettes :",initialvalue=1,minvalue=1,maxvalue=200,parent=self)
        if copies is None:return
        path=filedialog.asksaveasfilename(parent=self,defaultextension=".pdf",filetypes=[("PDF","*.pdf")],title="Enregistrer les étiquettes")
        if not path:return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.graphics.barcode import code128
            with connect() as c:
                row=c.execute("""SELECT p.name,p.sale_price_cents,(SELECT barcode FROM product_barcodes b WHERE b.product_id=p.id ORDER BY id LIMIT 1) barcode FROM products p WHERE p.id=?""",(pid,)).fetchone()
            if not row:raise ValueError("Article introuvable.")
            barcode=(row["barcode"] or "").strip()
            if not barcode:raise ValueError("Cet article n'a pas de code-barres.")
            cv=canvas.Canvas(path,pagesize=A4);page_w,page_h=A4;label_w=page_w/3;label_h=95
            for n in range(copies):
                slot=n%24;col=slot%3;line=slot//3
                if n and slot==0:cv.showPage()
                x=col*label_w+8;y=page_h-(line+1)*label_h+8
                cv.rect(x,y,label_w-16,label_h-10)
                cv.setFont("Helvetica-Bold",9);cv.drawCentredString(x+(label_w-16)/2,y+label_h-25,row["name"][:34])
                cv.setFont("Helvetica-Bold",13);cv.drawCentredString(x+(label_w-16)/2,y+label_h-42,fmt(row["sale_price_cents"]))
                bc=code128.Code128(barcode,barHeight=24,barWidth=0.7);bc.drawOn(cv,x+((label_w-16)-bc.width)/2,y+14)
                cv.setFont("Helvetica",7);cv.drawCentredString(x+(label_w-16)/2,y+5,barcode)
            cv.save();messagebox.showinfo("Étiquette",f"{copies} étiquette(s) créée(s).",parent=self)
        except Exception as e:messagebox.showerror("Étiquette",str(e),parent=self)

    def export_catalogue(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension=".xlsx",filetypes=[("Excel","*.xlsx")],title=self.tr("Exporter le catalogue","تصدير الكتالوج"))
        if not path:return
        try:
            from openpyxl import Workbook
            wb=Workbook();ws=wb.active;ws.title="Catalogue"
            ws.append(["barcode","article","famille","prix achat","prix vente","alerte","barcode label","multiplicateur","prix pack","sku","fraction"])
            with connect() as c:
                rows=c.execute("""SELECT p.id,p.sku,p.name,COALESCE(c.name,'Général') category,p.purchase_price_cents,p.sale_price_cents,p.alert_qty,p.allow_fraction
                    FROM products p LEFT JOIN categories c ON c.id=p.category_id
                    ORDER BY p.name COLLATE NOCASE""").fetchall()
            for r in rows:
                with connect() as c:
                    codes=c.execute("SELECT barcode,label,qty_multiplier,price_override_cents FROM product_barcodes WHERE product_id=? ORDER BY id",(r["id"],)).fetchall()
                if not codes:codes=[{"barcode":"","label":"","qty_multiplier":1,"price_override_cents":None}]
                for code in codes:ws.append([code["barcode"],r["name"],r["category"],r["purchase_price_cents"]/100,r["sale_price_cents"]/100,r["alert_qty"],code["label"],code["qty_multiplier"],None if code["price_override_cents"] is None else code["price_override_cents"]/100,r["sku"],r["allow_fraction"]])
            ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
            for col,width in {"A":20,"B":34,"C":22,"D":14,"E":14,"F":12,"G":18,"H":14,"I":14,"J":18,"K":10}.items():ws.column_dimensions[col].width=width
            wb.save(path)
            messagebox.showinfo(self.tr("Export catalogue","تصدير الكتالوج"),self.tr(f"{len(rows)} article(s) exporté(s). Le stock, les ventes et les clients ne sont pas exportés.",f"تم تصدير {len(rows)} منتوج. لم يتم تصدير المخزون أو المبيعات أو الزبائن."),parent=self)
        except Exception as e:messagebox.showerror(self.tr("Export catalogue","تصدير الكتالوج"),str(e),parent=self)

    def import_excel(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[("Excel","*.xlsx")],title="Importer les articles")
        if not path:return
        try:
            from openpyxl import load_workbook
            wb=load_workbook(path,read_only=True,data_only=True);ws=wb.active
            headers=[str(x.value or '').strip().lower() for x in next(ws.iter_rows())]
            aliases={'barcode':['barcode','code barre','code-barres'],'name':['article','nom','name'],'category':['famille','categorie','catégorie'],'buy':['achat','prix achat'],'sell':['vente','prix vente'],'stock':['stock'],'alert':['alerte','alert'],'bar_label':['barcode label'],'mult':['multiplicateur'],'pack_price':['prix pack'],'sku':['sku'],'fraction':['fraction']}
            idx={}
            for key,names in aliases.items():
                idx[key]=next((headers.index(n) for n in names if n in headers),None)
            if idx['name'] is None:raise ValueError("Colonne Article/Nom obligatoire.")
            preview=[];errors=[]
            for line,row in enumerate(ws.iter_rows(values_only=True),start=2):
                if not any(v not in (None,'') for v in row):continue
                try:
                    get=lambda k: row[idx[k]] if idx[k] is not None and idx[k]<len(row) else None
                    name=str(get('name') or '').strip()
                    raw_barcode=get('barcode')
                    if raw_barcode in (None,''):barcode=''
                    elif isinstance(raw_barcode,bool):raise ValueError("barcode invalide")
                    elif isinstance(raw_barcode,int):barcode=str(raw_barcode)
                    elif isinstance(raw_barcode,float):
                        if not math.isfinite(raw_barcode) or not raw_barcode.is_integer():raise ValueError("barcode numérique invalide")
                        barcode=str(int(raw_barcode))
                    else:barcode=str(raw_barcode).strip()
                    if not name:raise ValueError("nom vide")
                    buy=to_cents(get('buy') or 0);sell=to_cents(get('sell') or 0);stock=float(get('stock') or 0);alert=float(get('alert') or 0);cat=str(get('category') or 'Général').strip() or 'Général'
                    if buy<0 or sell<0 or alert<0 or not math.isfinite(stock):raise ValueError("valeurs invalides")
                    preview.append((line,barcode,name,cat,buy,sell,stock,alert))
                except Exception as e:errors.append(f"Ligne {line}: {e}")
            if errors:
                messagebox.showerror("Import Excel","Import annulé. Corrigez d'abord:\n"+"\n".join(errors[:15]),parent=self);return
            # Excel permanently drops leading zeroes when a barcode cell is stored as a number.
            # Refuse to guess: warn the operator to format barcode cells as Text before importing.
            numeric_barcode_lines=[]
            if idx['barcode'] is not None:
                for line,row in enumerate(ws.iter_rows(values_only=True),start=2):
                    if idx['barcode']<len(row) and isinstance(row[idx['barcode']],(int,float)) and not isinstance(row[idx['barcode']],bool):numeric_barcode_lines.append(line)
            if numeric_barcode_lines:
                sample=", ".join(map(str,numeric_barcode_lines[:10]))
                if not messagebox.askyesno("Import Excel",f"Barcode numérique détecté (lignes {sample}).\n\nExcel peut supprimer les zéros au début. Vérifiez le fichier et mettez la colonne Barcode au format Texte si nécessaire.\n\nContinuer quand même ?",parent=self):return
            if not preview:raise ValueError("Aucun article valide.")
            # Existing barcode conflicts are resolved explicitly during catalogue exchange.
            with connect() as c:
                existing={}
                for r in c.execute("""SELECT b.barcode,p.id,p.name,p.purchase_price_cents,p.sale_price_cents
                                     FROM product_barcodes b JOIN products p ON p.id=b.product_id
                                     WHERE b.barcode<>'' ORDER BY p.name"""):
                    existing.setdefault(r["barcode"],[]).append(dict(r))
            seen={};conflicts=[]
            for line,barcode,name,cat,buy,sell,stock,alert,*meta in preview:
                if not barcode:continue
                if barcode in existing:
                    names=", ".join(x["name"] for x in existing[barcode][:3])
                    conflicts.append(f"Ligne {line}: {barcode} existe déjà — {names}")
                if barcode in seen:conflicts.append(f"Ligne {line}: {barcode} répété dans Excel (ligne {seen[barcode]})")
                else:seen[barcode]=line
            w=tk.Toplevel(self);w.title("Aperçu import Excel");w.geometry("980x560");w.transient(self.winfo_toplevel());w.grab_set()
            tree=ttk.Treeview(w,columns=("line","barcode","name","cat","buy","sell","stock","alert"),show="headings")
            for key,title,width in [("line","Ligne",55),("barcode","Barcode",145),("name","Article",220),("cat","Famille",120),("buy","Achat",75),("sell","Vente",75),("stock","Stock",70),("alert","Alerte",70)]:tree.heading(key,text=title);tree.column(key,width=width,anchor="center")
            tree.pack(fill="both",expand=True,padx=10,pady=10)
            for row in preview[:500]:tree.insert("","end",values=(row[0],row[1],row[2],row[3],f"{row[4]/100:.2f}",f"{row[5]/100:.2f}",f"{row[6]:g}",f"{row[7]:g}"))
            warning=ttk.Label(w,text=(f"⚠ {len(conflicts)} barcode(s) partagé(s) détecté(s). Ils seront conservés et demanderont un choix à la vente." if conflicts else "✓ Aucun barcode partagé détecté."),foreground="#B45309" if conflicts else "#15803D",wraplength=930)
            warning.pack(anchor="w",padx=12)
            if conflicts:ttk.Label(w,text="\n".join(conflicts[:6]),wraplength=930).pack(anchor="w",padx=12,pady=4)
            decision={"ok":False}
            def accept():decision["ok"]=True;w.destroy()
            buttons=ttk.Frame(w);buttons.pack(fill="x",padx=10,pady=10);ttk.Button(buttons,text="Annuler",command=w.destroy).pack(side="right");ttk.Button(buttons,text=f"Importer {len(preview)} article(s)",style="Primary.TButton",command=accept).pack(side="right",padx=8)
            self.wait_window(w)
            if not decision["ok"]:return
            resolved=[]
            conflict_items=[item for item in preview if item[1] and item[1] in existing]
            bulk_action=None
            if len(conflict_items)>1:
                bulk=messagebox.askyesnocancel(self.tr("Conflits barcode","تعارضات الباركود"),
                    self.tr(f"{len(conflict_items)} lignes ont un barcode déjà présent.\n\nOui = traiter chaque conflit\nNon = ignorer tous les conflits\nAnnuler = conserver tous comme barcodes partagés",
                            f"{len(conflict_items)} سطر فيها باركود موجود مسبقاً.\n\nنعم = معالجة كل تعارض على حدة\nلا = تجاهل جميع التعارضات\nإلغاء = إضافة الجميع كمنتوجات بباركود مشترك"),parent=self)
                if bulk is False:bulk_action="skip"
                elif bulk is None:bulk_action="shared"
            for item in preview:
                line,barcode,name,cat,buy,sell,stock,alert,*meta=item
                matches=existing.get(barcode,[]) if barcode else []
                if not matches:
                    resolved.append(("new",item,None));continue
                if bulk_action:
                    resolved.append((bulk_action,item,matches[0]));continue
                current="; ".join(f'{x["name"]} ({x["sale_price_cents"]/100:.2f})' for x in matches[:4])
                answer=messagebox.askyesnocancel(self.tr("Conflit barcode","تعارض الباركود"),
                    self.tr(f"Barcode {barcode}\n\nExistant: {current}\nImporté: {name} ({sell/100:.2f})\n\nOui = mettre à jour le premier article existant\nNon = ajouter comme barcode partagé\nAnnuler = ignorer cette ligne",
                            f"الباركود {barcode}\n\nالموجود: {current}\nالمستورَد: {name} ({sell/100:.2f})\n\nنعم = تحديث أول منتوج موجود\nلا = إضافة منتوج جديد بنفس الباركود\nإلغاء = تجاهل هذا السطر"),parent=self)
                resolved.append(("replace" if answer is True else ("shared" if answer is False else "skip"),item,matches[0]))
            with connect() as c:
                c.execute("BEGIN IMMEDIATE");require_admin(c)
                imported=updated=skipped=0
                for action,item,target in resolved:
                    _,barcode,name,cat,buy,sell,stock,alert,*meta=item
                    if action=="skip":skipped+=1;continue
                    c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)",(cat,));catid=c.execute("SELECT id FROM categories WHERE name=?",(cat,)).fetchone()[0]
                    if action=="replace":
                        pid=target["id"]
                        bar_label,mult,pack_price,sku,fraction=meta
                        c.execute("UPDATE products SET name=?,category_id=?,purchase_price_cents=?,sale_price_cents=?,alert_qty=?,sku=?,allow_fraction=? WHERE id=?",(name,catid,buy,sell,alert,sku,fraction,pid))
                        if barcode:c.execute("UPDATE product_barcodes SET label=?,qty_multiplier=?,price_override_cents=? WHERE product_id=? AND barcode=?",(bar_label,mult,pack_price,pid,barcode))
                        set_product_categories(c,pid,[catid]);audit(c,'PRODUCT_IMPORT_UPDATE',pid);updated+=1
                        continue
                    bar_label,mult,pack_price,sku,fraction=meta
                    cur=c.execute("INSERT INTO products(name,category_id,purchase_price_cents,sale_price_cents,stock_qty,alert_qty,sku,allow_fraction) VALUES(?,?,?,?,0,?,?,?)",(name,catid,buy,sell,alert,sku,fraction));pid=cur.lastrowid
                    set_product_categories(c,pid,[catid])
                    if barcode:c.execute("INSERT INTO product_barcodes(product_id,barcode,label,qty_multiplier,price_override_cents) VALUES(?,?,?,?,?)",(pid,barcode,bar_label,mult,pack_price))
                    if abs(stock)>1e-9:apply_stock_movement(c,pid,stock,'OPENING',buy,'import',pid,'Import Excel — stock initial')
                    audit(c,'PRODUCT_IMPORT',pid);imported+=1
                c.commit()
            messagebox.showinfo(self.tr("Import Excel","استيراد Excel"),self.tr(f"{imported} ajouté(s), {updated} mis à jour, {skipped} ignoré(s).",f"تمت إضافة {imported}، تحديث {updated}، وتجاهل {skipped}."),parent=self);self.refresh()
        except Exception as e:messagebox.showerror("Import Excel",str(e),parent=self)

    def sel(self):
        s=self.t.selection();return int(self.t.item(s[0],"values")[0]) if s else None
    def new(self):ProductEditor(self,on_saved=self.refresh)
    def edit(self):
        if self.sel():ProductEditor(self,self.sel(),self.refresh)
    def add_barcode(self):
        pid=self.sel()
        if not pid:return
        w=tk.Toplevel(self);w.title("Barcode / Pack");w.geometry("460x310");w.transient(self);w.grab_set()
        b=tk.StringVar();mult=tk.StringVar(value="1");price=tk.StringVar()
        f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True)
        eb=labeled_entry(f,"Barcode",b,0,bold=True);labeled_entry(f,"Qté multiplier",mult,1);labeled_entry(f,"Prix pack (optionnel)",price,2)
        ttk.Label(f,text="مثال: باركود كرتونة 6 قطع → multiplier = 6").grid(row=3,column=0,columnspan=2,sticky="w",pady=8)
        def save():
            try:
                code=b.get().strip()
                if not code:raise ValueError("Barcode obligatoire")
                m=float(mult.get() or 1);pr=to_cents(price.get()) if price.get().strip() else None
                if not math.isfinite(m) or m<=0 or (pr is not None and pr<0):raise ValueError("Pack invalide")
                with connect() as c:
                    require_admin(c)
                    c.execute("INSERT INTO product_barcodes(product_id,barcode,qty_multiplier,price_override_cents) VALUES(?,?,?,?)",(pid,code,m,pr));c.commit()
                w.destroy();self.refresh()
            except Exception as e:messagebox.showerror("ToDo",str(e),parent=w)
        ttk.Button(f,text="Enregistrer",command=save).grid(row=4,column=0,columnspan=2,pady=15)
        eb.bind("<Return>",lambda e:save());w.after(100,eb.focus_force)
