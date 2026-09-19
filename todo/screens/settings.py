import tkinter as tk
from tkinter import ttk,messagebox,filedialog,simpledialog
from database import get_setting,set_setting,connect
from services.backup import create_backup,restore_backup
from services.security import hash_pin, require_admin, audit

class SettingsFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=15);self.app=app
        ttk.Label(self,text="Paramètres / الإعدادات",font=("Segoe UI",22,"bold")).pack(anchor="w",pady=(0,12))
        f=ttk.LabelFrame(self,text="Magasin",padding=10);f.pack(fill="x")
        self.shop=tk.StringVar(value=get_setting("shop_name","ToDo"));self.cur=tk.StringVar(value=get_setting("currency","DH"));self.neg=tk.BooleanVar(value=get_setting("allow_negative_stock","0")=="1")
        ttk.Label(f,text="Nom magasin").grid(row=0,column=0,sticky="w");ttk.Entry(f,textvariable=self.shop,width=30).grid(row=0,column=1,padx=8)
        ttk.Label(f,text="Devise").grid(row=1,column=0,sticky="w",pady=5);ttk.Entry(f,textvariable=self.cur,width=10).grid(row=1,column=1,sticky="w",padx=8)
        ttk.Checkbutton(f,text="Autoriser stock négatif",variable=self.neg).grid(row=2,column=0,columnspan=2,sticky="w")
        ttk.Button(f,text="Enregistrer",command=self.save).grid(row=3,column=0,pady=8)
        b=ttk.LabelFrame(self,text="Données",padding=10);b.pack(fill="x",pady=10)
        ttk.Button(b,text="Backup maintenant",command=self.backup).pack(side="left",padx=4)
        ttk.Button(b,text="Restaurer backup",command=self.restore).pack(side="left",padx=4)
        u=ttk.LabelFrame(self,text="Utilisateurs",padding=10);u.pack(fill="x")
        ttk.Button(u,text="Nouvel utilisateur",command=self.new_user).pack(side="left")
        ttk.Button(u,text="Changer mon PIN",command=self.change_pin).pack(side="left",padx=8)
        ttk.Button(u,text="Journal des actions",command=self.audit_log).pack(side="left",padx=8)
        ttk.Label(u,text="Admin initial: admin / PIN 1234 — changez-le.").pack(side="left",padx=15)
    def save(self):
        set_setting("shop_name",self.shop.get().strip() or "ToDo");set_setting("currency",self.cur.get().strip() or "DH");set_setting("allow_negative_stock","1" if self.neg.get() else "0");messagebox.showinfo("ToDo","Enregistré.",parent=self)
    def backup(self):
        try:messagebox.showinfo("ToDo",f"Backup:\n{create_backup()}",parent=self)
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def restore(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("SQLite DB","*.db"),("Tous","*.*")])
        if not p:return
        if not messagebox.askyesno("ToDo","Restaurer ce backup ? Une copie de sécurité sera créée.",parent=self):return
        try:
            s=restore_backup(p)
            messagebox.showinfo('ToDo',f'Restauré. Copie sécurité: {s}\nLe programme va se fermer. Relancez ToDo.',parent=self)
            self.app.destroy()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def new_user(self):
        user=simpledialog.askstring("Utilisateur","Username:",parent=self)
        if not user:return
        name=simpledialog.askstring("Utilisateur","Nom affiché:",parent=self) or user
        pin=simpledialog.askstring("Utilisateur","PIN:",parent=self,show="*")
        if not pin:return
        if not pin.isdigit() or len(pin)<4:
            messagebox.showerror("ToDo","PIN: au moins 4 chiffres",parent=self);return
        role=simpledialog.askstring("Utilisateur","Role (admin/cashier):",parent=self) or "cashier"
        if role not in ("admin","cashier"):
            messagebox.showerror("ToDo","Rôle invalide",parent=self);return
        try:
            with connect() as c:c.execute("INSERT INTO users(username,display_name,pin_hash,role) VALUES(?,?,?,?)",(user,name,hash_pin(pin),role));c.commit()
            messagebox.showinfo("ToDo","Utilisateur créé.",parent=self)
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)

    def change_pin(self):
        pin=simpledialog.askstring('PIN','Nouveau PIN (4 chiffres minimum):',parent=self,show='*')
        if pin is None:return
        if not pin.isdigit() or len(pin)<4:
            messagebox.showerror('ToDo','Utilisez au moins 4 chiffres.',parent=self);return
        with connect() as conn:
            conn.execute('UPDATE users SET pin_hash=? WHERE id=?',(hash_pin(pin),self.app.user['id']))
            audit(conn,'PIN_CHANGE',self.app.user['id'])
        messagebox.showinfo('ToDo','PIN modifié.',parent=self)

    def audit_log(self):
        w=tk.Toplevel(self);w.title('Journal des actions');w.geometry('960x520')
        tree=ttk.Treeview(w,columns=('date','user','action','document','details'),show='headings')
        for key,label,width in [('date','Date',150),('user','Utilisateur',140),('action','Action',140),('document','Document',100),('details','Détails',300)]:
            tree.heading(key,text=label);tree.column(key,width=width)
        tree.pack(fill='both',expand=True,padx=12,pady=12)
        with connect() as conn:
            rows=conn.execute("SELECT a.*,COALESCE(u.display_name,'Système') username FROM audit_log a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 1000").fetchall()
        for r in rows:tree.insert('','end',values=(r['created_at'],r['username'],r['action'],r['document'],r['details']))
