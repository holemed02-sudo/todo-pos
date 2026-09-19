"""Copy an existing ToDo installation into a fresh release without changing it."""
from pathlib import Path
import sqlite3
import shutil
import sys
from contextlib import closing
import tkinter as tk
from tkinter import filedialog,messagebox

ROOT=Path(sys.executable).resolve().parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
sys.path.insert(0,str(Path(getattr(sys,'_MEIPASS',ROOT))/'todo'))
from services.backup import validate


def main():
    app=tk.Tk();app.withdraw()
    try:
        destination=ROOT/'todo'/'data'/'todo.db'
        if destination.exists():
            messagebox.showinfo('ToDo','Cette version contient déjà une base. Utilisez une copie neuve du dossier 1.1.0 pour importer.');return
        folder=filedialog.askdirectory(title='Choisissez le dossier de l’ancienne version contenant ToDo.pyw')
        if not folder:return
        source=Path(folder)/'todo'/'data'/'todo.db'
        if not source.is_file():
            raise ValueError('Base introuvable : choisissez le dossier qui contient ToDo.pyw.')
        if not messagebox.askyesno('Importer','Fermez l’ancien et le nouveau ToDo avant de continuer.\nLes données et images seront copiées; l’original reste intact.\nContinuer ?'):return
        destination.parent.mkdir(parents=True,exist_ok=True)
        staging=destination.with_suffix('.importing')
        with closing(sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)) as old:
            validate(old)
            with closing(sqlite3.connect(staging)) as new:
                old.backup(new);validate(new)
        images=Path(folder)/'todo'/'assets'
        if images.is_dir():shutil.copytree(images,ROOT/'todo'/'assets',dirs_exist_ok=True)
        staging.replace(destination)
        messagebox.showinfo('ToDo','Import terminé. Lancez START_TODO.vbs.\nVos comptes et PIN existants sont conservés.')
    except Exception as error:
        messagebox.showerror('ToDo',str(error))
    finally:
        app.destroy()


if __name__=='__main__':main()
