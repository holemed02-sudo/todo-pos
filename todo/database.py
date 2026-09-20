from pathlib import Path
import os, sqlite3, sys

BASE_DIR = Path(sys.executable).resolve().parent / 'todo' if getattr(sys,'frozen',False) else Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "data" / "todo.db"
DB_PATH = Path(os.environ.get("TODO_DB_PATH", str(DEFAULT_DB)))

SCHEMA = r"""
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    pin_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'cashier',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS suppliers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku TEXT NOT NULL DEFAULT '',
    name TEXT NOT NULL,
    category_id INTEGER,
    purchase_price_cents INTEGER NOT NULL DEFAULT 0,
    sale_price_cents INTEGER NOT NULL DEFAULT 0,
    stock_qty REAL NOT NULL DEFAULT 0,
    alert_qty REAL NOT NULL DEFAULT 0,
    image_path TEXT NOT NULL DEFAULT '',
    allow_fraction INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS product_barcodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    barcode TEXT NOT NULL,
    label TEXT NOT NULL DEFAULT '',
    qty_multiplier REAL NOT NULL DEFAULT 1,
    price_override_cents INTEGER,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_barcodes_barcode ON product_barcodes(barcode);

CREATE TABLE IF NOT EXISTS quantity_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    min_qty REAL NOT NULL,
    unit_price_cents INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_quantity_prices_product ON quantity_prices(product_id, min_qty);

CREATE TABLE IF NOT EXISTS cash_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    opening_cash_cents INTEGER NOT NULL DEFAULT 0,
    expected_cash_cents INTEGER NOT NULL DEFAULT 0,
    actual_cash_cents INTEGER,
    difference_cents INTEGER,
    status TEXT NOT NULL DEFAULT 'OPEN',
    FOREIGN KEY(user_id) REFERENCES users(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_open_session
ON cash_sessions(status) WHERE status='OPEN';

CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_no TEXT NOT NULL UNIQUE,
    session_id INTEGER NOT NULL,
    cashier_user_id INTEGER NOT NULL,
    subtotal_cents INTEGER NOT NULL,
    discount_cents INTEGER NOT NULL DEFAULT 0,
    total_cents INTEGER NOT NULL,
    payment_method TEXT NOT NULL DEFAULT 'CASH',
    paid_cents INTEGER NOT NULL,
    change_cents INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'COMPLETED',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES cash_sessions(id),
    FOREIGN KEY(cashier_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS sale_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sale_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    barcode_used TEXT NOT NULL DEFAULT '',
    name_snapshot TEXT NOT NULL,
    qty REAL NOT NULL,
    unit_price_cents INTEGER NOT NULL,
    cost_price_cents INTEGER NOT NULL DEFAULT 0,
    discount_cents INTEGER NOT NULL DEFAULT 0,
    line_total_cents INTEGER NOT NULL,
    FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS held_sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL DEFAULT '',
    cashier_user_id INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(cashier_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    qty_delta REAL NOT NULL,
    stock_after REAL NOT NULL,
    unit_cost_cents INTEGER NOT NULL DEFAULT 0,
    ref_type TEXT NOT NULL DEFAULT '',
    ref_id INTEGER,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(product_id) REFERENCES products(id)
);
CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id, id);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    supplier_invoice TEXT NOT NULL DEFAULT '',
    total_cents INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(supplier_id) REFERENCES suppliers(id)
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty REAL NOT NULL,
    unit_cost_cents INTEGER NOT NULL,
    line_total_cents INTEGER NOT NULL,
    FOREIGN KEY(purchase_id) REFERENCES purchases(id) ON DELETE CASCADE,
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS returns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_no TEXT NOT NULL UNIQUE,
    sale_id INTEGER NOT NULL,
    session_id INTEGER NOT NULL,
    cashier_user_id INTEGER NOT NULL,
    total_cents INTEGER NOT NULL,
    refund_method TEXT NOT NULL DEFAULT 'CASH',
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(sale_id) REFERENCES sales(id),
    FOREIGN KEY(session_id) REFERENCES cash_sessions(id),
    FOREIGN KEY(cashier_user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS return_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    return_id INTEGER NOT NULL,
    sale_item_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    qty REAL NOT NULL,
    unit_price_cents INTEGER NOT NULL,
    line_total_cents INTEGER NOT NULL,
    FOREIGN KEY(return_id) REFERENCES returns(id) ON DELETE CASCADE,
    FOREIGN KEY(sale_item_id) REFERENCES sale_items(id),
    FOREIGN KEY(product_id) REFERENCES products(id)
);

CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    label TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES cash_sessions(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cash_movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    movement_type TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES cash_sessions(id),
    FOREIGN KEY(user_id) REFERENCES users(id)
);


CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS client_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER NOT NULL,
    sale_id INTEGER,
    amount_cents INTEGER NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(client_id) REFERENCES clients(id),
    FOREIGN KEY(sale_id)   REFERENCES sales(id)
);
CREATE INDEX IF NOT EXISTS idx_client_payments_client ON client_payments(client_id);


CREATE TABLE IF NOT EXISTS product_categories (
    product_id  INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    PRIMARY KEY(product_id, category_id),
    FOREIGN KEY(product_id)  REFERENCES products(id)  ON DELETE CASCADE,
    FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_product_categories_cat ON product_categories(category_id);

INSERT OR IGNORE INTO settings(key,value) VALUES
('shop_name','ToDo'),
('currency','DH'),
('allow_negative_stock','1'),
('receipt_footer','Merci pour votre visite'),
('backup_on_close','1');
"""

