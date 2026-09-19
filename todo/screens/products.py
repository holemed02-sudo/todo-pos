import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from database import connect
from services.inventory import apply_stock_movement
from services.security import require_admin, audit
import math
from services.money import to_cents
from services.images import import_image, abs_image
from screens.common import labeled_entry
try:
    from PIL import Image,ImageTk
    PIL=True
except Exception:
    PIL=False

class ProductEditor(tk.Toplevel):
    def __init__(self,master,product_id=None,on_saved=None):
        super().__init__(master)
        self.pid=product_id; self.on_saved=on_saved
        self.loaded_stock=0
        self.img_source="";self.img_rel="";self.img_ref=None
        self.title("ToDo — Article");self.geometry("920x790");self.resizable(False,False);self.transient(master);self.grab_set()
        self.sku=tk.StringVar();self.alias=tk.StringVar();self.supplier_code=tk.StringVar();self.fraction=tk.BooleanVar();self.stock_note=tk.StringVar()
        self.bar=tk.StringVar();self.name=tk.StringVar();self.cat=tk.StringVar()
        self.buy=tk.StringVar(value="0");self.sell=tk.StringVar(value="0");self.stock=tk.StringVar(value="0");self.alert=tk.StringVar(value="0")
        root=ttk.Frame(self,padding=15);root.pack(fill="both",expand=True)
        left=ttk.Frame(root);left.pack(side="left",fill="both",expand=True,padx=(0,18))
        right=ttk.LabelFrame(root,text="Image produit",padding=8);right.pack(side="right",fill="y")
        self.e_bar=labeled_entry(left,"CODE-BARRES / الباركود",self.bar,0,bold=True)
        self.e_name=labeled_entry(left,"Article / المنتوج",self.name,1)
        self.e_cat=labeled_entry(left,"Famille",self.cat,2)
        ttk.Button(left,text="+ Famille",command=self.add_category).grid(row=2,column=2,padx=6)
        self.e_buy=labeled_entry(left,"Prix achat",self.buy,3)
        self.e_sell=labeled_entry(left,"Prix vente",self.sell,4)
        self.e_stock=labeled_entry(left,"Stock",self.stock,5)
        self.e_alert=labeled_entry(left,"Alerte stock",self.alert,6)
        left.columnconfigure(1,weight=1)
        self.e_bar.bind("<Return>",lambda e:self.e_name.focus_set())
        chain=[(self.e_name,self.e_cat),(self.e_cat,self.e_buy),(self.e_buy,self.e_sell),(self.e_sell,self.e_stock),(self.e_stock,self.e_alert)]
        for a,b in chain:a.bind("<Return>",lambda e,n=b:n.focus_set())
        ttk.Label(left,text="Promotions et prix par quantité",font=("Segoe UI",10,"bold")).grid(row=7,column=0,columnspan=2,sticky="w",pady=(16,4))
        self.offer_rows=[]
        self.offers_frame=ttk.Frame(left);self.offers_frame.grid(row=8,column=0,columnspan=2,sticky="ew")
        self.add_offer_row()
        ttk.Button(left,text="+ Ajouter une offre",command=self.add_offer_row).grid(row=9,column=0,columnspan=2,sticky="w",pady=4)
        ttk.Label(left,text="Les prix sont saisis comme par le caissier : quantité minimale et prix unitaire.").grid(row=10,column=0,columnspan=2,sticky="w",pady=6)
        b=ttk.Frame(left);b.grid(row=11,column=0,columnspan=2,sticky="e",pady=16)
        ttk.Button(b,text="Enregistrer",command=self.save).pack(side="left",padx=4)
        ttk.Button(b,text="Annuler",command=self.destroy).pack(side="left")
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

        self.after(100,self.e_bar.focus_force)

    def add_offer_row(self, minimum="", price=""):
        row=ttk.Frame(self.offers_frame);row.pack(fill="x",pady=2)
        minimum_var=tk.StringVar(value=str(minimum));price_var=tk.StringVar(value=str(price))
        ttk.Label(row,text="Dès",width=6).pack(side="left")
        ttk.Entry(row,textvariable=minimum_var,width=9).pack(side="left",padx=4)
        ttk.Label(row,text="unités : prix",width=14).pack(side="left")
        ttk.Entry(row,textvariable=price_var,width=12).pack(side="left",padx=4)
        def remove():
            if len(self.offer_rows)>1:
                row.destroy();self.offer_rows.remove((minimum_var,price_var))
        ttk.Button(row,text="×",width=3,command=remove).pack(side="left")
        self.offer_rows.append((minimum_var,price_var))

    def read_offers(self):
        values=[]
        for minimum_var,price_var in self.offer_rows:
            if not minimum_var.get().strip() and not price_var.get().strip():continue
            q=float(minimum_var.get());price=to_cents(price_var.get())
            if not math.isfinite(q) or q<=0 or price<0:raise ValueError("Offre invalide")
            values.append((q,price))
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
                conn.execute("INSERT OR IGNORE INTO categories(name) VALUES(?)",(name,));conn.commit()
            self.cat.set(name);self.e_cat.focus_set()
        except Exception as error:
            messagebox.showerror("ToDo",str(error),parent=self)

    def preview_image(self,p):
        if not PIL:return
        try:
            im=Image.open(p);im.thumbnail((230,230));self.img_ref=ImageTk.PhotoImage(im);self.preview.config(image=self.img_ref,text="",width=230,height=230)
        except:pass

    def load(self):
        with connect() as c:
            p=c.execute("""SELECT p.*,COALESCE(cat.name,'') category FROM products p LEFT JOIN categories cat ON cat.id=p.category_id WHERE p.id=?""",(self.pid,)).fetchone()
            b=c.execute("SELECT barcode FROM product_barcodes WHERE product_id=? ORDER BY id LIMIT 1",(self.pid,)).fetchone()
            rs=c.execute("SELECT min_qty,unit_price_cents FROM quantity_prices WHERE product_id=? ORDER BY min_qty",(self.pid,)).fetchall()
        self.sku.set(p["sku"]);self.alias.set(p["alias"]);self.supplier_code.set(p["supplier_code"]);self.fraction.set(bool(p["allow_fraction"]))
        self.bar.set(b["barcode"] if b else "");self.name.set(p["name"]);self.cat.set(p["category"])
        self.buy.set(f"{p['purchase_price_cents']/100:.2f}");self.sell.set(f"{p['sale_price_cents']/100:.2f}")
        self.stock.set(f"{p['stock_qty']:g}");self.alert.set(f"{p['alert_qty']:g}");self.img_rel=p["image_path"] or ""
        self.loaded_stock=float(p['stock_qty'])
        for child in self.offers_frame.winfo_children():child.destroy()
        self.offer_rows=[]
        for r in rs:self.add_offer_row(r['min_qty'],f"{r['unit_price_cents']/100:.2f}")
        if not self.offer_rows:self.add_offer_row()
        q=abs_image(self.img_rel)
        if q:self.preview_image(q)

    def save(self):
        try:
            barcode=self.bar.get().strip();name=self.name.get().strip()
            if not barcode:raise ValueError("سكانِي الباركود أولاً.")
            if not name:raise ValueError("اسم المنتوج إجباري.")
            buy=to_cents(self.buy.get());sell=to_cents(self.sell.get());stock=float(self.stock.get() or 0);alert=float(self.alert.get() or 0)
            if not all(math.isfinite(x) for x in (stock,alert)) or min(buy,sell,alert)<0:
                raise ValueError('Valeurs invalides')
            cat=self.cat.get().strip() or "Général"
            rules=self.read_offers()
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
                old=c.execute('SELECT stock_qty FROM products WHERE id=?',(pid,)).fetchone()[0]
                if abs(stock-self.loaded_stock)>1e-9 and abs(stock-old)>1e-9:
                    apply_stock_movement(c,pid,stock-old,'ADJUSTMENT' if self.pid else 'OPENING',buy,'product',pid,self.stock_note.get().strip() or ('Correction depuis la fiche produit' if self.pid else 'Stock initial'))
                c.execute('UPDATE products SET sku=?,alias=?,supplier_code=?,allow_fraction=? WHERE id=?',(self.sku.get().strip(),self.alias.get().strip(),self.supplier_code.get().strip(),int(self.fraction.get()),pid))
                audit(c,'PRODUCT_SAVE',pid)
                first=c.execute("SELECT id FROM product_barcodes WHERE product_id=? ORDER BY id LIMIT 1",(pid,)).fetchone()
                if first:c.execute("UPDATE product_barcodes SET barcode=? WHERE id=?",(barcode,first["id"]))
                else:c.execute("INSERT INTO product_barcodes(product_id,barcode) VALUES(?,?)",(pid,barcode))
                c.execute("DELETE FROM quantity_prices WHERE product_id=?",(pid,))
                c.executemany("INSERT INTO quantity_prices(product_id,min_qty,unit_price_cents) VALUES(?,?,?)",[(pid,q,p) for q,p in rules])
                c.commit()
            if self.on_saved:self.on_saved()
            self.destroy()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)

