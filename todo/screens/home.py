from tkinter import ttk
from services.reports import today_summary
from services.money import fmt


class HomeFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=22)
        ttk.Label(self,text='Aujourd’hui / اليوم',style='Title.TLabel').pack(anchor='w')
        ttk.Label(self,text=f"Bonjour {app.user['display_name']} · Vue du magasin",font=('Segoe UI',12)).pack(anchor='w',pady=(5,22))
        data=today_summary()
        cards=ttk.Frame(self);cards.pack(fill='x')
        values=[('Ventes nettes',fmt(data['net_sales'])),('Tickets',str(data['tickets'])),('Stock faible',str(data['alerts'])),('En attente',str(data['held']))]
        if app.user['role']=='admin':values.insert(1,('Marge brute',fmt(data['gross_margin'])))
        for index,(label,value) in enumerate(values):
            card=ttk.Frame(cards,padding=18,style='Card.TFrame');card.grid(row=0,column=index,sticky='nsew',padx=5)
            cards.columnconfigure(index,weight=1)
            ttk.Label(card,text=label,style='Card.TLabel').pack(anchor='w')
            ttk.Label(card,text=value,style='CardTitle.TLabel').pack(anchor='w',pady=(10,0))
        ttk.Label(self,text='Marge brute après remises et retours, avant frais et taxes. Les retours sont comptés à leur date.').pack(anchor='w',pady=14)
        ttk.Label(self,text='Dernières opérations',font=('Segoe UI',16,'bold')).pack(anchor='w',pady=(12,10))
        tree=ttk.Treeview(self,columns=('type','document','amount','date'),show='headings')
        for key,title,width in [('type','TYPE',80),('document','DOCUMENT',310),('amount','MONTANT',110),('date','DATE',160)]:
            tree.heading(key,text=title);tree.column(key,width=width)
        tree.pack(fill='both',expand=True)
        for row in data['recent']:tree.insert('','end',values=(row['kind'],row['document'],fmt(row['amount']),row['created_at']))
        ttk.Button(self,text='Ouvrir la vente',style='Primary.TButton',command=lambda:app.show('sale')).pack(anchor='e',pady=16)
