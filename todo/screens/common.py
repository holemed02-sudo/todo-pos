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

def kpi_row(parent, items, container=None):
    """Row of colored summary boxes, like the reference screens' red/orange/
    blue/green/purple cards. items: list of (title, value, subtitle_or_None, color).
    Pass an existing `container` (from a previous call) to refresh it in place."""
    row = container if container is not None else ttk.Frame(parent)
    if container is not None:
        clear(row)
    else:
        row.pack(fill='x', pady=(0, 14))
    for i, (title, value, subtitle, color) in enumerate(items):
        card = tk.Frame(row, bg=color)
        card.grid(row=0, column=i, sticky='nsew', padx=4)
        row.columnconfigure(i, weight=1)
        tk.Label(card, text=value, bg=color, fg='white', font=('Segoe UI', 20, 'bold')).pack(anchor='w', padx=14, pady=(12, 0))
        tk.Label(card, text=title, bg=color, fg='white', font=('Segoe UI', 11, 'bold')).pack(anchor='w', padx=14, pady=(0, 4 if subtitle else 12))
        if subtitle:
            tk.Label(card, text=subtitle, bg=color, fg='white', font=('Segoe UI', 9)).pack(anchor='w', padx=14, pady=(0, 12))
    return row
