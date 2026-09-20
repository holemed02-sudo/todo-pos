import tkinter as tk
from tkinter import ttk, messagebox
from services.customers import list_customers, save_customer


class CustomerEditor(tk.Toplevel):
    def __init__(self, master, customer=None, on_saved=None):
        super().__init__(master)
        self.title('Client')
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.customer_id = customer['id'] if customer else None
        self.on_saved = on_saved
        self.name = tk.StringVar(value=(customer or {}).get('name', ''))
        self.phone = tk.StringVar(value=(customer or {}).get('phone', ''))
        form = ttk.Frame(self, padding=20)
        form.pack(fill='both', expand=True)
        for row, (label, variable) in enumerate([('Nom / الاسم', self.name), ('Téléphone / الهاتف', self.phone)]):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', pady=8)
            ttk.Entry(form, textvariable=variable, width=36).grid(row=row, column=1, padx=12)
        ttk.Label(form, text='Notes / ملاحظات').grid(row=2, column=0, sticky='nw')
        self.notes = tk.Text(form, width=36, height=5)
        self.notes.grid(row=2, column=1, padx=12)
        self.notes.insert('1.0', (customer or {}).get('notes', ''))
        ttk.Button(form, text='Enregistrer', style='Primary.TButton', command=self.save).grid(row=3, column=1, sticky='ew', padx=12, pady=16)
        ttk.Button(form, text='Annuler', command=self.destroy).grid(row=3, column=0)

    def save(self):
        try:
            customer_id = save_customer(self.name.get(), self.phone.get(), self.notes.get('1.0', 'end-1c'), self.customer_id)
        except (ValueError, PermissionError) as error:
            messagebox.showerror('Client', str(error), parent=self)
            return
        self.destroy()
        if self.on_saved:
            self.on_saved(customer_id)


class CustomersFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=16)
        ttk.Label(self, text='Clients / الزبناء', style='Title.TLabel').pack(anchor='w')
        ttk.Label(self, text="Règlements et état des crédits : à venir dans une étape séparée.",
                  foreground='#64748B').pack(anchor='w', pady=(0, 10))
        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', pady=12)
        self.query = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.query)
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<KeyRelease>', lambda event: self.refresh())
        ttk.Button(toolbar, text='Nouveau', command=lambda: CustomerEditor(self, on_saved=self.refresh)).pack(side='left', padx=8)
        ttk.Button(toolbar, text='Modifier', command=self.edit).pack(side='left')
        self.tree = ttk.Treeview(self, columns=('name', 'phone', 'notes'), show='headings')
        for key, label, width in [('name', 'Nom', 250), ('phone', 'Téléphone', 160), ('notes', 'Notes', 400)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width)
        scroll = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        scroll.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda event: self.edit())
        self.refresh()

    def refresh(self, selected=None):
        self.rows = {str(row['id']): row for row in list_customers(self.query.get())}
        self.tree.delete(*self.tree.get_children())
        for key, row in self.rows.items():
            self.tree.insert('', 'end', iid=key, values=(row['name'], row['phone'], row['notes']))
        if str(selected) in self.rows:
            self.tree.selection_set(str(selected))
            self.tree.see(str(selected))

    def edit(self):
        selected = self.tree.selection()
        if selected:
            CustomerEditor(self, self.rows[selected[0]], self.refresh)
