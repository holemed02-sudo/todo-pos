"""screens/virtual_keyboard.py — Clavier virtuel AZERTY flottant.

Utilisation :
    from screens.virtual_keyboard import VirtualKeyboard
    VirtualKeyboard(master, target_widget)
    VirtualKeyboard.toggle(master, widget)   # crée ou détruit
"""
import tkinter as tk
from tkinter import ttk

# ── Layout AZERTY ─────────────────────────────────────────────────────────
# Chaque cellule : (label_normal, label_shift, largeur_relative)
# largeur: 1=normale, 1.5=large, 2=très large

_ROW0 = [
    ('&', '1', 1), ('é', '2', 1), ('"', '3', 1), ("'", '4', 1), ('(', '5', 1),
    ('-', '6', 1), ('è', '7', 1), ('_', '8', 1), ('ç', '9', 1), ('à', '0', 1),
    (')', '°', 1), ('=', '+', 1), ('⌫', '⌫', 1.8),
]
_ROW1 = [
    ('Tab', 'Tab', 1.5),
    ('a', 'A', 1), ('z', 'Z', 1), ('e', 'E', 1), ('r', 'R', 1), ('t', 'T', 1),
    ('y', 'Y', 1), ('u', 'U', 1), ('i', 'I', 1), ('o', 'O', 1), ('p', 'P', 1),
    ('^', '¨', 1), ('$', '£', 1), ('↵', '↵', 1.8),
]
_ROW2 = [
    ('Maj', 'Maj', 1.8),
    ('q', 'Q', 1), ('s', 'S', 1), ('d', 'D', 1), ('f', 'F', 1), ('g', 'G', 1),
    ('h', 'H', 1), ('j', 'J', 1), ('k', 'K', 1), ('l', 'L', 1), ('m', 'M', 1),
    ('ù', '%', 1), ('*', 'µ', 1),
]
_ROW3 = [
    ('⇧', '⇧', 2.2),
    ('w', 'W', 1), ('x', 'X', 1), ('c', 'C', 1), ('v', 'V', 1), ('b', 'B', 1),
    ('n', 'N', 1), (',', ';', 1), (';', ':', 1), (':', '/', 1), ('!', '§', 1),
    ('⇧', '⇧', 2.2),
]
_ROW4 = [
    ('Sym', 'Sym', 1.5),
    ('←', '←', 1),
    (' ', ' ', 5.5),
    ('→', '→', 1),
    ('@', '@', 1), ('.', '…', 1),
    ('✕', '✕', 1.5),
]

_SYM0 = [
    ('1', '!', 1), ('2', '@', 1), ('3', '#', 1), ('4', '$', 1), ('5', '%', 1),
    ('6', '^', 1), ('7', '&', 1), ('8', '*', 1), ('9', '(', 1), ('0', ')', 1),
    ('⌫', '⌫', 1.8),
]
_SYM1 = [
    ('+', '+', 1), ('-', '-', 1), ('×', '×', 1), ('÷', '÷', 1), ('=', '=', 1),
    ('/', '/', 1), ('\\', '\\', 1), ('|', '|', 1), ('<', '<', 1), ('>', '>', 1),
    ('_', '_', 1), ('↵', '↵', 1.8),
]
_SYM2 = [
    ('[', '[', 1), (']', ']', 1), ('{', '{', 1), ('}', '}', 1),
    ('(', '(', 1), (')', ')', 1), ('@', '@', 1), ('&', '&', 1),
    ('#', '#', 1), ('%', '%', 1), ('€', '€', 1), ('£', '£', 1), ('$', '$', 1),
]
_SYM3 = [
    ('é', 'É', 1), ('è', 'È', 1), ('ê', 'Ê', 1), ('ë', 'Ë', 1),
    ('à', 'À', 1), ('â', 'Â', 1), ('ä', 'Ä', 1), ('î', 'Î', 1),
    ('ï', 'Ï', 1), ('ô', 'Ô', 1), ('ù', 'Ù', 1), ('û', 'Û', 1),
    ('ç', 'Ç', 1),
]
_SYM4 = [
    ('ABC', 'ABC', 2),
    ('←', '←', 1), (' ', ' ', 4), ('→', '→', 1),
    ('.', '.', 1), (',', ',', 1), ('✕', '✕', 1.5),
]

_PAGES = {
    'alpha': [_ROW0, _ROW1, _ROW2, _ROW3, _ROW4],
    'sym':   [_SYM0, _SYM1, _SYM2, _SYM3, _SYM4],
}

# ── Colors ─────────────────────────────────────────────────────────────────
_BG     = '#1E293B'
_KEY_BG = '#334155'
_KEY_FG = '#F1F5F9'
_KEY_HV = '#475569'
_KEY_SP = '#0878C9'
_BORDER = '#0F172A'


