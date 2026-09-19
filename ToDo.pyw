from pathlib import Path
import os, sys, traceback

ROOT = Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
APP_DIR = Path(getattr(sys,'_MEIPASS',ROOT)) / "todo"
os.chdir(APP_DIR)
sys.path.insert(0, str(APP_DIR))

try:
    from app import ToDoApp
    app = ToDoApp()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()
except Exception:
    log = ROOT / "launch_error.txt"
    log.write_text(traceback.format_exc(), encoding="utf-8")
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        messagebox.showerror(
            "ToDo",
            "Erreur de démarrage.\n\nLe détail est enregistré dans:\n" + str(log),
        )
        r.destroy()
    except Exception:
        pass
