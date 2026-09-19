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
