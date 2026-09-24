"""screens/rendez_vous.py — Rendez-vous / المواعيد."""
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
from database import connect, get_setting


def _init_table():
    with connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS rendez_vous (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL,
                rdv_date   TEXT NOT NULL,
                rdv_time   TEXT NOT NULL DEFAULT '',
                contact    TEXT NOT NULL DEFAULT '',
                notes      TEXT NOT NULL DEFAULT '',
                done       INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


class RendezVousFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=16)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        _init_table()
        ttk.Label(self, text=self.tr('Rendez-vous','المواعيد'),
                  font=('Segoe UI', 20, 'bold')).pack(anchor='w')

        toolbar = ttk.Frame(self); toolbar.pack(fill='x', pady=10)
        self.query = tk.StringVar()
        entry = ttk.Entry(toolbar, textvariable=self.query, width=28)
        entry.pack(side='left')
        entry.bind('<KeyRelease>', lambda e: self.refresh())
        self.show_done = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text=self.tr('Afficher terminés','إظهار المنتهية'),
                        variable=self.show_done,
                        command=self.refresh).pack(side='left', padx=8)
        ttk.Button(toolbar, text=self.tr('+ Nouveau','+ جديد'),
                   style='Primary.TButton',
                   command=self.new_rdv).pack(side='right')
        ttk.Button(toolbar, text=self.tr('Marquer fait','تحديد كمنجز'),
                   command=self.mark_done).pack(side='right', padx=6)
        ttk.Button(toolbar, text=self.tr('Supprimer','حذف'),
                   command=self.delete_rdv).pack(side='right')

        cols = ('date', 'time', 'title', 'contact', 'notes', 'done')
        self.tree = ttk.Treeview(self, columns=cols, show='headings')
        for col, lbl, w, anc in [
            ('date',    'Date',      110, 'w'),
            ('time',    'Heure',      75, 'w'),
            ('title',   'Objet',     250, 'w'),
            ('contact', 'Contact',   160, 'w'),
            ('notes',   'Notes',     280, 'w'),
            ('done',    'Statut',     80, 'center'),
        ]:
            self.tree.heading(col, text=lbl)
            self.tree.column(col, width=w, anchor=anc)
        self.tree.tag_configure('done',    foreground='#94A3B8')
        self.tree.tag_configure('today',   foreground='#16A34A',
                                font=('Segoe UI', 9, 'bold'))
        self.tree.tag_configure('overdue', foreground='#DC2626')
        sb = ttk.Scrollbar(self, orient='vertical', command=self.tree.yview)
        sb.pack(side='right', fill='y')
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(fill='both', expand=True)
        self.tree.bind('<Double-1>', lambda e: self.edit_rdv())
        self.refresh()

    def refresh(self):
        today = datetime.date.today().isoformat()
        q = self.query.get().strip()
        with connect() as conn:
            if self.show_done.get():
                rows = conn.execute(
                    "SELECT * FROM rendez_vous "
                    "WHERE instr(lower(title),lower(?))>0 OR instr(lower(contact),lower(?))>0 "
                    "ORDER BY rdv_date, rdv_time", (q, q)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM rendez_vous WHERE done=0 "
                    "AND (instr(lower(title),lower(?))>0 OR instr(lower(contact),lower(?))>0) "
                    "ORDER BY rdv_date, rdv_time", (q, q)).fetchall()
        self.rows = {str(r['id']): dict(r) for r in rows}
        self.tree.delete(*self.tree.get_children())
        for key, r in self.rows.items():
            if r['done']:
                tag = 'done'
            elif r['rdv_date'] < today:
                tag = 'overdue'
            elif r['rdv_date'] == today:
                tag = 'today'
            else:
                tag = ''
            status = self.tr('Fait','منجز') if r['done'] else (self.tr('Passé','فات') if r['rdv_date'] < today else self.tr('À venir','قادم'))
            self.tree.insert('', 'end', iid=key,
                values=(r['rdv_date'], r['rdv_time'], r['title'],
                        r['contact'], r['notes'], status),
                tags=(tag,))

    def _selected(self):
        sel = self.tree.selection()
        return self.rows.get(sel[0]) if sel else None

    def new_rdv(self):   RdvEditor(self)
    def edit_rdv(self):
        r = self._selected()
        if r: RdvEditor(self, r)

    def mark_done(self):
        r = self._selected()
        if not r: return
        with connect() as conn:
            conn.execute('UPDATE rendez_vous SET done=1 WHERE id=?', (r['id'],))
        self.refresh()

    def delete_rdv(self):
        r = self._selected()
        if not r: return
        msg = self.tr('Supprimer ce rendez-vous ?','حذف هذا الموعد؟')
        if messagebox.askyesno(self.tr('Supprimer','حذف'), msg, parent=self):
            with connect() as conn:
                conn.execute('DELETE FROM rendez_vous WHERE id=?', (r['id'],))
            self.refresh()


class RdvEditor(tk.Toplevel):
    def __init__(self, master_frame, rdv=None):
        super().__init__(master_frame)
        self.lang=get_setting('language','fr');self.tr=lambda fr,ar: ar if self.lang=='ar' else fr
        self.master_frame = master_frame
        self.rdv_id = rdv['id'] if rdv else None
        self.title(self.tr('Rendez-vous','المواعيد'))
        self.resizable(False, False)
        self.transient(master_frame.winfo_toplevel())
        self.grab_set()

        f = ttk.Frame(self, padding=20); f.pack(fill='both', expand=True)
        fields = [
            (self.tr('Objet *','الموضوع *'),  'title',   rdv['title']    if rdv else ''),
            (self.tr('Date *','التاريخ *'),   'date',    rdv['rdv_date']  if rdv else
             datetime.date.today().isoformat()),
            (self.tr('Heure','الوقت'),    'time',    rdv['rdv_time']  if rdv else '09:00'),
            (self.tr('Contact','الاتصال'),  'contact', rdv['contact']   if rdv else ''),
            (self.tr('Notes','ملاحظات'),    'notes',   rdv['notes']     if rdv else ''),
        ]
        self.vars = {}
        for row, (label, key, val) in enumerate(fields):
            ttk.Label(f, text=label).grid(row=row, column=0, sticky='w', pady=6)
            var = tk.StringVar(value=val)
            ttk.Entry(f, textvariable=var, width=36).grid(
                row=row, column=1, sticky='ew', padx=12)
            self.vars[key] = var

        ttk.Button(f, text=self.tr('Enregistrer','حفظ'), style='Primary.TButton',
                   command=self.save).grid(
                       row=len(fields), column=0, columnspan=2,
                       sticky='ew', pady=14)

    def save(self):
        title   = self.vars['title'].get().strip()
        date    = self.vars['date'].get().strip()
        time_v  = self.vars['time'].get().strip()
        contact = self.vars['contact'].get().strip()
        notes   = self.vars['notes'].get().strip()
        if not title or not date:
            messagebox.showerror(self.tr('Rendez-vous','المواعيد'),
                                 self.tr('Objet et date obligatoires.','الموضوع والتاريخ إجباريان.'), parent=self)
            return
        with connect() as conn:
            if self.rdv_id:
                conn.execute(
                    'UPDATE rendez_vous SET title=?,rdv_date=?,rdv_time=?,'
                    'contact=?,notes=? WHERE id=?',
                    (title, date, time_v, contact, notes, self.rdv_id))
            else:
                conn.execute(
                    'INSERT INTO rendez_vous(title,rdv_date,rdv_time,contact,notes)'
                    ' VALUES(?,?,?,?,?)',
                    (title, date, time_v, contact, notes))
        self.destroy()
        self.master_frame.refresh()
