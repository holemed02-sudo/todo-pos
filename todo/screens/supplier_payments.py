"""screens/supplier_payments.py — Règlements fournisseurs + état crédits."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from services.money import fmt, to_cents
from database import get_setting
from services.supplier_payments import (
    add_supplier_payment, list_supplier_payments,
    supplier_credit_statement, supplier_purchases,
)
from services.suppliers import list_suppliers


class SupplierPaymentsWindow(tk.Toplevel):
    """Règlements d'un fournisseur: factures à gauche, paiements à droite."""
    def __init__(self, master, supplier):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.supplier = supplier
        self.title(f"{self.tr('Règlements','التسديدات')} — {supplier['name']}")
        self.geometry('860x500')
        self.transient(master.winfo_toplevel())
        self._build()

    def _build(self):
        top = ttk.Frame(self, padding=(16, 10, 16, 0)); top.pack(fill='x')
        self.lbl_balance = ttk.Label(top, font=('Segoe UI', 14, 'bold'))
        self.lbl_balance.pack(side='left')
        ttk.Button(top, text=self.tr('+ Ajouter règlement','+ إضافة تسديد'), style='Primary.TButton',
                   command=self._add).pack(side='right')

        paned = ttk.Panedwindow(self, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=16, pady=10)

        lf = ttk.LabelFrame(paned, text=self.tr('Achats','الفواتير'), padding=6)
        paned.add(lf, weight=3)
        self.pur_tree = ttk.Treeview(lf,
            columns=('inv','date','total','paid','balance'), show='headings', height=14)
        for col,lbl,w,anc in [('inv','Facture',120,'w'),('date','Date',120,'w'),
                               ('total','Montant',90,'e'),('paid','Payé',90,'e'),('balance','Reste',90,'e')]:
            self.pur_tree.heading(col, text=lbl); self.pur_tree.column(col, width=w, anchor=anc)
        self.pur_tree.tag_configure('settled', foreground='#16a34a')
        self.pur_tree.tag_configure('partial', foreground='#d97706')
        self.pur_tree.tag_configure('unpaid',  foreground='#dc2626')
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.pur_tree.yview)
        sb.pack(side='right', fill='y')
        self.pur_tree.configure(yscrollcommand=sb.set); self.pur_tree.pack(fill='both', expand=True)

        rf = ttk.LabelFrame(paned, text=self.tr('Paiements effectués','التسديدات المنجزة'), padding=6)
        paned.add(rf, weight=2)
        self.pay_tree = ttk.Treeview(rf, columns=('date','amount','note'), show='headings', height=14)
        for col,lbl,w in [('date',self.tr('Date','التاريخ'),120),('amount',self.tr('Montant','المبلغ'),90),('note',self.tr('Note','ملاحظة'),180)]:
            self.pay_tree.heading(col, text=lbl); self.pay_tree.column(col, width=w, anchor='e' if col=='amount' else 'w')
        sb2 = ttk.Scrollbar(rf, orient='vertical', command=self.pay_tree.yview)
        sb2.pack(side='right', fill='y')
        self.pay_tree.configure(yscrollcommand=sb2.set); self.pay_tree.pack(fill='both', expand=True)
        self._refresh()

    def _refresh(self):
        from database import connect
        with connect() as conn:
            billed = conn.execute('SELECT COALESCE(SUM(total_cents),0) FROM purchases WHERE supplier_id=?',
                                   (self.supplier['id'],)).fetchone()[0]
            paid   = conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM supplier_payments WHERE supplier_id=?',
                                   (self.supplier['id'],)).fetchone()[0]
        balance = billed - paid
        self.lbl_balance.config(
            text=self.tr(f"Solde dû : {fmt(balance)}",f"الرصيد المستحق: {fmt(balance)}"),
            foreground='#dc2626' if balance > 0 else '#16a34a')

        self.pur_tree.delete(*self.pur_tree.get_children())
        for p in supplier_purchases(self.supplier['id']):
            bal = p['total_cents'] - p['paid']
            tag = 'settled' if bal <= 0 else ('partial' if p['paid'] > 0 else 'unpaid')
            self.pur_tree.insert('', 'end', iid=str(p['id']),
                values=(p['supplier_invoice'] or '—', p['created_at'][:16],
                        fmt(p['total_cents']), fmt(p['paid']), fmt(bal)), tags=(tag,))

        self.pay_tree.delete(*self.pay_tree.get_children())
        for p in list_supplier_payments(self.supplier['id']):
            self.pay_tree.insert('', 'end',
                values=(p['created_at'][:16], fmt(p['amount_cents']), p['note'] or ''))

    def _add(self):
        purchase_id = None
        sel = self.pur_tree.selection()
        if sel: purchase_id = int(sel[0])
        amount_str = simpledialog.askstring(self.tr('Règlement','تسديد'), self.tr('Montant payé (DH) :','المبلغ المؤدى (DH):'), parent=self)
        if amount_str is None: return
        note = simpledialog.askstring(self.tr('Règlement','تسديد'), self.tr('Note (facultatif) :','ملاحظة (اختيارية):'), parent=self) or ''
        try:
            add_supplier_payment(self.supplier['id'], to_cents(amount_str), note, purchase_id)
            self._refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror(self.tr('Règlement','تسديد'), str(e), parent=self)


