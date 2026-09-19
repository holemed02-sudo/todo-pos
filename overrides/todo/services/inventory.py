from database import get_setting

def apply_stock_movement(conn, product_id, qty_delta, movement_type,
                         unit_cost_cents=0, ref_type="", ref_id=None, note=""):
    row = conn.execute(
        "SELECT name,stock_qty FROM products WHERE id=?",
        (product_id,)
    ).fetchone()
    if not row:
        raise ValueError("Article introuvable")
    new_stock = float(row["stock_qty"]) + float(qty_delta)
    allow_negative = get_setting("allow_negative_stock","0", conn=conn) == "1"
    if new_stock < -1e-9 and not allow_negative:
        raise ValueError(f"Stock insuffisant: {row['name']} (disponible {row['stock_qty']})")

    conn.execute("UPDATE products SET stock_qty=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                 (new_stock, product_id))
    conn.execute(
        """
        INSERT INTO stock_movements
        (product_id,movement_type,qty_delta,stock_after,unit_cost_cents,ref_type,ref_id,note)
        VALUES(?,?,?,?,?,?,?,?)
        """,
        (product_id,movement_type,qty_delta,new_stock,int(unit_cost_cents or 0),
         ref_type,ref_id,note)
    )
    return new_stock
