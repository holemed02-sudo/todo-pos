from pathlib import Path
from datetime import datetime
import sqlite3
from contextlib import closing
from database import DB_PATH, BASE_DIR, connect, init_db, SCHEMA

BASE=BASE_DIR
REQUIRED={'settings','users','products','sales','sale_items','stock_movements','cash_sessions'}

def validate(conn):
    if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
        raise ValueError('Sauvegarde corrompue')
    if conn.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('Relations invalides dans la sauvegarde')
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not REQUIRED.issubset(tables):
        raise ValueError('Ce fichier ne contient pas une base ToDo complète.')
    with closing(sqlite3.connect(':memory:')) as expected:
        expected.executescript(SCHEMA)
        for (table,) in expected.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            if table in ('clients','client_payments','product_categories') and table not in tables:
                continue
            needed={r[1] for r in expected.execute(f'PRAGMA table_info({table})')}
            actual={r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
            if not needed.issubset(actual):
                raise ValueError(f'Structure ToDo incompatible : {table}')
    if conn.execute('PRAGMA user_version').fetchone()[0]>122:
        raise ValueError('Sauvegarde issue d’une version plus récente de ToDo.')

def create_backup():
    folder=BASE/'backups';folder.mkdir(parents=True,exist_ok=True)
    dst=folder/f"todo_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    with connect() as source, closing(sqlite3.connect(dst)) as target:
        source.backup(target)
        validate(target)
    return dst

def restore_backup(source):
    src=Path(source).resolve()
    if not src.is_file() or src==DB_PATH.resolve():
        raise ValueError('Choisissez une sauvegarde distincte.')
    with closing(sqlite3.connect(src.as_uri()+'?mode=ro',uri=True)) as origin:
        validate(origin)
        safety=create_backup()
        with connect() as target:
            origin.backup(target)
    init_db()
    return safety
