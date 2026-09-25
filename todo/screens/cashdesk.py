import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from services.cash import get_open_session,open_session,close_session,session_totals,record_cash
from services.money import to_cents,fmt
from database import connect, get_setting

class CashFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=15);self.app=app
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        ttk.Label(self,text=self.tr('Caisse','الصندوق'),style='Title.TLabel').pack(anchor='w',pady=(0,8))
        self.info=ttk.Label(self,text="",font=("Segoe UI",12));self.info.pack(anchor="w",pady=8)
        self.kpis=ttk.Frame(self);self.kpis.pack(fill="x",pady=8);self.kpi_labels={}
        for key,title in [("expected",self.tr("Cash attendu","النقد المتوقع")),("sales",self.tr("Ventes cash","المبيعات النقدية")),("expenses",self.tr("Dépenses","المصاريف")),("returns",self.tr("Retours cash","المرتجعات النقدية"))]:
            card=ttk.LabelFrame(self.kpis,text=title,padding=8);card.pack(side="left",fill="x",expand=True,padx=3);lbl=ttk.Label(card,text="—",font=("Segoe UI",16,"bold"));lbl.pack();self.kpi_labels[key]=lbl
        b=ttk.Frame(self);b.pack(anchor="w",pady=8)
        ttk.Button(b,text=self.tr('Ouvrir caisse','فتح الصندوق'),style='Success.TButton',command=self.open).pack(side='left',padx=4)
        ttk.Button(b,text=self.tr('Dépense','مصروف'),style='Danger.TButton',command=self.expense).pack(side='left',padx=4)
        ttk.Button(b,text=self.tr('Cash IN','إدخال نقدي'),style='Soft.TButton',command=lambda:self.cashmove('IN')).pack(side='left',padx=4)
        ttk.Button(b,text=self.tr('Cash OUT','إخراج نقدي'),style='Soft.TButton',command=lambda:self.cashmove('OUT')).pack(side='left',padx=4)
        if get_setting('closure_enabled','1')=='1':
            ttk.Button(b,text=self.tr('Clôturer','إغلاق الصندوق'),style='Primary.TButton',command=self.close).pack(side='left',padx=4)
        ttk.Button(b,text=self.tr('Historique clôtures','سجل الإغلاقات'),style='Soft.TButton',command=self.history).pack(side='left',padx=4)
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

    def _count_close_cash(self, expected):
        w=tk.Toplevel(self);w.title(self.tr('Comptage caisse','عدّ الصندوق'));w.transient(self.winfo_toplevel());w.grab_set();w.geometry('560x520')
        ttk.Label(w,text=self.tr('Cash attendu','النقد المتوقع'),font=('Segoe UI',11)).pack(pady=(16,2))
        ttk.Label(w,text=fmt(expected),font=('Segoe UI',24,'bold')).pack()
        counts={};result={'value':None}
        summary=ttk.Label(w,text='',font=('Segoe UI',10));summary.pack(pady=6)
        total_label=ttk.Label(w,text=fmt(0),font=('Segoe UI',22,'bold'));total_label.pack(pady=4)
        grid=ttk.Frame(w);grid.pack(fill='x',padx=16,pady=8)
        values=(200,100,50,20,10,5,2,1,0.5)
        def refresh():
            cents=sum(to_cents(str(v))*n for v,n in counts.items());total_label.config(text=fmt(cents))
            summary.config(text=' · '.join(f'{v:g}×{n}' for v,n in counts.items() if n))
            return cents
        def add(v,delta=1):counts[v]=max(0,counts.get(v,0)+delta);refresh()
        for i,v in enumerate(values):
            box=ttk.Frame(grid);box.grid(row=i//3,column=i%3,sticky='nsew',padx=4,pady=4)
            ttk.Button(box,text=f'+ {v:g} DH',command=lambda x=v:add(x),width=13).pack(fill='x')
            ttk.Button(box,text=self.tr('Retirer','نقص')+f' {v:g}',command=lambda x=v:add(x,-1),width=13).pack(fill='x',pady=(2,0))
        for c in range(3):grid.columnconfigure(c,weight=1)
        def clear():counts.clear();refresh()
        def validate():result['value']=refresh();w.destroy()
        buttons=ttk.Frame(w);buttons.pack(side='bottom',fill='x',padx=16,pady=16)
        ttk.Button(buttons,text=self.tr('Effacer','مسح'),command=clear).pack(side='left')
        ttk.Button(buttons,text=self.tr('Annuler','إلغاء'),command=w.destroy).pack(side='right',padx=6)
        ttk.Button(buttons,text=self.tr('Valider le comptage','تأكيد العد'),style='Primary.TButton',command=validate).pack(side='right')
        w.bind('<Escape>',lambda e:w.destroy());self.wait_window(w)
        return None if result['value'] is None else result['value']/100

    def close(self):
        if get_setting('closure_enabled','1')!='1':
            messagebox.showinfo('ToDo',self.tr('La clôture est désactivée dans les paramètres.','إغلاق الصندوق معطل من الإعدادات.'),parent=self);return
        s=get_open_session()
        if not s:return
        with connect() as c:t=session_totals(c,s["id"])
        expected=int(s["opening_cash_cents"])+t["cash_sales"]-t["cash_returns"]-t["expenses"]+t["cash_in"]-t["cash_out"]
        actual=self._count_close_cash(expected)
        if actual is None:return
        try:
            expected,diff,t=close_session(s["id"],to_cents(actual))
            messagebox.showinfo(self.tr("Clôture","إغلاق الصندوق"),self.tr(f"Attendu: {fmt(expected)}\nRéel: {actual:.2f} DH\nDifférence: {fmt(diff)}",f"المتوقع: {fmt(expected)}\nالفعلي: {actual:.2f} DH\nالفرق: {fmt(diff)}"),parent=self);self.refresh()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
