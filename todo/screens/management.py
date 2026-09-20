from tkinter import ttk, messagebox

class ManagementFrame(ttk.Frame):
    """Reference entries, with explicit status for unfinished workflows."""
    def __init__(self, master, app):
        super().__init__(master, padding=30)
        ttk.Label(self, text='Gestion', font=('Segoe UI',22,'bold')).pack(pady=(0,22))
        groups=[
            [('Réceptions','purchases'),('Sorties',None),('Inventaire',None),('Mouvements de stock','stock')],
            [('Fournisseurs','suppliers'),('Règlements fournisseurs',None),('État crédits fournisseurs',None)],
            [('Clients','customers'),('Règlements clients',None),('État crédits clients',None)],
            [('Dépenses','cash'),('Rendez-vous',None)],
        ]
        for row,items in enumerate(groups):
            line=ttk.Frame(self);line.pack(pady=8)
            for label,key in items:
                def activate(k=key, title=label):
                    if k:
                        app.show(k)
                        if title == 'Dépenses':
                            app.current.expense()
                    else:
                        messagebox.showinfo(title, 'Cette fonction du référentiel reste à implémenter.\nهاد الخدمة مازال ما تكملاتش.', parent=self)
                button=ttk.Button(line,text=label if key else label+' · à compléter',width=25,command=activate)
                button.pack(side='left',padx=8,ipady=12)
