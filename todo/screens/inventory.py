"""screens/inventory.py — Inventaire (comptage physique) + Sorties de stock."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from database import connect, get_setting
from services.inventory import apply_stock_movement
from services.money import fmt


# ── Inventaire ────────────────────────────────────────────────────────────

class InventaireFrame(ttk.Frame):
    """Saisie du comptage physique — compare stock théorique vs réel."""

    def __init__(self, master):
        super().__init__(master, padding=16)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        ttk.Label(self, text=self.tr('📝  Inventaire','📝  الجرد'),
                  font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(self, text=self.tr('Saisissez la quantité réelle comptée. Validez pour ajuster le stock.','أدخل الكمية الحقيقية المحسوبة ثم أكد لتعديل المخزون.'),
                  foreground='#475569').pack(anchor='w', pady=(0, 10))

        toolbar = ttk.Frame(self); toolbar.pack(fill='x', pady=(0, 8))
        self.query = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.query, width=32)
        entry.pack(side='left')
        entry.bind('<KeyRelease>', lambda e: self.refresh())
        ttk.Button(toolbar, text=self.tr('✔  Valider les écarts','✔  تأكيد الفروقات'),
                   style='Primary.TButton', command=self.apply_all).pack(side='right')
        ttk.Button(toolbar, text=self.tr('↺ Actualiser','↺ تحديث'), command=self.refresh).pack(side='right', padx=8)

        cols = ('id', 'name', 'theory', 'counted', 'diff')
        self.tree = ttk.Treeview(self, columns=cols, show='headings')
        for col, lbl, w, anc in [
            ('id',      'ID',       55,  'center'),
            ('name',    self.tr('Article','المنتوج'),  350, 'w'),
            ('theory',  self.tr('Théorique','النظري'),95,  'e'),
            ('counted', self.tr('Compté ✏','المعدود ✏'), 95,  'e'),
            ('diff',    self.tr('Écart','الفرق'),    85,  'e'),
        ]:
            self.tree.heading(col, text=lbl)
            self.tree.column(col, width=w, anchor=anc)
        self.tree.tag_configure('neg',  foreground='#DC2626')
        self.tree.tag_configure('pos',  foreground='#16A34A')
        self.tree.tag_configure('zero', foreground='#64748B')
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', self._edit_cell)

        self.counted = {}   # product_id → float
        self.products = []
        self.pending_label=ttk.Label(toolbar,text=self.tr('0 écart','0 فرق'),foreground='#475569');self.pending_label.pack(side='right',padx=12)
        self.tree.bind('<Return>', self._edit_cell)
        self.refresh()

    def refresh(self):
        q = self.query.get().strip()
        with connect() as conn:
            rows = conn.execute(
                "SELECT id,name,stock_qty FROM products WHERE active=1 "
                "AND (? = '' OR instr(lower(name), lower(?)) > 0) ORDER BY name",
                (q, q)
            ).fetchall()
        self.products = [dict(r) for r in rows]
        self._redraw()

    def _redraw(self):
        self.tree.delete(*self.tree.get_children())
        for p in self.products:
            pid = p['id']; theory = float(p['stock_qty'])
            counted = self.counted.get(pid, theory)
            diff = counted - theory
            tag = 'neg' if diff < -0.001 else ('pos' if diff > 0.001 else 'zero')
            self.tree.insert('', 'end', iid=str(pid),
                values=(pid, p['name'],
                        f'{theory:g}',
                        f'{counted:g}',
                        f'{diff:+g}' if abs(diff) > 0.001 else '—'),
                tags=(tag,))
        pending=sum(1 for p in self.products if abs(self.counted.get(p['id'],float(p['stock_qty']))-float(p['stock_qty']))>0.001)
        self.pending_label.config(text=f'{pending} écart(s) à valider')

    def _edit_cell(self, event):
        sel = self.tree.selection()
        if not sel: return
        pid = int(sel[0])
        pname = self.tree.item(sel[0], 'values')[1]
        val = simpledialog.askfloat(
            'Inventaire', f'Quantité comptée — {pname} :', parent=self)
        if val is None: return
        self.counted[pid] = val
        self._redraw()

    def apply_all(self):
        diffs = {pid: cnt for pid, cnt in self.counted.items()}
        if not diffs:
            messagebox.showinfo(self.tr('Inventaire','الجرد'), self.tr('Aucun écart saisi.','لم يتم إدخال أي فرق.'), parent=self); return
        n_adj = 0
        with connect() as conn:
            conn.execute('BEGIN IMMEDIATE')
            for p in self.products:
                pid = p['id']; theory = float(p['stock_qty'])
                counted = diffs.get(pid)
                if counted is None: continue
                delta = counted - theory
                if abs(delta) < 0.001: continue
                apply_stock_movement(conn, pid, delta, 'INVENTAIRE',
                                     note=f'Inventaire : théorique {theory:g} → compté {counted:g}')
                n_adj += 1
            conn.commit()
        messagebox.showinfo(self.tr('Inventaire','الجرد'), self.tr(f'{n_adj} article(s) ajusté(s).',f'تمت تسوية {n_adj} منتج.'), parent=self)
        self.counted.clear()
        self.refresh()


# ── Sorties ───────────────────────────────────────────────────────────────

class SortiesFrame(ttk.Frame):
    """Sorties manuelles de stock (casse, perte, don…)."""

    def __init__(self, master):
        super().__init__(master, padding=16)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        ttk.Label(self, text=self.tr('📤  Sorties de stock','📤  إخراج المخزون'),
                  font=('Segoe UI', 20, 'bold')).pack(anchor='w')
        ttk.Label(self, text=self.tr('Casse, perte, don, consommation interne.','كسر، ضياع، تبرع، استهلاك داخلي.'),
                  foreground='#475569').pack(anchor='w', pady=(0, 10))

        toolbar = ttk.Frame(self); toolbar.pack(fill='x', pady=(0, 8))
        self.query = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.query, width=32)
        entry.pack(side='left')
        entry.bind('<KeyRelease>', lambda e: self.refresh())
        ttk.Button(toolbar, text=self.tr('📤 Enregistrer une sortie','📤 تسجيل إخراج'),
                   style='Primary.TButton', command=self.add_exit).pack(side='right')

        cols = ('id', 'name', 'stock', 'last_exit')
        self.tree = ttk.Treeview(self, columns=cols, show='headings')
        for col, lbl, w, anc in [
            ('id',        'ID',         55,  'center'),
            ('name',      'Article',    350, 'w'),
            ('stock',     'Stock actuel',105, 'e'),
            ('last_exit', 'Dernière sortie', 300, 'w'),
        ]:
            self.tree.heading(col, text=lbl)
            self.tree.column(col, width=w, anchor=anc)
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill='both', expand=True)

        # Recent exits log
        ttk.Label(self, text=self.tr('Dernières sorties','آخر عمليات الإخراج'),
                  font=('Segoe UI', 11, 'bold')).pack(anchor='w', pady=(10, 4))
        log_cols = ('date', 'product', 'qty', 'reason')
        self.log = ttk.Treeview(self, columns=log_cols, show='headings', height=5)
        for col, lbl, w in [('date','Date',140),('product','Article',280),('qty','Qté',70),('reason','Raison',300)]:
            self.log.heading(col, text=lbl); self.log.column(col, width=w)
        self.log.pack(fill='x')
        self.refresh()

    def refresh(self):
        q = self.query.get().strip()
        with connect() as conn:
            rows = conn.execute(
                "SELECT p.id, p.name, p.stock_qty, "
                "  COALESCE((SELECT sm.qty_delta||'  '||sm.note||'  @ '||sm.created_at "
                "             FROM stock_movements sm WHERE sm.product_id=p.id AND sm.movement_type='SORTIE' "
                "             ORDER BY sm.id DESC LIMIT 1),'') last_exit "
                "FROM products p WHERE p.active=1 "
                "AND (? = '' OR instr(lower(p.name), lower(?)) > 0) ORDER BY p.name",
                (q, q)).fetchall()
            self.rows = {str(r['id']): dict(r) for r in rows}
            log_rows = conn.execute(
                "SELECT sm.created_at, p.name, sm.qty_delta, sm.note "
                "FROM stock_movements sm JOIN products p ON p.id=sm.product_id "
                "WHERE sm.movement_type='SORTIE' ORDER BY sm.id DESC LIMIT 30"
            ).fetchall()

        self.tree.delete(*self.tree.get_children())
        for key, r in self.rows.items():
            self.tree.insert('', 'end', iid=key,
                values=(r['id'], r['name'], f'{float(r["stock_qty"]):g}', r['last_exit'] or '—'))

        self.log.delete(*self.log.get_children())
        for r in log_rows:
            self.log.insert('', 'end',
                values=(r['created_at'][:16], r['name'], f'{float(r["qty_delta"]):g}', r['note']))

    def add_exit(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(self.tr('Sorties','الإخراج'), self.tr('Sélectionnez un article.','اختر منتجاً.'), parent=self); return
        pid   = int(sel[0])
        pname = self.rows[sel[0]]['name']
        qty   = simpledialog.askfloat(self.tr('Sortie','إخراج'), self.tr(f'Quantité sortie — {pname} :',f'الكمية المخرجة — {pname}:'), parent=self)
        if qty is None or qty <= 0: return
        reason = simpledialog.askstring(self.tr('Sortie','إخراج'), self.tr('Raison obligatoire (casse, perte, don…) :','السبب إجباري (كسر، ضياع، تبرع…):'), parent=self)
        if reason is None or not reason.strip():
            messagebox.showinfo(self.tr('Sorties','الإخراج'),self.tr('La raison est obligatoire.','السبب إلزامي.'),parent=self); return
        try:
            with connect() as conn:
                conn.execute('BEGIN IMMEDIATE')
                apply_stock_movement(conn, pid, -qty, 'SORTIE', note=reason)
                conn.commit()
            self.refresh()
        except Exception as e:
            messagebox.showerror(self.tr('Sortie','إخراج'), str(e), parent=self)
