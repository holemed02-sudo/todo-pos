from tkinter import ttk
from services.reports import today_summary
from services.money import fmt

class StatisticsFrame(ttk.Frame):
    def __init__(self,master):
        super().__init__(master,padding=22)
        ttk.Label(self,text='Statistiques',font=('Segoe UI',22,'bold')).pack(anchor='w')
        ttk.Label(self,text='Ventes mensuelles · Top articles · Top caissiers · Évolution',foreground='#475569').pack(anchor='w',pady=(4,18))
        data=today_summary(); cards=ttk.Frame(self);cards.pack(fill='x')
        for i,(label,value) in enumerate([('Total ventes',fmt(data['net_sales'])),('Tickets',str(data['tickets'])),('Total retours',fmt(data['refunds'])),('Stock faible',str(data['alerts']))]):
            card=ttk.Frame(cards,style='Card.TFrame',padding=18);card.grid(row=0,column=i,sticky='ew',padx=5);cards.columnconfigure(i,weight=1)
            ttk.Label(card,text=label,style='Card.TLabel').pack(anchor='w');ttk.Label(card,text=value,style='CardTitle.TLabel').pack(anchor='w',pady=(8,0))
        ttk.Label(self,text='الفترة',font=('Segoe UI',12,'bold')).pack(anchor='w',pady=(28,8))
        ttk.Combobox(self,values=['اليوم','هذا الأسبوع','هذا الشهر','هذه السنة'],state='readonly').pack(anchor='w')
        ttk.Label(self,text='الرسوم البيانية التفصيلية كتحتاج بيانات مبيعات، وكتبان منين تكون الفترة عامرة.',foreground='#64748B').pack(anchor='w',pady=20)
