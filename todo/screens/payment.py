import tkinter as tk
from tkinter import ttk
from services.money import fmt, to_cents


class PaymentDialog(tk.Toplevel):
    """Collect a payment choice; closing this dialog never writes a sale."""

    def __init__(self, master, total, currency='DH', method='CASH', client_name=None):
        super().__init__(master)
        self.client_name = client_name
        self.total = total
        self.currency = currency
        self.result = None
        self.title('Encaissement / الخلاص')
        self.geometry(f'580x{min(650,self.winfo_screenheight()-90)}')
        self.configure(bg='#F6F7FB')
        self.transient(master.winfo_toplevel())
        self.method = tk.StringVar(value=method)
        self.amount = tk.StringVar(value=f'{total / 100:.2f}')
        self.card_amount = tk.StringVar(value='0.00')
        self.print_ticket = tk.BooleanVar(value=False)
        self.cash_tendered_cents = total
        tk.Label(self, text='TOTAL À PAYER / المجموع', bg='#2563EB', fg='white',
                 font=('Segoe UI', 13, 'bold')).pack(fill='x', pady=(0, 0))
        tk.Label(self, text=fmt(total, currency), bg='#2563EB', fg='white',
                 font=('Segoe UI', 34, 'bold')).pack(fill='x', ipady=12)
        controls = ttk.Frame(self, padding=8)
        controls.pack(side='bottom',fill='x')
        body = ttk.Frame(self, padding=10)
        body.pack(fill='both', expand=True)
        modes = ttk.Frame(body)
        modes.pack(fill='x', pady=(0, 12))
        choices=[('F2 Espèces / نقداً','CASH'),('F3 Carte / بطاقة','CARD'),('Mixte / مختلط','MIXED')]
        if client_name:choices.append(('Crédit / كريدي','CREDIT'))
        if client_name:ttk.Label(body,text='Client : '+client_name).pack(anchor='w')
        for label, value in choices:
            ttk.Radiobutton(modes, text=label, variable=self.method, value=value,
                            command=self.update_amount).pack(side='left', expand=True, padx=8)
        ttk.Label(body, text='Montant reçu / المبلغ المدفوع').pack(anchor='w')
        self.entry = ttk.Entry(body, textvariable=self.amount, font=('Segoe UI', 24), justify='right')
        self.entry.pack(fill='x', pady=8)
        ttk.Label(body, text='Billets / pièces reçus / النقد المستلم').pack(anchor='w', pady=(4, 0))
        denominations = ttk.Frame(body)
        denominations.pack(fill='x', pady=6)
        for index, value in enumerate((200, 100, 50, 20, 10, 5, 2, 1, 0.5)):
            ttk.Button(denominations, text=f'{value:g} DH', command=lambda n=value: self.add_cash(n)).grid(
                row=index//5, column=index%5, sticky='nsew', padx=3, pady=3, ipady=5)
        for column in range(5):
            denominations.columnconfigure(column, weight=1)
        ttk.Button(body, text='Effacer espèces / مسح', command=self.clear_cash).pack(fill='x', pady=(0, 4))
        ttk.Button(body, text='Montant exact / المبلغ بالضبط', command=self.exact).pack(fill='x', pady=4)
        ttk.Label(body, text='Part carte (mode mixte) / جزء البطاقة').pack(anchor='w', pady=(8,0))
        self.card_entry = ttk.Entry(body, textvariable=self.card_amount, font=('Segoe UI', 18), justify='right')
        self.card_entry.pack(fill='x', pady=4)
        self.change = tk.Label(body, bg='white', fg='#166534', font=('Segoe UI', 23, 'bold'), pady=14)
        self.change.pack(fill='x', pady=14)
        self.error = ttk.Label(body, foreground='#DC2626', wraplength=500)
        self.error.pack(fill='x')
        ttk.Checkbutton(body, text='Imprimer le ticket / طباعة التيكي', variable=self.print_ticket).pack(anchor='w', pady=12)
        self.confirm_button = ttk.Button(controls, text='VALIDER / تأكيد  Entrée', style='Primary.TButton', command=self.confirm)
        self.confirm_button.pack(fill='x', ipady=12, pady=8)
        ttk.Button(controls, text='Retour au ticket / رجوع  Esc', command=self.destroy).pack(fill='x', ipady=6)
        self.amount.trace_add('write', self.amount_changed)
        self.card_amount.trace_add('write', self.amount_changed)
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
        self.cash_tendered_cents = to_cents(str(amount))
        self.amount.set(f'{amount:.2f}')
        self.focus_amount()

    def add_cash(self, amount):
        self.method.set('CASH')
        try:
            current = to_cents(self.amount.get())
        except Exception:
            current = 0
        # If the cashier selected the initial exact amount, the first denomination
        # starts a fresh cash count; after that every tap accumulates.
        if self.cash_tendered_cents == self.total and current == self.total:
            current = 0
        self.cash_tendered_cents = current + to_cents(str(amount))
        self.amount.set(f'{self.cash_tendered_cents / 100:.2f}')
        self.focus_amount()

    def clear_cash(self):
        self.method.set('CASH')
        self.cash_tendered_cents = 0
        self.amount.set('0.00')
        self.focus_amount()

    def exact(self):
        self.method.set('CASH')
        self.cash_tendered_cents = self.total
        self.amount.set(f'{self.total / 100:.2f}')
        self.focus_amount()

    def amount_changed(self, *_):
        if not hasattr(self, 'card_entry') or not hasattr(self, 'confirm_button'):
            return
        if self.method.get() == 'CASH':
            try:
                self.cash_tendered_cents = to_cents(self.amount.get())
            except Exception:
                pass
        self.update_amount()

    def paid_cents(self):
        if self.method.get() == 'CARD': return self.total
        cash=to_cents(self.amount.get())
        return cash + (to_cents(self.card_amount.get()) if self.method.get() == 'MIXED' else 0)

    def update_amount(self):
        method = self.method.get()
        card = method == 'CARD'
        mixed = method == 'MIXED'
        self.entry.configure(state='disabled' if card else 'normal')
        self.card_entry.configure(state='normal' if mixed else 'disabled')
        try:
            paid = self.paid_cents()
            cash = to_cents(self.amount.get()) if not card else 0
            card_paid = to_cents(self.card_amount.get()) if mixed else (self.total if card else 0)
            if paid < 0 or cash < 0 or card_paid < 0: raise ValueError()
            difference = paid - self.total
            credit=method=='CREDIT' and self.client_name is not None
            valid=(0<=paid<=self.total) if credit else (difference>=0 if method=='CASH' else difference==0)
            self.change.configure(text=('Reste à payer / باقي : ' if difference < 0 else 'Monnaie / الصرف : ') + fmt(abs(difference), self.currency), fg='#DC2626' if difference < 0 else '#166534')
            self.confirm_button.configure(state='normal' if valid else 'disabled')
            self.error.configure(text='Reste enregistré en dette client. Acompte en espèces.' if credit and valid else ('' if valid else 'Le paiement mixte doit couvrir exactement le ticket.' if mixed else 'Montant reçu invalide ou insuffisant.'))
        except Exception:
            self.change.configure(text='—'); self.error.configure(text='Saisissez un montant valide / دخل مبلغ صحيح'); self.confirm_button.configure(state='disabled')

    def confirm(self):
        try:
            paid = self.paid_cents()
            credit=self.method.get()=='CREDIT' and self.client_name is not None
            if (credit and not 0<=paid<=self.total) or (not credit and paid<self.total):
                self.update_amount()
                return
        except Exception:
            self.update_amount()
            return
        payments = None
        if self.method.get() == 'MIXED':
            payments = [('CASH', to_cents(self.amount.get())), ('CARD', to_cents(self.card_amount.get()))]
        self.result = (self.method.get(), paid, self.print_ticket.get(), payments)
        self.destroy()
