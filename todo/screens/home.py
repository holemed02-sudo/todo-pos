from tkinter import ttk
from services.reports import today_summary
from services.money import fmt


class HomeFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=22)
        ttk.Label(self,text='TODOMARKET',style='Title.TLabel').pack(pady=(28,6))
        ttk.Label(self,text='Vente · Stock · Journal · Gestion · Paramètres · Statistiques',font=('Segoe UI',12)).pack(pady=(0,28))
        menu=ttk.Frame(self);menu.pack(anchor='center')
        items=[('▣','Vente','sale'),('▤','Stock','stock'),('▦','Journal','journal'),('▰','Gestion','management'),('⚙','Paramètres','settings'),('▥','Statistiques','statistics')]
        for i,(icon,label,key) in enumerate(items):
            card=ttk.Frame(menu,style='Card.TFrame',padding=14);card.grid(row=0,column=i,padx=7)
            ttk.Button(card,text=f'{icon}\n{label}',command=lambda k=key:app.show(k),width=13).pack(ipady=18)
        ttk.Button(self,text='⏻  Sortir',command=app.on_close).pack(pady=50)
