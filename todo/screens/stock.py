import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from database import connect, get_setting
from services.inventory import apply_stock_movement

class StockFrame(ttk.Frame):
    def __init__(self,master,app=None):
        super().__init__(master,padding=10)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        top=ttk.Frame(self);top.pack(fill="x",pady=(0,8))
        ttk.Label(top,text=self.tr('Stock','المخزون'),font=("Segoe UI",22,"bold")).pack(side="left")
        ttk.Label(self,text=self.tr('Quantités, mouvements et inventaire — nom, prix et photo restent dans Articles.','الكميات والحركات والجرد — تعديل الاسم والثمن والصورة يبقى في المنتجات.'),foreground="#475569").pack(anchor="w",pady=(0,8))
        ttk.Button(top,text=self.tr('Ajustement','تسوية المخزون'),command=self.adjust).pack(side="right")
        self.q=tk.StringVar();self.filter=tk.StringVar(value=self.tr('Tous','الكل'))
        search=ttk.Entry(top,textvariable=self.q,width=24);search.pack(side="left",padx=(20,6));search.bind("<KeyRelease>",lambda e:self.refresh())
        box=ttk.Combobox(top,textvariable=self.filter,values=[self.tr('Tous','الكل'),self.tr('Alertes stock','تنبيهات المخزون'),self.tr('Stock négatif','مخزون سالب')],state="readonly",width=15);box.pack(side="left");box.bind("<<ComboboxSelected>>",lambda e:self.refresh())
        ttk.Button(top,text=self.tr('Historique','السجل'),command=self.ledger).pack(side="right",padx=8)
        if app is not None:
            ttk.Button(top,text=self.tr('Articles','المنتجات'),command=lambda: app.show("products")).pack(side="right",padx=8)
        cols=("id","name","stock","alert","last")
        self.t=ttk.Treeview(self,columns=cols,show="headings")
        for c,h,w in [("id","ID",50),("name","Article",320),("stock","Stock",100),("alert","Alerte",90),("last","Dernier mouvement",220)]:self.t.heading(c,text=h);self.t.column(c,width=w,anchor="center")
        self.t.pack(fill="both",expand=True)
        self.kpi=tk.Frame(self,bg="#F6F7FB");self.kpi.pack(fill="x",pady=(8,0))
        self.kpi_values=[]
        for title,bg in [("Articles","#2563EB"),("Alertes","#F59E0B"),("Stock négatif","#DC2626"),("Valeur achat","#16A34A"),("Valeur vente","#7C3AED")]:
            card=tk.Frame(self.kpi,bg=bg,height=62);card.pack(side="left",fill="x",expand=True,padx=3);card.pack_propagate(False)
            value=tk.Label(card,text="0",bg=bg,fg="white",font=("Segoe UI",15,"bold"));value.pack(anchor="w",padx=10,pady=(5,0));tk.Label(card,text=title,bg=bg,fg="white").pack(anchor="w",padx=10);self.kpi_values.append(value)
        self.refresh()
    def refresh(self):
        q=f"%{self.q.get().strip()}%";extra=""
        if self.filter.get()==self.tr("Alertes stock","تنبيهات المخزون"):extra=" AND p.stock_qty<=p.alert_qty"
        elif self.filter.get()==self.tr("Stock négatif","مخزون سالب"):extra=" AND p.stock_qty<0"
        with connect() as c:
            r=c.execute("""SELECT p.id,p.name,p.stock_qty,p.alert_qty,
                COALESCE((SELECT movement_type||' '||qty_delta||' @ '||created_at FROM stock_movements sm WHERE sm.product_id=p.id ORDER BY sm.id DESC LIMIT 1),'') last
                FROM products p WHERE p.active=1 AND p.name LIKE ?"""+extra+""" ORDER BY p.name""",(q,)).fetchall()
            st=c.execute("""SELECT COUNT(*),COALESCE(SUM(CASE WHEN stock_qty<=alert_qty THEN 1 ELSE 0 END),0),COALESCE(SUM(CASE WHEN stock_qty<0 THEN 1 ELSE 0 END),0),COALESCE(SUM(stock_qty*purchase_price_cents),0),COALESCE(SUM(stock_qty*sale_price_cents),0) FROM products WHERE active=1""").fetchone()
        for label,value in zip(self.kpi_values,[st[0],st[1],st[2],f"{st[3]/100:.2f}",f"{st[4]/100:.2f}"]):label.config(text=str(value))
        self.t.delete(*self.t.get_children())
        for x in r:
            tags=('negative',) if x['stock_qty']<0 else (('alert',) if x['stock_qty']<=x['alert_qty'] else ())
            self.t.insert("", "end",values=(x["id"],x["name"],f"{x['stock_qty']:g}",f"{x['alert_qty']:g}",x["last"]),tags=tags)
        self.t.tag_configure('negative',background='#FEE2E2',foreground='#991B1B');self.t.tag_configure('alert',background='#FEF3C7',foreground='#92400E')
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
