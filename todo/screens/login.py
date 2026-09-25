import tkinter as tk
from screens.virtual_keyboard import VirtualKeyboard
from tkinter import ttk, messagebox
from database import connect, get_setting
from services.security import verify_pin

class LoginDialog(tk.Toplevel):
    def __init__(self,master,on_login):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.on_login=on_login
        self.title('ToDo — '+self.tr('Connexion','تسجيل الدخول'))
        self.geometry("460x330")
        self.resizable(False,False)
        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", master.destroy)
        self.configure(bg='#0F172A')
        f=ttk.Frame(self,padding=30,style='Card.TFrame');f.pack(fill='both',expand=True,padx=22,pady=22)
        ttk.Label(f,text="ToDo POS",style="CardTitle.TLabel",font=("Segoe UI",26,"bold")).pack(pady=(0,6))
        ttk.Label(f,text=self.tr("Connexion caisse","تسجيل الدخول إلى الصندوق"),style="Card.TLabel",foreground="#64748B").pack(pady=(0,18))
        self.user=tk.StringVar(value="admin");self.pin=tk.StringVar()
        ttk.Entry(f,textvariable=self.user,font=("Segoe UI",12),style="Search.TEntry").pack(fill="x",pady=6)
        e=ttk.Entry(f,textvariable=self.pin,show="●",font=("Segoe UI",18),justify="center")
        e.pack(fill="x",pady=5);e.bind("<Return>",lambda x:self.login())
        ttk.Button(f,text=self.tr('Entrer','دخول'),style='Success.TButton',command=self.login).pack(fill='x',pady=14,ipady=5)
        e.focus_force()
    def login(self):
        with connect() as c:
            u=c.execute("SELECT * FROM users WHERE username=? AND active=1",(self.user.get().strip(),)).fetchone()
        if not u or not verify_pin(self.pin.get(),u["pin_hash"]):
            messagebox.showerror("ToDo",self.tr('Utilisateur/PIN incorrect.','اسم المستخدم أو الرمز غير صحيح.'),parent=self);return
        self.destroy();self.on_login(dict(u))
