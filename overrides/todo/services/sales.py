import json
from datetime import datetime
from database import connect
from services.inventory import apply_stock_movement
from services.pricing import resolve_line_price


def sale_number():
    return "V-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]


def return_number():
    return "R-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f")[:-3]


def complete_sale(session_id, user_id, cart, payment_method, paid_cents, discount_cents=0):
    if not cart:
        raise ValueError("Ticket vide")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        session = conn.execute(
            "SELECT id FROM cash_sessions WHERE id=? AND status='OPEN'", (session_id,)
        ).fetchone()
        if not session:
            raise ValueError("خاص تفتح الكيس قبل البيع.")

        subtotal = 0
        normalized = []
        for line in cart:
            pid = int(line["product_id"])
            qty = float(line["qty"])
            if qty <= 0:
                raise ValueError("Quantité invalide")
            p = conn.execute(
                "SELECT name,purchase_price_cents,stock_qty FROM products WHERE id=? AND active=1",
                (pid,),
            ).fetchone()
            if not p:
                raise ValueError("Article introuvable")
            if float(p["stock_qty"]) + 1e-9 < qty:
                raise ValueError(f"Stock insuffisant: {p['name']}")

            pricing = resolve_line_price(pid, qty, line.get("barcode_id"), conn=conn)
            line_total = int(pricing["line_total_cents"])
            subtotal += line_total
            normalized.append((pid, qty, pricing, line_total, p))

        discount_cents = max(0, int(discount_cents))
        total_cents = max(0, subtotal - discount_cents)
        paid_cents = int(paid_cents)
        if payment_method == "CASH" and paid_cents < total_cents:
            raise ValueError("المبلغ المؤدى ناقص.")
        if payment_method != "CASH":
            paid_cents = total_cents
        change = max(0, paid_cents - total_cents) if payment_method == "CASH" else 0

        no = sale_number()
        cur = conn.execute(
            """
            INSERT INTO sales(sale_no,session_id,cashier_user_id,subtotal_cents,discount_cents,total_cents,
                              payment_method,paid_cents,change_cents)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (no, session_id, user_id, subtotal, discount_cents, total_cents, payment_method, paid_cents, change),
        )
        sid = cur.lastrowid

        for pid, qty, pricing, line_total, p in normalized:
            conn.execute(
                """
                INSERT INTO sale_items
                (sale_id,product_id,barcode_used,name_snapshot,qty,unit_price_cents,cost_price_cents,
                 line_total_cents,qty_multiplier,pricing_mode)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    pid,
                    pricing["barcode"],
                    p["name"],
                    qty,
                    pricing["unit_price_cents"],
                    int(p["purchase_price_cents"]),
                    line_total,
                    pricing["qty_multiplier"],
                    pricing["pricing_mode"],
                ),
            )
            apply_stock_movement(conn, pid, -qty, "SALE", p["purchase_price_cents"], "sale", sid, no)

        conn.commit()
        return dict(
            id=sid,
            sale_no=no,
            subtotal_cents=subtotal,
            discount_cents=discount_cents,
            total_cents=total_cents,
            paid_cents=paid_cents,
            change_cents=change,
        )


def hold_sale(user_id, cart, label=""):
    with connect() as conn:
        cur = conn.execute(
            "INSERT INTO held_sales(label,cashier_user_id,payload_json) VALUES(?,?,?)",
            (label or "Ticket en attente", user_id, json.dumps(cart, ensure_ascii=False)),
        )
        conn.commit()
        return cur.lastrowid


def list_held():
    with connect() as conn:
        return conn.execute("SELECT * FROM held_sales ORDER BY id DESC").fetchall()


def resume_held(held_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM held_sales WHERE id=?", (held_id,)).fetchone()
        if not row:
            raise ValueError("Ticket introuvable")
        payload = json.loads(row["payload_json"])
        conn.execute("DELETE FROM held_sales WHERE id=?", (held_id,))
        conn.commit()
        return payload


def create_return(sale_id, session_id, user_id, items, reason="", refund_method="CASH"):
    if not items:
        raise ValueError("Aucun article à retourner")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        sale = conn.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
        if not sale:
            raise ValueError("Vente introuvable")
        total = 0
        validated = []
        for sale_item_id, qty in items:
            si = conn.execute(
                "SELECT * FROM sale_items WHERE id=? AND sale_id=?", (sale_item_id, sale_id)
            ).fetchone()
            if not si:
                raise ValueError("Ligne de vente introuvable")
            already = conn.execute(
                """
                SELECT COALESCE(SUM(ri.qty),0) q
                FROM return_items ri JOIN returns r ON r.id=ri.return_id
                WHERE ri.sale_item_id=?
                """,
                (sale_item_id,),
            ).fetchone()["q"]
            max_qty = float(si["qty"]) - float(already)
            qty = float(qty)
            if qty <= 0 or qty > max_qty + 1e-9:
                raise ValueError("Quantité retour invalide")

            if si["pricing_mode"] == "PACK":
                mult = float(si["qty_multiplier"] or 1)
                packs = qty / mult
                if abs(packs - round(packs)) > 1e-9:
                    raise ValueError("Le retour d'un pack/carton doit respecter sa quantité")
                lt = int(si["unit_price_cents"]) * int(round(packs))
            else:
                lt = int(round(int(si["unit_price_cents"]) * qty))
            total += lt
            validated.append((si, qty, lt))

        no = return_number()
        cur = conn.execute(
            "INSERT INTO returns(return_no,sale_id,session_id,cashier_user_id,total_cents,refund_method,reason) VALUES(?,?,?,?,?,?,?)",
            (no, sale_id, session_id, user_id, total, refund_method, reason),
        )
        rid = cur.lastrowid
        for si, qty, lt in validated:
            conn.execute(
                "INSERT INTO return_items(return_id,sale_item_id,product_id,qty,unit_price_cents,line_total_cents) VALUES(?,?,?,?,?,?)",
                (rid, si["id"], si["product_id"], qty, si["unit_price_cents"], lt),
            )
            apply_stock_movement(conn, si["product_id"], qty, "RETURN", si["cost_price_cents"], "return", rid, no)
        conn.commit()
        return dict(id=rid, return_no=no, total_cents=total)