class ProductsFrame(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=10)
        self.page=0
        top=ttk.Frame(self);top.pack(fill="x",pady=(0,8))
        ttk.Label(top,text="Articles / المنتجات",font=("Segoe UI",20,"bold")).pack(side="left")
        self.q=tk.StringVar();e=ttk.Entry(top,textvariable=self.q,width=32);e.pack(side="left",padx=15);e.bind("<KeyRelease>",lambda x:self.go_page(0))
        ttk.Button(top,text="+ Nouveau",command=self.new).pack(side="right",padx=3)
        ttk.Button(top,text="Modifier",command=self.edit).pack(side="right",padx=3)
        ttk.Button(top,text="+ Barcode / Pack",command=self.add_barcode).pack(side="right",padx=3)
        cols=("id","barcode","name","cat","buy","sell","stock","alert","img")
        self.t=ttk.Treeview(self,columns=cols,show="headings")
        cfg=[("id","ID",50),("barcode","Barcode",145),("name","Article",260),("cat","Famille",130),("buy","Achat",85),("sell","Vente",85),("stock","Stock",80),("alert","Alerte",80),("img","Img",45)]
        for c,h,w in cfg:self.t.heading(c,text=h);self.t.column(c,width=w,anchor="center")
        self.t.pack(fill="both",expand=True);self.t.bind("<Double-1>",lambda e:self.edit())
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
            rows=c.execute("""SELECT p.*,COALESCE(cat.name,'') category,
                (SELECT barcode FROM product_barcodes b WHERE b.product_id=p.id ORDER BY id LIMIT 1) barcode
                FROM products p LEFT JOIN categories cat ON cat.id=p.category_id
                WHERE p.active=1 AND (p.name LIKE ? OR cat.name LIKE ? OR EXISTS(SELECT 1 FROM product_barcodes b2 WHERE b2.product_id=p.id AND b2.barcode LIKE ?))
                ORDER BY p.name LIMIT 200 OFFSET ?""",(q,q,q,self.page*200)).fetchall()
        self.page_label.config(text=f'Page {self.page+1} · {len(rows)} produits · 200 par page')
        self.t.delete(*self.t.get_children())
        for r in rows:self.t.insert("", "end",values=(r["id"],r["barcode"] or "",r["name"],r["category"],f"{r['purchase_price_cents']/100:.2f}",f"{r['sale_price_cents']/100:.2f}",f"{r['stock_qty']:g}",f"{r['alert_qty']:g}","✓" if r["image_path"] else ""))
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
