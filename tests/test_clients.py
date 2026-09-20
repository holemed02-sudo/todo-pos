"""Regression tests — clients, règlements, état des crédits."""
import os, sys, types, pytest
os.environ.setdefault("TODO_DB_PATH", ":memory:")
sys.modules.setdefault("win32print", types.ModuleType("win32print"))
from database import init_db
from services.clients import (
    save_client, list_clients, get_client, add_payment,
    list_payments, client_sales, credit_statement,
)


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    db = str(tmp_path / "test.db")
    monkeypatch.setenv("TODO_DB_PATH", db)
    import importlib, database
    importlib.reload(database)
    init_db()
    yield


def test_create_and_list():
    cid = save_client("Ahmed", "0601020304")
    rows = list_clients()
    assert any(r["id"] == cid for r in rows)


def test_update_client():
    cid = save_client("Khalid")
    save_client("Khalid Benali", "0611223344", client_id=cid)
    c = get_client(cid)
    assert c["name"] == "Khalid Benali"
    assert c["phone"] == "0611223344"


def test_payment_reduces_balance():
    from database import connect
    # need a session + sale to bill the client
    with connect() as conn:
        conn.execute("INSERT INTO users(username,display_name,pin_hash) VALUES('a','A','x')")
        conn.execute("INSERT INTO cash_sessions(user_id,opening_cash_cents,expected_cash_cents) VALUES(1,0,0)")
        uid = conn.execute("SELECT id FROM users WHERE username='a'").fetchone()["id"]
        cid = save_client("Fatima")
        conn.execute("INSERT INTO sales(sale_no,session_id,cashier_user_id,subtotal_cents,total_cents,payment_method,paid_cents,client_id) VALUES('V-001',1,?,1000,1000,'CASH',1000,?)", (uid, cid))
    c = get_client(cid)
    assert c["billed_cents"] == 1000
    add_payment(cid, 600, "acompte")
    c2 = get_client(cid)
    assert c2["paid_cents"] == 600


def test_credit_statement_shows_debtors():
    from database import connect
    with connect() as conn:
        conn.execute("INSERT INTO users(username,display_name,pin_hash) VALUES('b','B','x')")
        conn.execute("INSERT INTO cash_sessions(user_id,opening_cash_cents,expected_cash_cents) VALUES(1,0,0)")
        uid = conn.execute("SELECT id FROM users WHERE username='b'").fetchone()["id"]
        cid = save_client("Debtor")
        conn.execute("INSERT INTO sales(sale_no,session_id,cashier_user_id,subtotal_cents,total_cents,payment_method,paid_cents,client_id) VALUES('V-002',1,?,2000,2000,'CASH',2000,?)", (uid, cid))
    statement = credit_statement()
    assert any(r["id"] == cid for r in statement)


def test_fully_paid_not_in_statement():
    from database import connect
    with connect() as conn:
        conn.execute("INSERT INTO users(username,display_name,pin_hash) VALUES('c','C','x')")
        conn.execute("INSERT INTO cash_sessions(user_id,opening_cash_cents,expected_cash_cents) VALUES(1,0,0)")
        uid = conn.execute("SELECT id FROM users WHERE username='c'").fetchone()["id"]
        cid = save_client("Paid Client")
        conn.execute("INSERT INTO sales(sale_no,session_id,cashier_user_id,subtotal_cents,total_cents,payment_method,paid_cents,client_id) VALUES('V-003',1,?,500,500,'CASH',500,?)", (uid, cid))
    add_payment(cid, 500, "solde")
    assert all(r["id"] != cid for r in credit_statement())
