import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from database import connect, get_setting
from services.inventory import apply_stock_movement
from services.security import require_admin, audit
import math
from services.money import to_cents
from services.images import import_image, abs_image
from screens.common import labeled_entry
from services.catalog import list_categories, get_product_categories, set_product_categories, add_product_barcode, list_product_label_barcodes, product_label_data
try:
    from PIL import Image,ImageTk
    PIL=True
except Exception:
    PIL=False

def _internal_product_barcode(product_id):
    return f"TODO-{int(product_id):08d}"

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
        self.grid_price_vars={}
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
        self.e_buy=labeled_entry(left,self.tr("Prix achat","ثمن الشراء"),self.buy,3)
        self.e_sell=labeled_entry(left,self.tr("Prix vente","ثمن البيع"),self.sell,4)
        self.e_stock=labeled_entry(left,self.tr("Stock","المخزون"),self.stock,5)
        self.e_alert=labeled_entry(left,self.tr("Alerte stock","تنبيه المخزون"),self.alert,6)
        left.columnconfigure(1,weight=1)
        self.e_bar.bind("<Return>",lambda e:self.e_name.focus_set())
        chain=[(self.e_name,self.e_buy),(self.e_buy,self.e_sell),(self.e_sell,self.e_stock),(self.e_stock,self.e_alert)]
        for a,b in chain:a.bind("<Return>",lambda e,n=b:n.focus_set())
        ttk.Label(left,text=self.tr("Codes-barres / Packs","الباركود / الحزم"),font=("Segoe UI",10,"bold")).grid(row=7,column=0,columnspan=2,sticky="w",pady=(14,4))
        self.barcodes_frame=ttk.Frame(left);self.barcodes_frame.grid(row=8,column=0,columnspan=2,sticky="ew")
        ttk.Button(left,text=self.tr("+ Ajouter barcode / pack","+ إضافة باركود / حزمة"),command=self.add_barcode_row).grid(row=9,column=0,columnspan=2,sticky="w",pady=4)
        ttk.Label(left,text=self.tr("Carton/pack : multiplicateur + prix total optionnel.","الكرتونة/الحزمة: المضاعف + الثمن الإجمالي اختياري."),wraplength=520).grid(row=10,column=0,columnspan=2,sticky="w")
        ttk.Label(left,text=self.tr("Promotions et prix par quantité","العروض والأثمنة حسب الكمية"),font=("Segoe UI",10,"bold")).grid(row=11,column=0,columnspan=2,sticky="w",pady=(10,4))
        self.offer_rows=[]
        self.offers_frame=ttk.Frame(left);self.offers_frame.grid(row=12,column=0,columnspan=2,sticky="ew")
        self.add_offer_row()
        ttk.Button(left,text=self.tr("+ Ajouter une offre","+ إضافة عرض"),command=self.add_offer_row).grid(row=13,column=0,columnspan=2,sticky="w",pady=4)
        ttk.Label(left,text=self.tr("Prix/unité : dès la quantité indiquée.\nLot : groupes complets, reste au prix normal.\nSi plusieurs offres : le plus grand seuil atteint s'applique.","ثمن الوحدة: ابتداءً من الكمية المحددة.\nالحزمة: مجموعات كاملة والباقي بالثمن العادي.\nعند تعدد العروض يطبق أكبر حد تم بلوغه."),wraplength=440).grid(row=14,column=0,columnspan=2,sticky="w",pady=6)
        b=ttk.Frame(left);b.grid(row=15,column=0,columnspan=2,sticky="e",pady=16)
        ttk.Button(b,text=self.tr('Enregistrer','حفظ'),style='Success.TButton',command=self.save).pack(side='left',padx=4,ipadx=8)
        ttk.Button(b,text=self.tr('Annuler','إلغاء'),style='Danger.TButton',command=self.destroy).pack(side='left',padx=4)
        ttk.Button(b,text=self.tr('⌨ Clavier','⌨ لوحة المفاتيح'),style='Primary.TButton',command=self.toggle_embedded_keyboard).pack(side='left',padx=(10,0))
        self.preview=tk.Label(right,text=self.tr("Aucune image","لا توجد صورة"),bg="white",relief="groove",width=25,height=13);self.preview.pack()
        ttk.Button(right,text=self.tr('Choisir image','اختيار صورة'),style='Soft.TButton',command=self.choose_image).pack(fill='x',pady=8)
        fields=ttk.LabelFrame(right,text=self.tr('Recherche','معلومات إضافية'),padding=8);fields.pack(fill='x',pady=10)
        for label,variable in [(self.tr('Référence','المرجع'),self.sku),(self.tr('Code fournisseur','رمز المورد'),self.supplier_code),(self.tr('Alias','اسم بديل'),self.alias)]:
            ttk.Label(fields,text=label).pack(anchor='w')
            ttk.Entry(fields,textvariable=variable,width=27).pack(fill='x',pady=(0,5))
        ttk.Checkbutton(fields,text=self.tr('Vente au poids / fraction','البيع بالوزن / الكسر'),variable=self.fraction).pack(anchor='w',pady=5)
        ttk.Label(fields,text=self.tr('Note stock (facultatif)','ملاحظة المخزون (اختيارية)')).pack(anchor='w')
        ttk.Entry(fields,textvariable=self.stock_note).pack(fill='x')
        if self.pid:
            self.load()

        # Embedded touch keyboard: same ProductEditor window, hidden by default.
        self.keyboard_frame = tk.Frame(self, bg='#1E293B', padx=10, pady=10)
        self.keyboard_visible = False
        self._build_embedded_keyboard()
        self.after_idle(lambda: self.e_bar.focus_force() if self.e_bar.winfo_exists() else None)
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
            row.pack(fill='x', pady=3)
            for key in keys:
                tk.Button(
                    row, text=key, font=('Segoe UI', 12, 'bold'),
                    bg='#334155', fg='white', activebackground='#475569',
                    activeforeground='white', relief='flat', bd=0,
                    padx=10, pady=9,
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
        ttk.Entry(row,textvariable=code,width=22).pack(side="left",padx=3);ttk.Label(row,text="×").pack(side="left");ttk.Entry(row,textvariable=mult,width=7).pack(side="left",padx=3);ttk.Label(row,text=self.tr("Prix pack","ثمن الحزمة")).pack(side="left");ttk.Entry(row,textvariable=pack,width=10).pack(side="left",padx=3)
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
            if value in seen:raise ValueError(self.tr("Code-barres répété dans la même fiche.","الباركود مكرر في نفس بطاقة المنتوج."))
            qty=float((mult.get() or "1").replace(",", "."));price=to_cents(pack.get()) if pack.get().strip() else None
            if not math.isfinite(qty) or qty<=0 or (price is not None and price<0):raise ValueError(self.tr("Barcode / pack invalide","باركود / حزمة غير صالحة"))
            seen.add(value);result.append((value,qty,price))
        return result

    def add_offer_row(self, minimum="", price="", mode="UNIT"):
        row=ttk.Frame(self.offers_frame);row.pack(fill="x",pady=2)
        minimum_var=tk.StringVar(value=str(minimum));price_var=tk.StringVar(value=str(price))
        mode_var=tk.StringVar(value=self.tr('À partir de Qté','ابتداءً من الكمية') if mode=='BUNDLE' else self.tr('Prix/unité','ثمن/الوحدة'))
        ttk.Combobox(row,textvariable=mode_var,values=[self.tr('Prix/unité','ثمن/الوحدة'),self.tr('À partir de Qté','ابتداءً من الكمية')],state='readonly',width=18).pack(side='left')
        ttk.Label(row,text=self.tr("Qté","الكمية")).pack(side="left")
        ttk.Entry(row,textvariable=minimum_var,width=9).pack(side="left",padx=4)
        ttk.Label(row,text=self.tr("Prix DH","الثمن DH")).pack(side="left")
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
            if not math.isfinite(q) or q<=0 or price<0:raise ValueError(self.tr("Offre invalide","عرض غير صالح"))
            if any(v[0]==q for v in values):raise ValueError(self.tr('Une seule offre par quantité.','يسمح بعرض واحد فقط لكل كمية.'))
            values.append((q,price,'BUNDLE' if mode_var.get()==self.tr('À partir de Qté','ابتداءً من الكمية') else 'UNIT'))
        return values

    def choose_image(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[(self.tr("Images","الصور"),"*.png *.jpg *.jpeg *.webp *.bmp"),(self.tr("Tous","الكل"),"*.*")])
        if p:self.img_source=p;self.preview_image(p)

    def add_category(self):
        name=simpledialog.askstring(self.tr("Famille","العائلة"),self.tr("Nom de la nouvelle famille :","اسم العائلة الجديدة:"),parent=self)
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
            gps=c.execute("SELECT grid_id,unit_price_cents FROM product_grid_prices WHERE product_id=?",(self.pid,)).fetchall()
        self.sku.set(p["sku"]);self.alias.set(p["alias"]);self.supplier_code.set(p["supplier_code"]);self.fraction.set(bool(p["allow_fraction"]))
        self.bar.set(b["barcode"] if b else "");self.name.set(p["name"]);self.cat.set(p["category"])
        for child in self.barcodes_frame.winfo_children():child.destroy()
        self.barcode_rows=[]
        for extra in bars[1:]:
            price="" if extra["price_override_cents"] is None else f"{extra['price_override_cents']/100:.2f}"
            self.add_barcode_row(extra["barcode"],f"{extra['qty_multiplier']:g}",price)
        self.buy.set(f"{p['purchase_price_cents']/100:.2f}");self.sell.set(f"{p['sale_price_cents']/100:.2f}")
        for gp in gps:
            if gp["grid_id"] in self.grid_price_vars:self.grid_price_vars[gp["grid_id"]].set(f"{gp['unit_price_cents']/100:.2f}")
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
                raise ValueError(self.tr('Valeurs invalides','قيم غير صالحة'))
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
                # Auto-generated internal barcode for image-driven products that have no scanned code.
                # Stable across edits because it is derived from the product id.
                if img and not barcodes:
                    barcodes=[(_internal_product_barcode(pid),1.0,None)]
                c.execute("DELETE FROM product_barcodes WHERE product_id=?",(pid,))
                c.executemany("INSERT INTO product_barcodes(product_id,barcode,qty_multiplier,price_override_cents) VALUES(?,?,?,?)",[(pid,code,mult,price) for code,mult,price in barcodes])
                c.execute("DELETE FROM product_grid_prices WHERE product_id=?",(pid,))
                for gid,var in self.grid_price_vars.items():
                    value=var.get().strip()
                    if value:
                        cents=to_cents(value)
                        if cents<0:raise ValueError(self.tr("Prix grille invalide","ثمن شبكة غير صالح"))
                        c.execute("INSERT INTO product_grid_prices(product_id,grid_id,unit_price_cents) VALUES(?,?,?)",(pid,gid,cents))
                c.execute("DELETE FROM quantity_prices WHERE product_id=?",(pid,))
                c.executemany("INSERT INTO quantity_prices(product_id,min_qty,unit_price_cents,pricing_mode) VALUES(?,?,?,?)",[(pid,q,p,m) for q,p,m in rules])
                c.commit()
            if self.on_saved:self.on_saved()
            self.destroy()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)

