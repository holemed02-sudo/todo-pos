import tkinter as tk
from tkinter import ttk
from services.money import fmt, to_cents


class PaymentDialog(tk.Toplevel):
    """Collect a payment choice; closing this dialog never writes a sale."""

    def __init__(self, master, total, currency='DH', method='CASH'):
        super().__init__(master)
        self.total = total
        self.currency = currency
        self.result = None
        self.title('Encaissement / الخلاص')
        self.geometry('580x650')
        self.configure(bg='#F6F7FB')
        self.transient(master.winfo_toplevel())
        self.method = tk.StringVar(value=method)
        self.amount = tk.StringVar(value=f'{total / 100:.2f}')
        self.print_ticket = tk.BooleanVar(value=False)
        tk.Label(self, text='TOTAL À PAYER / المجموع', bg='#2563EB', fg='white',
                 font=('Segoe UI', 13, 'bold')).pack(fill='x', pady=(0, 0))
        tk.Label(self, text=fmt(total, currency), bg='#2563EB', fg='white',
                 font=('Segoe UI', 34, 'bold')).pack(fill='x', ipady=12)
        body = ttk.Frame(self, padding=18)
        body.pack(fill='both', expand=True)
        modes = ttk.Frame(body)
        modes.pack(fill='x', pady=(0, 12))
        for label, value in [('F2 Espèces / نقداً', 'CASH'), ('F3 Carte / بطاقة', 'CARD')]:
            ttk.Radiobutton(modes, text=label, variable=self.method, value=value,
                            command=self.update_amount).pack(side='left', expand=True, padx=8)
        ttk.Label(body, text='Montant reçu / المبلغ المدفوع').pack(anchor='w')
        self.entry = ttk.Entry(body, textvariable=self.amount, font=('Segoe UI', 24), justify='right')
        self.entry.pack(fill='x', pady=8)
        notes = ttk.Frame(body)
        notes.pack(fill='x', pady=6)
        for value in (20, 50, 100, 200):
            ttk.Button(notes, text=f'{value} DH', command=lambda n=value: self.set_amount(n)).pack(side='left', expand=True, fill='x', padx=3)
        ttk.Button(body, text='Montant exact / المبلغ بالضبط', command=self.exact).pack(fill='x', pady=4)
        self.change = tk.Label(body, bg='white', fg='#166534', font=('Segoe UI', 23, 'bold'), pady=14)
        self.change.pack(fill='x', pady=14)
        self.error = ttk.Label(body, foreground='#DC2626', wraplength=500)
        self.error.pack(fill='x')
        ttk.Checkbutton(body, text='Imprimer le ticket / طباعة التيكي', variable=self.print_ticket).pack(anchor='w', pady=12)
        self.confirm_button = ttk.Button(body, text='VALIDER / تأكيد  Entrée', style='Primary.TButton', command=self.confirm)
        self.confirm_button.pack(fill='x', ipady=12, pady=8)
        ttk.Button(body, text='Retour au ticket / رجوع  Esc', command=self.destroy).pack(fill='x', ipady=6)
        self.amount.trace_add('write', lambda *_: self.update_amount())
        self.bind('<Return>', lambda e: self.confirm())
        self.bind('<Escape>', lambda e: self.destroy())
        self.bind('<F2>', lambda e: self.choose_method('CASH'))
        self.bind('<F3>', lambda e: self.choose_method('CARD'))
        self.grab_set()
        self.update_amount()
        self.after_idle(self.focus_amount)

    def focus_amount(self):
        self.entry.focus_set()
        self.entry.selection_range(0, 'end')

    def choose_method(self, method):
        self.method.set(method)
        self.update_amount()

    def set_amount(self, amount):
        self.method.set('CASH')
        self.amount.set(f'{amount:.2f}')
        self.focus_amount()

    def exact(self):
        self.amount.set(f'{self.total / 100:.2f}')
        self.focus_amount()

    def paid_cents(self):
        return self.total if self.method.get() == 'CARD' else to_cents(self.amount.get())

    def update_amount(self):
        card = self.method.get() == 'CARD'
        self.entry.configure(state='disabled' if card else 'normal')
        try:
            paid = self.paid_cents()
            if paid < 0:
                raise ValueError()
            difference = paid - self.total
            self.change.configure(text=('Reste à payer / باقي : ' if difference < 0 else 'Monnaie / الصرف : ') + fmt(abs(difference), self.currency),
                                  fg='#DC2626' if difference < 0 else '#166534')
            self.confirm_button.configure(state='disabled' if difference < 0 else 'normal')
            self.error.configure(text='Montant reçu insuffisant.' if difference < 0 else '')
        except Exception:
            self.change.configure(text='—')
            self.error.configure(text='Saisissez un montant valide / دخل مبلغ صحيح')
            self.confirm_button.configure(state='disabled')

    def confirm(self):
        try:
            paid = self.paid_cents()
            if paid < self.total:
                self.update_amount()
                return
        except Exception:
            self.update_amount()
            return
        self.result = (self.method.get(), paid, self.print_ticket.get())
        self.destroy()
