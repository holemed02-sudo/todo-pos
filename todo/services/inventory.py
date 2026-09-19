import math
from database import get_setting
from services.security import current_user, require_admin, audit

def apply_stock_movement(conn, product_id, qty_delta, movement_type,
                         unit_cost_cents=0, ref_type='', ref_id=None, note='', user_id=None):
    if movement_type in ('ADJUSTMENT','OPENING','INVENTORY'):
        require_admin(conn)
        if not note.strip():
            raise ValueError('La raison est obligatoire.')
    row=conn.execute('SELECT name,stock_qty FROM products WHERE id=?',(product_id,)).fetchone()
    if not row:
        raise ValueError('Article introuvable')
    delta=float(qty_delta)
    if not math.isfinite(delta):
        raise ValueError('Quantité invalide')
    old=float(row['stock_qty']);new=old+delta
    if not math.isfinite(new):
        raise ValueError('Quantité invalide')
    if delta < 0 and new < -1e-9 and get_setting('allow_negative_stock','1',conn)!='1':
        raise ValueError(f"Stock insuffisant: {row['name']} (disponible {old:g})")
    uid=user_id or current_user.get()
    conn.execute('UPDATE products SET stock_qty=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(new,product_id))
    conn.execute('INSERT INTO stock_movements(product_id,movement_type,qty_delta,old_qty,stock_after,unit_cost_cents,ref_type,ref_id,note,user_id) VALUES(?,?,?,?,?,?,?,?,?,?)',
                 (product_id,movement_type,delta,old,new,int(unit_cost_cents or 0),ref_type,ref_id,note,uid))
    audit(conn,'STOCK_'+movement_type,ref_id or product_id,note,uid)
    return new
