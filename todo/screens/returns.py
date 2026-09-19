import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from database import connect
from services.cash import get_open_session
from services.sales import create_return
from services.money import fmt

class ReturnsFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=10);self.app=app
        top=ttk.Frame(self);top.pack(fill="x")
        ttk.Label(top,text="Retours / المرتجعات",font=("Segoe UI",22,"bold")).pack(side="left")
        self.no=tk.StringVar();e=ttk.Entry(top,textvariable=self.no,width=28);e.pack(side="left",padx=15);e.bind("<Return>",lambda x:self.load())
        ttk.Button(top,text="Chercher ticket",command=self.load).pack(side="left")
        self.info=ttk.Label(self,text="");self.info.pack(anchor="w",pady=8)
        self.t=ttk.Treeview(self,columns=("id","name","sold","returned","available","price"),show="headings")
        for c,h,w in [("id","Line",55),("name","Article",260),("sold","Vendu",75),("returned","Retourné",80),("available","Disponible",85),("price","Prix",90)]:self.t.heading(c,text=h);self.t.column(c,width=w,anchor="center")
        self.t.pack(fill="both",expand=True);ttk.Button(self,text="Retourner ligne sélectionnée",command=self.do_return).pack(fill="x",pady=8)
        self.sale_id=None
    def load(self):
        no=self.no.get().strip()
        with connect() as c:
            s=c.execute("SELECT * FROM sales WHERE sale_no=?",(no,)).fetchone()
            if not s:messagebox.showerror("ToDo","Ticket introuvable.",parent=self);return
            rows=c.execute("""SELECT si.*,
             COALESCE((SELECT SUM(ri.qty) FROM return_items ri WHERE ri.sale_item_id=si.id),0) returned
             FROM sale_items si WHERE si.sale_id=?""",(s["id"],)).fetchall()
        self.sale_id=s["id"];self.info.config(text=f"{s['sale_no']} — {fmt(s['total_cents'])} — {s['created_at']}");self.t.delete(*self.t.get_children())
        for x in rows:self.t.insert("", "end",values=(x["id"],x["name_snapshot"],f"{x['qty']:g}",f"{x['returned']:g}",f"{float(x['qty'])-float(x['returned']):g}",fmt(x["unit_price_cents"],"")))
    def do_return(self):
        if not self.sale_id:return
        s=self.t.selection()
        if not s:return
        vals=self.t.item(s[0],"values");line=int(vals[0]);available=float(vals[4])
        if available<=0:return
        qty=simpledialog.askfloat("Retour","Quantité à retourner:",parent=self,minvalue=0.001,maxvalue=available)
        if qty is None:return
        sess=get_open_session()
        if not sess:messagebox.showerror("ToDo","Ouvrez la caisse.",parent=self);return
        reason=simpledialog.askstring("Retour","Raison:",parent=self) or ""
        try:
            r=create_return(self.sale_id,sess["id"],self.app.user["id"],[(line,qty)],reason)
            messagebox.showinfo("ToDo",f"{r['return_no']}\nRemboursement: {fmt(r['total_cents'])}",parent=self);self.load()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
