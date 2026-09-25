import tkinter as tk
from tkinter import ttk

def clear(frame):
    for w in frame.winfo_children():
        w.destroy()

def labeled_entry(parent, label, variable, row, width=28, bold=False):
    ttk.Label(parent,text=label,font=("Segoe UI",10,"bold") if bold else ("Segoe UI",10)).grid(row=row,column=0,sticky="w",padx=(0,10),pady=5)
    e=ttk.Entry(parent,textvariable=variable,width=width,font=("Segoe UI",11))
    e.grid(row=row,column=1,sticky="ew",pady=5)
    return e


class EmbeddedTouchKeyboard:
    """Reusable keyboard that stays inside modal editors, so Tk grabs cannot block touch input."""
    keyboard_default_target = None

    def init_touch_keyboard(self, default_target=None):
        self._keyboard_target = default_target
        self.keyboard_default_target = default_target
        self.keyboard_frame = tk.Frame(self, bg='#1E293B', padx=6, pady=6)
        self.keyboard_visible = False
        self.bind_all('<FocusIn>', self._remember_keyboard_target, add='+')
        self._build_embedded_keyboard()

    def _is_text_input(self, widget):
        try:
            return widget is not None and widget.winfo_exists() and widget.winfo_class() in (
                'Entry','TEntry','Text','Spinbox','TSpinbox','TCombobox'
            )
        except tk.TclError:
            return False

    def _remember_keyboard_target(self, event):
        if self._is_text_input(event.widget) and event.widget.winfo_toplevel() is self:
            self._keyboard_target = event.widget

    def _default_keyboard_widget(self):
        if self._is_text_input(self.keyboard_default_target):
            return self.keyboard_default_target
        for widget in self.winfo_children():
            for child in widget.winfo_children():
                if self._is_text_input(child):
                    return child
        return None

    def toggle_embedded_keyboard(self):
        if self.keyboard_visible:
            self.keyboard_frame.pack_forget()
            self.keyboard_visible=False
            target=self._keyboard_target or self._default_keyboard_widget()
            if self._is_text_input(target): self.after_idle(target.focus_set)
            return
        target=self.focus_get()
        if self._is_text_input(target) and target.winfo_toplevel() is self:
            self._keyboard_target=target
        if not self._is_text_input(self._keyboard_target):
            self._keyboard_target=self._default_keyboard_widget()
        self.keyboard_frame.pack(side='bottom',fill='x')
        self.keyboard_visible=True
        if self._is_text_input(self._keyboard_target): self.after_idle(self._keyboard_target.focus_set)

    def _build_embedded_keyboard(self):
        rows=[
            ['1','2','3','4','5','6','7','8','9','0','⌫'],
            ['a','z','e','r','t','y','u','i','o','p'],
            ['q','s','d','f','g','h','j','k','l','m'],
            ['w','x','c','v','b','n',',','.','-','_'],
            ['Espace','@','/','Effacer','Entrée','Fermer'],
        ]
        for keys in rows:
            row=tk.Frame(self.keyboard_frame,bg='#1E293B');row.pack(fill='x',pady=2)
            for key in keys:
                tk.Button(row,text=key,font=('Segoe UI',11,'bold'),bg='#334155',fg='white',
                    activebackground='#475569',activeforeground='white',relief='flat',bd=0,
                    padx=8,pady=7,command=lambda k=key:self._keyboard_press(k)
                ).pack(side='left',fill='x',expand=True,padx=2)

    def _keyboard_press(self,key):
        w=self._keyboard_target
        if not self._is_text_input(w): w=self.focus_get()
        if not self._is_text_input(w) or w.winfo_toplevel() is not self:
            w=self._default_keyboard_widget()
            self._keyboard_target=w
        if not self._is_text_input(w): return
        if key=='Fermer':
            self.toggle_embedded_keyboard();return
        if key=='⌫': w.event_generate('<BackSpace>')
        elif key=='Entrée': w.event_generate('<Return>')
        elif key=='Effacer':
            try:w.delete(0,tk.END)
            except tk.TclError:w.delete('1.0',tk.END)
        else:
            char=' ' if key=='Espace' else key
            try:w.insert(tk.INSERT,char)
            except tk.TclError:pass
        self._keyboard_target=w
        self.after_idle(w.focus_set)