class VirtualKeyboard(tk.Toplevel):
    """Clavier virtuel AZERTY flottant, non-modal.
    • Pas de grab_set → ne bloque pas la fenêtre principale
    • se ferme dès que l’utilisateur quitte le champ cible
    • target : Entry ou Text qui reçoit les frappes
    """

    _instance = None

    @classmethod
    def toggle(cls, master, target):
        if cls._instance and cls._instance.winfo_exists():
            cls._instance.destroy()
            cls._instance = None
        else:
            cls._instance = cls(master, target)

    def __init__(self, master, target):
        super().__init__(master)
        self.target     = target
        self._shift     = False
        self._page      = 'alpha'
        self._minimized = False
        self.overrideredirect(True)
        self.transient(master.winfo_toplevel())
        self._close_after = None
        self.configure(bg=_BORDER)
        self.resizable(False, False)

        # ── header draggable ───────────────────────────────────────────────
        self._hdr = tk.Frame(self, bg='#0F172A', height=28, cursor='fleur')
        self._hdr.pack(fill='x')
        tk.Label(self._hdr, text='⌨  Clavier', bg='#0F172A', fg='#94A3B8',
                 font=('Segoe UI', 9)).pack(side='left', padx=8)
        tk.Button(self._hdr, text='—', bg='#0F172A', fg='#94A3B8', bd=0,
                  activebackground='#1E293B',
                  font=('Segoe UI', 10), command=self._minimize).pack(side='right', padx=2)
        tk.Button(self._hdr, text='✕', bg='#0F172A', fg='#94A3B8', bd=0,
                  activebackground='#DC2626', activeforeground='#fff',
                  font=('Segoe UI', 10), command=self._close).pack(side='right')

        for w in [self._hdr] + list(self._hdr.winfo_children()):
            w.bind('<ButtonPress-1>', self._drag_start)
            w.bind('<B1-Motion>',     self._drag_move)

        # ── key area ──────────────────────────────────────────────────────
        self._key_frame = tk.Frame(self, bg=_BG, padx=6, pady=6)
        self._key_frame.pack(fill='both', expand=True)
        self._build_page('alpha')

        # ── position bottom-center ────────────────────────────────────────
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        kw = self.winfo_reqwidth()  or 720
        kh = self.winfo_reqheight() or 220
        self.geometry(f'+{(sw - kw) // 2}+{sh - kh - 48}')
        self.protocol('WM_DELETE_WINDOW', self._close)
        self.bind('<Escape>', lambda event: self._close())
        self.target.bind('<FocusOut>', self._schedule_close, add='+')
        self.target.bind('<Destroy>', lambda event: self._close(), add='+')
        self.after_idle(self._focus_target)

    def _focus_target(self):
        try:
            if self.target.winfo_exists():
                self.target.focus_set()
        except tk.TclError:
            self._close()

    def _schedule_close(self, event=None):
        if self._close_after is not None:
            self.after_cancel(self._close_after)
        self._close_after = self.after(120, self._close_if_inactive)

    def _close_if_inactive(self):
        self._close_after = None
        try:
            focused = self.focus_get()
            if focused is self.target or str(focused).startswith(str(self)):
                return
        except tk.TclError:
            pass
        self._close()

    def _close(self):
        if VirtualKeyboard._instance is self:
            VirtualKeyboard._instance = None
        try:
            if self.winfo_exists():
                self.destroy()
        except tk.TclError:
            pass

    # ── build ─────────────────────────────────────────────────────────────
    def _build_page(self, page):
        self._page = page
        for w in self._key_frame.winfo_children():
            w.destroy()
        for row_def in _PAGES[page]:
            row_frame = tk.Frame(self._key_frame, bg=_BG)
            row_frame.pack(fill='x', pady=2)
            for cell in row_def:
                if isinstance(cell, tuple) and len(cell) == 3:
                    self._make_key(row_frame, *cell)

    def _make_key(self, parent, norm, shifted, rel_w):
        special = norm in ('⌫', '↵', 'Tab', 'Maj', '⇧', 'Sym', 'ABC', '✕', '←', '→', ' ')
        bg      = _KEY_SP if special else _KEY_BG
        ipadx   = max(4, int(rel_w * 6))
        btn = tk.Button(
            parent, text=norm,
            bg=bg, fg=_KEY_FG,
            activebackground=_KEY_HV, activeforeground=_KEY_FG,
            font=('Segoe UI', 11), bd=1, relief='flat',
            highlightbackground=_BORDER,
            padx=ipadx, pady=6, cursor='hand2',
            command=lambda n=norm, s=shifted: self._press(n, s),
        )
        btn.pack(side='left', padx=2)
        if rel_w > 1:
            btn.configure(width=max(2, int(rel_w * 2)))
        btn.bind('<Enter>', lambda e, b=btn, h=_KEY_HV: b.configure(bg=h))
        btn.bind('<Leave>', lambda e, b=btn, c=bg:       b.configure(bg=c))

    # ── press ─────────────────────────────────────────────────────────────
    def _press(self, norm, shifted):
        w = self._get_target()
        if norm == '✕':
            self.destroy(); return
        if norm == 'Sym':
            self._build_page('sym'); return
        if norm == 'ABC':
            self._build_page('alpha'); return
        if norm in ('⇧', 'Maj'):
            self._shift = not self._shift
            self._build_page(self._page); return
        if norm == '⌫':
            if w: w.event_generate('<BackSpace>')
            return
        if norm == '↵':
            if w: w.event_generate('<Return>')
            return
        if norm == 'Tab':
            if w: w.event_generate('<Tab>')
            return
        if norm == '←':
            if w: w.event_generate('<Left>')
            return
        if norm == '→':
            if w: w.event_generate('<Right>')
            return
        char = shifted if self._shift else norm
        if w:
            try:
                w.insert(tk.INSERT, char)
            except Exception:
                pass
        if self._shift and norm not in ('⇧', 'Maj'):
            self._shift = False
            self._build_page(self._page)

    def _get_target(self):
        try:
            if self.target and self.target.winfo_exists():
                self.target.focus_set()
                return self.target
        except Exception:
            pass
        try:
            return self.focus_get()
        except Exception:
            return None

    # ── drag ──────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._dx = e.x_root - self.winfo_x()
        self._dy = e.y_root - self.winfo_y()

    def _drag_move(self, e):
        self.geometry(f'+{e.x_root - self._dx}+{e.y_root - self._dy}')

    # ── minimize ──────────────────────────────────────────────────────────
    def _minimize(self):
        if self._minimized:
            self._key_frame.pack(fill='both', expand=True)
        else:
            self._key_frame.pack_forget()
        self._minimized = not self._minimized
        self.update_idletasks()
