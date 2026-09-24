from database import get_setting
import tkinter as tk
from tkinter import ttk
from services.money import fmt, to_cents


class PaymentDialog(tk.Toplevel):
    """Collect a payment choice; closing this dialog never writes a sale."""

    def __init__(self, master, total, currency='DH', method='CASH', client_name=None):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.client_name = client_name
        self.total = total
        self.currency = currency
        self.result = None
        self.title(self.tr('Encaissement','الخلاص'))
        self.geometry(f'580x{min(650,self.winfo_screenheight()-90)}')
        self.configure(bg='#F6F7FB')
        self.transient(master.winfo_toplevel())
        self.method = tk.StringVar(value=method)
        self.amount = tk.StringVar(value=f'{total / 100:.2f}')
        self.card_amount = tk.StringVar(value='0.00')
        self.print_ticket = tk.BooleanVar(value=False)
        self.cash_parts = {}
        self.cash_count_started = False
        self.cash_tendered_cents = total
        tk.Label(self, text=self.tr('TOTAL À PAYER','المجموع'), bg='#2563EB', fg='white',
                 font=('Segoe UI', 13, 'bold')).pack(fill='x', pady=(0, 0))
        tk.Label(self, text=fmt(total, currency), bg='#2563EB', fg='white',
                 font=('Segoe UI', 34, 'bold')).pack(fill='x', ipady=12)
        controls = ttk.Frame(self, padding=8)
        controls.pack(side='bottom',fill='x')
        body = ttk.Frame(self, padding=10)
        body.pack(fill='both', expand=True)
        modes = ttk.Frame(body)
        modes.pack(fill='x', pady=(0, 12))
        choices=[(self.tr('F2 Espèces','F2 نقداً'),'CASH'),(self.tr('F3 Carte','F3 بطاقة'),'CARD'),(self.tr('Mixte','مختلط'),'MIXED')]
        if client_name:choices.append((self.tr('Crédit','دين'),'CREDIT'))
        if client_name:ttk.Label(body,text=self.tr('Client : ','الزبون: ')+client_name).pack(anchor='w')
        for label, value in choices:
            ttk.Radiobutton(modes, text=label, variable=self.method, value=value,
                            command=self.update_amount).pack(side='left', expand=True, padx=8)
        self.method.trace_add('write', self.method_changed)
        ttk.Label(body, text=self.tr('Montant reçu','المبلغ المدفوع')).pack(anchor='w')
        self.entry = ttk.Entry(body, textvariable=self.amount, font=('Segoe UI', 24), justify='right')
        self.entry.pack(fill='x', pady=8)
        ttk.Label(body, text=self.tr('Billets / pièces reçus','النقد المستلم')).pack(anchor='w', pady=(4, 0))
        denominations = ttk.Frame(body)
        denominations.pack(fill='x', pady=6)
        for index, value in enumerate((200, 100, 50, 20, 10, 5, 2, 1, 0.5)):
            ttk.Button(denominations, text=f'{value:g} DH', command=lambda n=value: self.add_cash(n)).grid(
                row=index//5, column=index%5, sticky='nsew', padx=3, pady=3, ipady=5)
        self.cash_breakdown = ttk.Label(body, text='')
        self.cash_breakdown.pack(fill='x', pady=(0,4))
        for column in range(5):
            denominations.columnconfigure(column, weight=1)
        ttk.Button(body, text=self.tr('Effacer espèces','مسح النقد'), command=self.clear_cash).pack(fill='x', pady=(0, 4))
        ttk.Button(body, text=self.tr('Montant exact','المبلغ بالضبط'), command=self.exact).pack(fill='x', pady=4)
        ttk.Label(body, text=self.tr('Part carte (mode mixte)','جزء البطاقة في الدفع المختلط')).pack(anchor='w', pady=(8,0))
        self.card_entry = ttk.Entry(body, textvariable=self.card_amount, font=('Segoe UI', 18), justify='right')
        self.card_entry.pack(fill='x', pady=4)
        self.change = tk.Label(body, bg='white', fg='#166534', font=('Segoe UI', 23, 'bold'), pady=14)
        self.change.pack(fill='x', pady=14)
        self.error = ttk.Label(body, foreground='#DC2626', wraplength=500)
        self.error.pack(fill='x')
        ttk.Checkbutton(body, text=self.tr('Imprimer le ticket','طباعة التذكرة'), variable=self.print_ticket).pack(anchor='w', pady=12)
        self.confirm_button = ttk.Button(controls, text=self.tr('VALIDER  Entrée','تأكيد  Enter'), style='Primary.TButton', command=self.confirm)
        self.confirm_button.pack(fill='x', ipady=12, pady=8)
        ttk.Button(controls, text=self.tr('Retour au ticket  Esc','رجوع  Esc'), command=self.destroy).pack(fill='x', ipady=6)
        self.amount.trace_add('write', self.amount_changed)
        self.card_amount.trace_add('write', self.amount_changed)
        self.bind('<Return>', lambda e: self.confirm())
        self.bind('<Escape>', lambda e: self.destroy())
        self.bind('<F2>', lambda e: self.choose_method('CASH'))
        self.bind('<F3>', lambda e: self.choose_method('CARD'))
        self.grab_set()
        self.update_amount()
        self.after_idle(self.focus_amount)

    def method_changed(self, *_):
        if not hasattr(self, 'card_entry'):
            return
        if self.method.get() == 'MIXED':
            try:
                cash=to_cents(self.amount.get())
            except Exception:
                cash=0
            self.card_amount.set(f'{max(0,self.total-cash)/100:.2f}')
        self.update_amount()

    def focus_amount(self):
        self.entry.focus_set()
        self.entry.selection_range(0, 'end')

    def choose_method(self, method):
        self.method.set(method)
        self.update_amount()

    def set_amount(self, amount):
        self.method.set('CASH')
        self.cash_parts.clear();self.cash_count_started=False;self._render_cash_parts()
        self.cash_tendered_cents = to_cents(str(amount))
        self.amount.set(f'{amount:.2f}')
        self.focus_amount()

    def add_cash(self, amount):
        # Denomination buttons are a cashier cash counter. The first tap starts
        # from zero; following taps always accumulate, even when the running
        # count happens to equal the ticket total.
        if self.method.get() not in ('CASH','CREDIT','MIXED'):self.method.set('CASH')
        current=self.cash_tendered_cents if self.cash_count_started else 0
        self.cash_count_started=True
        self.cash_parts[amount]=self.cash_parts.get(amount,0)+1
        self.cash_tendered_cents = current + to_cents(str(amount))
        self._render_cash_parts()
        self.amount.set(f'{self.cash_tendered_cents / 100:.2f}')
        self.focus_amount()

    def clear_cash(self):
        self.method.set('CASH')
        self.cash_tendered_cents = 0
        self.cash_parts.clear();self.cash_count_started=True;self._render_cash_parts()
        self.amount.set('0.00')
        self.focus_amount()

    def exact(self):
        self.method.set('CASH')
        self.cash_tendered_cents = self.total
        self.cash_parts.clear();self.cash_count_started=False;self._render_cash_parts()
        self.amount.set(f'{self.total / 100:.2f}')
        self.focus_amount()

    def amount_changed(self, *_):
        if not hasattr(self, 'card_entry') or not hasattr(self, 'confirm_button'):
            return
        if self.method.get() in ('CASH','MIXED'):
            try:
                self.cash_tendered_cents = to_cents(self.amount.get())
            except Exception:
                pass
        if self.method.get() == 'MIXED':
            try:
                cash=to_cents(self.amount.get())
                card=to_cents(self.card_amount.get())
                if cash + card != self.total:
                    self.card_amount.set(f'{max(0,self.total-cash)/100:.2f}')
            except Exception:
                pass
        self.update_amount()

    def _render_cash_parts(self):
        if not hasattr(self,'cash_breakdown'):return
        parts=[f"{value:g}×{count}" for value,count in sorted(self.cash_parts.items(),reverse=True) if count]
        self.cash_breakdown.configure(text=(self.tr('Compté : ','محسوب: ')+'  ·  '.join(parts)) if parts else '')

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
            self.change.configure(text=(self.tr('Reste à payer : ','الباقي للأداء: ') if difference < 0 else self.tr('Monnaie : ','الصرف: ')) + fmt(abs(difference), self.currency), fg='#DC2626' if difference < 0 else '#166534')
            self.confirm_button.configure(state='normal' if valid else 'disabled')
            self.error.configure(text=self.tr('Reste enregistré en dette client. Acompte en espèces.','تم تسجيل الباقي كدين على الزبون. التسبيق نقدي.') if credit and valid else ('' if valid else self.tr('Le paiement mixte doit couvrir exactement le ticket.','يجب أن يغطي الأداء المختلط مبلغ التذكرة بالكامل.') if mixed else self.tr('Montant reçu invalide ou insuffisant.','المبلغ المدفوع غير صالح أو غير كافٍ.')))
        except Exception:
            self.change.configure(text='—'); self.error.configure(text=self.tr('Saisissez un montant valide','أدخل مبلغا صحيحا')); self.confirm_button.configure(state='disabled')

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
