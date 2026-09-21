"""screens/virtual_keyboard.py — Clavier virtuel AZERTY flottant.

Utilisation :
    from screens.virtual_keyboard import VirtualKeyboard
    VirtualKeyboard(master, target_widget)   # flottant, non-modal
    VirtualKeyboard.toggle(master, widget)   # crée ou détruit
"""
import tkinter as tk
from tkinter import ttk

# ── layout AZERTY complet ──────────────────────────────────────────────────
# Chaque cellule : (label_normal, label_shift, largeur_relative)
# label_shift='' → même touche en majuscule
# label_shift='⌫' etc. → touche spéciale
# largeur : 1 = touche normale, 1.5 = touche large, 2 = très large

_ROW0 = [  # Chiffres + symboles
    ('&','1',1),('é','2',1),('"','3',1),("'",'4',1),('(','5',1),
    ('-','6',1),('è','7',1),'_','8',1),('ç','9',1),('à','0',1),
    (')','°',1),('=','+',1),('⌫','⌫',1.8),
]
# Corriger la typo ci-dessus:
_ROW0 = [
    ('&','1',1),('é','2',1),('"','3',1),("'",'4',1),('(','5',1),
    ('-','6',1),('è','7',1),('_','8',1),('ç','9',1),('à','0',1),
    (')','°',1),('=','+',1),('⌫','⌫',1.8),
]
_ROW1 = [  # AZERTY
    ('Tab','Tab',1.5),
    ('a','A',1),('z','Z',1),('e','E',1),('r','R',1),('t','T',1),
    ('y','Y',1),('u','U',1),('i','I',1),('o','O',1),('p','P',1),
    ('^','¨',1),('$','£',1),('↵','↵',1.8),
]
_ROW2 = [  # Home row
    ('Maj','Maj',1.8),
    ('q','Q',1),('s','S',1),('d','D',1),('f','F',1),('g','G',1),
    ('h','H',1),('j','J',1),('k','K',1),('l','L',1),('m','M',1),
    ('ù','%',1),('*','µ',1),
]
_ROW3 = [  # Shift row
    ('⇧','⇧',2.2),
    ('w','W',1),('x','X',1),('c','C',1),('v','V',1),('b','B',1),
    ('n','N',1),(',',';',1),(';',':',1),(':','/',1),('!','§',1),
    ('⇧','⇧',2.2),
]
_ROW4 = [  # Space + special
    ('Sym','Sym',1.5),
    ('←','←',1),
    (' ',' ',5.5),
    ('→','→',1),
    ('@','@',1),('.','…',1),
    ('✕','✕',1.5),
]

# Symbols page
_SYM0 = [
    ('1','!',1),('2','@',1),('3','#',1),('4','$',1),('5','%',1),
    ('6','^',1),('7','&',1),('8','*',1),('9','(',1),('0',')',1),('⌫','⌫',1.8),
]
_SYM1 = [
    ('+','+',1),('-','-',1),('×','×',1),('÷','÷',1),('=','=',1),
    ('/','/',1),('\\\\','\\\\',1),('|','|',1),('<','<',1),('>','>',1),('_','_',1),('↵','↵',1.8),
]
_SYM2 = [
    ('[','[',1),(']',']',1),('{','{',1),('}','}',1),
    ('(','(',1),(')',')',1),('@','@',1),('&','&',1),
    ('#','#',1),('%','%',1),('€','€',1),('£','£',1),('$','$',1),
]
_SYM3 = [
    ('é','é',1),('è','è',1),('ê','ê',1),('ë','ë',1),
    ('à','à',1),('â','â',1),('ä','ä',1),('î','î',1),
    ('ï','ï',1),('ô','ô',1),('ù','ù',1),('û','û',1),
    ('ç','ç',1),
]
_SYM4 = [
    ('ABC','ABC',2),
    ('←','←',1),(' ',' ',4),('→','→',1),
    ('.','.', 1),(',',',',1),('✕','✕',1.5),
]

_PAGES = {
    'alpha': [_ROW0, _ROW1, _ROW2, _ROW3, _ROW4],
    'sym':   [_SYM0, _SYM1, _SYM2, _SYM3, _SYM4],
}

# ── colors ─────────────────────────────────────────────────────────────────
_BG      = '#1E293B'
_KEY_BG  = '#334155'
_KEY_FG  = '#F1F5F9'
_KEY_HV  = '#475569'
_KEY_SP  = '#0878C9'   # space / special keys
_KEY_ACT = '#2563EB'   # shift active
_BORDER  = '#0F172A'


