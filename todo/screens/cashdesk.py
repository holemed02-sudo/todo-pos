import tkinter as tk
from tkinter import ttk,messagebox,simpledialog
from services.cash import get_open_session,open_session,close_session,session_totals,record_cash
from services.money import to_cents,fmt
from database import connect

class CashFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=15);self.app=app
        ttk.Label(self,text="Caisse / الصندوق",font=("Segoe UI",22,"bold")).pack(anchor="w",pady=(0,15))
        self.info=ttk.Label(self,text="",font=("Segoe UI",12));self.info.pack(anchor="w",pady=8)
        b=ttk.Frame(self);b.pack(anchor="w",pady=8)
        ttk.Button(b,text="Ouvrir caisse",command=self.open).pack(side="left",padx=4)
        ttk.Button(b,text="Dépense",command=self.expense).pack(side="left",padx=4)
        ttk.Button(b,text="Cash IN",command=lambda:self.cashmove("IN")).pack(side="left",padx=4)
        ttk.Button(b,text="Cash OUT",command=lambda:self.cashmove("OUT")).pack(side="left",padx=4)
        ttk.Button(b,text="Clôturer",command=self.close).pack(side="left",padx=4)
        self.details=tk.Text(self,height=16,font=("Consolas",11));self.details.pack(fill="x",pady=15);self.refresh()
    def refresh(self):
        s=get_open_session();self.details.config(state="normal");self.details.delete("1.0","end")
        if not s:self.info.config(text="Aucune caisse ouverte");self.details.config(state="disabled");return
        with connect() as c:t=session_totals(c,s["id"])
        self.info.config(text=f"Caisse #{s['id']} ouverte depuis {s['opened_at']}")
        txt=f"""Fond de caisse : {fmt(s['opening_cash_cents'])}
Ventes cash    : {fmt(t['cash_sales'])}
Retours cash   : {fmt(t['cash_returns'])}
Dépenses       : {fmt(t['expenses'])}
Cash IN        : {fmt(t['cash_in'])}
Cash OUT       : {fmt(t['cash_out'])}
"""
        self.details.insert("1.0",txt);self.details.config(state="disabled")
    def open(self):
        v=simpledialog.askfloat("Ouverture","Fond de caisse (DH):",parent=self,minvalue=0)
        if v is None:return
        try:open_session(self.app.user["id"],to_cents(v));self.refresh()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def expense(self):
        s=get_open_session()
        if not s:messagebox.showerror("ToDo","Ouvrez la caisse.",parent=self);return
        label=simpledialog.askstring("Dépense","Libellé:",parent=self)
        if not label:return
        amount=simpledialog.askfloat("Dépense","Montant (DH):",parent=self,minvalue=0.01)
        if amount is None:return
        try:record_cash(s['id'],self.app.user['id'],to_cents(amount),'EXPENSE',label)
        except Exception as e:messagebox.showerror('ToDo',str(e),parent=self);return
        self.refresh()
    def cashmove(self,typ):
        s=get_open_session()
        if not s:return
        amount=simpledialog.askfloat(typ,"Montant (DH):",parent=self,minvalue=0.01)
        if amount is None:return
        note=simpledialog.askstring(typ,"Note:",parent=self) or ""
        try:record_cash(s['id'],self.app.user['id'],to_cents(amount),typ,note)
        except Exception as e:messagebox.showerror('ToDo',str(e),parent=self);return
        self.refresh()
    def close(self):
        s=get_open_session()
        if not s:return
        actual=simpledialog.askfloat("Clôture","Cash réel compté (DH):",parent=self,minvalue=0)
        if actual is None:return
        try:
            expected,diff,t=close_session(s["id"],to_cents(actual))
            messagebox.showinfo("Clôture",f"Attendu: {fmt(expected)}\nRéel: {actual:.2f} DH\nDifférence: {fmt(diff)}",parent=self);self.refresh()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
