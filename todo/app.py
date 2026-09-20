import tkinter as tk
from tkinter import ttk, messagebox

from database import init_db, get_setting
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
        self.shell = None
        self.lock_window = None

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

        self.show_login()

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
        ttk.Label(outer,text='Votre commerce. En toute simplicité.').pack(pady=(0,18))
        with connect() as conn:
            self.login_users=[dict(r) for r in conn.execute('SELECT * FROM users WHERE active=1 ORDER BY id')]
        self.avatar=ttk.Label(outer,text='●',font=('Segoe UI',28),foreground='#2563EB')
        self.avatar.pack()
        names=[u['display_name']+' · '+u['username'] for u in self.login_users]
        self.user_choice=ttk.Combobox(outer,values=names,state='readonly',font=('Segoe UI',12))
        self.user_choice.pack(fill='x',pady=8)
        if names:self.user_choice.current(0)
        self.login_pin=tk.StringVar()
        ttk.Label(outer,text='PIN / الرمز السري').pack(anchor='w',pady=(8,4))
        pin=ttk.Entry(outer,textvariable=self.login_pin,show='●',font=('Segoe UI',20),justify='center')
        pin.pack(fill='x',ipady=5);pin.bind('<Return>',lambda e:self.login())
        ttk.Button(outer,text='Entrer / الدخول',style='Primary.TButton',command=self.login).pack(fill='x',pady=16)
        self.after(100,lambda: pin.focus_set() if pin.winfo_exists() else None)

    def login(self):
        import time
        if time.monotonic()<self.login_blocked_until:
            messagebox.showerror('ToDo','Patientez 30 secondes avant de réessayer.');return
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
            messagebox.showerror('ToDo','PIN incorrect.');return
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
        bar=tk.Frame(self.shell,bg="#0878C9",height=58)
        bar.pack(fill="x");bar.pack_propagate(False)
        tk.Label(bar,text=get_setting("shop_name","ToDo"),bg="#0878C9",fg="white",font=("Segoe UI",17,"bold")).pack(side="left",padx=18)
        nav=[("Vente","sale"),("Stock","stock"),("Journal","journal"),("Gestion","management"),("Paramètres","settings"),("Statistiques","statistics")]
        self.nav_buttons={}
        for txt,key in nav:
            if self.user["role"]!="admin" and key in ("settings","journal","management","statistics"):continue
            b=tk.Button(bar,text=txt,bg="#0878C9",fg="white",activebackground="#075B96",activeforeground="white",relief="flat",bd=0,font=("Segoe UI",10,"bold"),padx=10,command=lambda k=key:self.show(k))
            b.pack(side="left",fill="y");self.nav_buttons[key]=b
        tk.Button(bar,text="Écran client",bg="#0878C9",fg="white",activebackground="#075B96",relief="flat",bd=0,font=("Segoe UI",9),command=self.toggle_customer_display).pack(side="right",padx=10)
        tk.Label(bar,text=f"{self.user['display_name']} · {self.user['role']}",bg="#0878C9",fg="white",font=("Segoe UI",9)).pack(side="right",padx=8)
        self.content=ttk.Frame(self.shell);self.content.pack(fill="both",expand=True)

    def show(self, key):
        if self.lock_window and self.lock_window.winfo_exists():
            self.lock_window.lift();return
        if self.user['role']!='admin' and key in ('products','purchases','settings','journal','management','statistics'):
            messagebox.showerror('ToDo','Action réservée à un administrateur.');return
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
            "returns": lambda: ReturnsFrame(self.content, self),
            "journal": lambda: JournalFrame(self.content),
            "settings": lambda: SettingsFrame(self.content, self),
            "management": lambda: ManagementFrame(self.content, self),
            "statistics": lambda: StatisticsFrame(self.content),
        }

        self.current = makers[key]()
        if key=="sale":self.sale_frame=self.current
        self.current.pack(fill="both", expand=True)
        self._mark_nav(key)

    def _mark_nav(self,key):
        for name,button in getattr(self,'nav_buttons',{}).items():
            button.configure(bg="#075B96" if name==key else "#0878C9")

    def toggle_customer_display(self):
        if self.customer_window and self.customer_window.winfo_exists():
            self.customer_window.destroy()
            self.customer_window = None
            self.customer_label = None
            return

        w = tk.Toplevel(self)
        self.customer_window = w
        w.title("ToDo — Écran client")
        w.geometry("900x600")

        ttk.Label(
            w,
            text=get_setting("shop_name", "ToDo"),
            font=("Segoe UI", 28, "bold"),
        ).pack(pady=20)

        self.customer_label = ttk.Label(
            w,
            text="Bienvenue",
            font=("Segoe UI", 18),
            justify="left",
        )
        self.customer_label.pack(fill="both", expand=True, padx=30, pady=20)

        ttk.Label(
            w,
            text="جر النافذة للشاشة الثانية ثم Full Screen.",
            font=("Segoe UI", 10),
        ).pack(pady=10)

    def update_customer_display(self, cart, total):
        if not (
            self.customer_window
            and self.customer_window.winfo_exists()
            and self.customer_label
        ):
            return

        lines = []
        for x in cart[-8:]:
            lines.append(f"{x['name']}   x{x['qty']:g}")

        lines.append(
            "\nTOTAL: "
            + f"{total/100:.2f} {get_setting('currency', 'DH')}"
        )
        self.customer_label.config(text="\n".join(lines))

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
                hold_sale(self.user['id'],self.sale_frame.cart,'Reprise après fermeture',self.sale_frame.ticket_discount_cents,self.sale_frame.held_id)
                self.sale_frame.cart=[]
            except Exception as e:
                messagebox.showerror('ToDo',f'Ticket non sauvegardé : {e}');return
        try:
            if get_setting("backup_on_close", "1") == "1":
                create_backup()
        except Exception as e:
            messagebox.showerror("Backup",f"Sauvegarde échouée : {e}\nLe programme reste ouvert pour réessayer.");return
        self.destroy()

if __name__ == "__main__":
    app = ToDoApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