class Connection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15, factory=Connection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn

def init_db():
    with connect() as conn:
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='products'").fetchone() and conn.execute('PRAGMA user_version').fetchone()[0] < 110:
            from datetime import datetime
            backup_dir=DB_PATH.parent / 'migration_backups'
            backup_dir.mkdir(parents=True,exist_ok=True)
            destination=sqlite3.connect(backup_dir / f"before_110_{datetime.now():%Y%m%d_%H%M%S_%f}.db")
            try:
                conn.backup(destination)
            finally:
                destination.close()
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        migrate(conn)
        conn.commit()

def get_setting(key, default="", conn=None):
    if conn is None:
        with connect() as db:
            return get_setting(key, default, db)
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default

def set_setting(key, value):
    with connect() as conn:
        conn.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value))
        )
        conn.commit()


def migrate(conn):
    # Agreed shop policy: keep checkout available when stock counts lag behind.
    # Apply once to existing installations; subsequent explicit settings survive.
    if not conn.execute("SELECT 1 FROM settings WHERE key='negative_stock_policy_v1'").fetchone():
        conn.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('allow_negative_stock','1')")
        conn.execute("INSERT INTO settings(key,value) VALUES('negative_stock_policy_v1','1')")
    additions = {
        'quantity_prices': {'pricing_mode': "TEXT NOT NULL DEFAULT 'UNIT'"},
        'products': {'supplier_code': "TEXT NOT NULL DEFAULT ''", 'alias': "TEXT NOT NULL DEFAULT ''", 'is_misc': 'INTEGER NOT NULL DEFAULT 0'},
        'stock_movements': {'user_id': 'INTEGER REFERENCES users(id)', 'old_qty': 'REAL'},
        'sale_items': {'net_total_cents': 'INTEGER', 'qty_multiplier': 'REAL NOT NULL DEFAULT 1', 'pricing_mode': "TEXT NOT NULL DEFAULT 'UNIT'"},
        'held_sales': {'discount_cents': 'INTEGER NOT NULL DEFAULT 0'},
        'sales': {'client_id': 'INTEGER REFERENCES clients(id)'},
        'categories': {'color': "TEXT NOT NULL DEFAULT '#2563EB'", 'icon': "TEXT NOT NULL DEFAULT ''"},
    }
    for table, fields in additions.items():
        existing = {r['name'] for r in conn.execute(f'PRAGMA table_info({table})')}
        for name, declaration in fields.items():
            if name not in existing:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {declaration}')
    conn.execute('UPDATE stock_movements SET old_qty=stock_after-qty_delta WHERE old_qty IS NULL')
    conn.execute("CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY, user_id INTEGER, action TEXT NOT NULL, document TEXT NOT NULL, details TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    conn.execute('CREATE INDEX IF NOT EXISTS idx_products_active_name ON products(active,name)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_barcodes_product ON product_barcodes(product_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_returns_sale_item ON return_items(sale_item_id)')
    conn.execute("INSERT OR IGNORE INTO settings VALUES('search_limit','60')")
    # Allocate historical ticket discounts deterministically, without altering old receipts.
    from services.money import allocate
    for sale in conn.execute('SELECT * FROM sales WHERE id IN (SELECT sale_id FROM sale_items WHERE net_total_cents IS NULL)').fetchall():
        rows=conn.execute('SELECT id,line_total_cents FROM sale_items WHERE sale_id=? ORDER BY id',(sale['id'],)).fetchall()
        nets=allocate(sale['total_cents'], [r['line_total_cents'] for r in rows])
        conn.executemany('UPDATE sale_items SET net_total_cents=? WHERE id=?',[(n,r['id']) for r,n in zip(rows,nets)])
    try:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='product_search'").fetchone():
            conn.execute("CREATE VIRTUAL TABLE product_search USING fts5(name,sku,alias,supplier_code,content='products',content_rowid='id',tokenize='trigram')")
            conn.execute("INSERT INTO product_search(product_search) VALUES('rebuild')")
        conn.executescript("""
        CREATE TRIGGER IF NOT EXISTS products_search_insert AFTER INSERT ON products BEGIN
          INSERT INTO product_search(rowid,name,sku,alias,supplier_code) VALUES(new.id,new.name,new.sku,new.alias,new.supplier_code);
        END;
        CREATE TRIGGER IF NOT EXISTS products_search_delete AFTER DELETE ON products BEGIN
          INSERT INTO product_search(product_search,rowid,name,sku,alias,supplier_code) VALUES('delete',old.id,old.name,old.sku,old.alias,old.supplier_code);
        END;
        CREATE TRIGGER IF NOT EXISTS products_search_update AFTER UPDATE OF name,sku,alias,supplier_code ON products BEGIN
          INSERT INTO product_search(product_search,rowid,name,sku,alias,supplier_code) VALUES('delete',old.id,old.name,old.sku,old.alias,old.supplier_code);
          INSERT INTO product_search(rowid,name,sku,alias,supplier_code) VALUES(new.id,new.name,new.sku,new.alias,new.supplier_code);
        END;
        """)
    except sqlite3.OperationalError as error:
        if 'no such module' not in str(error) and 'no such tokenizer' not in str(error):
            raise
    # Back-fill product_categories from existing single category_id
    conn.execute('''
        INSERT OR IGNORE INTO product_categories(product_id,category_id)
        SELECT id,category_id FROM products WHERE category_id IS NOT NULL
    ''')
    conn.execute('PRAGMA user_version=110')
