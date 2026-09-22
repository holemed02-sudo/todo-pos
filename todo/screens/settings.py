from database import connect
import tkinter as tk
from tkinter import ttk,messagebox,filedialog,simpledialog
from database import get_setting,set_setting,connect
from services.backup import create_backup,restore_backup
from services.security import hash_pin, require_admin, audit



class CategoryEditor(tk.Toplevel):
    """Edit or create a category — name, color, icon."""
    PALETTE = [
        '#DC2626','#EA580C','#D97706','#65A30D','#16A34A',
        '#0891B2','#2563EB','#7C3AED','#DB2777','#6B7280',
        '#0F766E','#B45309','#1D4ED8','#7E22CE','#BE185D',
    ]
    ICONS = ['','🥩','🧃','🥖','🍎','🧴','🧹','🧊','🥛','🍫',
             '🫙','🧺','💊','🐟','🌿','🔧','📦','🍬','🥚','🧀']

    def __init__(self, master, cat=None, on_saved=None):
        super().__init__(master)
        self.cat_id  = cat['id']   if cat else None
        self.on_saved= on_saved
        self.title('Famille / عائلة')
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.name_var  = tk.StringVar(value=cat['name']  if cat else '')
        self.color_var = tk.StringVar(value=cat['color'] if cat else '#2563EB')
        self.icon_var  = tk.StringVar(value=cat['icon']  if cat else '')

        f = ttk.Frame(self, padding=20); f.pack(fill='both', expand=True)

        ttk.Label(f, text='Nom / الاسم').grid(row=0, column=0, sticky='w')
        ttk.Entry(f, textvariable=self.name_var, width=30).grid(row=0, column=1, columnspan=3, sticky='ew', pady=6)

        ttk.Label(f, text='Couleur').grid(row=1, column=0, sticky='w', pady=8)
        self.swatch = tk.Label(f, width=6, relief='groove')
        self.swatch.grid(row=1, column=1, sticky='w', padx=4)
        self._update_swatch()

        palette_frame = ttk.Frame(f); palette_frame.grid(row=2, column=0, columnspan=4, sticky='ew', pady=4)
        for i, color in enumerate(self.PALETTE):
            btn = tk.Button(palette_frame, bg=color, width=2, height=1, relief='flat', cursor='hand2',
                            command=lambda c=color: self._pick(c))
            btn.grid(row=i//8, column=i%8, padx=2, pady=2)

        ttk.Label(f, text='Icône').grid(row=3, column=0, sticky='w', pady=8)
        icon_frame = ttk.Frame(f); icon_frame.grid(row=3, column=1, columnspan=3, sticky='ew')
        for i,icon in enumerate(self.ICONS):
            lbl = icon if icon else '—'
            tk.Button(icon_frame, text=lbl, width=3, font=('Segoe UI', 12),
                      relief='flat', cursor='hand2',
                      command=lambda ic=icon: self.icon_var.set(ic)).grid(row=i//7,column=i%7,padx=1)

        ttk.Button(f, text='Enregistrer', style='Primary.TButton',
                   command=self.save).grid(row=4, column=0, columnspan=4, sticky='ew', pady=16)

    def _pick(self, color):
        self.color_var.set(color)
        self._update_swatch()

    def _update_swatch(self):
        self.swatch.config(bg=self.color_var.get(), text=self.color_var.get(),
                           fg='#ffffff', font=('Consolas', 8))

    def save(self):
        name  = self.name_var.get().strip()
        color = self.color_var.get().strip() or '#2563EB'
        icon  = self.icon_var.get().strip()
        if not name:
            from tkinter import messagebox
            messagebox.showerror('Famille', 'Le nom est obligatoire.', parent=self); return
        with connect() as conn:
            require_admin(conn)
            if self.cat_id:
                conn.execute('UPDATE categories SET name=?,color=?,icon=? WHERE id=?',
                             (name, color, icon, self.cat_id))
            else:
                conn.execute('INSERT INTO categories(name,color,icon) VALUES(?,?,?)',
                             (name, color, icon))
            conn.commit()
        self.destroy()
        if self.on_saved: self.on_saved()

class SettingsFrame(ttk.Frame):
    def __init__(self,master,app):
        super().__init__(master,padding=15);self.app=app
        ttk.Label(self,text="Paramètres / الإعدادات",font=("Segoe UI",22,"bold")).pack(anchor="w",pady=(0,12))
        f=ttk.LabelFrame(self,text="Magasin et vente",padding=10);f.pack(fill="x")
        self.shop=tk.StringVar(value=get_setting("shop_name","ToDo"));self.cur=tk.StringVar(value=get_setting("currency","DH"));self.neg=tk.BooleanVar(value=get_setting("allow_negative_stock","1")=="1")
        self.footer=tk.StringVar(value=get_setting("receipt_footer","Merci"))
        self.search_limit=tk.StringVar(value=get_setting("search_limit","60"))
        ttk.Label(f,text="Nom magasin").grid(row=0,column=0,sticky="w");ttk.Entry(f,textvariable=self.shop,width=30).grid(row=0,column=1,padx=8)
        ttk.Label(f,text="Devise").grid(row=1,column=0,sticky="w",pady=5);ttk.Entry(f,textvariable=self.cur,width=10).grid(row=1,column=1,sticky="w",padx=8)
        ttk.Checkbutton(f,text="Autoriser stock négatif",variable=self.neg).grid(row=2,column=0,columnspan=2,sticky="w")
        ttk.Label(f,text="Message bas du ticket").grid(row=3,column=0,sticky="w",pady=5);ttk.Entry(f,textvariable=self.footer,width=34).grid(row=3,column=1,padx=8)
        ttk.Label(f,text="Limite résultats recherche").grid(row=4,column=0,sticky="w");ttk.Entry(f,textvariable=self.search_limit,width=10).grid(row=4,column=1,sticky="w",padx=8)
        ttk.Button(f,text="Enregistrer",command=self.save).grid(row=5,column=0,pady=8)
        p=ttk.LabelFrame(self,text="Impression / الطباعة",padding=10);p.pack(fill="x",pady=10)
        self.printer=tk.StringVar(value=get_setting("printer_name",""));self.print_mode=tk.StringVar(value=get_setting("print_mode","ask"))
        ttk.Label(p,text="Imprimante (اختياري)").grid(row=0,column=0,sticky="w")
        self.printer_choice=ttk.Combobox(p,textvariable=self.printer,width=34)
        self.printer_choice.grid(row=0,column=1,padx=8)
        ttk.Button(p,text='Actualiser imprimantes',command=self.refresh_printers).grid(row=0,column=2,padx=5)
        ttk.Label(p,text="Après validation").grid(row=1,column=0,sticky="w",pady=5)
        ttk.Combobox(p,textvariable=self.print_mode,values=['ask','always','never'],state='readonly',width=12).grid(row=1,column=1,sticky='w',padx=8)
        ttk.Label(p,text="ask = يسولك، always = يطبع، never = بلا طباعة").grid(row=2,column=0,columnspan=2,sticky='w')
        self.drawer_enabled=tk.BooleanVar(value=get_setting('drawer_enabled','0')=='1')
        self.drawer_pin=tk.StringVar(value=get_setting('drawer_pin','0'))
        ttk.Checkbutton(p,text='Tiroir connecté à une imprimante ESC/POS',variable=self.drawer_enabled).grid(row=3,column=0,columnspan=2,sticky='w')
        ttk.Label(p,text='Connecteur tiroir').grid(row=4,column=0,sticky='w')
        ttk.Combobox(p,textvariable=self.drawer_pin,values=['0','1'],state='readonly',width=5).grid(row=4,column=1,sticky='w',padx=8)
        ttk.Button(p,text='Enregistrer impression',command=self.save).grid(row=4,column=2)
        d=ttk.LabelFrame(self,text="Écran client / شاشة الزبون",padding=10);d.pack(fill="x",pady=10)
        self.customer_seconds=tk.StringVar(value=get_setting("customer_slide_seconds","6"))
        ttk.Label(d,text="Durée de chaque image (secondes)").pack(side="left")
        ttk.Spinbox(d,from_=2,to=120,textvariable=self.customer_seconds,width=6).pack(side="left",padx=8)
        ttk.Label(d,text="Dossier : customer_media · PNG/JPG/WEBP · format conseillé 16:9",foreground="#475569").pack(side="left",padx=12)
        ttk.Button(d,text="Tester écran client",command=self.test_customer).pack(side="right")
        b=ttk.LabelFrame(self,text="Données",padding=10);b.pack(fill="x",pady=10)
        ttk.Button(b,text="Backup maintenant",command=self.backup).pack(side="left",padx=4)
        self.auto_backup=tk.StringVar(value=get_setting("auto_backup_minutes","15"))
        ttk.Label(b,text="Backup auto").pack(side="left",padx=(18,4))
        ttk.Combobox(b,textvariable=self.auto_backup,values=["0","5","10","15","30","60"],state="readonly",width=5).pack(side="left")
        ttk.Label(b,text="min (0 = désactivé)").pack(side="left",padx=4)
        ttk.Button(b,text="Restaurer backup",command=self.restore).pack(side="left",padx=4)
        u=ttk.LabelFrame(self,text="Utilisateurs",padding=10);u.pack(fill="x")
        ttk.Button(u,text="Nouvel utilisateur",command=self.new_user).pack(side="left")
        ttk.Button(u,text="Changer mon PIN",command=self.change_pin).pack(side="left",padx=8)
        ttk.Button(u,text="Journal des actions",command=self.audit_log).pack(side="left",padx=8)
        ttk.Label(u,text="Admin initial: admin / PIN 1234 — changez-le.").pack(side="left",padx=15)
    def save(self):
        try:
            limit=int(self.search_limit.get())
            if limit<1 or limit>1000:raise ValueError()
        except ValueError:
            messagebox.showerror("ToDo","Limite recherche بين 1 و1000.",parent=self);return
        set_setting("shop_name",self.shop.get().strip() or "ToDo");set_setting("currency",self.cur.get().strip() or "DH");set_setting("allow_negative_stock","1" if self.neg.get() else "0")
        set_setting("receipt_footer",self.footer.get());set_setting("search_limit",limit);set_setting("printer_name",self.printer.get().strip());set_setting("print_mode",self.print_mode.get())
        set_setting('drawer_enabled','1' if self.drawer_enabled.get() else '0');set_setting('drawer_pin',self.drawer_pin.get())
        try:
            seconds=int(self.customer_seconds.get())
            if seconds<2 or seconds>120:raise ValueError()
        except ValueError:
            messagebox.showerror("ToDo","Durée écran client entre 2 et 120 secondes.",parent=self);return
        set_setting("customer_slide_seconds",str(seconds))
        set_setting("auto_backup_minutes",self.auto_backup.get())
        self.app.schedule_auto_backup()
        messagebox.showinfo("ToDo","الإعدادات تسجلات.",parent=self)
    def test_customer(self):
        self.app.toggle_customer_display()

    def refresh_printers(self):
        from services.printers import installed_printers
        try:self.printer_choice['values']=installed_printers()
        except Exception as error:messagebox.showerror('Imprimantes',str(error),parent=self)

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
