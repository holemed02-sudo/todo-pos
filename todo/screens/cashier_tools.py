"""Small cashier tools that leave the active ticket untouched."""
import ast
import time
import tkinter as tk
from tkinter import ttk
from decimal import Decimal, InvalidOperation, localcontext
from database import connect, get_setting
from services.security import verify_pin, audit


def calculate(expression):
    expression=expression.strip().replace(',', '.').replace('×','*').replace('÷','/')
    if not expression or len(expression)>160:
        raise ValueError('Calcul invalide')
    tree=ast.parse(expression,mode='eval')
    if sum(1 for _ in ast.walk(tree))>80:
        raise ValueError('Calcul trop long')
    def value(node):
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            return Decimal(ast.get_source_segment(expression,node))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            result=value(node.operand)
            return -result if isinstance(node.op,ast.USub) else result
        if isinstance(node,ast.BinOp):
            a,b=value(node.left),value(node.right)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.Div):return a/b
        raise ValueError('Utilisez +, −, ×, ÷ et les parenthèses')
    with localcontext() as context:
        context.prec=28
        result=value(tree.body)
    if not result.is_finite() or abs(result)>Decimal('1e24'):
        raise ValueError('Résultat hors limites')
    return format(result.normalize(),'f')


class Calculator(tk.Toplevel):
    def __init__(self,master):
        super().__init__(master)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.title(self.tr('Calculatrice','الآلة الحاسبة'));self.transient(master.winfo_toplevel());self.grab_set()
        self.expression=tk.StringVar()
        entry=ttk.Entry(self,textvariable=self.expression,font=('Segoe UI',22),justify='right')
        entry.grid(row=0,column=0,columnspan=4,padx=10,pady=10,sticky='ew')
        self.error=ttk.Label(self,foreground='#DC2626',wraplength=310)
        self.error.grid(row=1,column=0,columnspan=4)
        for index,key in enumerate(('7','8','9','÷','4','5','6','×','1','2','3','-','0',',','=','+','C','⌫','(',')')):
            ttk.Button(self,text=key,command=lambda k=key:self.press(k)).grid(row=2+index//4,column=index%4,padx=3,pady=3,ipady=8,sticky='ew')
        ttk.Button(self,text=self.tr('Fermer','إغلاق'),command=self.destroy).grid(row=7,column=0,columnspan=4,pady=8)
        entry.bind('<Return>',lambda e:self.press('='));self.bind('<Escape>',lambda e:self.destroy())
        entry.focus_set()

    def press(self,key):
        self.error.config(text='')
        if key=='C':self.expression.set('')
        elif key=='⌫':self.expression.set(self.expression.get()[:-1])
        elif key=='=':
            try:self.expression.set(calculate(self.expression.get()))
            except (ValueError,SyntaxError,ArithmeticError,InvalidOperation):self.error.config(text=self.tr('Calcul invalide ou division par zéro.','عملية غير صحيحة أو قسمة على صفر.'))
        else:self.expression.set(self.expression.get()+key)


class CashierLock(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.app=app;self.failures=0;self.blocked_until=0
        self.title(self.tr('Caisse verrouillée','الصندوق مقفل'))
        self.transient(app);self.grab_set();self.protocol('WM_DELETE_WINDOW',lambda:None)
        self.pin=tk.StringVar()
        ttk.Label(self,text=app.user['display_name'],font=('Segoe UI',18,'bold')).pack(padx=28,pady=15)
        ttk.Label(self,text=self.tr('PIN pour reprendre le ticket','الرمز للرجوع للبيع')).pack(padx=20)
        entry=ttk.Entry(self,textvariable=self.pin,show='●',justify='center',font=('Segoe UI',22))
        entry.pack(padx=25,pady=12)
        self.error=ttk.Label(self,foreground='#DC2626');self.error.pack()
        ttk.Button(self,text=self.tr('Déverrouiller','فتح'),command=self.unlock).pack(pady=15)
        self.bind('<Return>',lambda e:self.unlock());entry.focus_set()

    def unlock(self):
        if time.monotonic()<self.blocked_until:
            self.error.config(text=self.tr('Patientez 30 secondes.','انتظر 30 ثانية.'));return
        with connect() as conn:
            user=conn.execute('SELECT pin_hash FROM users WHERE id=? AND active=1',(self.app.user['id'],)).fetchone()
            if not user or not verify_pin(self.pin.get(),user['pin_hash']):
                self.pin.set('');self.failures+=1
                if self.failures>=5:self.blocked_until=time.monotonic()+30;self.failures=0
                self.error.config(text=self.tr('PIN incorrect','الرمز غير صحيح'));return
            audit(conn,'UNLOCK',self.app.user['id'])
        self.app.lock_window=None
        self.destroy()
        if self.app.sale_frame:self.app.sale_frame.focus_search()
