import math
from database import connect
from services.security import require_admin, audit
from services.inventory import apply_stock_movement

def receive_purchase(supplier_id, supplier_invoice, lines, notes="", paid_cents=0, payment_method="CARD"):
    if not lines:
        raise ValueError("Réception vide")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        require_admin(conn)
        normalized=[]
        for x in lines:
            pid=int(x["product_id"]);qty=float(x["qty"]);cost=int(x["unit_cost_cents"])
            if not math.isfinite(qty) or qty <= 0 or cost < 0:
                raise ValueError("Quantité réception invalide")
            product=conn.execute("SELECT allow_fraction FROM products WHERE id=? AND active=1",(pid,)).fetchone()
            if not product:
                raise ValueError("Article introuvable")
            if not product["allow_fraction"] and not qty.is_integer():
                raise ValueError("Quantité fractionnée interdite pour cet article")
            normalized.append((pid,qty,cost))
        total = sum(int(round(qty * cost)) for pid,qty,cost in normalized)
        paid_cents = int(paid_cents or 0)
        payment_method = str(payment_method).upper()
        if paid_cents < 0 or paid_cents > total:
            raise ValueError("Règlement fournisseur invalide")
        if payment_method not in ('CASH','CARD'):
            raise ValueError("Mode de paiement invalide")
        if supplier_id:
            supplier=conn.execute("SELECT 1 FROM suppliers WHERE id=? AND active=1",(supplier_id,)).fetchone()
            if not supplier:
                raise ValueError("Fournisseur introuvable")
        if paid_cents and not supplier_id:
            raise ValueError("Fournisseur obligatoire pour enregistrer un règlement")
        invoice = (supplier_invoice or "").strip()
        if supplier_id and invoice:
            duplicate = conn.execute("SELECT id FROM purchases WHERE supplier_id=? AND lower(trim(supplier_invoice))=lower(?) LIMIT 1", (supplier_id, invoice)).fetchone()
            if duplicate:
                raise ValueError("Facture fournisseur déjà enregistrée.")
        cur = conn.execute(
            "INSERT INTO purchases(supplier_id,supplier_invoice,total_cents,notes) VALUES(?,?,?,?)",
            (supplier_id or None, invoice, total, notes or "")
        )
        pid_purchase = cur.lastrowid
        for pid,qty,cost in normalized:
            lt=int(round(qty*cost))
            conn.execute(
                "INSERT INTO purchase_items(purchase_id,product_id,qty,unit_cost_cents,line_total_cents) VALUES(?,?,?,?,?)",
                (pid_purchase,pid,qty,cost,lt)
            )
            conn.execute("UPDATE products SET purchase_price_cents=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",(cost,pid))
            apply_stock_movement(conn,pid,qty,"PURCHASE",cost,"purchase",pid_purchase,invoice)
        if paid_cents:
            session_id = user_id = None
            if payment_method == 'CASH':
                from services.cash import get_open_session
                from services.security import current_user
                session = get_open_session()
                user_id = current_user.get()
                if not session:
                    raise ValueError("Ouvrez la caisse avant un règlement fournisseur en espèces.")
                if user_id is None or int(session['user_id']) != int(user_id):
                    raise PermissionError("Cette caisse appartient à un autre utilisateur.")
                session_id = int(session['id'])
            payment_id=conn.execute(
                "INSERT INTO supplier_payments(supplier_id,purchase_id,amount_cents,note,payment_method,session_id,user_id) VALUES(?,?,?,?,?,?,?)",
                (supplier_id,pid_purchase,paid_cents,"Règlement à la réception",payment_method,session_id,user_id)
            ).lastrowid
            audit(conn,"SUPPLIER_PAYMENT",payment_id,str(paid_cents))
        audit(conn,"PURCHASE_RECEIVE",pid_purchase,str(total))
        conn.commit()
        return pid_purchase, total
