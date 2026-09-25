from database import connect
import tkinter as tk
from tkinter import ttk,messagebox,filedialog,simpledialog
from database import get_setting,set_setting,connect
from services.backup import create_backup,restore_backup,create_full_backup,restore_full_backup
from services.security import hash_pin, require_admin, audit



def _sync_windows_startup(enabled):
    """Register/unregister ToDo for the current Windows user."""
    if os.name != 'nt':
        return
    import winreg
    key_path=r'Software\Microsoft\Windows\CurrentVersion\Run'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key_path,0,winreg.KEY_SET_VALUE) as key:
        if enabled:
            if getattr(sys,'frozen',False):
                command=f'"{sys.executable}"'
            else:
                root=Path(__file__).resolve().parents[2]
                py=Path(sys.executable)
                pythonw=py.with_name('pythonw.exe')
                launcher=pythonw if pythonw.exists() else py
                command=f'"{launcher}" "{root / "ToDo.pyw"}"'
            winreg.SetValueEx(key,'ToDoPOS',0,winreg.REG_SZ,command)
        else:
            try:winreg.DeleteValue(key,'ToDoPOS')
            except FileNotFoundError:pass

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
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.cat_id  = cat['id']   if cat else None
        self.on_saved= on_saved
        self.title(self.tr('Famille','العائلة'))
        self.resizable(False, False)
        self.transient(master.winfo_toplevel())
        self.grab_set()

        self.name_var  = tk.StringVar(value=cat['name']  if cat else '')
        self.color_var = tk.StringVar(value=cat['color'] if cat else '#2563EB')
        self.icon_var  = tk.StringVar(value=cat['icon']  if cat else '')

        f = ttk.Frame(self, padding=20); f.pack(fill='both', expand=True)

        ttk.Label(f, text=self.tr('Nom','الاسم')).grid(row=0, column=0, sticky='w')
        ttk.Entry(f, textvariable=self.name_var, width=30).grid(row=0, column=1, columnspan=3, sticky='ew', pady=6)

        ttk.Label(f, text=self.tr('Couleur','اللون')).grid(row=1, column=0, sticky='w', pady=8)
        self.swatch = tk.Label(f, width=6, relief='groove')
        self.swatch.grid(row=1, column=1, sticky='w', padx=4)
        self._update_swatch()

        palette_frame = ttk.Frame(f); palette_frame.grid(row=2, column=0, columnspan=4, sticky='ew', pady=4)
        for i, color in enumerate(self.PALETTE):
            btn = tk.Button(palette_frame, bg=color, width=2, height=1, relief='flat', cursor='hand2',
                            command=lambda c=color: self._pick(c))
            btn.grid(row=i//8, column=i%8, padx=2, pady=2)

        ttk.Label(f, text=self.tr('Icône','الأيقونة')).grid(row=3, column=0, sticky='w', pady=8)
        icon_frame = ttk.Frame(f); icon_frame.grid(row=3, column=1, columnspan=3, sticky='ew')
        for i,icon in enumerate(self.ICONS):
            lbl = icon if icon else '—'
            tk.Button(icon_frame, text=lbl, width=3, font=('Segoe UI', 12),
                      relief='flat', cursor='hand2',
                      command=lambda ic=icon: self.icon_var.set(ic)).grid(row=i//7,column=i%7,padx=1)

        ttk.Button(f, text=self.tr('Enregistrer','حفظ'), style='Primary.TButton',
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
            messagebox.showerror(self.tr('Famille','العائلة'), self.tr('Le nom est obligatoire.','الاسم إجباري.'), parent=self); return
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
        super().__init__(master,padding=16);self.app=app
        self.lang_ui=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang_ui=='ar' else fr
        ttk.Label(self,text=self.tr('Paramètres','الإعدادات'),style='Title.TLabel').pack(anchor='w')
        ttk.Label(self,text=self.tr('Configuration du magasin, impression, données et utilisateurs','إعدادات المتجر والطباعة والبيانات والمستخدمين'),foreground='#64748B',font=('Segoe UI',9)).pack(anchor='w',pady=(0,12))
        f=ttk.LabelFrame(self,text=self.tr('Magasin et vente','المتجر والبيع'),padding=10);f.pack(fill="x")
        self.shop=tk.StringVar(value=get_setting("shop_name","ToDo"));self.cur=tk.StringVar(value=get_setting("currency","DH"));self.neg=tk.BooleanVar(value=get_setting("allow_negative_stock","1")=="1")
        self.footer=tk.StringVar(value=get_setting("receipt_footer","Merci"))
        self.block_insufficient=tk.BooleanVar(value=get_setting('block_insufficient_stock','0')=='1')
        self.require_client=tk.BooleanVar(value=get_setting('require_client_on_sale','0')=='1')
        self.choose_seller=tk.BooleanVar(value=get_setting('choose_seller_on_sale','0')=='1')
        self.start_with_windows=tk.BooleanVar(value=get_setting('start_with_windows','0')=='1')
        self.windows_mode=tk.BooleanVar(value=get_setting('windows_mode','1')=='1')
        self.credit_enabled=tk.BooleanVar(value=get_setting('credit_enabled','1')=='1')
        self.closure_enabled=tk.BooleanVar(value=get_setting('closure_enabled','1')=='1')
        self.sans_ticket_enabled=tk.BooleanVar(value=get_setting('sans_ticket_enabled','1')=='1')
        self.payment_window_enabled=tk.BooleanVar(value=get_setting('payment_window_enabled','1')=='1')
        self.search_limit=tk.StringVar(value=get_setting("search_limit","60"))
        self.language=tk.StringVar(value=get_setting("language","fr"))
        ttk.Label(f,text=self.tr('Nom magasin','اسم المتجر')).grid(row=0,column=0,sticky="w");ttk.Entry(f,textvariable=self.shop,width=30).grid(row=0,column=1,padx=8)
        ttk.Label(f,text=self.tr('Langue','اللغة')).grid(row=0,column=2,sticky="w",padx=(18,4));ttk.Combobox(f,textvariable=self.language,values=("fr","ar"),state="readonly",width=8).grid(row=0,column=3,sticky="w")
        ttk.Label(f,text=self.tr('Devise','العملة')).grid(row=1,column=0,sticky="w",pady=5);ttk.Entry(f,textvariable=self.cur,width=10).grid(row=1,column=1,sticky="w",padx=8)
        ttk.Checkbutton(f,text=self.tr('Autoriser stock négatif','السماح بالمخزون السالب'),variable=self.neg,command=self.sync_stock_options).grid(row=2,column=0,columnspan=2,sticky="w")
        ttk.Checkbutton(f,text=self.tr('Bloquer vente si stock insuffisant','منع البيع عند نقص المخزون'),variable=self.block_insufficient,command=self.sync_stock_options).grid(row=3,column=0,columnspan=2,sticky="w")
        ttk.Checkbutton(f,text=self.tr('Afficher le choix du client pendant la vente','إظهار اختيار الزبون أثناء البيع'),variable=self.require_client).grid(row=4,column=0,columnspan=2,sticky="w")
        ttk.Checkbutton(f,text=self.tr('Choix du vendeur pendant la vente','اختيار البائع أثناء البيع'),variable=self.choose_seller).grid(row=5,column=0,columnspan=2,sticky="w")
        ttk.Checkbutton(f,text=self.tr('Lancer ToDo au démarrage de Windows','تشغيل ToDo مع بدء Windows'),variable=self.start_with_windows,command=self.toggle_windows_startup).grid(row=6,column=0,columnspan=3,sticky="w",pady=(3,0))
        ttk.Checkbutton(f,text=self.tr('Mode Windows (fenêtre)','وضع Windows (نافذة)'),variable=self.windows_mode,command=self.toggle_windows_mode).grid(row=7,column=0,columnspan=3,sticky="w",pady=(3,0))
        ttk.Checkbutton(f,text=self.tr('Activer la vente à crédit','تفعيل البيع بالدين'),variable=self.credit_enabled).grid(row=8,column=0,columnspan=3,sticky="w",pady=(3,0))
        ttk.Checkbutton(f,text=self.tr('Activer la clôture de caisse','تفعيل إغلاق الصندوق'),variable=self.closure_enabled).grid(row=9,column=0,columnspan=3,sticky="w",pady=(3,0))
        ttk.Checkbutton(f,text=self.tr('Autoriser SOLDER sans ticket','السماح بالأداء بدون تذكرة'),variable=self.sans_ticket_enabled).grid(row=10,column=0,columnspan=3,sticky="w",pady=(3,0))
        ttk.Checkbutton(f,text=self.tr('Afficher la fenêtre de paiement','إظهار نافذة الأداء'),variable=self.payment_window_enabled).grid(row=11,column=0,columnspan=3,sticky="w",pady=(3,0))
        ttk.Label(f,text=self.tr('Message bas du ticket','رسالة أسفل التذكرة')).grid(row=12,column=0,sticky="w",pady=5);ttk.Entry(f,textvariable=self.footer,width=34).grid(row=12,column=1,padx=8)
        ttk.Label(f,text=self.tr('Limite résultats recherche','حد نتائج البحث')).grid(row=13,column=0,sticky="w");ttk.Entry(f,textvariable=self.search_limit,width=10).grid(row=13,column=1,sticky="w",padx=8)
        ttk.Button(f,text=self.tr('Enregistrer','حفظ'),style='Primary.TButton',command=self.save).grid(row=14,column=0,pady=8,sticky='ew')
        pg=ttk.LabelFrame(self,text=self.tr('Grilles de prix','لوائح الأثمان'),padding=10);pg.pack(fill="x",pady=10)
        ttk.Label(pg,text=self.tr('Créez les grilles ici, puis définissez le prix de chaque article dans sa fiche.','أنشئ لوائح الأثمان هنا، ثم حدد ثمن كل منتوج في بطاقته.')).pack(anchor="w")
        self.price_grids_frame=ttk.Frame(pg);self.price_grids_frame.pack(fill="x",pady=6)
        self.new_grid_name=tk.StringVar();row=ttk.Frame(pg);row.pack(fill="x")
        ttk.Entry(row,textvariable=self.new_grid_name,width=28).pack(side="left")
        ttk.Button(row,text=self.tr('+ Ajouter grille','+ إضافة لائحة'),style='Soft.TButton',command=self.add_price_grid).pack(side='left',padx=6)
        self.refresh_price_grids()
        sellers=ttk.LabelFrame(self,text=self.tr('Vendeurs','البائعون'),padding=10);sellers.pack(fill="x",pady=10)
        self.sellers_frame=ttk.Frame(sellers);self.sellers_frame.pack(fill="x",pady=(0,6))
        self.new_seller_name=tk.StringVar();sr=ttk.Frame(sellers);sr.pack(fill="x")
        ttk.Entry(sr,textvariable=self.new_seller_name,width=28).pack(side="left")
        ttk.Button(sr,text=self.tr('+ Ajouter vendeur','+ إضافة بائع'),style='Soft.TButton',command=self.add_seller).pack(side='left',padx=6)
        self.refresh_sellers()
        p=ttk.LabelFrame(self,text=self.tr('Impression','الطباعة'),padding=10);p.pack(fill="x",pady=10)
        self.printer=tk.StringVar(value=get_setting("printer_name",""));self.print_mode=tk.StringVar(value=get_setting("print_mode","ask"));self.thermal_raw=tk.BooleanVar(value=get_setting('thermal_raw','0')=='1');self.receipt_chars=tk.StringVar(value=get_setting('receipt_chars','42'))
        ttk.Label(p,text=self.tr('Imprimante (optionnel)','الطابعة (اختياري)')).grid(row=0,column=0,sticky="w")
        self.printer_choice=ttk.Combobox(p,textvariable=self.printer,width=34)
        self.printer_choice.grid(row=0,column=1,padx=8)
        ttk.Button(p,text=self.tr('Actualiser imprimantes','تحديث الطابعات'),command=self.refresh_printers).grid(row=0,column=2,padx=5)
        ttk.Button(p,text=self.tr('Tester imprimante','اختبار الطابعة'),style='Soft.TButton',command=self.test_printer).grid(row=0,column=3,padx=5)
        ttk.Label(p,text=self.tr('Après validation','بعد تأكيد البيع')).grid(row=1,column=0,sticky="w",pady=5)
        self.print_mode_box=ttk.Combobox(p,state='readonly',width=18)
        self.print_mode_labels={self.tr('Demander','سؤال'):'ask',self.tr('Toujours imprimer','الطباعة دائماً'):'always',self.tr('Ne jamais imprimer','عدم الطباعة'):'never'}
        self.print_mode_box['values']=list(self.print_mode_labels);self.print_mode_box.set(next((k for k,v in self.print_mode_labels.items() if v==self.print_mode.get()),list(self.print_mode_labels)[0]));self.print_mode_box.bind('<<ComboboxSelected>>',lambda e:self.print_mode.set(self.print_mode_labels.get(self.print_mode_box.get(),'ask')));self.print_mode_box.grid(row=1,column=1,sticky='w',padx=8)
        ttk.Label(p,text=self.tr('Comportement impression','سلوك الطباعة')).grid(row=2,column=0,sticky='w')
        ttk.Label(p,text=self.tr('Demander / Toujours / Jamais','سؤال / دائماً / أبداً')).grid(row=2,column=1,columnspan=2,sticky='w')
        ttk.Checkbutton(p,text=self.tr('Mode ticket thermique ESC/POS (RAW)','وضع التذكرة الحرارية ESC/POS (RAW)'),variable=self.thermal_raw).grid(row=3,column=0,columnspan=2,sticky='w')
        ttk.Label(p,text=self.tr('Largeur ticket (caractères)','عرض التذكرة (حروف)')).grid(row=3,column=2,sticky='e')
        ttk.Combobox(p,textvariable=self.receipt_chars,values=['32','42','48'],state='readonly',width=5).grid(row=3,column=3,sticky='w',padx=6)
        self.drawer_enabled=tk.BooleanVar(value=get_setting('drawer_enabled','0')=='1')
        self.drawer_pin=tk.StringVar(value=get_setting('drawer_pin','0'))
        ttk.Checkbutton(p,text=self.tr('Tiroir connecté à une imprimante ESC/POS','درج النقود متصل بطابعة ESC/POS'),variable=self.drawer_enabled).grid(row=4,column=0,columnspan=2,sticky='w')
        ttk.Label(p,text=self.tr('Connecteur tiroir','موصل درج النقود')).grid(row=5,column=0,sticky='w')
        ttk.Combobox(p,textvariable=self.drawer_pin,values=['0','1'],state='readonly',width=5).grid(row=5,column=1,sticky='w',padx=8)
        ttk.Button(p,text=self.tr('Enregistrer impression','حفظ إعدادات الطباعة'),command=self.save).grid(row=5,column=2)
        d=ttk.LabelFrame(self,text=self.tr('Écran client','شاشة الزبون'),padding=10);d.pack(fill="x",pady=10)
        self.customer_enabled=tk.BooleanVar(value=get_setting('customer_display_enabled','0')=='1')
        self.customer_seconds=tk.StringVar(value=get_setting("customer_slide_seconds","6"))
        current_mode=get_setting('customer_display_mode','promotions')
        self.customer_mode_labels={
            self.tr('Promotions · photos / vidéos','العروض · صور / فيديوهات'):'promotions',
            self.tr('Ticket · articles / prix','التذكرة · المنتجات / الأثمنة'):'prices',
        }
        ttk.Checkbutton(d,text=self.tr('Afficher écran client / publicitaire','إظهار شاشة الزبون / الإعلانات'),variable=self.customer_enabled,command=self.toggle_customer_enabled).pack(anchor='w',pady=(0,8))
        mode_row=ttk.Frame(d);mode_row.pack(fill='x',pady=(0,8))
        ttk.Label(mode_row,text=self.tr('Contenu affiché','المحتوى المعروض'),font=('Segoe UI',10,'bold')).pack(side='left')
        self.customer_mode_box=ttk.Combobox(mode_row,state='readonly',width=30,values=list(self.customer_mode_labels))
        self.customer_mode_box.set(next((label for label,value in self.customer_mode_labels.items() if value==current_mode),list(self.customer_mode_labels)[0]))
        self.customer_mode_box.pack(side='left',padx=8)
        ttk.Button(mode_row,text=self.tr('Tester écran client','اختبار شاشة الزبون'),style='Primary.TButton',command=self.test_customer).pack(side='right')
        media_row=ttk.Frame(d);media_row.pack(fill='x')
        ttk.Label(media_row,text=self.tr('Durée de chaque image (secondes)','مدة كل صورة (ثوانٍ)')).pack(side='left')
        ttk.Spinbox(media_row,from_=2,to=300,textvariable=self.customer_seconds,width=6).pack(side='left',padx=8)
        ttk.Label(media_row,text=self.tr('Dossier : customer_media · images + vidéos · format conseillé 16:9','المجلد: customer_media · صور + فيديوهات · القياس المقترح 16:9'),foreground="#475569").pack(side='left',padx=12)
        b=ttk.LabelFrame(self,text=self.tr('Données','البيانات'),padding=10);b.pack(fill="x",pady=10)
        ttk.Button(b,text=self.tr('Backup maintenant','نسخ احتياطي الآن'),style='Success.TButton',command=self.backup).pack(side='left',padx=4)
        self.auto_backup=tk.StringVar(value=get_setting("auto_backup_minutes","15"))
        ttk.Label(b,text=self.tr('Backup auto','نسخ احتياطي تلقائي')).pack(side="left",padx=(18,4))
        ttk.Combobox(b,textvariable=self.auto_backup,values=["0","5","10","15","30","60"],state="readonly",width=5).pack(side="left")
        ttk.Label(b,text=self.tr('min (0 = désactivé)','دقيقة (0 = معطل)')).pack(side="left",padx=4)
        ttk.Button(b,text=self.tr('Restaurer backup','استرجاع نسخة احتياطية'),style='Soft.TButton',command=self.restore).pack(side='left',padx=4)
        ttk.Button(b,text=self.tr('Backup complet portable','نسخة كاملة للنقل'),style='Soft.TButton',command=self.full_backup).pack(side='left',padx=4)
        ttk.Button(b,text=self.tr('Restaurer backup complet','استرجاع النسخة الكاملة'),style='Soft.TButton',command=self.full_restore).pack(side='left',padx=4)
        u=ttk.LabelFrame(self,text=self.tr('Utilisateurs','المستخدمون'),padding=10);u.pack(fill="x")
        ttk.Button(u,text=self.tr('Nouvel utilisateur','مستخدم جديد'),style='Primary.TButton',command=self.new_user).pack(side='left');ttk.Button(u,text=self.tr('Gérer utilisateurs','إدارة المستخدمين'),style='Soft.TButton',command=self.manage_users).pack(side='left',padx=8)
        ttk.Button(u,text=self.tr('Changer mon PIN','تغيير PIN'),command=self.change_pin).pack(side="left",padx=8)
        ttk.Button(u,text=self.tr('Journal des actions','سجل العمليات'),command=self.audit_log).pack(side="left",padx=8)
        ttk.Label(u,text=self.tr('Admin initial: admin / PIN 1234 — changez-le.','المدير الأولي: admin / PIN 1234 — غيّره.')).pack(side="left",padx=15)
    def toggle_windows_startup(self):
        enabled=bool(self.start_with_windows.get())
        try:
            _sync_windows_startup(enabled)
            set_setting('start_with_windows','1' if enabled else '0')
        except Exception as error:
            self.start_with_windows.set(not enabled)
            messagebox.showerror('ToDo',self.tr(f"Impossible de modifier le démarrage Windows: {error}",f"تعذر تعديل تشغيل Windows: {error}"),parent=self)

    def toggle_windows_mode(self):
        enabled=bool(self.windows_mode.get())
        set_setting('windows_mode','1' if enabled else '0')
        try:self.app.apply_window_mode(enabled)
        except Exception as error:
            messagebox.showerror('ToDo',self.tr(f'Impossible de changer le mode fenêtre: {error}',f'تعذر تغيير وضع النافذة: {error}'),parent=self)


    def sync_stock_options(self):
        if self.block_insufficient.get(): self.neg.set(False)
        elif self.neg.get(): self.block_insufficient.set(False)

    def refresh_sellers(self):
        for w in self.sellers_frame.winfo_children():w.destroy()
        with connect() as c:rows=c.execute("SELECT id,name,active FROM sellers ORDER BY name COLLATE NOCASE").fetchall()
        for r in rows:
            line=ttk.Frame(self.sellers_frame);line.pack(fill="x",pady=2)
            ttk.Label(line,text=r["name"],width=30).pack(side="left")
            ttk.Label(line,text=self.tr("Actif","نشط") if r["active"] else self.tr("Inactif","معطل"),width=12).pack(side="left")
            ttk.Button(line,text=self.tr("Désactiver","تعطيل") if r["active"] else self.tr("Activer","تفعيل"),command=lambda sid=r["id"],a=r["active"]:self.toggle_seller(sid,a)).pack(side="left",padx=4)
    def add_seller(self):
        name=self.new_seller_name.get().strip()
        if not name:return
        try:
            with connect() as c:c.execute("INSERT INTO sellers(name,active) VALUES(?,1)",(name,))
            self.new_seller_name.set("");self.refresh_sellers()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def toggle_seller(self,seller_id,active):
        with connect() as c:c.execute("UPDATE sellers SET active=? WHERE id=?",(0 if active else 1,seller_id))
        self.refresh_sellers()

    def refresh_price_grids(self):
        for w in self.price_grids_frame.winfo_children():w.destroy()
        with connect() as c:rows=c.execute("SELECT id,name,active FROM price_grids ORDER BY name COLLATE NOCASE").fetchall()
        for r in rows:
            line=ttk.Frame(self.price_grids_frame);line.pack(fill="x",pady=2)
            ttk.Label(line,text=r["name"],width=30).pack(side="left")
            ttk.Label(line,text=self.tr("Active","نشطة") if r["active"] else self.tr("Inactive","معطلة"),width=12).pack(side="left")
            ttk.Button(line,text=self.tr("Désactiver","تعطيل") if r["active"] else self.tr("Activer","تفعيل"),command=lambda gid=r["id"],a=r["active"]:self.toggle_price_grid(gid,a)).pack(side="left",padx=4)
    def add_price_grid(self):
        name=self.new_grid_name.get().strip()
        if not name:return
        try:
            with connect() as c:c.execute("INSERT INTO price_grids(name,active) VALUES(?,1)",(name,))
            self.new_grid_name.set("");self.refresh_price_grids()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def toggle_price_grid(self,grid_id,active):
        with connect() as c:c.execute("UPDATE price_grids SET active=? WHERE id=?",(0 if active else 1,grid_id))
        self.refresh_price_grids()

    def save(self):
        try:
            limit=int(self.search_limit.get())
            if limit<1 or limit>1000:raise ValueError()
        except ValueError:
            messagebox.showerror("ToDo",self.tr("Limite de recherche entre 1 et 1000.","حد البحث بين 1 و1000."),parent=self);return
        set_setting("shop_name",self.shop.get().strip() or "ToDo");set_setting("currency",self.cur.get().strip() or "DH");set_setting("allow_negative_stock","1" if self.neg.get() else "0")
        print_mode=self.print_mode.get() or "ask"
        if print_mode not in ('ask','always','never'):print_mode='ask'
        set_setting("receipt_footer",self.footer.get());set_setting("search_limit",limit);set_setting("printer_name",self.printer.get().strip());set_setting("print_mode",print_mode)
        set_setting('thermal_raw','1' if self.thermal_raw.get() else '0');set_setting('receipt_chars',self.receipt_chars.get() if self.receipt_chars.get() in ('32','42','48') else '42');set_setting('drawer_enabled','1' if self.drawer_enabled.get() else '0');set_setting('drawer_pin',self.drawer_pin.get());set_setting('block_insufficient_stock','1' if self.block_insufficient.get() else '0');set_setting('credit_enabled','1' if self.credit_enabled.get() else '0');set_setting('closure_enabled','1' if self.closure_enabled.get() else '0');set_setting('sans_ticket_enabled','1' if self.sans_ticket_enabled.get() else '0');set_setting('payment_window_enabled','1' if self.payment_window_enabled.get() else '0');set_setting('require_client_on_sale','1' if self.require_client.get() else '0');set_setting('choose_seller_on_sale','1' if self.choose_seller.get() else '0');new_language=self.language.get();language_changed=new_language!=get_setting('language','fr');set_setting('language',new_language)
        try:
            seconds=int(self.customer_seconds.get())
            if seconds<2 or seconds>300:raise ValueError()
        except ValueError:
            messagebox.showerror("ToDo",self.tr("Durée écran client entre 2 et 300 secondes.","مدة شاشة الزبون بين 2 و300 ثانية."),parent=self);return
        set_setting('customer_display_enabled','1' if self.customer_enabled.get() else '0')
        set_setting("customer_slide_seconds",str(seconds))
        mode=self.customer_mode_labels.get(self.customer_mode_box.get(),'promotions')
        set_setting('customer_display_mode',mode)
        if self.app.customer_window and self.app.customer_window.winfo_exists():
            self.app._apply_customer_display_mode()
        backup_minutes=self.auto_backup.get()
        if backup_minutes not in ('0','5','10','15','30','60'):backup_minutes='15'
        set_setting("auto_backup_minutes",backup_minutes)
        self.app.schedule_auto_backup()
        messagebox.showinfo("ToDo",self.tr("Paramètres enregistrés.","تم حفظ الإعدادات."),parent=self)
    def toggle_customer_enabled(self):
        enabled=bool(self.customer_enabled.get())
        set_setting('customer_display_enabled','1' if enabled else '0')
        opened=bool(self.app.customer_window and self.app.customer_window.winfo_exists())
        if enabled and not opened:
            self.app.toggle_customer_display()
        elif not enabled and opened:
            self.app.toggle_customer_display()

    def test_customer(self):
        mode=self.customer_mode_labels.get(self.customer_mode_box.get(),'promotions')
        if not (self.app.customer_window and self.app.customer_window.winfo_exists()):
            self.app.toggle_customer_display()
        self.app._apply_customer_display_mode(mode)

    def test_printer(self):
        try:
            from services.printers import test_printer
            test_printer(self.printer.get().strip(),bool(self.thermal_raw.get()))
            messagebox.showinfo('ToDo',self.tr('Test envoyé à l’imprimante.','تم إرسال الاختبار إلى الطابعة.'),parent=self)
        except Exception as error:
            messagebox.showerror('ToDo',str(error),parent=self)

    def refresh_printers(self):
        from services.printers import installed_printers
        try:self.printer_choice['values']=installed_printers()
        except Exception as error:messagebox.showerror(self.tr('Imprimantes','الطابعات'),str(error),parent=self)

    def backup(self):
        try:
            p=create_backup()
            messagebox.showinfo("ToDo",self.tr(f"Backup:\n{p}",f"نسخة احتياطية:\n{p}"),parent=self)
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def restore(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("SQLite DB","*.db"),(self.tr("Tous les fichiers","كل الملفات"),"*.*")])
        if not p:return
        if not messagebox.askyesno("ToDo",self.tr("Restaurer ce backup ? Une copie de sécurité sera créée.","استرجاع هذه النسخة؟ سيتم إنشاء نسخة أمان أولاً."),parent=self):return
        try:
            s=restore_backup(p)
            messagebox.showinfo("ToDo",self.tr(f"Restauré. Copie sécurité: {s}\nLe programme va se fermer. Relancez ToDo.",f"تم الاسترجاع. نسخة الأمان: {s}\nسيتم إغلاق البرنامج. أعد تشغيل ToDo."),parent=self)
            self.app.destroy()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def full_backup(self):
        try:
            p=create_full_backup()
            messagebox.showinfo("ToDo",self.tr(f"Backup complet créé:\n{p}",f"تم إنشاء النسخة الكاملة:\n{p}"),parent=self)
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def full_restore(self):
        p=filedialog.askopenfilename(parent=self,filetypes=[("ToDo Full Backup","*.todozip")])
        if not p:return
        if not messagebox.askyesno("ToDo",self.tr("Restaurer toutes les données et médias ? Une copie complète de sécurité sera créée.","استرجاع جميع البيانات والوسائط؟ سيتم إنشاء نسخة أمان كاملة أولاً."),parent=self):return
        try:
            safety=restore_full_backup(p)
            messagebox.showinfo("ToDo",self.tr(f"Restauration complète terminée.\nCopie sécurité: {safety}\nToDo va se fermer.","تم الاسترجاع الكامل.\nنسخة الأمان: {safety}\nسيتم إغلاق ToDo."),parent=self)
            self.app.destroy()
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)
    def new_user(self):
        user=simpledialog.askstring(self.tr("Utilisateur","المستخدم"),self.tr("Username:","اسم المستخدم:"),parent=self)
        if not user:return
        name=simpledialog.askstring(self.tr("Utilisateur","المستخدم"),self.tr("Nom affiché:","الاسم المعروض:"),parent=self) or user
        pin=simpledialog.askstring(self.tr("Utilisateur","المستخدم"),"PIN:",parent=self,show="*")
        if not pin:return
        if not pin.isdigit() or len(pin)<4:
            messagebox.showerror("ToDo",self.tr("PIN : au moins 4 chiffres","PIN: أربعة أرقام على الأقل"),parent=self);return
        role=simpledialog.askstring(self.tr("Utilisateur","المستخدم"),self.tr("Rôle (admin/cashier):","الصلاحية (admin/cashier):"),parent=self) or "cashier"
        if role not in ("admin","cashier"):
            messagebox.showerror("ToDo",self.tr("Rôle invalide","صلاحية غير صالحة"),parent=self);return
        try:
            with connect() as c:c.execute("INSERT INTO users(username,display_name,pin_hash,role) VALUES(?,?,?,?)",(user,name,hash_pin(pin),role));c.commit()
            messagebox.showinfo("ToDo",self.tr("Utilisateur créé.","تم إنشاء المستخدم."),parent=self)
        except Exception as e:messagebox.showerror("ToDo",str(e),parent=self)

    def manage_users(self):
        with connect() as conn: require_admin(conn)
        w=tk.Toplevel(self);w.title(self.tr("Utilisateurs","المستخدمون"));w.geometry("720x500");w.transient(self.winfo_toplevel())
        tree=ttk.Treeview(w,columns=("id","username","name","role","active"),show="headings")
        for key,label,width in [("id","ID",55),("username",self.tr("Utilisateur","المستخدم"),150),("name",self.tr("Nom","الاسم"),190),("role",self.tr("Rôle","الصلاحية"),100),("active",self.tr("Actif","نشط"),70)]:tree.heading(key,text=label);tree.column(key,width=width,anchor="center" if key in ("id","role","active") else "w")
        tree.pack(fill="both",expand=True,padx=12,pady=12);bar=ttk.Frame(w);bar.pack(fill="x",padx=12,pady=(0,12))
        def reload():
            tree.delete(*tree.get_children())
            with connect() as conn: rows=conn.execute("SELECT id,username,display_name,role,active FROM users ORDER BY display_name").fetchall()
            for r in rows:
                role_label=self.tr("Administrateur","مدير") if r["role"]=="admin" else self.tr("Caissier","كاشير") if r["role"]=="cashier" else r["role"]
                tree.insert("","end",iid=str(r["id"]),values=(r["id"],r["username"],r["display_name"],role_label,self.tr("Oui","نعم") if r["active"] else self.tr("Non","لا")))
        def selected():
            sel=tree.selection()
            if not sel: messagebox.showwarning(self.tr("Utilisateurs","المستخدمون"),self.tr("Sélectionnez un utilisateur.","اختر مستخدماً."),parent=w);return None
            return int(sel[0])
        def toggle():
            uid=selected()
            if uid is None:return
            if uid==self.app.user["id"]:messagebox.showwarning(self.tr("Utilisateurs","المستخدمون"),self.tr("Impossible de désactiver votre propre compte.","لا يمكن تعطيل حسابك الحالي."),parent=w);return
            with connect() as conn:
                require_admin(conn);row=conn.execute("SELECT active FROM users WHERE id=?",(uid,)).fetchone();new=0 if row["active"] else 1
                conn.execute("UPDATE users SET active=? WHERE id=?",(new,uid));audit(conn,"USER_ACTIVE_TOGGLE",uid,str(new));conn.commit()
            reload()
        def role():
            uid=selected()
            if uid is None:return
            if uid==self.app.user["id"]:messagebox.showwarning(self.tr("Utilisateurs","المستخدمون"),self.tr("Modifiez un autre compte.","اختر حساباً آخر للتعديل."),parent=w);return
            with connect() as conn:
                require_admin(conn);row=conn.execute("SELECT role FROM users WHERE id=?",(uid,)).fetchone();new="admin" if row["role"]!="admin" else "cashier"
                conn.execute("UPDATE users SET role=? WHERE id=?",(new,uid));audit(conn,"USER_ROLE_CHANGE",uid,new);conn.commit()
            reload()
        ttk.Button(bar,text=self.tr('Activer / Désactiver','تفعيل / تعطيل'),command=toggle).pack(side="left");ttk.Button(bar,text=self.tr('Admin ↔ Caissier','مدير ↔ كاشير'),command=role).pack(side="left",padx=8);reload()

    def change_pin(self):
        pin=simpledialog.askstring('PIN',self.tr('Nouveau PIN (4 chiffres minimum):','PIN جديد (4 أرقام على الأقل):'),parent=self,show='*')
        if pin is None:return
        if not pin.isdigit() or len(pin)<4:
            messagebox.showerror('ToDo',self.tr('Utilisez au moins 4 chiffres.','استعمل أربعة أرقام على الأقل.'),parent=self);return
        with connect() as conn:
            conn.execute('UPDATE users SET pin_hash=? WHERE id=?',(hash_pin(pin),self.app.user['id']))
            audit(conn,'PIN_CHANGE',self.app.user['id'])
        messagebox.showinfo('ToDo',self.tr('PIN modifié.','تم تغيير PIN.'),parent=self)

    def audit_log(self):
        w=tk.Toplevel(self);w.title(self.tr('Journal des actions','سجل العمليات'));w.geometry('960x520')
        tree=ttk.Treeview(w,columns=('date','user','action','document','details'),show='headings')
        for key,label,width in [('date',self.tr('Date','التاريخ'),150),('user',self.tr('Utilisateur','المستخدم'),140),('action',self.tr('Action','العملية'),140),('document',self.tr('Document','الوثيقة'),100),('details',self.tr('Détails','التفاصيل'),300)]:
            tree.heading(key,text=label);tree.column(key,width=width)
        tree.pack(fill='both',expand=True,padx=12,pady=12)
        with connect() as conn:
            rows=conn.execute("SELECT a.*,u.display_name username FROM audit_log a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 1000").fetchall()
        for r in rows:tree.insert('','end',values=(r['created_at'],r['username'] or self.tr('Système','النظام'),r['action'],r['document'],r['details']))