class VirtualKeyboard(tk.Toplevel):
    """Clavier virtuel AZERTY flottant, non-modal.

    • Ne bloque pas la fenêtre principale  (pas de grab_set)
    • Toujours au premier plan             (attributes('-topmost', True))
    • Déplaçable par glisser               (header bar)
    • target : widget Entry/Text qui reçoit les frappes
    """

    _instance = None   # singleton par fenêtre root

    @classmethod
    def toggle(cls, master, target):
        """Ouvre si fermé, ferme si ouvert."""
        if cls._instance and cls._instance.winfo_exists():
            cls._instance.destroy()
            cls._instance = None
        else:
            cls._instance = cls(master, target)

    # ── init ────────────────────────────────────────────────────────────────
    def __init__(self, master, target):
        super().__init__(master)
        self.target  = target
        self._shift  = False
        self._page   = 'alpha'
        self.overrideredirect(True)          # pas de barre Windows
        self.attributes('-topmost', True)
        self.configure(bg=_BORDER)
        self.resizable(False, False)

        # ── header déplaçable ───────────────────────────────────────────────
        hdr = tk.Frame(self, bg='#0F172A', height=28, cursor='fleur')
        hdr.pack(fill='x')
        tk.Label(hdr, text='⌨  Clavier / لوحة المفاتيح',
                 bg='#0F172A', fg='#94A3B8', font=('Segoe UI', 9)).pack(side='left', padx=8)
        tk.Button(hdr, text='—', bg='#0F172A', fg='#94A3B8', bd=0,
                  activebackground='#1E293B', font=('Segoe UI', 10),
                  command=self._minimize).pack(side='right', padx=2)
        tk.Button(hdr, text='✕', bg='#0F172A', fg='#94A3B8', bd=0,
                  activebackground='#DC2626', activeforeground='#fff',
                  font=('Segoe UI', 10), command=self.destroy).pack(side='right')

        hdr.bind('<ButtonPress-1>',   self._drag_start)
        hdr.bind('<B1-Motion>',       self._drag_move)
        for child in hdr.winfo_children():
            child.bind('<ButtonPress-1>',   self._drag_start)
            child.bind('<B1-Motion>',       self._drag_move)

        # ── key area ────────────────────────────────────────────────────────
        self._key_frame = tk.Frame(self, bg=_BG, padx=6, pady=6)
        self._key_frame.pack(fill='both', expand=True)
        self._build_page(self._page)

        # ── position : bas de l'écran ────────────────────────────────────────
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        kw = self.winfo_width() or 720
        kh = self.winfo_height() or 220
        x  = (sw - kw) // 2
        y  = sh - kh - 40
        self.geometry(f'+{x}+{y}')
        self._minimized = False

    # ── build ────────────────────────────────────────────────────────────────
    def _build_page(self, page):
        for w in self._key_frame.winfo_children():
            w.destroy()
        for row_def in _PAGES[page]:
            row_frame = tk.Frame(self._key_frame, bg=_BG)
            row_frame.pack(fill='x', pady=2)
            for cell in row_def:
                if isinstance(cell, tuple):
                    norm, shifted, rel_w = cell
                else:
                    continue
                self._make_key(row_frame, norm, shifted, rel_w)

    def _make_key(self, parent, norm, shifted, rel_w):
        special = norm in ('⌫','↵','Tab','Maj','⇧','⇧','Sym','ABC','✕','←','→',' ')
        bg   = _KEY_SP if special or norm == ' ' else _KEY_BG
        padx = max(1, int(rel_w * 1))
        ipad = max(6, int(rel_w * 6))

        btn = tk.Button(
            parent,
            text=norm,
            bg=bg, fg=_KEY_FG,
            activebackground=_KEY_HV,
            activeforeground=_KEY_FG,
            font=('Segoe UI', 11),
            bd=1, relief='flat',
            highlightbackground=_BORDER,
            padx=ipad, pady=6,
            cursor='hand2',
            command=lambda n=norm, s=shifted: self._press(n, s),
        )
        btn.pack(side='left', padx=2)
        if rel_w != 1:
            btn.configure(width=max(2, int(rel_w * 2)))
        # hover
        btn.bind('<Enter>', lambda e, b=btn, h=_KEY_HV: b.configure(bg=h))
        btn.bind('<Leave>', lambda e, b=btn, c=bg:       b.configure(bg=c))

    # ── press ────────────────────────────────────────────────────────────────
    def _press(self, norm, shifted):
        w = self._get_target()

        if norm == '✕':
            self.destroy(); return
        if norm == 'Sym':
            self._page = 'sym'; self._build_page('sym'); return
        if norm == 'ABC':
            self._page = 'alpha'; self._build_page('alpha'); return
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
            if w: w.focus_set(); w.event_generate('<Tab>')
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
                w.event_generate('<<Paste>>', data=char)
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
        # fallback: widget focused
        try:
            return self.focus_get()
        except Exception:
            return None

    # ── drag ────────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._dx = e.x_root - self.winfo_x()
        self._dy = e.y_root - self.winfo_y()

    def _drag_move(self, e):
        x = e.x_root - self._dx
        y = e.y_root - self._dy
        self.geometry(f'+{x}+{y}')

    # ── minimize ────────────────────────────────────────────────────────────
    def _minimize(self):
        if self._minimized:
            self._key_frame.pack(fill='both', expand=True)
            self._minimized = False
        else:
            self._key_frame.pack_forget()
            self._minimized = True
        self.update_idletasks()
