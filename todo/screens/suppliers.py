import tkinter as tk
from tkinter import ttk, messagebox
from database import connect, get_setting
from services.money import fmt
from services.suppliers import list_suppliers, save_supplier


class SupplierEditor(tk.Toplevel):
    def __init__(self, master, supplier=None, on_saved=None):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.title(self.tr('Fournisseur','المورد'))
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self.supplier_id = supplier['id'] if supplier else None
        self.on_saved = on_saved
        self.name = tk.StringVar(value=(supplier or {}).get('name', ''))
        self.phone = tk.StringVar(value=(supplier or {}).get('phone', ''))
        form = ttk.Frame(self, padding=20)
        form.pack(fill='both', expand=True)
        for row, (label, variable) in enumerate([(self.tr('Nom','الاسم'), self.name), (self.tr('Téléphone','الهاتف'), self.phone)]):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', pady=8)
            ttk.Entry(form, textvariable=variable, width=36).grid(row=row, column=1, padx=12)
        ttk.Label(form, text=self.tr('Notes','ملاحظات')).grid(row=2, column=0, sticky='nw')
        self.notes = tk.Text(form, width=36, height=5)
        self.notes.grid(row=2, column=1, padx=12)
        self.notes.insert('1.0', (supplier or {}).get('notes', ''))
        ttk.Button(form, text=self.tr('Enregistrer','حفظ'), style='Primary.TButton', command=self.save).grid(row=3, column=1, sticky='ew', padx=12, pady=16)
        ttk.Button(form, text=self.tr('Annuler','إلغاء'), command=self.destroy).grid(row=3, column=0)

    def save(self):
        try:
            supplier_id = save_supplier(self.name.get(), self.phone.get(), self.notes.get('1.0', 'end-1c'), self.supplier_id)
        except (ValueError, PermissionError) as error:
            messagebox.showerror(self.tr('Fournisseur','المورد'), str(error), parent=self)
            return
        self.destroy()
        if self.on_saved:
            self.on_saved(supplier_id)


class SuppliersFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=16)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        ttk.Label(self, text=self.tr('Fournisseurs','الموردون'), style='Title.TLabel').pack(anchor='w')
        toolbar = ttk.Frame(self)
        toolbar.pack(fill='x', pady=12)
        self.query = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.query)
        entry.pack(side='left', fill='x', expand=True)
        entry.bind('<KeyRelease>', lambda event: self.refresh())
        ttk.Button(toolbar, text=self.tr('Nouveau','جديد'), command=lambda: SupplierEditor(self, on_saved=self.refresh)).pack(side='left', padx=8)
        ttk.Button(toolbar, text=self.tr('Modifier','تعديل'), command=self.edit).pack(side='left')
        ttk.Button(toolbar, text=self.tr('Réceptions du fournisseur','استلامات المورد'), command=self.history).pack(side='left', padx=8)
        self.tree = ttk.Treeview(self, columns=('name', 'phone', 'notes'), show='headings')
        for key, label, width in [('name', self.tr('Nom','الاسم'), 250), ('phone', self.tr('Téléphone','الهاتف'), 160), ('notes', self.tr('Notes','ملاحظات'), 400)]:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width)
        scroll = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        scroll.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda event: self.edit())
        self.refresh()

    def refresh(self, selected=None):
        self.rows = {str(row['id']): row for row in list_suppliers(self.query.get())}
        self.tree.delete(*self.tree.get_children())
        for key, row in self.rows.items():
            self.tree.insert('', 'end', iid=key, values=(row['name'], row['phone'], row['notes']))
        if str(selected) in self.rows:
            self.tree.selection_set(str(selected))
            self.tree.see(str(selected))

    def edit(self):
        selected = self.tree.selection()
        if selected:
            SupplierEditor(self, self.rows[selected[0]], self.refresh)

    def history(self):
        selected = self.tree.selection()
        if not selected:
            return
        supplier = self.rows[selected[0]]
        window = tk.Toplevel(self)
        window.title(self.tr('Réceptions','الاستلامات')+' — '+supplier['name'])
        window.geometry('760x420')
        with connect() as conn:
            rows = conn.execute('SELECT * FROM purchases WHERE supplier_id=? ORDER BY id DESC', (supplier['id'],)).fetchall()
        total = fmt(sum(row['total_cents'] for row in rows))
        ttk.Label(window, text=self.tr(f"{len(rows)} réception(s) · Total achats : {total}", f"{len(rows)} استلام · إجمالي المشتريات: {total}")).pack(pady=12)
        tree = ttk.Treeview(window, columns=('id', 'date', 'invoice', 'total'), show='headings')
        for key, label in [('id', self.tr('Réception','الاستلام')), ('date', self.tr('Date','التاريخ')), ('invoice', self.tr('Facture fournisseur','فاتورة المورد')), ('total', self.tr('Total achats','إجمالي المشتريات'))]:
            tree.heading(key, text=label)
            tree.column(key, width=170)
        tree.pack(fill='both', expand=True, padx=12, pady=12)
        for row in rows:
            tree.insert('', 'end', values=(row['id'], row['created_at'], row['supplier_invoice'], fmt(row['total_cents'])))
