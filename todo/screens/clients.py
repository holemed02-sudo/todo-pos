"""screens/clients.py — Clients, règlements et état des crédits."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from database import connect, get_setting
from services.clients import (
    save_client, list_clients, get_client, deactivate_client,
    add_payment, list_payments, client_sales, credit_statement,
)
from services.money import fmt


# ── Éditeur client ────────────────────────────────────────────────────────────

class ClientEditor(tk.Toplevel):
    def __init__(self, master, client=None, on_saved=None):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.title(self.tr('Client','زبون'))
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.client_id = client['id'] if client else None
        self.on_saved  = on_saved
        self.name  = tk.StringVar(value=(client or {}).get('name',  ''))
        self.phone = tk.StringVar(value=(client or {}).get('phone', ''))
        form = ttk.Frame(self, padding=20)
        form.pack(fill='both', expand=True)
        for row, (label, var) in enumerate([
            (self.tr('Nom','الاسم'), self.name),
            (self.tr('Téléphone','الهاتف'), self.phone),
        ]):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', pady=8)
            ttk.Entry(form, textvariable=var, width=36).grid(row=row, column=1, padx=12)
        ttk.Label(form, text=self.tr('Notes','ملاحظات')).grid(row=2, column=0, sticky='nw')
        self.notes = tk.Text(form, width=36, height=4)
        self.notes.grid(row=2, column=1, padx=12)
        self.notes.insert('1.0', (client or {}).get('notes', ''))
        ttk.Button(form, text=self.tr('Enregistrer','حفظ'), style='Primary.TButton',
                   command=self.save).grid(row=3, column=1, sticky='ew', padx=12, pady=16)
        ttk.Button(form, text=self.tr('Annuler','إلغاء'), command=self.destroy).grid(row=3, column=0)

    def save(self):
        try:
            cid = save_client(self.name.get(), self.phone.get(),
                              self.notes.get('1.0', 'end-1c'), self.client_id)
        except (ValueError, PermissionError) as e:
            messagebox.showerror('Client', str(e), parent=self); return
        self.destroy()
        if self.on_saved: self.on_saved(cid)


# ── Règlements (paiements reçus) ──────────────────────────────────────────────

class PaymentsWindow(tk.Toplevel):
    def __init__(self, master, client):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.client   = client
        self.currency = 'DH'
        self.title(f"{self.tr('Règlements','التسديدات')} — {client['name']}")
        self.geometry('820x520')
        self.transient(master.winfo_toplevel())
        self._build()

    def _build(self):
        top = ttk.Frame(self, padding=(16, 12, 16, 0))
        top.pack(fill='x')
        self.lbl_balance = ttk.Label(top, font=('Segoe UI', 14, 'bold'))
        self.lbl_balance.pack(side='left')
        ttk.Button(top, text=self.tr('+ Ajouter un règlement','+ إضافة تسديد'), style='Primary.TButton',
                   command=self._add).pack(side='right')

        paned = ttk.Panedwindow(self, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=16, pady=12)

        # Left: sales
        lf = ttk.LabelFrame(paned, text=self.tr('Ventes','الفواتير'), padding=8)
        paned.add(lf, weight=3)
        self.sales_tree = ttk.Treeview(lf,
            columns=('no', 'date', 'total', 'paid', 'balance'),
            show='headings', height=14)
        for col, label, w in [
            ('no','Ticket',110),('date','Date',130),
            ('total','Montant',90),('paid','Payé',90),('balance','Reste',90),
        ]:
            self.sales_tree.heading(col, text=label)
            self.sales_tree.column(col, width=w, anchor='e' if w==90 else 'w')
        self.sales_tree.tag_configure('settled', foreground='#16a34a')
        self.sales_tree.tag_configure('partial', foreground='#d97706')
        self.sales_tree.tag_configure('unpaid',  foreground='#dc2626')
        sb = ttk.Scrollbar(lf, orient='vertical', command=self.sales_tree.yview)
        sb.pack(side='right', fill='y')
        self.sales_tree.configure(yscrollcommand=sb.set)
        self.sales_tree.pack(fill='both', expand=True)

        # Right: payments
        rf = ttk.LabelFrame(paned, text=self.tr('Paiements reçus','التسديدات'), padding=8)
        paned.add(rf, weight=2)
        self.pay_tree = ttk.Treeview(rf,
            columns=('date', 'amount', 'note'), show='headings', height=14)
        for col, label, w in [('date',self.tr('Date','التاريخ'),120),('amount',self.tr('Montant','المبلغ'),90),('note',self.tr('Note','ملاحظة'),180)]:
            self.pay_tree.heading(col, text=label)
            self.pay_tree.column(col, width=w, anchor='e' if col=='amount' else 'w')
        sb2 = ttk.Scrollbar(rf, orient='vertical', command=self.pay_tree.yview)
        sb2.pack(side='right', fill='y')
        self.pay_tree.configure(yscrollcommand=sb2.set)
        self.pay_tree.pack(fill='both', expand=True)

        self._refresh()

    def _refresh(self):
        c = get_client(self.client['id'])
        balance = c['billed_cents'] - c['paid_cents']
        self.lbl_balance.config(
            text=f"{self.tr('Solde dû','الرصيد المستحق')} : {fmt(balance, self.currency)}",
            foreground='#dc2626' if balance > 0 else '#16a34a')

        self.sales_tree.delete(*self.sales_tree.get_children())
        for s in client_sales(self.client['id']):
            bal = s['total_cents'] - s['paid']
            tag = 'settled' if bal <= 0 else ('partial' if s['paid'] > 0 else 'unpaid')
            self.sales_tree.insert('', 'end', iid=str(s['id']),
                values=(s['sale_no'], s['created_at'][:16],
                        fmt(s['total_cents'], ''), fmt(s['paid'], ''), fmt(bal, '')),
                tags=(tag,))

        self.pay_tree.delete(*self.pay_tree.get_children())
        for p in list_payments(self.client['id']):
            self.pay_tree.insert('', 'end',
                values=(p['created_at'][:16], fmt(p['amount_cents'], ''), p['note'] or ''))

    def _add(self):
        # Use selected sale if any, otherwise global payment
        sale_id = None
        sel = self.sales_tree.selection()
        if sel:
            sale_id = int(sel[0])
        amount_str = simpledialog.askstring(
            self.tr('Règlement','التسديد'), self.tr('Montant reçu en espèces (DH) :','المبلغ المقبوض نقداً (DH):'), parent=self)
        if amount_str is None: return
        note = simpledialog.askstring(self.tr('Règlement','التسديد'), self.tr('Note (facultatif) :','ملاحظة (اختيارية):'), parent=self) or ''
        try:
            from services.money import to_cents
            add_payment(self.client['id'], to_cents(amount_str), note, sale_id)
            self._refresh()
        except (ValueError, PermissionError) as e:
            messagebox.showerror(self.tr('Règlement','التسديد'), str(e), parent=self)


# ── État des crédits ──────────────────────────────────────────────────────────

class CreditStateWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.title(self.tr('État des crédits clients','حالة ديون الزبائن'))
        self.geometry('720x460')
        self.transient(master.winfo_toplevel())
        self._build()

    def _build(self):
        top = ttk.Frame(self, padding=(16, 12, 16, 0))
        top.pack(fill='x')
        ttk.Label(top, text=self.tr('Clients avec solde impayé','زبائن برصيد غير مؤدى'), font=('Segoe UI', 14, 'bold')).pack(side='left')
        ttk.Button(top, text=self.tr('Actualiser ↺','تحديث ↺'), command=self._refresh).pack(side='right')

        self.tree = ttk.Treeview(self,
            columns=('name', 'phone', 'billed', 'paid', 'balance'),
            show='headings')
        for col, label, w, anchor in [
            ('name',    'Client',         200, 'w'),
            ('phone',   'Téléphone',      130, 'w'),
            ('billed',  'Total facturé',  110, 'e'),
            ('paid',    'Total payé',     110, 'e'),
            ('balance', 'Solde dû',       110, 'e'),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, anchor=anchor)
        self.tree.tag_configure('high',   foreground='#dc2626')
        self.tree.tag_configure('medium', foreground='#d97706')
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill='both', expand=True, padx=16, pady=12)

        self.lbl_total = ttk.Label(self, font=('Segoe UI', 11))
        self.lbl_total.pack(anchor='e', padx=16, pady=(0, 12))
        self._refresh()

    def _refresh(self):
        rows = credit_statement()
        self.tree.delete(*self.tree.get_children())
        grand = 0
        for r in rows:
            bal = r['balance_cents']
            grand += bal
            tag = 'high' if bal > 50000 else 'medium'   # >500 DH = red
            self.tree.insert('', 'end',
                values=(r['name'], r['phone'],
                        fmt(r['billed_cents'], ''), fmt(r['paid_cents'], ''), fmt(bal, '')),
                tags=(tag,))
        self.lbl_total.config(text=f"Total dû global : {fmt(grand, 'DH')}")


# ── Écran principal clients ───────────────────────────────────────────────────

class ClientsFrame(ttk.Frame):
    def __init__(self, master, app=None):
        super().__init__(master, padding=16)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.app = app
        ttk.Label(self, text=self.tr('Clients','الزبائن'), style='Title.TLabel').pack(anchor='w')

        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', pady=12)
        self.query = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.query)
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<KeyRelease>', lambda e: self.refresh())

        for label, cmd in [
            ('Nouveau',          lambda: ClientEditor(self, on_saved=self.refresh)),
            ('Modifier',         self.edit),
            ('Règlements',       self.payments),
            ('État crédits',     self.credit_state),
        ]:
            ttk.Button(toolbar, text=label, command=cmd).pack(side='left', padx=4)

        self.tree = ttk.Treeview(self,
            columns=('name', 'phone', 'billed', 'paid', 'balance'),
            show='headings')
        for col, label, w, anchor in [
            ('name',    'Nom',             220, 'w'),
            ('phone',   'Téléphone',       140, 'w'),
            ('billed',  'Facturé',          95, 'e'),
            ('paid',    'Payé',             95, 'e'),
            ('balance', 'Solde',            95, 'e'),
        ]:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=w, anchor=anchor)
        self.tree.tag_configure('debt',    foreground='#dc2626')
        self.tree.tag_configure('settled', foreground='#16a34a')
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda e: self.payments())
        self.refresh()

    def refresh(self, selected=None):
        self.rows = {str(r['id']): r for r in list_clients(self.query.get())}
        self.tree.delete(*self.tree.get_children())
        for key, r in self.rows.items():
            balance = r['billed_cents'] - r['paid_cents']
            tag = 'debt' if balance > 0 else 'settled'
            self.tree.insert('', 'end', iid=key,
                values=(r['name'], r['phone'],
                        fmt(r['billed_cents'], ''), fmt(r['paid_cents'], ''), fmt(balance, '')),
                tags=(tag,))
        if str(selected) in self.rows:
            self.tree.selection_set(str(selected))
            self.tree.see(str(selected))

    def _selected(self):
        sel = self.tree.selection()
        return self.rows[sel[0]] if sel else None

    def edit(self):
        c = self._selected()
        if c: ClientEditor(self, c, self.refresh)

    def payments(self):
        c = self._selected()
        if not c:
            messagebox.showinfo('Clients', 'Sélectionnez un client.', parent=self); return
        PaymentsWindow(self, c)

    def credit_state(self):
        CreditStateWindow(self)