class SupplierCreditStateWindow(tk.Toplevel):
    """État des crédits fournisseurs — ce qu'on doit."""
    def __init__(self, master):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.title(self.tr('État crédits fournisseurs','حالة ديون الموردين'))
        self.geometry('720x440')
        self.transient(master.winfo_toplevel())
        self._build()

    def _build(self):
        top = ttk.Frame(self, padding=(16, 12, 16, 0)); top.pack(fill='x')
        ttk.Label(top, text=self.tr('Fournisseurs avec solde impayé','موردون برصيد غير مؤدى'),
                  font=('Segoe UI', 14, 'bold')).pack(side='left')
        ttk.Button(top, text=self.tr('↺ Actualiser','↺ تحديث'), command=self._refresh).pack(side='right')

        self.tree = ttk.Treeview(self,
            columns=('name','phone','billed','paid','balance'), show='headings')
        for col,lbl,w,anc in [
            ('name',   'Fournisseur',   200, 'w'),
            ('phone',  'Téléphone',     130, 'w'),
            ('billed', 'Total achats',  110, 'e'),
            ('paid',   'Total payé',    110, 'e'),
            ('balance','Solde dû',      110, 'e'),
        ]:
            self.tree.heading(col, text=lbl); self.tree.column(col, width=w, anchor=anc)
        self.tree.tag_configure('high',   foreground='#dc2626')
        self.tree.tag_configure('medium', foreground='#d97706')
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set); self.tree.pack(fill='both', expand=True, padx=16, pady=10)
        self.lbl_total = ttk.Label(self, font=('Segoe UI', 11))
        self.lbl_total.pack(anchor='e', padx=16, pady=(0,12))
        self._refresh()

    def _refresh(self):
        rows = supplier_credit_statement()
        self.tree.delete(*self.tree.get_children())
        grand = 0
        for r in rows:
            bal = r['balance_cents']; grand += bal
            tag = 'high' if bal > 50000 else 'medium'
            self.tree.insert('', 'end',
                values=(r['name'], r['phone'],
                        fmt(r['billed_cents']), fmt(r['paid_cents']), fmt(bal)),
                tags=(tag,))
        self.lbl_total.config(text=self.tr(f"Total dû : {fmt(grand)}",f"إجمالي المستحق: {fmt(grand)}"))


class SupplierReglementFrame(ttk.Frame):
    """Page principale règlements fournisseurs."""
    def __init__(self, master):
        super().__init__(master, padding=16)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        ttk.Label(self, text=self.tr('Règlements fournisseurs','تسديدات الموردين'),
                  style='Title.TLabel').pack(anchor='w')

        toolbar = ttk.Frame(self); toolbar.pack(fill='x', pady=10)
        self.query = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.query)
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<KeyRelease>', lambda e: self.refresh())
        ttk.Button(toolbar, text=self.tr('Règlements','التسديدات'),    command=self.payments).pack(side='left', padx=4)
        ttk.Button(toolbar, text=self.tr('État crédits','حالة الديون'),  command=self.credit_state).pack(side='left', padx=4)

        self.tree = ttk.Treeview(self,
            columns=('name','phone','billed','paid','balance'), show='headings')
        for col,lbl,w,anc in [
            ('name',    'Fournisseur',  230, 'w'),
            ('phone',   'Téléphone',   140, 'w'),
            ('billed',  'Achats',        95, 'e'),
            ('paid',    'Payé',          95, 'e'),
            ('balance', 'Solde',         95, 'e'),
        ]:
            self.tree.heading(col, text=lbl); self.tree.column(col, width=w, anchor=anc)
        self.tree.tag_configure('debt',    foreground='#dc2626')
        self.tree.tag_configure('settled', foreground='#16a34a')
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set); self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda e: self.payments())
        self.refresh()

    def refresh(self):
        from database import connect
        q = self.query.get().strip()
        with connect() as conn:
            rows = conn.execute("""
                SELECT s.id, s.name, s.phone,
                       COALESCE(b.billed,0) billed_cents,
                       COALESCE(p.paid,0)   paid_cents
                FROM suppliers s
                LEFT JOIN (SELECT supplier_id,SUM(total_cents) billed FROM purchases GROUP BY supplier_id) b ON b.supplier_id=s.id
                LEFT JOIN (SELECT supplier_id,SUM(amount_cents) paid FROM supplier_payments GROUP BY supplier_id) p ON p.supplier_id=s.id
                WHERE s.active=1 AND (instr(lower(s.name),lower(?))>0 OR instr(s.phone,?)>0)
                ORDER BY s.name
            """, (q,q)).fetchall()
        self.rows = {str(r['id']): dict(r) for r in rows}
        self.tree.delete(*self.tree.get_children())
        for key, r in self.rows.items():
            bal = r['billed_cents'] - r['paid_cents']
            self.tree.insert('', 'end', iid=key,
                values=(r['name'], r['phone'],
                        fmt(r['billed_cents']), fmt(r['paid_cents']), fmt(bal)),
                tags=('debt' if bal > 0 else 'settled',))

    def _selected(self):
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def payments(self):
        s = self._selected()
        if not s: messagebox.showinfo(self.tr('Règlements','التسديدات'), self.tr('Sélectionnez un fournisseur.','اختر مورداً.'), parent=self); return
        SupplierPaymentsWindow(self, s)

    def credit_state(self):
        SupplierCreditStateWindow(self)
