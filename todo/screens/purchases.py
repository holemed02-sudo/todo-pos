import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from database import connect
from services.money import to_cents,fmt
from services.purchases import receive_purchase

class PurchasesFrame(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=10);self.lines=[]
        top=ttk.Frame(self);top.pack(fill="x")
        ttk.Label(top,text="Réceptions / المشتريات",font=("Segoe UI",22,"bold")).pack(side="left")
        self.supplier=tk.StringVar();self.invoice=tk.StringVar()
        ttk.Entry(top,textvariable=self.supplier,width=22).pack(side="left",padx=(20,5));ttk.Label(top,text="Fournisseur").pack(side="left")
        ttk.Entry(top,textvariable=self.invoice,width=18).pack(side="left",padx=(20,5));ttk.Label(top,text="Facture").pack(side="left")
        body=ttk.Panedwindow(self,orient="horizontal");body.pack(fill="both",expand=True,pady=8)
        p=ttk.Frame(body);body.add(p,weight=2)
        self.q=tk.StringVar();e=ttk.Entry(p,textvariable=self.q);e.pack(fill="x",pady=4);e.bind("<KeyRelease>",lambda x:self.search())
        self.prod=ttk.Treeview(p,columns=("id","name","stock","cost"),show="headings")
        for c,h,w in [("id","ID",50),("name","Article",240),("stock","Stock",80),("cost","Achat",80)]:self.prod.heading(c,text=h);self.prod.column(c,width=w,anchor="center")
        self.prod.pack(fill="both",expand=True);self.prod.bind("<Double-1>",lambda e:self.addline());self.search()
        r=ttk.Frame(body);body.add(r,weight=3)
        self.lines_t=ttk.Treeview(r,columns=("name","qty","cost","total"),show="headings")
        for c,h,w in [("name","Article",230),("qty","Qté",80),("cost","Coût",90),("total","Total",100)]:self.lines_t.heading(c,text=h);self.lines_t.column(c,width=w,anchor="center")
        self.lines_t.pack(fill="both",expand=True)
        ttk.Button(r,text="Valider réception",command=self.save).pack(fill="x",pady=6)
    def search(self):
        q=f"%{self.q.get().strip()}%"
        with connect() as c:r=c.execute("SELECT id,name,stock_qty,purchase_price_cents FROM products WHERE active=1 AND name LIKE ? ORDER BY name LIMIT 100",(q,)).fetchall()
        self.prod.delete(*self.prod.get_children())
        for x in r:self.prod.insert("", "end",values=(x["id"],x["name"],f"{x['stock_qty']:g}",f"{x['purchase_price_cents']/100:.2f}"))
    def addline(self):
        s=self.prod.selection()
        if not s:return
        vals=self.prod.item(s[0],"values");pid=int(vals[0]);name=vals[1]
        qty=simpledialog.askfloat("Qté",f"{name}\nQuantité reçue:",parent=self,minvalue=0.001)
        if qty is None:return
        cost=simpledialog.askfloat("Coût",f"Prix achat unitaire {name}:",parent=self,minvalue=0)
        if cost is None:return
        self.lines.append(dict(product_id=pid,name=name,qty=qty,unit_cost_cents=to_cents(cost)));self.refresh_lines()
    def refresh_lines(self):
        self.lines_t.delete(*self.lines_t.get_children())
        for x in self.lines:self.lines_t.insert("", "end",values=(x["name"],f"{x['qty']:g}",fmt(x["unit_cost_cents"],""),fmt(round(x["qty"]*x["unit_cost_cents"]),"")))
    def save(self):
        if not self.lines:return
        supplier_id=None
        sname=self.supplier.get().strip()
        with connect() as c:
            if sname:
                r=c.execute("SELECT id FROM suppliers WHERE name=?",(sname,)).fetchone()
                if r:supplier_id=r["id"]
                else:
                    cur=c.execute("INSERT INTO suppliers(name) VALUES(?)",(sname,));supplier_id=cur.lastrowid;c.commit()
        try:
            pid,total=receive_purchase(supplier_id,self.invoice.get().strip(),self.lines)
            messagebox.showinfo("ToDo",f"Réception #{pid}\nTotal: {fmt(total)}",parent=self);self.lines=[];self.refresh_lines();self.search()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
