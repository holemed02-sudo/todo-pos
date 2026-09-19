import math
from database import connect
from services.security import require_admin
from services.inventory import apply_stock_movement

def receive_purchase(supplier_id, supplier_invoice, lines, notes=""):
    if not lines:
        raise ValueError("Réception vide")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        require_admin(conn)
        total = sum(int(round(float(x["qty"]) * int(x["unit_cost_cents"]))) for x in lines)
        cur = conn.execute(
            "INSERT INTO purchases(supplier_id,supplier_invoice,total_cents,notes) VALUES(?,?,?,?)",
            (supplier_id or None, supplier_invoice or "", total, notes or "")
        )
        pid_purchase = cur.lastrowid
        for x in lines:
            pid = int(x["product_id"]); qty=float(x["qty"]); cost=int(x["unit_cost_cents"])
            if not math.isfinite(qty) or qty <= 0 or cost < 0:
                raise ValueError("Quantité réception invalide")
            lt=int(round(qty*cost))
            conn.execute(
                "INSERT INTO purchase_items(purchase_id,product_id,qty,unit_cost_cents,line_total_cents) VALUES(?,?,?,?,?)",
                (pid_purchase,pid,qty,cost,lt)
            )
            conn.execute("UPDATE products SET purchase_price_cents=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(cost,pid))
            apply_stock_movement(conn,pid,qty,"PURCHASE",cost,"purchase",pid_purchase,supplier_invoice or "")
        conn.commit()
        return pid_purchase, total
