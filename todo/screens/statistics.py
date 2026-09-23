"""screens/statistics.py — Statistiques avec graphiques canvas natifs Tkinter."""
import tkinter as tk
from tkinter import ttk
from services.reports import (
    today_summary, period_summary, sales_evolution, top_products,
    top_cashiers, top_clients, top_month, category_breakdown, payment_breakdown, product_evolution,
)
from services.money import fmt
from database import connect

# ── Palette ───────────────────────────────────────────────────────────────────
CHART_COLORS = [
    '#2563EB','#16A34A','#DC2626','#D97706','#7C3AED',
    '#0891B2','#DB2777','#65A30D','#EA580C','#6B7280',
]

PERIOD_OPTIONS = [
    ('Semaine',  'week'),
    ('Mois',     'month'),
    ('Année',    'year'),
]


# ── Canvas bar chart ──────────────────────────────────────────────────────────
class BarChart(tk.Canvas):
    """Pure-Tkinter bar chart — no external deps."""
    def __init__(self, master, labels, values, title='', color='#2563EB', **kw):
        kw.setdefault('bg', '#FFFFFF')
        kw.setdefault('highlightthickness', 0)
        super().__init__(master, **kw)
        self._labels = labels
        self._values = values
        self._title  = title
        self._color  = color
        self.bind('<Configure>', lambda e: self._draw())


    def update_data(self, labels, values):
        self._labels = labels
        self._values = values
        self._draw()

    def _draw(self):
        self.delete('all')
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 10 or H < 10:
            return
        pad_l, pad_r, pad_t, pad_b = 48, 16, 30, 40
        chart_w = W - pad_l - pad_r
        chart_h = H - pad_t - pad_b

        # title
        if self._title:
            self.create_text(W//2, 14, text=self._title,
                             font=('Segoe UI', 9, 'bold'), fill='#1e293b')

        if not self._values or not any(self._values):
            self.create_text(W//2, H//2, text='Aucune donnée',
                             fill='#94a3b8', font=('Segoe UI', 10))
            return

        max_val = max(0,max(self._values))
        min_val = min(0,min(self._values))
        span = max_val-min_val or 1
        zero_y = pad_t + chart_h * max_val / span
        n = len(self._values)
        bar_w = max(4, (chart_w - n * 4) // n)
        gap   = max(2, (chart_w - n * bar_w) // max(n, 1))

        # Y axis labels (4 steps)
        for step in range(5):
            y_val = min_val + span * step / 4
            y_px  = pad_t + chart_h - int(chart_h * step / 4)
            self.create_line(pad_l - 4, y_px, pad_l + chart_w, y_px,
                             fill='#e2e8f0', dash=(2, 4))
            label = f'{y_val/100:,.0f}' if max_val > 500 else f'{y_val/100:.1f}'
            self.create_text(pad_l - 6, y_px, text=label, anchor='e',
                             font=('Consolas', 7), fill='#64748b')

        # bars
        for i, (lbl, val) in enumerate(zip(self._labels, self._values)):
            x0 = pad_l + i * (bar_w + gap)
            x1 = x0 + bar_w
            bar_h_px = int(chart_h * val / span)
            y0 = zero_y - bar_h_px
            y1 = zero_y
            # shadow
            self.create_rectangle(x0+2, y0+2, x1+2, y1+2,
                                  fill='#e2e8f0', outline='')
            # bar
            self.create_rectangle(x0, y0, x1, y1,
                                  fill=self._color, outline='', tags='bar')
            # value label on top
            if bar_h_px > 18:
                self.create_text((x0+x1)//2, y0+4, text=f'{val/100:,.0f}',
                                 font=('Segoe UI', 7), fill='white', anchor='n')
            # x label
            short = lbl[:4] if len(lbl) > 5 else lbl
            self.create_text((x0+x1)//2, pad_t + chart_h + 6, text=short,
                             font=('Segoe UI', 7), fill='#475569', anchor='n')

        # X axis line
        self.create_line(pad_l, pad_t + chart_h, pad_l + chart_w, pad_t + chart_h,
                         fill='#cbd5e1')
        self.create_line(pad_l, pad_t, pad_l, pad_t + chart_h, fill='#cbd5e1')


# ── Canvas horizontal bar (top products / cashiers) ───────────────────────────
class HBarChart(tk.Canvas):
    """Horizontal bar chart for ranked items."""
    def __init__(self, master, items, title='', **kw):
        kw.setdefault('bg', '#FFFFFF')
        kw.setdefault('highlightthickness', 0)
        super().__init__(master, **kw)
        self._items = items   # list of (label, value)
        self._title = title
        self.bind('<Configure>', lambda e: self._draw())


    def update_data(self, items):
        self._items = items
        self._draw()

    def _draw(self):
        self.delete('all')
        W = self.winfo_width()
        H = self.winfo_height()
        if W < 10 or H < 10 or not self._items:
            if not self._items:
                self.create_text(W//2 if W>10 else 50,
                                 H//2 if H>10 else 50,
                                 text='Aucune donnée', fill='#94a3b8')
            return

        if self._title:
            self.create_text(W//2, 14, text=self._title,
                             font=('Segoe UI', 9, 'bold'), fill='#1e293b')

        pad_l, pad_r, pad_t = 160, 70, 28
        n       = len(self._items)
        row_h   = max(18, (H - pad_t - 10) // n)
        max_val = max(0,max(v for _,v in self._items))
        min_val = min(0,min(v for _,v in self._items))
        span = max_val-min_val or 1
        bar_area = max(1,W - pad_l - pad_r)
        zero_x = pad_l - bar_area * min_val / span

        for i, (lbl, val) in enumerate(self._items):
            y_mid = pad_t + i * row_h + row_h // 2
            # label
            short = lbl[:22] if len(lbl) > 22 else lbl
            self.create_text(pad_l - 6, y_mid, text=short,
                             anchor='e', font=('Segoe UI', 8), fill='#334155')
            # bar bg
            self.create_rectangle(pad_l, y_mid - row_h//3,
                                  pad_l + bar_area, y_mid + row_h//3,
                                  fill='#f1f5f9', outline='')
            # bar fill
            bar_px = int(bar_area * val / span)
            color  = CHART_COLORS[i % len(CHART_COLORS)]
            self.create_rectangle(zero_x, y_mid - row_h//3,
                                  zero_x + bar_px, y_mid + row_h//3,
                                  fill=color, outline='')
            # value
            self.create_text(pad_l + bar_area + 4, y_mid,
                             text=f'{val/100:,.0f}', anchor='w',
                             font=('Consolas', 8), fill='#475569')


# ── Main StatisticsFrame ──────────────────────────────────────────────────────
class StatisticsFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=16)
        self._period = 'month'
        import datetime
        self._year = datetime.date.today().year

        # ── Header ────────────────────────────────────────────────────────────
        header = ttk.Frame(self)
        header.pack(fill='x', pady=(0, 14))
        ttk.Label(header, text='Statistiques',
                  font=('Segoe UI', 20, 'bold')).pack(side='left')
        ttk.Label(header, text='Évolution ventes · Top articles · Top caissiers · Familles',
                  foreground='#475569').pack(side='left', padx=16)

        # period selector
        period_bar = ttk.Frame(header)
        period_bar.pack(side='right')
        self._period_btns = {}
        for label, key in PERIOD_OPTIONS:
            btn = ttk.Button(period_bar, text=label,
                             command=lambda k=key: self._set_period(k))
            btn.pack(side='left', padx=2)
            self._period_btns[key] = btn
        ttk.Button(header, text='↺ Actualiser',
                   command=self.refresh).pack(side='right', padx=8)
        year_box = ttk.Frame(header)
        year_box.pack(side='right', padx=6)
        ttk.Button(year_box, text='‹', width=3, command=lambda: self._change_year(-1)).pack(side='left')
        self.year_label = ttk.Label(year_box, text=str(self._year), width=6, anchor='center', font=('Segoe UI',10,'bold'))
        self.year_label.pack(side='left')
        ttk.Button(year_box, text='›', width=3, command=lambda: self._change_year(1)).pack(side='left')

        # ── KPI cards row ─────────────────────────────────────────────────────
        self.kpi_frame = ttk.Frame(self)
        self.kpi_frame.pack(fill='x', pady=(0, 14))
        self._kpi_labels = {}
        kpi_defs = [
            ('net_sales',    'Total ventes',   '#2563EB'),
            ('gross_margin', 'Marge brute',    '#16A34A'),
            ('tickets',      'Tickets',        '#D97706'),
            ('alerts',       'Stock faible',   '#DC2626'),
            ('stock_value',   'Valeur stock',    '#7C3AED'),
            ('returns',       'Retours',         '#0891B2'),
            ('top_month',     'Top mois',        '#6B7280'),
        ]
        for i, (key, title, color) in enumerate(kpi_defs):
            card = tk.Frame(self.kpi_frame, bg=color, height=76)
            card.grid(row=0, column=i, sticky='ew', padx=4)
            card.grid_propagate(False)
            self.kpi_frame.columnconfigure(i, weight=1)
            tk.Label(card, text=title, bg=color, fg='white',
                     font=('Segoe UI', 9)).pack(anchor='w', padx=12, pady=(8, 0))
            val_lbl = tk.Label(card, text='—', bg=color, fg='white',
                               font=('Segoe UI', 18, 'bold'))
            val_lbl.pack(anchor='w', padx=12)
            self._kpi_labels[key] = val_lbl

        # ── Charts grid ───────────────────────────────────────────────────────
        charts = ttk.Frame(self)
        charts.pack(fill='both', expand=True)
        charts.columnconfigure(0, weight=3)
        charts.columnconfigure(1, weight=2)
        charts.rowconfigure(0, weight=3)
        charts.rowconfigure(1, weight=2)
        charts.rowconfigure(2, weight=2)

        # Evolution bar chart (big, top-left)
        evo_card = ttk.LabelFrame(charts, text='Évolution des ventes', padding=4)
        evo_card.grid(row=0, column=0, sticky='nsew', padx=(0, 6), pady=(0, 6))
        self.evo_chart = BarChart(evo_card, [], [], color='#2563EB',
                                  height=200)
        self.evo_chart.pack(fill='both', expand=True)

        # Category breakdown (top-right)
        cat_card = ttk.LabelFrame(charts, text='Ventes par famille', padding=4)
        cat_card.grid(row=0, column=1, sticky='nsew', pady=(0, 6))
        self.cat_chart = HBarChart(cat_card, [], height=200)
        self.cat_chart.pack(fill='both', expand=True)

        # Top products (bottom-left)
        top_card = ttk.LabelFrame(charts, text='Top 8 articles', padding=4)
        top_card.grid(row=1, column=0, sticky='nsew', padx=(0, 6))
        self.top_chart = HBarChart(top_card, [], height=160)
        self.top_chart.pack(fill='both', expand=True)

        # Top cashiers (bottom-right)
        cash_card = ttk.LabelFrame(charts, text='Top caissiers', padding=4)
        cash_card.grid(row=1, column=1, sticky='nsew')
        self.cashier_chart = HBarChart(cash_card, [], height=160)
        self.cashier_chart.pack(fill='both', expand=True)

        # Article evolution selector
        article_card = ttk.LabelFrame(charts, text='Évolution article', padding=6)
        article_card.grid(row=2, column=0, sticky='nsew', padx=(0, 6), pady=(6, 0))
        article_head = ttk.Frame(article_card)
        article_head.pack(fill='x')
        self.article_choice = ttk.Combobox(article_head, state='readonly', width=34)
        self.article_choice.pack(side='left', padx=(0, 6))
        self.article_choice.bind('<<ComboboxSelected>>', lambda e: self._load_article_evolution())
        self.article_chart = BarChart(article_card, [], [], color='#7C3AED', height=140)
        self.article_chart.pack(fill='both', expand=True, pady=(4, 0))

        # Top clients (third row, full width)
        client_card = ttk.LabelFrame(charts, text='Top 10 clients', padding=4)
        client_card.grid(row=2, column=1, sticky='nsew', pady=(6, 0))
        self.client_chart = HBarChart(client_card, [], height=150)
        self.client_chart.pack(fill='both', expand=True)

        # recent transactions sidebar
        recent_card = ttk.LabelFrame(self, text='Dernières opérations', padding=6)
        recent_card.pack(fill='x', pady=(10, 0))
        self.recent_tree = ttk.Treeview(recent_card,
            columns=('doc', 'amount', 'kind', 'time'), show='headings', height=5)
        for col, lbl, w, anchor in [
            ('doc',    'N°',       110, 'w'),
            ('amount', 'Montant',   90, 'e'),
            ('kind',   'Type',      65, 'w'),
            ('time',   'Heure',    110, 'w'),
        ]:
            self.recent_tree.heading(col, text=lbl)
            self.recent_tree.column(col, width=w, anchor=anchor)
        self.recent_tree.tag_configure('return', foreground='#DC2626')
        self.recent_tree.pack(fill='x')

        pay_card = ttk.LabelFrame(self, text='Paiements nets', padding=6)
        pay_card.pack(fill='x', pady=(8, 0))
        self.payment_summary = ttk.Label(pay_card, text='—', font=('Segoe UI', 11, 'bold'))
        self.payment_summary.pack(anchor='w')

        self._set_period('month')

    # ── Period ────────────────────────────────────────────────────────────────
    def _set_period(self, key):
        self._period = key
        for k, btn in self._period_btns.items():
            btn.state(['pressed'] if k == key else ['!pressed'])
        self.refresh()

    def _change_year(self, delta):
        self._year += delta
        self.year_label.config(text=str(self._year))
        self._period = 'year'
        for k, btn in self._period_btns.items():
            btn.state(['pressed'] if k == 'year' else ['!pressed'])
        self.refresh()

    # ── Refresh ───────────────────────────────────────────────────────────────
    def refresh(self):
        try:
            self._load_kpis()
            self._load_evolution()
            self._load_top_products()
            self._load_cashiers()
            self._load_clients()
            self._load_article_evolution()
            self._load_categories()
            self._load_recent()
            self._load_payments()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror('Statistiques',str(e),parent=self)

    def _load_kpis(self):
        data = period_summary(self._period)
        self._kpi_labels['net_sales'].config(   text=fmt(data['net_sales']))
        self._kpi_labels['gross_margin'].config( text=fmt(data['gross_margin']))
        self._kpi_labels['tickets'].config(      text=str(data['tickets']))
        self._kpi_labels['alerts'].config(       text=str(data['alerts']))
        with connect() as conn:
            stock=conn.execute('SELECT COALESCE(SUM(stock_qty*purchase_price_cents),0) FROM products WHERE active=1').fetchone()[0]
            returns=conn.execute("SELECT COALESCE(SUM(total_cents),0) FROM returns WHERE date(created_at)>=date('now',CASE ? WHEN 'week' THEN '-6 days' WHEN 'month' THEN 'start of month' ELSE 'start of year' END)",(self._period,)).fetchone()[0]
        self._kpi_labels['stock_value'].config(text=fmt(stock))
        self._kpi_labels['returns'].config(text=fmt(returns))
        best=top_month(self._year)
        month_names=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Août','Sep','Oct','Nov','Déc']
        label='—' if not best['month'] else f"{month_names[best['month']-1]} · {fmt(best['revenue'])}"
        self._kpi_labels['top_month'].config(text=label)

    def _load_payments(self):
        data=payment_breakdown(self._period)
        parts=[]
        for method,label in [('CASH','Espèces'),('CARD','Carte'),('CREDIT','Crédit')]:
            amount=data.get(method,0)
            if amount or method in ('CASH','CARD'):
                parts.append(f'{label}: {fmt(amount)}')
        self.payment_summary.config(text='   ·   '.join(parts) if parts else 'Aucun paiement')

    def _load_evolution(self):
        labels, values = sales_evolution(self._period)
        self.evo_chart.update_data(labels, values)

    def _load_top_products(self):
        rows = top_products(8, self._period)
        items = [(r['name'], r['revenue']) for r in rows]
        self.top_chart.update_data(items)

    def _load_cashiers(self):
        rows = top_cashiers(self._period)
        items = [(r['name'], r['revenue']) for r in rows]
        self.cashier_chart.update_data(items)

    def _load_article_evolution(self):
        with connect() as conn:
            rows=conn.execute("SELECT id,name FROM products WHERE active=1 ORDER BY name COLLATE NOCASE").fetchall()
        labels=[f"{r['name']}  ·  #{r['id']}" for r in rows]
        current=self.article_choice.get()
        self.article_choice['values']=labels
        if not labels:
            self.article_choice.set('')
            self.article_chart.update_data([], [])
            return
        if current not in labels:
            self.article_choice.current(0)
        try:
            product_id=int(self.article_choice.get().rsplit('#',1)[1])
        except (ValueError, IndexError):
            return
        x,y=product_evolution(product_id,self._period)
        self.article_chart.update_data(x,y)

    def _load_clients(self):
        rows = top_clients(self._period)
        items = [(r['name'], r['revenue']) for r in rows]
        self.client_chart.update_data(items)

    def _load_categories(self):
        rows = category_breakdown(self._period)
        items = [(r['name'], r['revenue']) for r in rows]
        self.cat_chart.update_data(items)

    def _load_recent(self):
        data = today_summary()
        self.recent_tree.delete(*self.recent_tree.get_children())
        for r in data['recent']:
            tag = 'return' if r['kind'] == 'Retour' else ''
            self.recent_tree.insert('', 'end',
                values=(r['document'], fmt(r['amount']), r['kind'],
                        r['created_at'][11:16]),
                tags=(tag,))
