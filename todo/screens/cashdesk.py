import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from services.cash import get_open_session,open_session,close_session,session_totals,record_cash
from services.money import to_cents,fmt
from database import connect, get_setting

class CashFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=15);self.app=app
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        ttk.Label(self,text=self.tr('Caisse','الصندوق'),font=("Segoe UI",22,"bold")).pack(anchor="w",pady=(0,15))
        self.info=ttk.Label(self,text="",font=("Segoe UI",12));self.info.pack(anchor="w",pady=8)
        self.kpis=ttk.Frame(self);self.kpis.pack(fill="x",pady=8);self.kpi_labels={}
        for key,title in [("expected",self.tr("Cash attendu","النقد المتوقع")),("sales",self.tr("Ventes cash","المبيعات النقدية")),("expenses",self.tr("Dépenses","المصاريف")),("returns",self.tr("Retours cash","المرتجعات النقدية"))]:
            card=ttk.LabelFrame(self.kpis,text=title,padding=8);card.pack(side="left",fill="x",expand=True,padx=3);lbl=ttk.Label(card,text="—",font=("Segoe UI",16,"bold"));lbl.pack();self.kpi_labels[key]=lbl
        b=ttk.Frame(self);b.pack(anchor="w",pady=8)
        ttk.Button(b,text=self.tr('Ouvrir caisse','فتح الصندوق'),command=self.open).pack(side="left",padx=4)
        ttk.Button(b,text=self.tr('Dépense','مصروف'),command=self.expense).pack(side="left",padx=4)
        ttk.Button(b,text=self.tr('Cash IN','إدخال نقدي'),command=lambda:self.cashmove("IN")).pack(side="left",padx=4)
        ttk.Button(b,text=self.tr('Cash OUT','إخراج نقدي'),command=lambda:self.cashmove("OUT")).pack(side="left",padx=4)
        ttk.Button(b,text=self.tr('Clôturer','إغلاق الصندوق'),command=self.close).pack(side="left",padx=4)
        ttk.Button(b,text=self.tr('Historique clôtures','سجل الإغلاقات'),command=self.history).pack(side="left",padx=4)
        self.details=tk.Text(self,height=16,font=("Consolas",11));self.details.pack(fill="x",pady=15);self.refresh()
    def refresh(self):
        s=get_open_session();self.details.config(state="normal");self.details.delete("1.0","end")
        if not s:
            self.info.config(text=self.tr('Aucune caisse ouverte','لا يوجد صندوق مفتوح'))
            for lbl in self.kpi_labels.values():lbl.config(text="—")
            self.details.config(state="disabled");return
        with connect() as c:t=session_totals(c,s["id"])
        expected=int(s["opening_cash_cents"])+t["cash_sales"]-t["cash_returns"]-t["expenses"]+t["cash_in"]-t["cash_out"]
        self.kpi_labels["expected"].config(text=fmt(expected));self.kpi_labels["sales"].config(text=fmt(t["cash_sales"]));self.kpi_labels["expenses"].config(text=fmt(t["expenses"]));self.kpi_labels["returns"].config(text=fmt(t["cash_returns"]))
        self.info.config(text=self.tr(f"Caisse #{s['id']} ouverte depuis {s['opened_at']}",f"الصندوق #{s['id']} مفتوح منذ {s['opened_at']}"))
        txt=self.tr(f"""Fond de caisse : {fmt(s['opening_cash_cents'])}
Ventes cash    : {fmt(t['cash_sales'])}
Retours cash   : {fmt(t['cash_returns'])}
Dépenses       : {fmt(t['expenses'])}
Cash IN        : {fmt(t['cash_in'])}
Cash OUT       : {fmt(t['cash_out'])}
""",f"""رصيد الافتتاح : {fmt(s['opening_cash_cents'])}
المبيعات النقدية : {fmt(t['cash_sales'])}
المرتجعات النقدية : {fmt(t['cash_returns'])}
المصاريف : {fmt(t['expenses'])}
إدخال نقدي : {fmt(t['cash_in'])}
إخراج نقدي : {fmt(t['cash_out'])}
""")
        self.details.insert("1.0",txt);self.details.config(state="disabled")
    def open(self):
        v=simpledialog.askfloat(self.tr("Ouverture","فتح الصندوق"),self.tr("Fond de caisse (DH):","رصيد الافتتاح (DH):"),parent=self,minvalue=0)
        if v is None:return
        try:open_session(self.app.user["id"],to_cents(v));self.refresh()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def expense(self):
        s=get_open_session()
        if not s:messagebox.showerror("ToDo",self.tr("Ouvrez la caisse.","افتح الصندوق أولاً."),parent=self);return
        label=simpledialog.askstring(self.tr("Dépense","مصروف"),self.tr("Libellé:","البيان:"),parent=self)
        if not label:return
        amount=simpledialog.askfloat(self.tr("Dépense","مصروف"),self.tr("Montant (DH):","المبلغ (DH):"),parent=self,minvalue=0.01)
        if amount is None:return
        try:record_cash(s['id'],self.app.user['id'],to_cents(amount),'EXPENSE',label)
        except Exception as e:messagebox.showerror('ToDo',str(e),parent=self);return
        self.refresh()
    def cashmove(self,typ):
        s=get_open_session()
        if not s:return
        amount=simpledialog.askfloat(typ,self.tr("Montant (DH):","المبلغ (DH):"),parent=self,minvalue=0.01)
        if amount is None:return
        note=simpledialog.askstring(typ,self.tr("Note:","ملاحظة:"),parent=self) or ""
        try:record_cash(s['id'],self.app.user['id'],to_cents(amount),typ,note)
        except Exception as e:messagebox.showerror('ToDo',str(e),parent=self);return
        self.refresh()
    def history(self):
        w=tk.Toplevel(self);w.title(self.tr('Historique des clôtures','سجل إغلاقات الصندوق'));w.geometry("1050x560");w.transient(self.winfo_toplevel())
        cols=("id","user","opened","closed","opening","expected","actual","diff")
        tree=ttk.Treeview(w,columns=cols,show="headings")
        cfg=[("id",self.tr("Caisse","الصندوق"),65),("user",self.tr("Caissier","الكاشير"),130),("opened",self.tr("Ouverture","الفتح"),145),("closed",self.tr("Clôture","الإغلاق"),145),("opening",self.tr("Fond","الرصيد"),95),("expected",self.tr("Attendu","المتوقع"),95),("actual",self.tr("Réel","الفعلي"),95),("diff",self.tr("Écart","الفرق"),95)]
        for key,title,width in cfg:tree.heading(key,text=title);tree.column(key,width=width,anchor="center")
        tree.tag_configure("bad",foreground="#DC2626");tree.tag_configure("ok",foreground="#15803D")
        tree.pack(fill="both",expand=True,padx=12,pady=12)
        with connect() as c:
            rows=c.execute("""SELECT cs.*,COALESCE(u.display_name,'?') username FROM cash_sessions cs LEFT JOIN users u ON u.id=cs.user_id WHERE cs.status='CLOSED' ORDER BY cs.id DESC LIMIT 1000""").fetchall()
        total_diff=0
        for r in rows:
            diff=int(r["difference_cents"] or 0);total_diff+=diff;tag="ok" if diff==0 else "bad"
            tree.insert("","end",values=(r["id"],r["username"],r["opened_at"],r["closed_at"],fmt(r["opening_cash_cents"],""),fmt(r["expected_cash_cents"],""),fmt(r["actual_cash_cents"] or 0,""),fmt(diff,"")),tags=(tag,))
        ttk.Label(w,text=self.tr(f"{len(rows)} clôture(s) · Écart cumulé {fmt(total_diff)}",f"{len(rows)} إغلاق · الفرق التراكمي {fmt(total_diff)}"),font=("Segoe UI",11,"bold")).pack(anchor="e",padx=12,pady=(0,12))

    def close(self):
        s=get_open_session()
        if not s:return
        with connect() as c:t=session_totals(c,s["id"])
        expected=int(s["opening_cash_cents"])+t["cash_sales"]-t["cash_returns"]-t["expenses"]+t["cash_in"]-t["cash_out"]
        actual=simpledialog.askfloat(self.tr("Clôture","إغلاق الصندوق"),self.tr(f"Cash attendu : {fmt(expected)}\n\nCash réel compté (DH):",f"النقد المتوقع : {fmt(expected)}\n\nالنقد الفعلي المحسوب (DH):"),parent=self,minvalue=0)
        if actual is None:return
        try:
            expected,diff,t=close_session(s["id"],to_cents(actual))
            messagebox.showinfo(self.tr("Clôture","إغلاق الصندوق"),self.tr(f"Attendu: {fmt(expected)}\nRéel: {actual:.2f} DH\nDifférence: {fmt(diff)}",f"المتوقع: {fmt(expected)}\nالفعلي: {actual:.2f} DH\nالفرق: {fmt(diff)}"),parent=self);self.refresh()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
