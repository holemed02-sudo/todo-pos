"""Regression tests — reports and statistics queries."""
import os, sys, types, pytest, datetime
os.environ.setdefault("TODO_DB_PATH", ":memory:")
sys.modules.setdefault("win32print", types.ModuleType("win32print"))
from database import init_db
from services.reports import (
    today_summary, sales_evolution, top_products,
    top_cashiers, category_breakdown,
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("TODO_DB_PATH", db)
    import importlib, database
    importlib.reload(database)
    init_db()
    yield


def _seed(conn):
    conn.execute("INSERT INTO users(username,display_name,pin_hash) VALUES('a','Admin','x')")
    conn.execute("INSERT INTO categories(name,color,icon) VALUES('Épicerie','#2563EB','🥫')")
    conn.execute("INSERT INTO products(name,category_id,sale_price_cents,purchase_price_cents,stock_qty) VALUES('Huile',1,1500,800,100)")
    conn.execute("INSERT INTO cash_sessions(user_id,opening_cash_cents,expected_cash_cents) VALUES(1,0,0)")
    conn.execute("INSERT INTO sales(sale_no,session_id,cashier_user_id,subtotal_cents,total_cents,payment_method,paid_cents) VALUES('V-001',1,1,3000,3000,'CASH',3000)")
    conn.execute("INSERT INTO sale_items(sale_id,product_id,name_snapshot,qty,unit_price_cents,cost_price_cents,line_total_cents) VALUES(1,1,'Huile',2,1500,800,3000)")
    conn.commit()


def test_today_summary_empty():
    s = today_summary()
    assert s['tickets'] == 0
    assert s['net_sales'] == 0


def test_today_summary_with_sale():
    from database import connect
    with connect() as conn:
        _seed(conn)
    s = today_summary()
    assert s['tickets'] == 1
    assert s['net_sales'] == 3000


def test_sales_evolution_week():
    from database import connect
    with connect() as conn:
        _seed(conn)
    labels, values = sales_evolution('week')
    assert len(labels) == 7
    assert sum(values) == 3000


def test_sales_evolution_month():
    labels, values = sales_evolution('month')
    today = datetime.date.today()
    assert len(values) == today.day


def test_top_products():
    from database import connect
    with connect() as conn:
        _seed(conn)
    rows = top_products(5, 'month')
    assert rows[0]['name'] == 'Huile'
    assert rows[0]['revenue'] == 3000


def test_top_cashiers():
    from database import connect
    with connect() as conn:
        _seed(conn)
    rows = top_cashiers('month')
    assert rows[0]['name'] == 'Admin'
    assert rows[0]['tickets'] == 1


def test_category_breakdown():
    from database import connect
    with connect() as conn:
        _seed(conn)
    rows = category_breakdown('month')
    assert rows[0]['name'] == 'Épicerie'
    assert rows[0]['revenue'] == 3000
