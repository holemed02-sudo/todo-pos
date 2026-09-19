import csv
from tkinter import ttk,filedialog,messagebox
from database import connect
from services.money import fmt

class JournalFrame(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=10)
        top=ttk.Frame(self);top.pack(fill="x")
        ttk.Label(top,text="Journal / التقارير",font=("Segoe UI",22,"bold")).pack(side="left")
        ttk.Button(top,text="Export CSV",command=self.export).pack(side="right");ttk.Button(top,text="Actualiser",command=self.refresh).pack(side="right",padx=5)
        cols=("id","ticket","date","cashier","pay","total","cost","margin")
        self.t=ttk.Treeview(self,columns=cols,show="headings")
        for c,h,w in [("id","ID",45),("ticket","Ticket",190),("date","Date",160),("cashier","Caissier",110),("pay","Paiement",90),("total","Total",90),("cost","Coût",90),("margin","Marge brute",100)]:self.t.heading(c,text=h);self.t.column(c,width=w,anchor="center")
        self.t.pack(fill="both",expand=True);self.refresh()
    def rows(self):
        with connect() as c:return c.execute("""SELECT s.id,s.sale_no,s.created_at,u.display_name,s.payment_method,
          s.total_cents-COALESCE((SELECT SUM(r.total_cents) FROM returns r WHERE r.sale_id=s.id),0) total_cents,
          COALESCE((SELECT SUM(si.cost_price_cents*si.qty) FROM sale_items si WHERE si.sale_id=s.id),0)
          -COALESCE((SELECT SUM(ri.qty*si.cost_price_cents) FROM return_items ri JOIN sale_items si ON si.id=ri.sale_item_id WHERE si.sale_id=s.id),0) cost
          FROM sales s JOIN users u ON u.id=s.cashier_user_id ORDER BY s.id DESC LIMIT 5000""").fetchall()
    def refresh(self):
        self.t.delete(*self.t.get_children())
        for r in self.rows():
            margin=int(r["total_cents"]-r["cost"])
            self.t.insert("", "end",values=(r["id"],r["sale_no"],r["created_at"],r["display_name"],r["payment_method"],fmt(r["total_cents"],""),fmt(r["cost"],""),fmt(margin,"")))
    def export(self):
        p=filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")],title="Exporter journal")
        if not p:return
        rows=self.rows()
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            wr=csv.writer(f);wr.writerow(["ID","Ticket","Date","Caissier","Paiement","Total cents","Cost cents","Margin cents"])
            for r in rows:wr.writerow([r["id"],r["sale_no"],r["created_at"],r["display_name"],r["payment_method"],r["total_cents"],r["cost"],r["total_cents"]-r["cost"]])
        messagebox.showinfo("ToDo","Export terminé.",parent=self)
