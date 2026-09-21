import tkinter as tk
from tkinter import ttk

def clear(frame):
    for w in frame.winfo_children():
        w.destroy()

def labeled_entry(parent, label, variable, row, width=28, bold=False):
    ttk.Label(parent,text=label,font=("Segoe UI",10,"bold") if bold else ("Segoe UI",10)).grid(row=row,column=0,sticky="w",padx=(0,10),pady=5)
    e=ttk.Entry(parent,textvariable=variable,width=width,font=("Segoe UI",11))
    e.grid(row=row,column=1,sticky="ew",pady=5)
    attach_keyboard(e)
    return e


class VirtualKeyboard(tk.Toplevel):
    """On-screen AZERTY keyboard for touch input, matching the reference's
    popup keyboard. One shared instance follows whichever entry currently
    has focus; it types into that entry at the cursor position and stays
    open across fields (tap another field, the keyboard keeps typing into
    it) until closed with Fermer/Escape."""

    ROWS = [
        list('1234567890'),
        list('AZERTYUIOP'),
        list('QSDFGHJKL'),
        list('WXCVBN'),
    ]

    _shared = None

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.configure(bg='#1F2937')
        self.target = None
        self.shift = False
        self._build()
        self.bind('<Escape>', lambda event: self.destroy())
        self.withdraw()

    @classmethod
    def show_for(cls, entry):
        root = entry.winfo_toplevel()
        if cls._shared is None or not cls._shared.winfo_exists():
            cls._shared = VirtualKeyboard(root)
        kb = cls._shared
        kb.target = entry
        kb.deiconify()
        kb.lift()
        x = root.winfo_rootx()
        y = root.winfo_rooty() + root.winfo_height() - kb.winfo_reqheight() - 10
        kb.geometry(f'+{max(x, 0)}+{max(y, 0)}')
        return kb

    def _key(self, char):
        def handler():
            entry = self.target
            if entry is None or not entry.winfo_exists():
                return
            entry.focus_set()
            entry.insert('insert', char.upper() if self.shift else char.lower())
            if self.shift:
                self.shift = False
                self._refresh_labels()
        return handler

    def _backspace(self):
        entry = self.target
        if entry is None or not entry.winfo_exists():
            return
        entry.focus_set()
        pos = entry.index('insert')
        if pos > 0:
            entry.delete(pos - 1, pos)

    def _space(self):
        entry = self.target
        if entry is None or not entry.winfo_exists():
            return
        entry.focus_set()
        entry.insert('insert', ' ')

    def _toggle_shift(self):
        self.shift = not self.shift
        self._refresh_labels()

    def _refresh_labels(self):
        for row_buttons, row_chars in zip(self.key_buttons, self.ROWS):
            for button, char in zip(row_buttons, row_chars):
                if char.isalpha():
                    button.configure(text=char.upper() if self.shift else char.lower())

    def _build(self):
        pad = dict(padx=3, pady=3)
        self.key_buttons = []
        for row_chars in self.ROWS:
            row_frame = tk.Frame(self, bg='#1F2937')
            row_frame.pack(fill='x')
            buttons = []
            for char in row_chars:
                b = tk.Button(row_frame, text=char, width=4, height=2, font=('Segoe UI', 11, 'bold'),
                               bg='#374151', fg='white', activebackground='#4B5563', relief='flat',
                               command=self._key(char))
                b.pack(side='left', **pad)
                buttons.append(b)
            self.key_buttons.append(buttons)
        bottom = tk.Frame(self, bg='#1F2937')
        bottom.pack(fill='x')
        tk.Button(bottom, text='{MAJ}', width=6, height=2, bg='#7C3AED', fg='white', relief='flat',
                  command=self._toggle_shift).pack(side='left', **pad)
        tk.Button(bottom, text='Espace / مسافة', height=2, bg='#374151', fg='white', relief='flat',
                  command=self._space).pack(side='left', fill='x', expand=True, **pad)
        tk.Button(bottom, text='\u232b', width=6, height=2, bg='#B91C1C', fg='white', relief='flat',
                  command=self._backspace).pack(side='left', **pad)
        tk.Button(bottom, text='Fermer / \u0625\u0650\u0642\u0641\u0627\u0644', width=12, height=2, bg='#065F46', fg='white', relief='flat',
                  command=self.destroy).pack(side='left', **pad)


def attach_keyboard(entry):
    """Wire a text Entry to open/target the shared VirtualKeyboard on focus,
    for touch use. Safe to call on many entries; only one keyboard exists.
    It stays open across fields (tap another wired entry, it keeps typing
    into that one) until closed explicitly with Fermer or Escape."""
    entry.bind('<FocusIn>', lambda event: VirtualKeyboard.show_for(entry))
    return entry
    return entry
