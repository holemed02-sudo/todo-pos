from tkinter import ttk

class ManagementFrame(ttk.Frame):
    """The six groups shown by the reference Gestion screen."""
    def __init__(self, master, app):
        super().__init__(master, padding=30)
        ttk.Label(self, text='Gestion', font=('Segoe UI',22,'bold')).pack(pady=(0,22))
        groups=[
            [('Articles / المنتجات','products'),('Réceptions','purchases'),('Sorties','returns'),('Inventaire','stock')],
            [('Mouvements de stock','stock'),('Fournisseurs','purchases'),('Règlements fournisseurs','cash'),('État crédits fournisseurs','journal')],
            [('Fournisseurs','purchases'),('Règlements fournisseurs','cash'),('État crédits fournisseurs','journal')],
            [('Clients','returns'),('Règlements clients','cash'),('État crédits clients','journal')],
            [('Dépenses','cash'),('Rendez-vous',None)],
        ]
        for row,items in enumerate(groups):
            line=ttk.Frame(self);line.pack(pady=8)
            for label,key in items:
                button=ttk.Button(line,text=label,width=21,command=(lambda k=key:app.show(k)) if key else None)
                button.pack(side='left',padx=8,ipady=12)
