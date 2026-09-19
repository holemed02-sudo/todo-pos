import tkinter as tk, json
from tkinter import ttk, messagebox, simpledialog
from database import connect, get_setting
from services.money import fmt,to_cents
from services.pricing import resolve_line_price
from services.sales import complete_sale,hold_sale,list_held,resume_held
from services.cash import get_open_session
from services.images import abs_image
from services.receipts import build_receipt, print_receipt_windows
try:
    from PIL import Image,ImageTk
    PIL=True
except Exception:
    PIL=False

class SaleFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=8);self.app=app;self.cart=[];self.images=[];self.category=None
        top=ttk.Frame(self);top.pack(fill="x")
        ttk.Label(top,text="VENTE / البيع",font=("Segoe UI",22,"bold")).pack(side="left")
        self.bar=tk.StringVar();self.eb=ttk.Entry(top,textvariable=self.bar,font=("Segoe UI",16),width=25);self.eb.pack(side="left",padx=(20,5),ipady=4);self.eb.bind("<Return>",self.scan)
        ttk.Label(top,text="SCANNER").pack(side="left")
        self.search=tk.StringVar();se=ttk.Entry(top,textvariable=self.search,width=24);se.pack(side="right",padx=4);se.bind("<KeyRelease>",lambda e:self.render_products())
        ttk.Label(top,text="Recherche").pack(side="right")
        body=ttk.Panedwindow(self,orient="horizontal");body.pack(fill="both",expand=True,pady=8)
        # ticket
        lf=ttk.Frame(body);body.add(lf,weight=3)
        cols=("name","qty","unit","total");self.t=ttk.Treeview(lf,columns=cols,show="headings")
        for c,h,w in [("name","Article",240),("qty","Qté",65),("unit","P.U",85),("total","Total",95)]:self.t.heading(c,text=h);self.t.column(c,width=w,anchor="center")
        self.t.pack(fill="both",expand=True)
        qb=ttk.Frame(lf);qb.pack(fill="x",pady=4)
        for txt,cmd in [("-1",lambda:self.change(-1)),("+1",lambda:self.change(1)),("×2",lambda:self.mul(2)),("×3",lambda:self.mul(3)),("Qté",self.set_qty),("Suppr.",self.remove)]:
            ttk.Button(qb,text=txt,command=cmd).pack(side="left",expand=True,fill="x")
        tools=ttk.Frame(lf);tools.pack(fill="x",pady=4)
        ttk.Button(tools,text="Attente",command=self.hold).pack(side="left",expand=True,fill="x")
        ttk.Button(tools,text="Liste attente",command=self.show_held).pack(side="left",expand=True,fill="x")
        ttk.Button(tools,text="Remise",command=self.discount).pack(side="left",expand=True,fill="x")
        self.total=ttk.Label(lf,text="TOTAL 0.00 DH",font=("Segoe UI",24,"bold"));self.total.pack(anchor="e",pady=4)
        pay=ttk.Frame(lf);pay.pack(fill="x")
        ttk.Button(pay,text="CASH",command=lambda:self.checkout("CASH")).pack(side="left",expand=True,fill="x",ipady=8)
        ttk.Button(pay,text="CARTE",command=lambda:self.checkout("CARD")).pack(side="left",expand=True,fill="x",ipady=8)
        # catalog
        rf=ttk.Frame(body);body.add(rf,weight=5)
        self.catbar=ttk.Frame(rf);self.catbar.pack(fill="x",pady=(0,4))
        self.canvas=tk.Canvas(rf,highlightthickness=0);sc=ttk.Scrollbar(rf,orient="vertical",command=self.canvas.yview)
        self.cards=ttk.Frame(self.canvas);self.cards.bind("<Configure>",lambda e:self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0,0),window=self.cards,anchor="nw");self.canvas.configure(yscrollcommand=sc.set);self.canvas.pack(side="left",fill="both",expand=True);sc.pack(side="right",fill="y")
        self.ticket_discount_cents=0
        self.render_categories();self.render_products();self.after(100,self.eb.focus_force)

    def render_categories(self):
        for x in self.catbar.winfo_children():x.destroy()
        with connect() as c:rows=c.execute("SELECT id,name FROM categories WHERE active=1 ORDER BY sort_order,name").fetchall()
        ttk.Button(self.catbar,text="TOUS",command=lambda:self.setcat(None)).pack(side="left",padx=2)
        for r in rows:ttk.Button(self.catbar,text=r["name"],command=lambda x=r["id"]:self.setcat(x)).pack(side="left",padx=2)

    def setcat(self,c):self.category=c;self.render_products();self.eb.focus_force()

    def render_products(self):
        for x in self.cards.winfo_children():x.destroy()
        self.images=[]
        q=f"%{self.search.get().strip()}%"
        with connect() as c:
            if self.category:
                rows=c.execute("SELECT * FROM products WHERE active=1 AND category_id=? AND name LIKE ? ORDER BY name LIMIT 150",(self.category,q)).fetchall()
            else:
                rows=c.execute("SELECT * FROM products WHERE active=1 AND name LIKE ? ORDER BY name LIMIT 150",(q,)).fetchall()
        for i,r in enumerate(rows):
            card=tk.Frame(self.cards,width=150,height=158,bg="white",bd=1,relief="solid");card.grid(row=i//4,column=i%4,padx=5,pady=5);card.grid_propagate(False)
            il=tk.Label(card,text="📦",font=("Segoe UI",24),bg="white");il.pack(fill="both",expand=True)
            if PIL and r["image_path"]:
                p=abs_image(r["image_path"])
                if p:
                    try:
                        im=Image.open(p);im.thumbnail((120,90));ph=ImageTk.PhotoImage(im);self.images.append(ph);il.config(image=ph,text="")
                    except:pass
            tk.Label(card,text=r["name"],wraplength=140,bg="white",font=("Segoe UI",9,"bold")).pack()
            tk.Label(card,text=fmt(r["sale_price_cents"],get_setting("currency","DH")),bg="white").pack()
            def bindall(widget,pid=r["id"]):
                widget.bind("<Button-1>",lambda e:self.add_product(pid,None,1,""))
            bindall(card)
            for ch in card.winfo_children():bindall(ch)

    def scan(self,e=None):
        code=self.bar.get().strip();self.bar.set("")
        if not code:return
        with connect() as c:
            rows=c.execute("""SELECT p.*,b.id barcode_id,b.qty_multiplier,b.price_override_cents,b.barcode
                              FROM product_barcodes b JOIN products p ON p.id=b.product_id
                              WHERE b.barcode=? AND p.active=1 ORDER BY p.name""",(code,)).fetchall()
        if not rows:messagebox.showwarning("ToDo",f"Barcode inconnu: {code}",parent=self)
        elif len(rows)==1:
            r=rows[0];self.add_product(r["id"],r["barcode_id"],r["qty_multiplier"],r["barcode"])
        else:self.pick_ambiguous(rows)
        self.after(50,self.eb.focus_force)

    def pick_ambiguous(self,rows):
        w=tk.Toplevel(self);w.title("نفس الباركود — اختار");w.geometry("620x430");w.transient(self);w.grab_set()
        ttk.Label(w,text="هذا الباركود مربوط بأكثر من منتوج",font=("Segoe UI",13,"bold")).pack(pady=8)
        t=ttk.Treeview(w,columns=("name","price","stock","mult"),show="headings")
        for c,h,wi in [("name","Article",300),("price","Prix",90),("stock","Stock",90),("mult","Pack",70)]:t.heading(c,text=h);t.column(c,width=wi,anchor="center")
        t.pack(fill="both",expand=True,padx=8);mp={}
        for r in rows:
            iid=t.insert("", "end",values=(r["name"],fmt(r["sale_price_cents"]),f"{r['stock_qty']:g}",f"x{r['qty_multiplier']:g}"));mp[iid]=r
        def choose(e=None):
            s=t.selection()
            if s:
                r=mp[s[0]];self.add_product(r["id"],r["barcode_id"],r["qty_multiplier"],r["barcode"]);w.destroy()
        t.bind("<Double-1>",choose);ttk.Button(w,text="Choisir",command=choose).pack(pady=8)

    def _reprice_line(self,x):
        pr=resolve_line_price(x["product_id"],x["qty"],x.get("barcode_id"))
        x.update(pr)

    def add_product(self,pid,barcode_id=None,qty=1,barcode=""):
        with connect() as c:p=c.execute("SELECT * FROM products WHERE id=?",(pid,)).fetchone()
        if not p:return
        # Same product may have a DIFFERENT barcode for unit and carton.
        # Merge only when the product AND the exact barcode rule match.
        for x in self.cart:
            if x["product_id"]==pid and x.get("barcode_id")==barcode_id:
                x["qty"]+=float(qty);self._reprice_line(x);self.refresh();return
        x=dict(product_id=pid,name=p["name"],qty=float(qty),barcode_id=barcode_id,barcode=barcode)
        self._reprice_line(x);self.cart.append(x)
        self.refresh()

    def selected(self):
        s=self.t.selection()
        if not s:return None
        return int(self.t.item(s[0],"tags")[0])

    def change(self,d):
        idx=self.selected()
        if idx is None:return
        x=self.cart[idx]
        step=float(x.get("qty_multiplier",1) or 1) if x.get("pricing_mode")=="PACK" else 1.0
        x["qty"]+=d*step
        if x["qty"]<=0:self.cart.pop(idx)
        else:self._reprice_line(x)
        self.refresh();self.eb.focus_force()

    def mul(self,n):
        idx=self.selected()
        if idx is None:return
        x=self.cart[idx];x["qty"]*=n;self._reprice_line(x);self.refresh();self.eb.focus_force()

    def set_qty(self):
        idx=self.selected()
        if idx is None:return
        x=self.cart[idx]
        if x.get("pricing_mode")=="PACK":
            packs=simpledialog.askfloat("Qté","Nombre de packs/cartons:",parent=self,minvalue=1)
            if packs:
                if abs(packs-round(packs))>1e-9:
                    messagebox.showerror("ToDo","Le nombre de packs/cartons doit être entier.",parent=self)
                else:
                    x["qty"]=round(packs)*float(x.get("qty_multiplier",1) or 1);self._reprice_line(x);self.refresh()
        else:
            q=simpledialog.askfloat("Qté","Quantité:",parent=self,minvalue=0.001)
            if q:
                x["qty"]=q;self._reprice_line(x);self.refresh()
        self.eb.focus_force()

    def remove(self):
        idx=self.selected()
        if idx is not None:self.cart.pop(idx);self.refresh()
        self.eb.focus_force()

    def discount(self):
        v=simpledialog.askfloat("Remise","Remise ticket (DH):",parent=self,minvalue=0)
        if v is not None:self.ticket_discount_cents=to_cents(v);self.refresh()

    def totals(self):
        sub=sum(int(x.get("line_total_cents",0)) for x in self.cart)
        return sub,max(0,sub-self.ticket_discount_cents)

    def refresh(self):
        self.t.delete(*self.t.get_children())
        for idx,x in enumerate(self.cart):
            lt=int(x.get("line_total_cents",0))
            if x.get("pricing_mode")=="PACK":
                mult=float(x.get("qty_multiplier",1) or 1);packs=x["qty"]/mult
                qtxt=f"{packs:g} pack ({x['qty']:g}u)";ptxt=f"{fmt(x['unit_price_cents'],'')}/pack"
            else:
                qtxt=f"{x['qty']:g}";ptxt=fmt(x["unit_price_cents"],"")
            self.t.insert("", "end",values=(x["name"],qtxt,ptxt,fmt(lt,"")),tags=(str(idx),))
        sub,total=self.totals();self.total.config(text=f"TOTAL {fmt(total,get_setting('currency','DH'))}")
        self.app.update_customer_display(self.cart,total)

    def hold(self):
        if not self.cart:return
        label=simpledialog.askstring("Attente","Nom/numéro du ticket:",parent=self) or ""
        hold_sale(self.app.user["id"],self.cart,label);self.cart=[];self.ticket_discount_cents=0;self.refresh();self.eb.focus_force()

    def show_held(self):
        rows=list_held()
        if not rows:messagebox.showinfo("ToDo","Aucun ticket en attente.",parent=self);return
        w=tk.Toplevel(self);w.title("Tickets en attente");w.geometry("550x400");w.transient(self);w.grab_set()
        t=ttk.Treeview(w,columns=("id","label","date"),show="headings")
        for c,h,wi in [("id","ID",60),("label","Label",280),("date","Date",170)]:t.heading(c,text=h);t.column(c,width=wi,anchor="center")
        t.pack(fill="both",expand=True,padx=8,pady=8)
        for r in rows:t.insert("", "end",values=(r["id"],r["label"],r["created_at"]))
        def resume():
            s=t.selection()
            if not s:return
            hid=int(t.item(s[0],"values")[0]);self.cart=resume_held(hid);self.ticket_discount_cents=0;self.refresh();w.destroy()
        ttk.Button(w,text="Reprendre",command=resume).pack(pady=8)

    def checkout(self,method):
        if not self.cart:return
        session=get_open_session()
        if not session:messagebox.showerror("ToDo","خاصك تفتح الكيس أولاً.",parent=self);return
        sub,total=self.totals()
        if method=="CASH":
            paid=simpledialog.askfloat("CASH",f"TOTAL: {fmt(total)}\nMontant reçu:",parent=self,minvalue=0)
            if paid is None:return
            paid_cents=to_cents(paid)
        else:paid_cents=total
        try:
            res=complete_sale(session["id"],self.app.user["id"],self.cart,method,paid_cents,self.ticket_discount_cents)
            txt=build_receipt(res["id"])
            w=tk.Toplevel(self);w.title("Ticket");w.geometry("420x520");w.transient(self)
            tx=tk.Text(w,font=("Consolas",10));tx.pack(fill="both",expand=True);tx.insert("1.0",txt);tx.config(state="disabled")
            b=ttk.Frame(w);b.pack(fill="x");ttk.Button(b,text="Imprimer",command=lambda:print_receipt_windows(res["id"])).pack(side="left",expand=True,fill="x")
            ttk.Button(b,text="Fermer",command=w.destroy).pack(side="left",expand=True,fill="x")
            self.cart=[];self.ticket_discount_cents=0;self.refresh();self.render_products()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
        self.eb.focus_force()
