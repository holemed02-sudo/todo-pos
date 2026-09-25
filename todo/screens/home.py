import tkinter as tk
from tkinter import ttk
from services.reports import today_summary
from services.money import fmt


# card definitions: emoji, label, route, bg, fg
NAV_CARDS = [
    ("🛒", "Vente",        "sale",       "#2563EB", "#ffffff"),
    ("📦", "Stock",        "stock",      "#0891B2", "#ffffff"),
    ("📋", "Journal",      "journal",    "#7C3AED", "#ffffff"),
    ("🗂️", "Gestion",     "management", "#1E293B", "#ffffff"),
    ("⚙️", "Paramètres",  "settings",   "#64748B", "#ffffff"),
    ("📊", "Statistiques", "statistics", "#16A34A", "#ffffff"),
]


class HomeFrame(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=0)
        self.app = app
        from database import get_setting
        self.lang = get_setting("language", "fr")
        self.tr = lambda fr, ar: ar if self.lang == "ar" else fr
        self._build()

    def _build(self):
        # ── top banner ────────────────────────────────────────────────────
        from database import get_setting
        shop = get_setting("shop_name", "ToDo")
        banner_color=getattr(self.app,"theme_color","#2563EB")
        banner = tk.Frame(self, bg=banner_color, height=96)
        banner.pack(fill="x")
        banner.pack_propagate(False)
        tk.Label(banner, text=shop, bg=banner_color, fg="white",
                 font=("Segoe UI", 32, "bold")).pack(side="left", padx=30, pady=12)
        tk.Label(banner, text=self.tr("Point de Vente","نقطة البيع"),
                 bg=banner_color, fg="#DBEAFE",
                 font=("Segoe UI", 11)).pack(side="left", padx=4)

        # ── KPI strip ────────────────────────────────────────────────────
        kpi_bar = tk.Frame(self, bg="#FFFFFF", height=76)
        kpi_bar.pack(fill="x")
        kpi_bar.pack_propagate(False)
        try:
            s = today_summary()
            kpis = [
                ("💰 Ventes aujourd'hui",  fmt(s["net_sales"])),
                (self.tr("🎫 Tickets","🎫 التذاكر"),               str(s["tickets"])),
                (self.tr("📈 Marge brute","📈 الهامش الإجمالي"),           fmt(s["gross_margin"])),
                (self.tr("⚠️ Stock faible","⚠️ مخزون منخفض"),          str(s["alerts"])),
            ]
        except Exception:
            kpis = []
        for label, val in kpis:
            cell = tk.Frame(kpi_bar, bg="#FFFFFF")
            cell.pack(side="left", padx=24, pady=8)
            tk.Label(cell, text=label, bg="#FFFFFF",
                     fg="#64748B", font=("Segoe UI", 9)).pack(anchor="w")
            tk.Label(cell, text=val, bg="#FFFFFF",
                     fg="#0F172A", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        tk.Frame(kpi_bar, bg="#E2E8F0", width=1).pack(side="left", fill="y", pady=12)

        # ── Nav cards ────────────────────────────────────────────────────
        cards_area = tk.Frame(self, bg="#F6F7FB")
        cards_area.pack(fill="both", expand=True, padx=40, pady=32)

        row_frame = None
        nav_labels = {"Vente":"البيع","Stock":"المخزون","Journal":"السجل","Gestion":"الإدارة","Paramètres":"الإعدادات","Statistiques":"الإحصائيات"}
        for i, (emoji, label, key, bg, fg) in enumerate(NAV_CARDS):
            label = self.tr(label, nav_labels.get(label, label))
            if i % 3 == 0:
                row_frame = tk.Frame(cards_area, bg="#F6F7FB")
                row_frame.pack(anchor="center", pady=8)

            card = tk.Frame(row_frame, bg=bg, width=220, height=150,
                            cursor="hand2", bd=0, relief="flat")
            card.pack(side="left", padx=10)
            card.pack_propagate(False)

            inner = tk.Frame(card, bg=bg)
            inner.place(relx=0.5, rely=0.5, anchor="center")

            tk.Label(inner, text=emoji, bg=bg, fg=fg,
                     font=("Segoe UI", 38)).pack()
            tk.Label(inner, text=label, bg=bg, fg=fg,
                     font=("Segoe UI", 13, "bold")).pack(pady=(6, 0))

            # hover effect
            def _enter(e, f=card, c=bg):
                import colorsys, struct
                r2,g2,b2=int(c[1:3],16)/255,int(c[3:5],16)/255,int(c[5:7],16)/255
                h,s,v=colorsys.rgb_to_hsv(r2,g2,b2)
                nr,ng,nb=colorsys.hsv_to_rgb(h,s,min(v+0.12,1))
                hover='#%02x%02x%02x'%(int(nr*255),int(ng*255),int(nb*255))
                for w in f.winfo_children(): _recolor(w, hover)
                f.configure(bg=hover)
            def _leave(e, f=card, c=bg):
                for w in f.winfo_children(): _recolor(w, c)
                f.configure(bg=c)
            def _recolor(w, c):
                try: w.configure(bg=c)
                except Exception: pass
                for ch in w.winfo_children(): _recolor(ch, c)

            cmd = lambda k=key: self.app.show(k)
            for w in [card, inner] + inner.winfo_children():
                try:
                    w.bind("<Button-1>", lambda e, k=key: self.app.show(k))
                    w.bind("<Enter>", _enter)
                    w.bind("<Leave>", _leave)
                except Exception:
                    pass
            card.bind("<Button-1>", lambda e, k=key: self.app.show(k))
            inner.bind("<Button-1>", lambda e, k=key: self.app.show(k))

        # ── exit button ──────────────────────────────────────────────────
        ttk.Button(cards_area, text=self.tr("⏻  Quitter","⏻  خروج"),style="Danger.TButton",
                   command=self.app.on_close).pack(pady=(18, 0),ipadx=10)
