import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from database import connect
from services.money import to_cents,fmt
from services.purchases import receive_purchase
from services.suppliers import list_suppliers, save_supplier
from screens.suppliers import SupplierEditor

class PurchasesFrame(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=10);self.lines=[]
        top=ttk.Frame(self);top.pack(fill="x")
        ttk.Label(top,text="Réceptions / المشتريات",font=("Segoe UI",22,"bold")).pack(side="left")
        self.supplier=tk.StringVar();self.invoice=tk.StringVar()
        self.supplier_choice=ttk.Combobox(top,textvariable=self.supplier,width=22)
        self.supplier_choice.pack(side="left",padx=(20,5))
        self.supplier_choice.bind('<<ComboboxSelected>>',self.select_supplier)
        self.supplier_id=None
        self.supplier.trace_add('write',lambda *args:setattr(self,'supplier_id',None))
        ttk.Label(top,text="Fournisseur").pack(side="left")
        ttk.Button(top,text='+',width=3,command=lambda:SupplierEditor(self,on_saved=self.refresh_suppliers)).pack(side='left')
        self.refresh_suppliers()
        ttk.Entry(top,textvariable=self.invoice,width=18).pack(side="left",padx=(20,5));ttk.Label(top,text="Facture").pack(side="left")
        body=ttk.Panedwindow(self,orient="horizontal");body.pack(fill="both",expand=True,pady=8)
        p=ttk.Frame(body);body.add(p,weight=2)
        self.q=tk.StringVar();e=ttk.Entry(p,textvariable=self.q);e.pack(fill="x",pady=4);e.bind("<KeyRelease>",lambda x:self.search())
        self.prod=ttk.Treeview(p,columns=("id","name","stock","cost"),show="headings")
        for c,h,w in [("id","ID",50),("name","Article",240),("stock","Stock",80),("cost","Achat",80)]:self.prod.heading(c,text=h);self.prod.column(c,width=w,anchor="center")
        self.prod.pack(fill="both",expand=True);self.prod.bind("<Double-1>",lambda e:self.addline());self.prod.bind("<Return>",lambda e:self.addline());self.search()
        r=ttk.Frame(body);body.add(r,weight=3)
        ttk.Button(r,text="VALIDER réception / تأكيد المشتريات",style="Primary.TButton",command=self.save).pack(side="bottom",fill="x",pady=6)
        self.lines_t=ttk.Treeview(r,columns=("name","qty","cost","total"),show="headings")
        for c,h,w in [("name","Article",230),("qty","Qté",80),("cost","Coût",90),("total","Total",100)]:self.lines_t.heading(c,text=h);self.lines_t.column(c,width=w,anchor="center")
        self.lines_t.pack(fill="both",expand=True)
        line_actions=ttk.Frame(r);line_actions.pack(fill="x",pady=4)
        ttk.Button(line_actions,text="Modifier ligne",command=self.edit_line).pack(side="left")
        ttk.Button(line_actions,text="Supprimer ligne",command=self.remove_line).pack(side="left",padx=6)
        self.total_label=ttk.Label(line_actions,text="Total : 0.00 DH",font=("Segoe UI",12,"bold"));self.total_label.pack(side="right")
    def refresh_suppliers(self, selected=None):
        self.suppliers=list_suppliers()
        self.supplier_choice['values']=[f"{r['name']} · #{r['id']}" for r in self.suppliers]
        if selected is not None:
            index=next(i for i,r in enumerate(self.suppliers) if r['id']==selected)
            self.supplier_choice.current(index)
            self.supplier_id=selected

    def select_supplier(self, event=None):
        index=self.supplier_choice.current()
        self.supplier_id=self.suppliers[index]['id'] if index>=0 else None

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
        total=0
        for x in self.lines:
            line_total=round(x["qty"]*x["unit_cost_cents"]);total+=line_total
            self.lines_t.insert("", "end",values=(x["name"],f"{x['qty']:g}",fmt(x["unit_cost_cents"],""),fmt(line_total,"")))
        self.total_label.configure(text=f"Total : {fmt(total)}")
    def _selected_line_index(self):
        sel=self.lines_t.selection()
        if not sel:return None
        return self.lines_t.index(sel[0])
    def edit_line(self):
        i=self._selected_line_index()
        if i is None:return
        x=self.lines[i]
        qty=simpledialog.askfloat("Qté",f"{x['name']}\nQuantité reçue:",initialvalue=x['qty'],parent=self,minvalue=0.001)
        if qty is None:return
        cost=simpledialog.askfloat("Coût",f"Prix achat unitaire {x['name']}:",initialvalue=x['unit_cost_cents']/100,parent=self,minvalue=0)
        if cost is None:return
        x['qty']=qty;x['unit_cost_cents']=to_cents(cost);self.refresh_lines()
    def remove_line(self):
        i=self._selected_line_index()
        if i is None:return
        del self.lines[i];self.refresh_lines()
    def save(self):
        if not self.lines:return
        supplier_id=self.supplier_id
        sname=self.supplier.get().strip()
        try:
            if sname and supplier_id is None:
                with connect() as c:
                    rows=c.execute("SELECT id FROM suppliers WHERE name=? AND active=1",(sname,)).fetchall()
                if len(rows)>1:
                    raise ValueError('Plusieurs fournisseurs portent ce nom. Choisissez dans la liste.')
                supplier_id=rows[0]['id'] if rows else save_supplier(sname)
                self.refresh_suppliers(supplier_id)
            pid,total=receive_purchase(supplier_id,self.invoice.get().strip(),self.lines)
            messagebox.showinfo("ToDo",f"Réception #{pid}\nTotal: {fmt(total)}",parent=self);self.lines=[];self.refresh_lines();self.search()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
