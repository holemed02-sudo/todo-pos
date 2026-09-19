import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from database import connect
from services.inventory import apply_stock_movement

class StockFrame(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=10)
        top=ttk.Frame(self);top.pack(fill="x",pady=(0,8))
        ttk.Label(top,text="Stock / المخزون",font=("Segoe UI",22,"bold")).pack(side="left")
        ttk.Button(top,text="Ajustement",command=self.adjust).pack(side="right")
        ttk.Button(top,text="Historique",command=self.ledger).pack(side="right",padx=8)
        cols=("id","name","stock","alert","last")
        self.t=ttk.Treeview(self,columns=cols,show="headings")
        for c,h,w in [("id","ID",50),("name","Article",320),("stock","Stock",100),("alert","Alerte",90),("last","Dernier mouvement",220)]:self.t.heading(c,text=h);self.t.column(c,width=w,anchor="center")
        self.t.pack(fill="both",expand=True);self.refresh()
    def refresh(self):
        with connect() as c:r=c.execute("""SELECT p.id,p.name,p.stock_qty,p.alert_qty,
            COALESCE((SELECT movement_type||' '||qty_delta||' @ '||created_at FROM stock_movements sm WHERE sm.product_id=p.id ORDER BY sm.id DESC LIMIT 1),'') last
            FROM products p WHERE p.active=1 ORDER BY p.name""").fetchall()
        self.t.delete(*self.t.get_children())
        for x in r:self.t.insert("", "end",values=(x["id"],x["name"],f"{x['stock_qty']:g}",f"{x['alert_qty']:g}",x["last"]))
    def adjust(self):
        s=self.t.selection()
        if not s:return
        pid=int(self.t.item(s[0],"values")[0]);q=simpledialog.askfloat("Ajustement","Variation (+/-):",parent=self)
        if q is None or q==0:return
        note=simpledialog.askstring("Ajustement","Raison obligatoire:",parent=self) or ""
        if not note.strip():return
        try:
            with connect() as c:c.execute("BEGIN IMMEDIATE");apply_stock_movement(c,pid,q,"ADJUSTMENT",note=note);c.commit()
            self.refresh()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)

    def ledger(self):
        selection=self.t.selection()
        if not selection:return
        pid=int(self.t.item(selection[0],'values')[0])
        w=tk.Toplevel(self);w.title('Historique des mouvements');w.geometry('1050x550');w.transient(self)
        tree=ttk.Treeview(w,columns=('date','user','type','old','delta','new','document','reason'),show='headings')
        for key,label,width in [('date','Date',145),('user','Utilisateur',100),('type','Type',100),('old','Avant',70),('delta','Variation',70),('new','Après',70),('document','Document',100),('reason','Raison',220)]:
            tree.heading(key,text=label);tree.column(key,width=width)
        tree.pack(fill='both',expand=True,padx=12,pady=12)
        with connect() as conn:
            rows=conn.execute("SELECT sm.*,COALESCE(u.display_name,'Historique') username FROM stock_movements sm LEFT JOIN users u ON u.id=sm.user_id WHERE product_id=? ORDER BY sm.id DESC",(pid,)).fetchall()
        for r in rows:
            tree.insert('','end',values=(r['created_at'],r['username'],r['movement_type'],r['old_qty'],r['qty_delta'],r['stock_after'],f"{r['ref_type']} #{r['ref_id'] or ''}",r['note']))
