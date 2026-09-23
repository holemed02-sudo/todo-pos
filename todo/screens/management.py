import tkinter as tk
from tkinter import ttk, messagebox


# group definitions: (emoji, label, route, bg, fg)
GROUPS = [
    [
        ("📥", "Réceptions",         "purchases",  "#0891B2", "#fff"),
        ("📤", "Sorties",             "sorties",    "#D97706", "#fff"),
        ("📝", "Inventaire",          "inventory",  "#16A34A", "#fff"),
        ("🔄", "Mouvements de stock", "stock",      "#7C3AED", "#fff"),
    ],
    [
        ("🚚", "Fournisseurs",              "suppliers",  "#EA580C", "#fff"),
        ("💳", "Règlements fournisseurs",   "supplier_payments", "#EA580C", "#fff"),
        ("📊", "État crédits fournisseurs", "supplier_credits",  "#DC2626", "#fff"),
    ],
    [
        ("👥", "Clients",             "clients",         "#2563EB", "#fff"),
        ("💰", "Règlements clients",  "clients_payments","#16A34A", "#fff"),
        ("📈", "État crédits clients","clients_credits", "#DC2626", "#fff"),
    ],
    [
        ("💸", "Dépenses",    "cash", "#D97706", "#fff"),
        ("📅", "Rendez-vous", "rendez_vous", "#0891B2", "#fff"),
    ],
]

CARD_W, CARD_H = 185, 90


def _recolor(w, c):
    try: w.configure(bg=c)
    except Exception: pass
    for ch in w.winfo_children():
        _recolor(ch, c)


def _hover_color(hex_color, delta=0.10):
    import colorsys
    r2,g2,b2 = int(hex_color[1:3],16)/255, int(hex_color[3:5],16)/255, int(hex_color[5:7],16)/255
    h,s,v = colorsys.rgb_to_hsv(r2,g2,b2)
    nr,ng,nb = colorsys.hsv_to_rgb(h, s, min(v+delta, 1))
    return '#%02x%02x%02x' % (int(nr*255), int(ng*255), int(nb*255))


class ManagementFrame(ttk.Frame):
    """Gestion — stock, fournisseurs, clients, dépenses."""

    def __init__(self, master, app):
        super().__init__(master, padding=0)
        self.app = app
        self._build()

    def _build(self):
        # header
        header = tk.Frame(self, bg="#1E293B", height=58)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🗂️  Gestion", bg="#1E293B", fg="white",
                 font=("Segoe UI", 18, "bold")).pack(side="left", padx=22, pady=10)

        # cards area
        area = tk.Frame(self, bg="#F8FAFC")
        area.pack(fill="both", expand=True, padx=30, pady=24)

        for group in GROUPS:
            row = tk.Frame(area, bg="#F8FAFC")
            row.pack(anchor="w", pady=6)
            for emoji, label, key, bg, fg in group:
                self._card(row, emoji, label, key, bg, fg)

    def _card(self, parent, emoji, label, key, bg, fg):
        is_placeholder = key is None
        actual_bg = "#CBD5E1" if is_placeholder else bg
        actual_fg = "#6B7280" if is_placeholder else fg

        card = tk.Frame(parent, bg=actual_bg, width=CARD_W, height=CARD_H,
                        cursor="hand2" if not is_placeholder else "arrow",
                        bd=0, relief="flat")
        card.pack(side="left", padx=7)
        card.pack_propagate(False)

        inner = tk.Frame(card, bg=actual_bg)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(inner, text=emoji, bg=actual_bg, fg=actual_fg,
                 font=("Segoe UI", 22)).pack()
        tk.Label(inner, text=label, bg=actual_bg, fg=actual_fg,
                 font=("Segoe UI", 9, "bold" if not is_placeholder else "normal"),
                 wraplength=CARD_W-16, justify="center").pack(pady=(2, 0))

        if is_placeholder:
            tk.Label(inner, text="bientôt", bg=actual_bg, fg="#9CA3AF",
                     font=("Segoe UI", 7)).pack()
            return

        hover = _hover_color(actual_bg)

        def on_enter(e, c=card, h=hover):
            _recolor(c, h)
        def on_leave(e, c=card, b=actual_bg):
            _recolor(c, b)
        def on_click(e=None, k=key, lbl=label):
            self._activate(k, lbl)

        for w in [card, inner] + inner.winfo_children():
            try:
                w.bind("<Button-1>", on_click)
                w.bind("<Enter>",    on_enter)
                w.bind("<Leave>",    on_leave)
            except Exception:
                pass

    def _activate(self, key, label):
        app = self.app
        if key == "clients_payments":
            app.show("clients"); return
        if key == "clients_credits":
            from screens.clients import CreditStateWindow
            CreditStateWindow(app); return
        if key == "supplier_credits":
            from screens.supplier_payments import SupplierCreditStateWindow
            SupplierCreditStateWindow(app); return
        if key:
            app.show(key)
            if label == "Dépenses":
                try: app.current.expense()
                except Exception: pass
