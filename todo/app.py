import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from database import init_db, get_setting, set_setting
from services.bootstrap import ensure_defaults
from services.backup import create_backup
from services.security import verify_pin, current_user, hash_pin, audit
from database import connect

from screens.home import HomeFrame
from screens.sale import SaleFrame
from screens.products import ProductsFrame
from screens.cashdesk import CashFrame
from screens.stock import StockFrame
from screens.purchases import PurchasesFrame
from screens.returns import ReturnsFrame
from screens.journal import JournalFrame
from screens.settings import SettingsFrame
from screens.management import ManagementFrame
from screens.statistics import StatisticsFrame
from screens.suppliers import SuppliersFrame
from screens.inventory import InventaireFrame, SortiesFrame
from screens.supplier_payments import SupplierReglementFrame
from screens.rendez_vous import RendezVousFrame
from screens.clients import ClientsFrame

class ToDoApp(tk.Tk):
    def __init__(self):
        super().__init__()
        init_db()
        ensure_defaults()

        self.user = None
        self.current = None
        self.sale_frame = None
        self.failed_logins = 0
        self.login_blocked_until = 0
        self.customer_window = None
        self.customer_label = None
        self.customer_photo = None
        self.customer_slides = []
        self.customer_slide_index = 0
        self.customer_after_id = None
        self.customer_video = None
        self.customer_video_delay = 33
        self.shell = None
        self.lock_window = None
        self._keyboard_target = None
        self.backup_after_id = None

        self.title("ToDo POS")
        self.geometry("460x330")
        self.minsize(460, 330)

        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except Exception:
            pass
        self.configure(background='#F6F7FB')
        self.option_add('*Font', ('Segoe UI', 10))
        st.configure('.', font=('Segoe UI',10),background='#F6F7FB',foreground='#1E293B')
        st.configure('TFrame',background='#F6F7FB')
        st.configure('TLabel',background='#F6F7FB')
        st.configure('TButton',font=('Segoe UI',10),padding=(10,9),background='white',borderwidth=0)
        st.map('TButton',background=[('active','#DBEAFE')])
        st.configure('Primary.TButton',background='#2563EB',foreground='white',font=('Segoe UI',12,'bold'))
        st.map('Primary.TButton',background=[('active','#1D4ED8')],foreground=[('active','white')])
        st.configure('Sidebar.TFrame',background='#1E293B')
        st.configure('Sidebar.TLabel',background='#1E293B',foreground='white')
        st.configure('Sidebar.TButton',background='#1E293B',foreground='#E2E8F0',anchor='w',padding=(12,12))
        st.map('Sidebar.TButton',background=[('active','#334155')],foreground=[('active','white')])
        st.configure('Card.TFrame',background='white')
        st.configure('Card.TLabel',background='white')
        st.configure('CardTitle.TLabel',background='white',font=('Segoe UI',15,'bold'))
        st.configure('Title.TLabel',font=('Segoe UI',23,'bold'))
        st.configure('Accent.TLabel',foreground='#2563EB',font=('Segoe UI',12,'bold'))
        st.configure('Total.TLabel',background='white',foreground='#2563EB',font=('Segoe UI',28,'bold'))
        st.configure('Treeview',font=('Segoe UI',10),rowheight=34,background='white',fieldbackground='white',borderwidth=0)
        st.configure('Treeview.Heading',font=('Segoe UI',10,'bold'),padding=9,background='#E2E8F0')
        st.map('Treeview',background=[('selected','#DBEAFE')],foreground=[('selected','#1E293B')])
        st.configure('Catalog.Treeview',rowheight=54)
        st.configure('Cart.Treeview',rowheight=48)

        self.apply_theme()
        self.show_login()
        self.schedule_auto_backup()

    def schedule_auto_backup(self):
        if self.backup_after_id:
            try:self.after_cancel(self.backup_after_id)
            except Exception:pass
            self.backup_after_id=None
        try:minutes=int(get_setting("auto_backup_minutes","15") or 0)
        except Exception:minutes=15
        if minutes>0:self.backup_after_id=self.after(minutes*60000,self.run_auto_backup)

    def run_auto_backup(self):
        try:create_backup()
        except Exception as e:
            try:messagebox.showerror("Backup automatique",str(e),parent=self)
            except Exception:pass
        finally:self.schedule_auto_backup()

    def clear_root(self):
        for w in self.winfo_children():
            w.destroy()

    def show_login(self):
        self.clear_root()
        self.geometry('460x460')
        self.resizable(False,False)
        outer=ttk.Frame(self,padding=32)
        outer.pack(fill='both',expand=True)
        ttk.Label(outer,text='ToDo',font=('Segoe UI',34,'bold'),foreground='#2563EB').pack(pady=(8,0))
        ttk.Label(outer,text=('تجارتك بكل بساطة.' if get_setting('language','fr')=='ar' else 'Votre commerce. En toute simplicité.')).pack(pady=(0,18))
        with connect() as conn:
            self.login_users=[dict(r) for r in conn.execute('SELECT * FROM users WHERE active=1 ORDER BY id')]
        self.avatar=ttk.Label(outer,text='●',font=('Segoe UI',28),foreground='#2563EB')
        self.avatar.pack()
        names=[u['display_name']+' · '+u['username'] for u in self.login_users]
        self.user_choice=ttk.Combobox(outer,values=names,state='readonly',font=('Segoe UI',12))
        self.user_choice.pack(fill='x',pady=8)
        if names:self.user_choice.current(0)
        self.login_pin=tk.StringVar()
        ttk.Label(outer,text=('الرمز السري' if get_setting('language','fr')=='ar' else 'PIN')).pack(anchor='w',pady=(8,4))
        pin=ttk.Entry(outer,textvariable=self.login_pin,show='●',font=('Segoe UI',20),justify='center')
        pin.pack(fill='x',ipady=5);pin.bind('<Return>',lambda e:self.login())
        ttk.Button(outer,text=('الدخول' if get_setting('language','fr')=='ar' else 'Entrer'),style='Primary.TButton',command=self.login).pack(fill='x',pady=16)
        self.after(100,lambda: pin.focus_set() if pin.winfo_exists() else None)

    def login(self):
        import time
        if time.monotonic()<self.login_blocked_until:
            messagebox.showerror('ToDo',('انتظر 30 ثانية قبل إعادة المحاولة.' if get_setting('language','fr')=='ar' else 'Patientez 30 secondes avant de réessayer.'));return
        index=self.user_choice.current()
        if index<0:return
        selected=self.login_users[index]
        with connect() as conn:
            row=conn.execute('SELECT * FROM users WHERE id=? AND active=1',(selected['id'],)).fetchone()
        pin=self.login_pin.get()
        if not row or not verify_pin(pin,row['pin_hash']):
            self.failed_logins+=1
            if self.failed_logins>=5:
                self.login_blocked_until=time.monotonic()+30;self.failed_logins=0
            self.login_pin.set('')
            messagebox.showerror('ToDo',('الرمز السري غير صحيح.' if get_setting('language','fr')=='ar' else 'PIN incorrect.'));return
        self.user=dict(row);current_user.set(row['id'])
        with connect() as conn:
            if not row['pin_hash'].startswith('pbkdf2$'):
                conn.execute('UPDATE users SET pin_hash=? WHERE id=?',(hash_pin(pin),row['id']))
            audit(conn,'LOGIN',row['id'])
        self.build_shell();self.show('home')

    def build_shell(self):
        self.clear_root()
        self.resizable(True, True)
        width=min(1360,self.winfo_screenwidth()-40)
        height=min(820,self.winfo_screenheight()-80)
        self.geometry(f'{width}x{height}')
        self.minsize(min(1100,width),min(640,height))
        # The shop workflow uses a compact blue module bar like the reference
        # screen: the cashier sees the current module immediately and has more
        # room for the product table and the cart than with a permanent sidebar.
        self.shell=ttk.Frame(self);self.shell.pack(fill="both",expand=True)
        self.bind_all('<FocusIn>', self.remember_keyboard_target, add='+')
        bar=tk.Frame(self.shell,bg="#0878C9",height=58)
        self.nav_bar=bar
        bar.pack(fill="x");bar.pack_propagate(False)
        tk.Label(bar,text=get_setting("shop_name","ToDo"),bg="#0878C9",fg="white",font=("Segoe UI",17,"bold")).pack(side="left",padx=18)
        lang=get_setting("language","fr")
        nav_fr=[("🛒 Vente","sale"),("📦 Stock","stock"),("📋 Journal","journal"),("🗂 Gestion","management"),("⚙ Paramètres","settings"),("📊 Statistiques","statistics")]
        nav_ar=[("🛒 البيع","sale"),("📦 المخزون","stock"),("📋 السجل","journal"),("🗂 الإدارة","management"),("⚙ الإعدادات","settings"),("📊 الإحصائيات","statistics")]
        nav=nav_ar if lang=="ar" else nav_fr
        self.nav_buttons={}
        for txt,key in nav:
            if self.user["role"]!="admin" and key in ("settings","journal","management","statistics"):continue
            b=tk.Button(bar,text=txt,bg="#0878C9",fg="white",activebackground="#075B96",activeforeground="white",relief="flat",bd=0,font=("Segoe UI",10,"bold"),padx=10,command=lambda k=key:self.show(k))
            b.pack(side="left",fill="y");self.nav_buttons[key]=b
        tk.Button(bar,text=("⌨ لوحة المفاتيح" if lang=="ar" else "⌨ Clavier"),bg="#0878C9",fg="white",activebackground="#075B96",relief="flat",bd=0,font=("Segoe UI",9),command=self.toggle_keyboard).pack(side="right",padx=4)
        tk.Button(bar,text=("شاشة الزبون" if lang=="ar" else "Écran client"),bg="#0878C9",fg="white",activebackground="#075B96",relief="flat",bd=0,font=("Segoe UI",9),command=self.toggle_customer_display).pack(side="right",padx=10)
        tk.Label(bar,text=f"{self.user['display_name']} · {self.user['role']}",bg="#0878C9",fg="white",font=("Segoe UI",9)).pack(side="right",padx=8)
        self.content=ttk.Frame(self.shell);self.content.pack(fill="both",expand=True)
        self.apply_theme()

    def change_language(self, language):
        if language not in ('fr','ar'): return
        set_setting('language',language)
        key=getattr(self,'current_key','sale')
        self.sale_frame=None
        self.current=None
        self.build_shell();self.show(key)

    def show(self, key):
        if self.lock_window and self.lock_window.winfo_exists():
            self.lock_window.lift();return
        if self.user['role']!='admin' and key in ('products','purchases','suppliers','clients','settings','journal','management','statistics','inventory','sorties','supplier_payments','rendez_vous'):
            messagebox.showerror('ToDo',('هذه العملية مخصصة للمدير.' if get_setting('language','fr')=='ar' else 'Action réservée à un administrateur.'));return
        if self.current:
            if self.current is self.sale_frame:self.current.pack_forget()
            else:self.current.destroy()
        if key=='sale' and self.sale_frame and self.sale_frame.winfo_exists():
            self.current=self.sale_frame
            self.current.pack(fill='both',expand=True)
            self.current.render_products();self.current.focus_search()
            self._mark_nav(key)
            return

        makers = {
            "home": lambda: HomeFrame(self.content, self),
            "sale": lambda: SaleFrame(self.content, self),
            "products": lambda: ProductsFrame(self.content),
            "cash": lambda: CashFrame(self.content, self),
            "stock": lambda: StockFrame(self.content, self),
            "purchases": lambda: PurchasesFrame(self.content),
            "suppliers": lambda: SuppliersFrame(self.content),
            "clients": lambda: ClientsFrame(self.content,self),
            "returns": lambda: ReturnsFrame(self.content, self),
            "journal": lambda: JournalFrame(self.content),
            "settings": lambda: SettingsFrame(self.content, self),
            "management": lambda: ManagementFrame(self.content, self),
            "statistics": lambda: StatisticsFrame(self.content),
            "inventory": lambda: InventaireFrame(self.content, self),
            "sorties": lambda: SortiesFrame(self.content, self),
            "supplier_payments": lambda: SupplierReglementFrame(self.content, self),
            "rendez_vous": lambda: RendezVousFrame(self.content, self),
        }

        self.current = makers[key]()
        if key=="sale":self.sale_frame=self.current
        self.current.pack(fill="both", expand=True)
        self._mark_nav(key)

    def _mark_nav(self,key):
        for name,button in getattr(self,'nav_buttons',{}).items():
            is_active = (name==key)
            button.configure(
                bg=self.theme_active if is_active else self.theme_color,
                relief='solid' if is_active else 'flat',
                bd=0,
                font=('Segoe UI',10,'bold') if is_active else ('Segoe UI',10,'normal'),
            )
        self.current_key=key

    def apply_theme(self):
        palette={'Bleu':('#2563EB','#1D4ED8'),'Vert':('#15803D','#166534'),'Violet':('#7C3AED','#6D28D9')}
        self.theme_color,self.theme_active=palette.get(get_setting('theme','Bleu'),palette['Bleu'])
        style=ttk.Style(self)
        style.configure('Primary.TButton',background=self.theme_color)
        style.map('Primary.TButton',background=[('active',self.theme_active)])
        style.configure('Accent.TLabel',foreground=self.theme_color)
        style.configure('Total.TLabel',foreground=self.theme_color)
        bar=getattr(self,'nav_bar',None)
        if bar is not None and bar.winfo_exists():
            bar.configure(bg=self.theme_color)
            for child in bar.winfo_children():
                child.configure(bg=self.theme_color)
                if isinstance(child,tk.Button):child.configure(activebackground=self.theme_active)
            self._mark_nav(getattr(self,'current_key','home'))

    def choose_theme(self):
        lang=get_setting('language','fr')
        tr=lambda fr,ar: ar if lang=='ar' else fr
        window=tk.Toplevel(self);window.title(tr('Thème','الألوان'));window.transient(self);window.grab_set()
        ttk.Label(window,text=tr('Couleur principale','اللون الرئيسي')).pack(padx=25,pady=15)
        def choose(name):
            set_setting('theme',name);self.apply_theme();window.destroy()
        themes=[('Bleu','أزرق','#2563EB'),('Vert','أخضر','#15803D'),('Violet','بنفسجي','#7C3AED')]
        for fr,ar,color in themes:
            tk.Button(window,text=tr(fr,ar),bg=color,fg='white',command=lambda n=fr:choose(n)).pack(fill='x',padx=25,pady=6,ipady=10)
        ttk.Button(window,text=tr('Fermer','إغلاق'),command=window.destroy).pack(pady=12)

    def _is_text_input(self, widget):
        try:
            return widget is not None and widget.winfo_exists() and widget.winfo_class() in ('Entry', 'TEntry', 'Text', 'Spinbox', 'TSpinbox', 'TCombobox')
        except tk.TclError:
            return False

    def remember_keyboard_target(self, event):
        if self._is_text_input(event.widget):
            self._keyboard_target = event.widget

    def toggle_keyboard(self, target=None):
        # The global keyboard must always be able to open.  A target field is
        # optional: if none is focused yet, the keyboard stays visible and the
        # next Entry/Text clicked becomes its target.
        target = target if self._is_text_input(target) else self.focus_get()
        if not self._is_text_input(target):
            target = self._keyboard_target
        from screens.virtual_keyboard import VirtualKeyboard
        VirtualKeyboard.toggle(self, target)

    def toggle_customer_display(self):
        if self.customer_window and self.customer_window.winfo_exists():
            if self.customer_after_id:
                try:self.after_cancel(self.customer_after_id)
                except Exception:pass
            self.customer_after_id=None
            if self.customer_video is not None:self.customer_video.release();self.customer_video=None
            self.customer_window.destroy();self.customer_window=None;self.customer_label=None;return
        w=tk.Toplevel(self);self.customer_window=w;lang=get_setting('language','fr');w.title('ToDo — '+('شاشة الزبون' if lang=='ar' else 'Écran client'));w.configure(bg="#0F172A")
        screens=[]
        try:
            from screeninfo import get_monitors
            screens=get_monitors()
        except Exception:pass
        if len(screens)>1:
            main_x=self.winfo_rootx();main_y=self.winfo_rooty()
            primary=min(screens,key=lambda m:(m.x-main_x)**2+(m.y-main_y)**2)
            others=[m for m in screens if m is not primary]
            target=min(others,key=lambda m:(m.x-main_x)**2+(m.y-main_y)**2)
            w.geometry(f"{target.width}x{target.height}+{target.x}+{target.y}");w.overrideredirect(True)
        else:
            w.geometry("1280x720")
        w.bind("<Escape>",lambda e:self.toggle_customer_display())
        tk.Label(w,text=get_setting("shop_name","ToDo"),bg="#0F172A",fg="white",font=("Segoe UI",34,"bold")).pack(pady=(35,8))
        tk.Label(w,text=('مرحبا بكم' if lang=='ar' else 'Bienvenue'),bg="#0F172A",fg="#FACC15",font=("Segoe UI",22,"bold")).pack()
        self.customer_label=tk.Label(w,text=('العروض والإعلانات' if lang=='ar' else 'Offres & promotions'),bg="#0F172A",fg="white",font=("Segoe UI",30,"bold"),justify="center")
        self.customer_label.pack(fill="both",expand=True)
        self.customer_label.bind("<Configure>",lambda e:self._render_customer_slide())
        w.lift();self._load_customer_slides()

    def _load_customer_slides(self):
        folder=Path.cwd()/"customer_media";folder.mkdir(exist_ok=True)
        self.customer_slides=sorted([p for p in folder.iterdir() if p.suffix.lower() in (".png",".jpg",".jpeg",".webp",".mp4",".avi",".mov",".mkv")])
        self.customer_slide_index=0;self._show_customer_slide()

    def _show_customer_slide(self):
        if not (self.customer_window and self.customer_window.winfo_exists()):return
        if self.customer_after_id:
            try:self.after_cancel(self.customer_after_id)
            except Exception:pass
        self.customer_after_id=None
        if self.customer_video is not None:self.customer_video.release();self.customer_video=None
        if self.customer_slides and self.customer_slides[self.customer_slide_index].suffix.lower() in (".mp4",".avi",".mov",".mkv"):
            self._start_customer_video();return
        self._render_customer_slide()
        seconds=max(2,int(get_setting("customer_slide_seconds","6") or 6))
        self.customer_after_id=self.after(seconds*1000,self._next_customer_slide)

    def _next_customer_slide(self):
        if self.customer_slides:self.customer_slide_index=(self.customer_slide_index+1)%len(self.customer_slides)
        self._show_customer_slide()

    def _cover_customer_image(self,im):
        w=max(16,self.customer_label.winfo_width());h=max(9,self.customer_label.winfo_height())
        scale=max(w/im.width,h/im.height);nw=max(1,round(im.width*scale));nh=max(1,round(im.height*scale));im=im.resize((nw,nh),Image.Resampling.LANCZOS)
        left=max(0,(nw-w)//2);top=max(0,(nh-h)//2)
        return im.crop((left,top,left+w,top+h))

    def _start_customer_video(self):
        try:
            import cv2
            self.customer_video=cv2.VideoCapture(str(self.customer_slides[self.customer_slide_index]))
            if not self.customer_video.isOpened():raise ValueError("video")
            fps=self.customer_video.get(cv2.CAP_PROP_FPS)
            self.customer_video_delay=max(15,round(1000/fps)) if fps and fps>0 else 33
            self._render_customer_video_frame()
        except Exception:
            if self.customer_video is not None:self.customer_video.release();self.customer_video=None
            self._next_customer_slide()

    def _render_customer_video_frame(self):
        if not (self.customer_window and self.customer_window.winfo_exists() and self.customer_video is not None):return
        import cv2
        ok,frame=self.customer_video.read()
        if not ok:
            self.customer_video.release();self.customer_video=None;self._next_customer_slide();return
        from PIL import Image,ImageTk
        frame=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
        im=self._cover_customer_image(Image.fromarray(frame))
        self.customer_photo=ImageTk.PhotoImage(im);self.customer_label.config(image=self.customer_photo,text="")
        self.customer_after_id=self.after(self.customer_video_delay,self._render_customer_video_frame)

    def _render_customer_slide(self):
        if not (self.customer_label and self.customer_label.winfo_exists()):return
        if not self.customer_slides:
            lang=get_setting('language','fr');self.customer_label.config(image="",text=('ضع الصور أو الفيديوهات داخل مجلد customer_media' if lang=='ar' else 'Ajoutez les images ou vidéos dans customer_media'));return
        path=self.customer_slides[self.customer_slide_index]
        if path.suffix.lower() in (".mp4",".avi",".mov",".mkv"):return
        try:
            from PIL import Image,ImageTk
            im=self._cover_customer_image(Image.open(path).convert("RGB"))
            self.customer_photo=ImageTk.PhotoImage(im);self.customer_label.config(image=self.customer_photo,text="")
        except Exception as e:
            lang=get_setting('language','fr');self.customer_label.config(image="",text=(f'وسائط غير صالحة: {e}' if lang=='ar' else f'Média invalide : {e}'))

    def update_customer_display(self, cart, total):
        # Customer screen is intentionally advertising-first: cashier prices,
        # ticket lines and totals are never mirrored to the public display.
        if not (self.customer_window and self.customer_window.winfo_exists() and self.customer_label):return
        lang=get_setting('language','fr');self.customer_label.config(text=('العروض والإعلانات' if lang=='ar' else 'Offres & promotions'))

    def lock_cashier(self):
        from screens.cashier_tools import CashierLock
        if not self.lock_window or not self.lock_window.winfo_exists():
            self.lock_window=CashierLock(self)

    def on_close(self):
        if self.lock_window and self.lock_window.winfo_exists():
            self.lock_window.lift();return
        if self.sale_frame and self.sale_frame.cart:
            from services.sales import hold_sale
            try:
                hold_sale(self.user['id'],self.sale_frame.cart,'Reprise après fermeture',self.sale_frame.ticket_discount_cents,self.sale_frame.held_id,client_id=self.sale_frame.client_id)
                self.sale_frame.cart=[]
            except Exception as e:
                lang=get_setting('language','fr');messagebox.showerror('ToDo',(f'لم يتم حفظ التذكرة: {e}' if lang=='ar' else f'Ticket non sauvegardé : {e}'));return
        try:
            if get_setting("backup_on_close", "1") == "1":
                create_backup()
        except Exception as e:
            lang=get_setting('language','fr');messagebox.showerror(('النسخ الاحتياطي' if lang=='ar' else 'Sauvegarde'),(f'فشل النسخ الاحتياطي: {e}\nسيبقى البرنامج مفتوحاً لإعادة المحاولة.' if lang=='ar' else f'Sauvegarde échouée : {e}\nLe programme reste ouvert pour réessayer.'));return
        self.destroy()

if __name__ == "__main__":
    app = ToDoApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()