class ProductsFrame(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=16)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.page=0
        top=ttk.Frame(self);top.pack(fill="x",pady=(0,8))
        ttk.Label(top,text=self.tr('Articles','المنتجات'),style='Title.TLabel').pack(side='left')
        ttk.Label(self,text=self.tr('Fiche article, codes-barres, images, prix et offres.','بطاقة المنتوج، الباركودات، الصور، الأثمنة والعروض.'),foreground="#475569").pack(anchor="w",pady=(0,8))
        self.q=tk.StringVar();self.search_entry=ttk.Entry(top,textvariable=self.q,width=30,style='Search.TEntry');self.search_entry.pack(side='left',padx=15);self.search_entry.bind('<KeyRelease>',lambda x:self.go_page(0))
        self.filter=tk.StringVar(value=self.tr('Tous','الكل'))
        ttk.Combobox(top,textvariable=self.filter,values=[self.tr('Tous','الكل'),self.tr('Alertes stock','تنبيهات المخزون'),self.tr('Stock négatif','مخزون سالب'),self.tr('Promotions','العروض')],state='readonly',width=18).pack(side='left',padx=4)
        self.filter.trace_add("write",lambda *_:self.go_page(0))
        ttk.Button(top,text=self.tr('+ Nouveau','+ جديد'),style='Primary.TButton',command=self.new).pack(side='right',padx=3)
        ttk.Button(top,text=self.tr('Importer Excel','استيراد Excel'),style='Soft.TButton',command=self.import_excel).pack(side='right',padx=3)
        ttk.Button(top,text=self.tr('Exporter catalogue','تصدير الكتالوج'),style='Soft.TButton',command=self.export_catalogue).pack(side='right',padx=3)
        ttk.Button(top,text=self.tr('Étiquette PDF','ملصق PDF'),style='Soft.TButton',command=self.label_pdf).pack(side='right',padx=3)
        ttk.Button(top,text=self.tr('Modifier','تعديل'),style='Soft.TButton',command=self.edit).pack(side='right',padx=3)
        cols=("id","barcode","name","cat","buy","sell","stock","alert","img")
        self.t=ttk.Treeview(self,columns=cols,show='headings',height=14)
        cfg=[("id","ID",50),("barcode",self.tr("Barcode","الباركود"),145),("name",self.tr("Article","المنتوج"),260),("cat",self.tr("Famille","العائلة"),130),("buy",self.tr("Achat","الشراء"),85),("sell",self.tr("Vente","البيع"),85),("stock",self.tr("Stock","المخزون"),80),("alert",self.tr("Alerte","التنبيه"),80),("img",self.tr("Img","صورة"),45)]
        for c,h,w in cfg:self.t.heading(c,text=h);self.t.column(c,width=w,anchor="center")
        self.t.pack(fill="both",expand=True);self.t.bind("<Double-1>",lambda e:self.edit())
        self.kpi_bar=tk.Frame(self,bg='#F6F7FB');self.kpi_bar.pack(fill='x',pady=(8,2))
        self.kpi_values=[]
        for title,color in [(self.tr('Articles','المنتجات'),'#DC2626'),(self.tr('Alertes stock','تنبيهات المخزون'),'#F59E0B'),(self.tr('Prix quantité','ثمن الكمية'),'#E07B00'),(self.tr('Valeur stock achat','قيمة مخزون الشراء'),'#2563EB'),(self.tr('Stock négatif','مخزون سالب'),'#16A34A')]:
            card=tk.Frame(self.kpi_bar,bg=color,height=72);card.pack(side='left',fill='x',expand=True,padx=3);card.pack_propagate(False)
            value=tk.Label(card,text='0',bg=color,fg='white',font=('Segoe UI',18,'bold'));value.pack(anchor='w',padx=12,pady=(7,0))
            tk.Label(card,text=title,bg=color,fg='white',font=('Segoe UI',9)).pack(anchor='w',padx=12)
            self.kpi_values.append(value)
        pages=ttk.Frame(self);pages.pack(fill='x',pady=6)
        ttk.Button(pages,text=self.tr('Précédent','السابق'),command=lambda:self.go_page(max(0,self.page-1))).pack(side='left')
        ttk.Button(pages,text=self.tr('Suivant','التالي'),command=lambda:self.go_page(self.page+1)).pack(side='left',padx=8)
        self.page_label=ttk.Label(pages);self.page_label.pack(side='right')
        self.refresh()
        self.after_idle(lambda:self.search_entry.focus_force() if self.search_entry.winfo_exists() else None)
        self.after(100,lambda:self.search_entry.focus_force() if self.search_entry.winfo_exists() else None)
    def go_page(self,page):
        self.page=page;self.refresh()
    def refresh(self):
        q=f"%{self.q.get().strip()}%"
        with connect() as c:
            extra=""
            if self.filter.get()==self.tr("Alertes stock","تنبيهات المخزون"):extra=" AND p.stock_qty<=p.alert_qty"
            elif self.filter.get()==self.tr("Stock négatif","مخزون سالب"):extra=" AND p.stock_qty<0"
            elif self.filter.get()==self.tr("Promotions","العروض"):extra=" AND EXISTS(SELECT 1 FROM quantity_prices qp WHERE qp.product_id=p.id AND qp.active=1)"
            sql="""SELECT p.*,COALESCE(cat.name,'') category,
                (SELECT barcode FROM product_barcodes b WHERE b.product_id=p.id ORDER BY id LIMIT 1) barcode
                FROM products p LEFT JOIN categories cat ON cat.id=p.category_id
                WHERE p.active=1 AND (p.name LIKE ? OR cat.name LIKE ? OR EXISTS(SELECT 1 FROM product_barcodes b2 WHERE b2.product_id=p.id AND b2.barcode LIKE ?))"""+extra+""" ORDER BY p.name LIMIT 200 OFFSET ?"""
            rows=c.execute(sql,(q,q,q,self.page*200)).fetchall()
            stats=c.execute("SELECT COUNT(*),COALESCE(SUM(stock_qty*purchase_price_cents),0),COALESCE(SUM(CASE WHEN stock_qty<0 THEN 1 ELSE 0 END),0),COALESCE(SUM(CASE WHEN stock_qty<=alert_qty THEN 1 ELSE 0 END),0) FROM products WHERE active=1").fetchone()
            promos=c.execute("SELECT COUNT(*) FROM quantity_prices WHERE active=1").fetchone()[0]
        self.kpi_values[0].config(text=str(stats[0]));self.kpi_values[1].config(text=str(stats[3]));self.kpi_values[2].config(text=str(promos));self.kpi_values[3].config(text=f"{stats[1]/100:.2f}");self.kpi_values[4].config(text=str(stats[2]))
        self.page_label.config(text=self.tr(f'Page {self.page+1} · {len(rows)} produits · 200 par page',f'الصفحة {self.page+1} · {len(rows)} منتوج · 200 في الصفحة'))
        self.t.delete(*self.t.get_children())
        for r in rows:self.t.insert("", "end",values=(r["id"],r["barcode"] or "",r["name"],r["category"],f"{r['purchase_price_cents']/100:.2f}",f"{r['sale_price_cents']/100:.2f}",f"{r['stock_qty']:g}",f"{r['alert_qty']:g}","✓" if r["image_path"] else ""))
    def label_pdf(self):
        pid=self.sel()
        if not pid:
            messagebox.showinfo(self.tr("Étiquette","الملصق"),self.tr("Sélectionnez un article.","اختر منتوجاً."),parent=self);return
        try:
            codes=list_product_label_barcodes(pid)
            if not codes:raise ValueError(self.tr("Cet article n'a pas de code-barres.","هذا المنتوج لا يتوفر على باركود."))
            barcode_id=codes[0]['id']
            if len(codes)>1:
                w=tk.Toplevel(self);w.title(self.tr("Choisir le code-barres","اختر الباركود"));w.transient(self);w.grab_set()
                choice=tk.IntVar(value=barcode_id)
                ttk.Label(w,text=self.tr("Unité / carton à imprimer :","الوحدة / الكرتونة المراد طباعتها:")).pack(anchor='w',padx=14,pady=(14,6))
                for code in codes:
                    mult=float(code['qty_multiplier']);label=(code['label'] or '').strip()
                    desc=f"{code['barcode']} — {label or self.tr('Unité','وحدة')}"
                    if abs(mult-1)>1e-9:desc+=f" — ×{mult:g}"
                    if code['price_override_cents'] is not None:desc+=f" — {fmt(code['price_override_cents'])}"
                    ttk.Radiobutton(w,text=desc,variable=choice,value=code['id']).pack(anchor='w',padx=18,pady=3)
                accepted={'ok':False}
                def accept():accepted['ok']=True;w.destroy()
                ttk.Button(w,text=self.tr("Continuer","متابعة"),command=accept).pack(pady=12)
                w.protocol("WM_DELETE_WINDOW",w.destroy);self.wait_window(w)
                if not accepted['ok']:return
                barcode_id=choice.get()
            data=product_label_data(pid,barcode_id)
            copies=simpledialog.askinteger(self.tr("Étiquette","الملصق"),self.tr("Nombre d'étiquettes :","عدد الملصقات:"),initialvalue=1,minvalue=1,maxvalue=500,parent=self)
            if copies is None:return
            size=simpledialog.askstring(self.tr("Format","القياس"),self.tr("Format: A4, 58x40 ou 50x30","القياس: A4 أو 58x40 أو 50x30"),initialvalue="58x40",parent=self)
            if size is None:return
            size=size.strip().upper().replace(' ','')
            if size not in ('A4','58X40','50X30'):raise ValueError(self.tr("Format invalide.","قياس غير صالح."))
            path=filedialog.asksaveasfilename(parent=self,defaultextension=".pdf",filetypes=[("PDF","*.pdf")],title=self.tr("Enregistrer les étiquettes","حفظ الملصقات"))
            if not path:return
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import mm
            from reportlab.pdfgen import canvas
            from reportlab.graphics.barcode import code128
            barcode=data['barcode'];name=data['name'];price=data['price_cents']
            if size=='A4':
                cv=canvas.Canvas(path,pagesize=A4);page_w,page_h=A4;label_w=page_w/3;label_h=95;slots=24
                for n in range(copies):
                    slot=n%slots;col=slot%3;line=slot//3
                    if n and slot==0:cv.showPage()
                    x=col*label_w+8;y=page_h-(line+1)*label_h+8
                    self._draw_label(cv,x,y,label_w-16,label_h-10,name,price,barcode,data)
            else:
                w_mm,h_mm=(58,40) if size=='58X40' else (50,30)
                page=(w_mm*mm,h_mm*mm);cv=canvas.Canvas(path,pagesize=page)
                for n in range(copies):
                    if n:cv.showPage()
                    self._draw_label(cv,2*mm,2*mm,page[0]-4*mm,page[1]-4*mm,name,price,barcode,data)
            cv.save();messagebox.showinfo(self.tr("Étiquette","الملصق"),self.tr(f"{copies} étiquette(s) créée(s).",f"تم إنشاء {copies} ملصق."),parent=self)
        except Exception as e:messagebox.showerror(self.tr("Étiquette","الملصق"),str(e),parent=self)

    def _draw_label(self,cv,x,y,w,h,name,price,barcode,data):
        from reportlab.graphics.barcode import code128
        cv.rect(x,y,w,h)
        title=name[:34]
        if data.get('barcode_label'):title=(title+" "+data['barcode_label'])[:38]
        mult=float(data.get('qty_multiplier') or 1)
        if abs(mult-1)>1e-9:title=(title+f" ×{mult:g}")[:42]
        cv.setFont("Helvetica-Bold",8);cv.drawCentredString(x+w/2,y+h-13,title)
        cv.setFont("Helvetica-Bold",12);cv.drawCentredString(x+w/2,y+h-29,fmt(price))
        bar_h=max(14,min(24,h-48));bc=code128.Code128(barcode,barHeight=bar_h,barWidth=0.55)
        scale=min(1,max(0.45,(w-8)/bc.width));cv.saveState();cv.translate(x+(w-bc.width*scale)/2,y+11);cv.scale(scale,1);bc.drawOn(cv,0,0);cv.restoreState()
        cv.setFont("Helvetica",6.5);cv.drawCentredString(x+w/2,y+3,barcode)

    def export_catalogue(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension=".xlsx",filetypes=[("Excel","*.xlsx")],title=self.tr("Exporter le catalogue","تصدير الكتالوج"))
        if not path:return
        try:
            from openpyxl import Workbook
            wb=Workbook();ws=wb.active;ws.title="Catalogue"
            ws.append(["product key","barcode","article","famille","prix achat","prix vente","stock","alerte","barcode label","multiplicateur","prix pack","sku","fraction"])
            with connect() as c:
                rows=c.execute("""SELECT p.id,p.sku,p.name,COALESCE(c.name,'Général') category,p.purchase_price_cents,p.sale_price_cents,p.stock_qty,p.alert_qty,p.allow_fraction
                    FROM products p LEFT JOIN categories c ON c.id=p.category_id
                    ORDER BY p.name COLLATE NOCASE""").fetchall()
                barcode_rows=c.execute("SELECT product_id,barcode,label,qty_multiplier,price_override_cents FROM product_barcodes WHERE barcode NOT LIKE 'TODO-%' ORDER BY product_id,id").fetchall()
            barcodes_by_product={}
            for code in barcode_rows:barcodes_by_product.setdefault(code["product_id"],[]).append(code)
            for seq,r in enumerate(rows,start=1):
                codes=barcodes_by_product.get(r["id"]) or [{"barcode":"","label":"","qty_multiplier":1,"price_override_cents":None}]
                # product key is an exchange-file grouping token only; it is deliberately not a database id.
                exchange_key=f"TODO-{seq:06d}"
                for code in codes:ws.append([exchange_key,code["barcode"],r["name"],r["category"],r["purchase_price_cents"]/100,r["sale_price_cents"]/100,r["stock_qty"],r["alert_qty"],code["label"],code["qty_multiplier"],None if code["price_override_cents"] is None else code["price_override_cents"]/100,r["sku"],r["allow_fraction"]])
            ws.freeze_panes="A2";ws.auto_filter.ref=ws.dimensions
            for col,width in {"A":12,"B":20,"C":34,"D":22,"E":14,"F":14,"G":12,"H":12,"I":18,"J":14,"K":14,"L":18,"M":10}.items():ws.column_dimensions[col].width=width
            wb.save(path)
            messagebox.showinfo(self.tr("Export catalogue","تصدير الكتالوج"),self.tr(f"{len(rows)} article(s) exporté(s), stock inclus. Les ventes et les clients ne sont pas exportés.",f"تم تصدير {len(rows)} منتوج مع المخزون. لم يتم تصدير المبيعات أو الزبائن."),parent=self)
        except Exception as e:messagebox.showerror(self.tr("Export catalogue","تصدير الكتالوج"),str(e),parent=self)

    def import_excel(self):
        path=filedialog.askopenfilename(parent=self,filetypes=[("Excel","*.xlsx")],title=self.tr("Importer les articles","استيراد المنتجات"))
        if not path:return
        try:
            from openpyxl import load_workbook
            wb=load_workbook(path,read_only=True,data_only=True);ws=wb.active
            headers=[str(x.value or '').strip().lower() for x in next(ws.iter_rows())]
            aliases={'product_key':['product key','product_key'],'barcode':['barcode','code barre','code-barres'],'name':['article','nom','name'],'category':['famille','categorie','catégorie'],'buy':['achat','prix achat'],'sell':['vente','prix vente'],'stock':['stock'],'alert':['alerte','alert'],'bar_label':['barcode label'],'mult':['multiplicateur'],'pack_price':['prix pack'],'sku':['sku'],'fraction':['fraction']}
            idx={}
            for key,names in aliases.items():
                idx[key]=next((headers.index(n) for n in names if n in headers),None)
            if idx['name'] is None:raise ValueError(self.tr("Colonne Article/Nom obligatoire.","عمود المنتوج/الاسم إجباري."))
            preview=[];errors=[]
            for line,row in enumerate(ws.iter_rows(values_only=True),start=2):
                if not any(v not in (None,'') for v in row):continue
                try:
                    get=lambda k: row[idx[k]] if idx[k] is not None and idx[k]<len(row) else None
                    name=str(get('name') or '').strip()
                    raw_barcode=get('barcode')
                    if raw_barcode in (None,''):barcode=''
                    elif isinstance(raw_barcode,bool):raise ValueError(self.tr("barcode invalide","باركود غير صالح"))
                    elif isinstance(raw_barcode,int):barcode=str(raw_barcode)
                    elif isinstance(raw_barcode,float):
                        if not math.isfinite(raw_barcode) or not raw_barcode.is_integer():raise ValueError(self.tr("barcode numérique invalide","باركود رقمي غير صالح"))
                        barcode=str(int(raw_barcode))
                    else:barcode=str(raw_barcode).strip()
                    if not name:raise ValueError(self.tr("nom vide","الاسم فارغ"))
                    buy=to_cents(get('buy') or 0);sell=to_cents(get('sell') or 0);stock_raw=get('stock');stock=None if stock_raw in (None,'') else float(stock_raw);alert=float(get('alert') or 0);cat=str(get('category') or 'Général').strip() or 'Général'
                    bar_label=str(get('bar_label') or '').strip();mult=float(get('mult') or 1)
                    pack_price=to_cents(get('pack_price')) if get('pack_price') not in (None,'') else None
                    sku=str(get('sku') or '').strip();product_key=str(get('product_key') or '').strip();fv=get('fraction');fraction=1 if str(fv).strip().lower() in ('1','true','oui','yes','نعم') else 0
                    if buy<0 or sell<0 or alert<0 or (stock is not None and not math.isfinite(stock)) or not math.isfinite(mult) or mult<=0 or (pack_price is not None and pack_price<0):raise ValueError(self.tr("valeurs invalides","قيم غير صالحة"))
                    preview.append((line,barcode,name,cat,buy,sell,stock,alert,bar_label,mult,pack_price,sku,fraction,product_key))
                except Exception as e:errors.append(f"Ligne {line}: {e}")
            if errors:
                messagebox.showerror(self.tr("Import Excel","استيراد Excel"),self.tr("Import annulé. Corrigez d'abord:\n","تم إلغاء الاستيراد. صحح أولاً:\n")+"\n".join(errors[:15]),parent=self);return
            # Excel permanently drops leading zeroes when a barcode cell is stored as a number.
            # Refuse to guess: warn the operator to format barcode cells as Text before importing.
            numeric_barcode_lines=[]
            if idx['barcode'] is not None:
                for line,row in enumerate(ws.iter_rows(values_only=True),start=2):
                    if idx['barcode']<len(row) and isinstance(row[idx['barcode']],(int,float)) and not isinstance(row[idx['barcode']],bool):numeric_barcode_lines.append(line)
            if numeric_barcode_lines:
                sample=", ".join(map(str,numeric_barcode_lines[:10]))
                if not messagebox.askyesno(self.tr("Import Excel","استيراد Excel"),self.tr(f"Barcode numérique détecté (lignes {sample}).\n\nExcel peut supprimer les zéros au début. Vérifiez le fichier et mettez la colonne Barcode au format Texte si nécessaire.\n\nContinuer quand même ?",f"تم اكتشاف باركود رقمي (الأسطر {sample}).\n\nقد يحذف Excel الأصفار في البداية. تحقق من الملف واجعل عمود Barcode بتنسيق نص عند الحاجة.\n\nهل تريد المتابعة؟"),parent=self):return
            if not preview:raise ValueError(self.tr("Aucun article valide.","لا يوجد أي منتوج صالح."))
            # Existing barcode conflicts are resolved explicitly during catalogue exchange.
            with connect() as c:
                existing={}
                for r in c.execute("""SELECT b.barcode,p.id,p.name,p.purchase_price_cents,p.sale_price_cents
                                     FROM product_barcodes b JOIN products p ON p.id=b.product_id
                                     WHERE b.barcode<>'' ORDER BY p.name"""):
                    existing.setdefault(r["barcode"],[]).append(dict(r))
            seen={};conflicts=[];group_fingerprints={};file_group_barcodes={}
            for line,barcode,name,cat,buy,sell,stock,alert,*meta in preview:
                product_key=meta[-1] if meta else ''
                if product_key:
                    fingerprint=(name,cat,buy,sell,stock,alert,meta[-3],meta[-2])
                    if product_key in group_fingerprints and group_fingerprints[product_key]!=fingerprint:
                        errors.append(f"Ligne {line}: product key {product_key} contient des données produit incohérentes")
                    else:group_fingerprints[product_key]=fingerprint
                if not barcode:continue
                if product_key:
                    group_codes=file_group_barcodes.setdefault(product_key,set())
                    if barcode in group_codes:
                        errors.append(f"Ligne {line}: barcode {barcode} répété dans le même product key {product_key}")
                    group_codes.add(barcode)
                if barcode in existing:
                    names=", ".join(x["name"] for x in existing[barcode][:3])
                    conflicts.append(f"Ligne {line}: {barcode} existe déjà — {names}")
                if barcode in seen:
                    previous_key=seen[barcode][1]
                    if not product_key or product_key!=previous_key:
                        conflicts.append(f"Ligne {line}: {barcode} partagé entre plusieurs produits (première ligne {seen[barcode][0]})")
                else:seen[barcode]=(line,product_key)
            if errors:
                messagebox.showerror(self.tr("Import Excel","استيراد Excel"),self.tr("Import annulé: le fichier contient des groupes produit incohérents ou des barcodes dupliqués dans le même produit.\n","تم إلغاء الاستيراد: الملف يحتوي مجموعات منتوج غير متناسقة أو باركود مكرر داخل نفس المنتوج.\n")+"\n".join(errors[:15]),parent=self);return
            w=tk.Toplevel(self);w.title(self.tr("Aperçu import Excel","معاينة استيراد Excel"));w.geometry("980x560");w.transient(self.winfo_toplevel());w.grab_set()
            tree=ttk.Treeview(w,columns=("line","barcode","name","cat","buy","sell","stock","alert"),show="headings")
            for key,title,width in [("line",self.tr("Ligne","السطر"),55),("barcode",self.tr("Barcode","الباركود"),145),("name",self.tr("Article","المنتوج"),220),("cat",self.tr("Famille","العائلة"),120),("buy",self.tr("Achat","الشراء"),75),("sell",self.tr("Vente","البيع"),75),("stock",self.tr("Stock","المخزون"),70),("alert",self.tr("Alerte","التنبيه"),70)]:tree.heading(key,text=title);tree.column(key,width=width,anchor="center")
            tree.pack(fill="both",expand=True,padx=10,pady=10)
            for row in preview[:500]:tree.insert("","end",values=(row[0],row[1],row[2],row[3],f"{row[4]/100:.2f}",f"{row[5]/100:.2f}",("" if row[6] is None else f"{row[6]:g}"),f"{row[7]:g}"))
            warning=ttk.Label(w,text=(self.tr(f"⚠ {len(conflicts)} barcode(s) partagé(s) détecté(s). Ils seront conservés et demanderont un choix à la vente.",f"⚠ تم اكتشاف {len(conflicts)} باركود مشترك. سيتم الاحتفاظ بها وسيطلب الاختيار عند البيع.") if conflicts else self.tr("✓ Aucun barcode partagé détecté.","✓ لم يتم اكتشاف أي باركود مشترك.")),foreground="#B45309" if conflicts else "#15803D",wraplength=930)
            warning.pack(anchor="w",padx=12)
            if conflicts:ttk.Label(w,text="\n".join(conflicts[:6]),wraplength=930).pack(anchor="w",padx=12,pady=4)
            decision={"ok":False}
            def accept():decision["ok"]=True;w.destroy()
            buttons=ttk.Frame(w);buttons.pack(fill="x",padx=10,pady=10);ttk.Button(buttons,text=self.tr("Annuler","إلغاء"),command=w.destroy).pack(side="right");ttk.Button(buttons,text=self.tr(f"Importer {len(preview)} article(s)",f"استيراد {len(preview)} منتوج"),style="Primary.TButton",command=accept).pack(side="right",padx=8)
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
                imported_groups={}
                for action,item,target in resolved:
                    _,barcode,name,cat,buy,sell,stock,alert,*meta=item
                    bar_label,mult,pack_price,sku,fraction,product_key=meta
                    if action=="skip":skipped+=1;continue
                    c.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)",(cat,));catid=c.execute("SELECT id FROM categories WHERE name=?",(cat,)).fetchone()[0]
                    if action=="replace":
                        pid=target["id"]
                        if product_key and product_key in imported_groups and imported_groups[product_key]!=pid:
                            raise ValueError(self.tr("Un même product key ne peut pas mettre à jour plusieurs articles existants.","لا يمكن لنفس مفتاح المنتوج تحديث عدة منتجات موجودة."))
                        if product_key:imported_groups[product_key]=pid
                        c.execute("UPDATE products SET name=?,category_id=?,purchase_price_cents=?,sale_price_cents=?,alert_qty=?,sku=?,allow_fraction=? WHERE id=?",(name,catid,buy,sell,alert,sku,fraction,pid))
                        if barcode:c.execute("UPDATE product_barcodes SET label=?,qty_multiplier=?,price_override_cents=? WHERE product_id=? AND barcode=?",(bar_label,mult,pack_price,pid,barcode))
                        set_product_categories(c,pid,[catid])
                        current_stock=float(c.execute("SELECT stock_qty FROM products WHERE id=?",(pid,)).fetchone()[0])
                        if stock is not None and abs(stock-current_stock)>1e-9:
                            apply_stock_movement(c,pid,stock-current_stock,'ADJUSTMENT',buy,'import',pid,'Import Excel — stock compté')
                        audit(c,'PRODUCT_IMPORT_UPDATE',pid);updated+=1
                        continue
                    group_key=product_key or None
                    if action in ("new","shared") and group_key and group_key in imported_groups:
                        pid=imported_groups[group_key]
                        if barcode and not c.execute("SELECT 1 FROM product_barcodes WHERE product_id=? AND barcode=?",(pid,barcode)).fetchone():
                            c.execute("INSERT INTO product_barcodes(product_id,barcode,label,qty_multiplier,price_override_cents) VALUES(?,?,?,?,?)",(pid,barcode,bar_label,mult,pack_price))
                        continue
                    cur=c.execute("INSERT INTO products(name,category_id,purchase_price_cents,sale_price_cents,stock_qty,alert_qty,sku,allow_fraction) VALUES(?,?,?,?,0,?,?,?)",(name,catid,buy,sell,alert,sku,fraction));pid=cur.lastrowid
                    set_product_categories(c,pid,[catid])
                    if group_key:imported_groups[group_key]=pid
                    if barcode:c.execute("INSERT INTO product_barcodes(product_id,barcode,label,qty_multiplier,price_override_cents) VALUES(?,?,?,?,?)",(pid,barcode,bar_label,mult,pack_price))
                    if stock is not None and abs(stock)>1e-9:apply_stock_movement(c,pid,stock,'OPENING',buy,'import',pid,'Import Excel — stock initial')
                    audit(c,'PRODUCT_IMPORT',pid);imported+=1
                c.commit()
            messagebox.showinfo(self.tr("Import Excel","استيراد Excel"),self.tr(f"{imported} ajouté(s), {updated} mis à jour, {skipped} ignoré(s).",f"تمت إضافة {imported}، تحديث {updated}، وتجاهل {skipped}."),parent=self);self.refresh()
        except Exception as e:messagebox.showerror(self.tr("Import Excel","استيراد Excel"),str(e),parent=self)

    def sel(self):
        s=self.t.selection();return int(self.t.item(s[0],"values")[0]) if s else None
    def new(self):ProductEditor(self,on_saved=self.refresh)
    def edit(self):
        if self.sel():ProductEditor(self,self.sel(),self.refresh)
    def add_barcode(self):
        pid=self.sel()
        if not pid:return
        w=tk.Toplevel(self);w.title(self.tr("Barcode / Pack","باركود / حزمة"));w.geometry("460x310");w.transient(self);w.grab_set()
        b=tk.StringVar();mult=tk.StringVar(value="1");price=tk.StringVar()
        f=ttk.Frame(w,padding=18);f.pack(fill="both",expand=True)
        eb=labeled_entry(f,self.tr("Barcode","الباركود"),b,0,bold=True);labeled_entry(f,self.tr("Qté multiplier","مضاعف الكمية"),mult,1);labeled_entry(f,self.tr("Prix pack (optionnel)","ثمن الحزمة (اختياري)"),price,2)
        ttk.Label(f,text=self.tr("Exemple : barcode carton de 6 unités → multiplicateur = 6","مثال: باركود كرتونة 6 قطع → المضاعف = 6")).grid(row=3,column=0,columnspan=2,sticky="w",pady=8)
        def save():
            try:
                code=b.get().strip()
                if not code:raise ValueError(self.tr("Barcode obligatoire","الباركود إجباري"))
                m=float((mult.get() or '1').replace(',','.'));pr=to_cents(price.get()) if price.get().strip() else None
                if not math.isfinite(m) or m<=0 or (pr is not None and pr<0):raise ValueError(self.tr("Pack invalide","الحزمة غير صالحة"))
                add_product_barcode(pid,code,m,pr)
                w.destroy();self.refresh()
            except Exception as e:messagebox.showerror("ToDo",str(e),parent=w)
        ttk.Button(f,text=self.tr("Enregistrer","حفظ"),command=save).grid(row=4,column=0,columnspan=2,pady=15)
        eb.bind("<Return>",lambda e:save());w.after(100,eb.focus_force)
