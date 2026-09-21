import csv
import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from services.money import fmt
from services.reports import journal_tickets, journal_by_family, journal_by_article, journal_by_day


REPORTS = {
    'tickets': ('Détail tickets / تفصيل التذاكر',
                [('id', 'ID', 45), ('ticket', 'Ticket', 170), ('date', 'Date', 150),
                 ('cashier', 'Caissier', 110), ('pay', 'Paiement', 90),
                 ('total', 'Total', 90), ('cost', 'Coût', 90), ('margin', 'Marge brute', 100)]),
    'family': ('Par Famille / بالفامي',
               [('name', 'Famille', 220), ('qty', 'Qté', 100), ('revenue', 'CA', 130)]),
    'article': ('Par Article / بالمقال',
                [('name', 'Article', 280), ('qty', 'Qté', 100), ('revenue', 'CA', 130)]),
    'day': ('Par Jours / باليوم',
            [('day', 'Jour', 140), ('tickets', 'Tickets', 100), ('revenue', 'CA', 130)]),
}


class JournalFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=10)
        today = datetime.date.today().isoformat()
        self.start = tk.StringVar(value=today)
        self.end = tk.StringVar(value=today)
        self.report = tk.StringVar(value='tickets')

        top = ttk.Frame(self)
        top.pack(fill='x')
        ttk.Label(top, text='Journal / التقارير', font=('Segoe UI', 22, 'bold')).pack(side='left')

        dates = ttk.Frame(self)
        dates.pack(fill='x', pady=(10, 0))
        ttk.Label(dates, text='De / من').pack(side='left')
        ttk.Entry(dates, textvariable=self.start, width=12).pack(side='left', padx=(4, 12))
        ttk.Label(dates, text='À / إلى').pack(side='left')
        ttk.Entry(dates, textvariable=self.end, width=12).pack(side='left', padx=(4, 12))
        ttk.Button(dates, text='OK', command=self.refresh).pack(side='left', padx=(0, 20))
        for key, (label, _cols) in REPORTS.items():
            ttk.Radiobutton(dates, text=label.split(' / ')[0], variable=self.report,
                            value=key, command=self.refresh).pack(side='left', padx=6)

        actions = ttk.Frame(self)
        actions.pack(fill='x', pady=(6, 8))
        ttk.Button(actions, text='Imprimer / طباعة', command=self.print_pdf).pack(side='right')
        ttk.Button(actions, text='Export CSV', command=self.export).pack(side='right', padx=8)
        ttk.Button(actions, text='Actualiser', command=self.refresh).pack(side='right')

        self.tree_holder = ttk.Frame(self)
        self.tree_holder.pack(fill='both', expand=True)
        self.tree = None
        self.refresh()

    def dates_or_error(self):
        try:
            start = datetime.date.fromisoformat(self.start.get().strip())
            end = datetime.date.fromisoformat(self.end.get().strip())
        except ValueError:
            messagebox.showerror('Journal', 'Dates invalides (format AAAA-MM-JJ).', parent=self)
            return None
        if start > end:
            start, end = end, start
        return start.isoformat(), end.isoformat()

    def rows(self):
        bounds = self.dates_or_error()
        if not bounds:
            return []
        start, end = bounds
        kind = self.report.get()
        if kind == 'tickets':
            data = journal_tickets(start, end)
            out = []
            for r in data:
                margin = int(r['total_cents'] - r['cost'])
                out.append((r['id'], r['sale_no'], r['created_at'], r['display_name'], r['payment_method'],
                             fmt(r['total_cents'], ''), fmt(r['cost'], ''), fmt(margin, '')))
            return out
        if kind == 'family':
            return [(r['name'], f"{r['qty']:g}", fmt(r['revenue'], '')) for r in journal_by_family(start, end)]
        if kind == 'article':
            return [(r['name'], f"{r['qty']:g}", fmt(r['revenue'], '')) for r in journal_by_article(start, end)]
        return [(r['day'], r['tickets'], fmt(r['revenue'], '')) for r in journal_by_day(start, end)]

    def refresh(self):
        for w in self.tree_holder.winfo_children():
            w.destroy()
        _label, columns = REPORTS[self.report.get()]
        keys = [c[0] for c in columns]
        self.tree = ttk.Treeview(self.tree_holder, columns=keys, show='headings')
        for key, header, width in columns:
            self.tree.heading(key, text=header)
            self.tree.column(key, width=width, anchor='center')
        self.tree.pack(fill='both', expand=True)
        for row in self.rows():
            self.tree.insert('', 'end', values=row)

    def export(self):
        path = filedialog.asksaveasfilename(defaultextension='.csv', filetypes=[('CSV', '*.csv')],
                                             title='Exporter journal')
        if not path:
            return
        _label, columns = REPORTS[self.report.get()]
        with open(path, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([h for _k, h, _w in columns])
            for row in self.rows():
                writer.writerow(row)
        messagebox.showinfo('ToDo', 'Export terminé.', parent=self)

    def print_pdf(self):
        path = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[('PDF', '*.pdf')],
                                             title='Imprimer / Exporter PDF')
        if not path:
            return
        from services.receipts import export_table_pdf
        label, columns = REPORTS[self.report.get()]
        bounds = self.dates_or_error()
        period = f" ({bounds[0]} -> {bounds[1]})" if bounds else ''
        headers = [h for _k, h, _w in columns]
        export_table_pdf(label.split(' / ')[0] + period, headers, self.rows(), path)
        messagebox.showinfo('ToDo', 'PDF généré.', parent=self)
