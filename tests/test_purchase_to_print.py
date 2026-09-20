import database
from services import bootstrap, cash, purchases, sales, receipts
from services.security import current_user


def test_purchase_to_sale_and_receipt(tmp_path):
    database.DB_PATH = tmp_path / "workflow.db"
    database.init_db()
    bootstrap.ensure_defaults()

    with database.connect() as conn:
        user = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
        product = conn.execute("SELECT id,sale_price_cents,purchase_price_cents FROM products ORDER BY id LIMIT 1").fetchone()
    current_user.set(user)

    session_id = cash.open_session(user, 10000)
    purchase_id, purchase_total = purchases.receive_purchase(
        None, "TEST-001",
        [{"product_id": product["id"], "qty": 5, "unit_cost_cents": 200}],
    )
    assert purchase_id > 0
    assert purchase_total == 1000

    with database.connect() as conn:
        stock_after_purchase = conn.execute(
            "SELECT stock_qty FROM products WHERE id=?", (product["id"],)
        ).fetchone()["stock_qty"]
    assert stock_after_purchase >= 5

    cart = [{
        "product_id": product["id"],
        "qty": 2,
        "unit_price_cents": 300,
        "discount_cents": 0,
    }]
    result = sales.complete_sale(
        session_id, user, cart, "CASH", paid_cents=1000, discount_cents=100
    )
    assert result["total_cents"] == 500
    assert result["change_cents"] == 500

    with database.connect() as conn:
        row = conn.execute(
            "SELECT stock_qty FROM products WHERE id=?", (product["id"],)
        ).fetchone()
    assert row["stock_qty"] == stock_after_purchase - 2

    receipt = receipts.build_receipt(result["id"])
    assert "TOTAL:" in receipt
    assert "Remise ticket:" in receipt
    assert "TEST" not in receipt
