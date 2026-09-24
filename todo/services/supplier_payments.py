"""services/supplier_payments.py — Règlements fournisseurs + état crédits."""
from database import connect
from services.security import audit


def add_supplier_payment(supplier_id, amount_cents, note='', purchase_id=None):
    """Record a supplier payment and keep invoice balances coherent.

    If purchase_id is omitted, the amount is allocated to the supplier's
    oldest open purchases. A payment cannot exceed the supplier outstanding
    balance.
    """
    amount = int(amount_cents)
    if amount <= 0:
        raise ValueError('Montant invalide.')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT id FROM suppliers WHERE id=? AND active=1', (supplier_id,)).fetchone():
            raise ValueError('Fournisseur introuvable.')

        if purchase_id is not None:
            purchase = conn.execute(
                """SELECT p.id,p.total_cents,
                          COALESCE((SELECT SUM(amount_cents) FROM supplier_payments
                                    WHERE purchase_id=p.id),0) paid
                   FROM purchases p WHERE p.id=? AND p.supplier_id=?""",
                (purchase_id, supplier_id)).fetchone()
            if not purchase:
                raise ValueError("Facture fournisseur invalide.")
            remaining = int(purchase['total_cents']) - int(purchase['paid'])
            if amount > remaining:
                raise ValueError("Le règlement dépasse le reste de la facture.")
            allocations = [(int(purchase_id), amount)]
        else:
            rows = conn.execute(
                """SELECT p.id,p.total_cents,
                          COALESCE((SELECT SUM(amount_cents) FROM supplier_payments
                                    WHERE purchase_id=p.id),0) paid
                   FROM purchases p
                   WHERE p.supplier_id=?
                   ORDER BY p.created_at,p.id""", (supplier_id,)).fetchall()
            outstanding = [(int(r['id']), int(r['total_cents']) - int(r['paid']))
                           for r in rows if int(r['total_cents']) > int(r['paid'])]
            if amount > sum(rest for _, rest in outstanding):
                raise ValueError("Le règlement dépasse le solde dû au fournisseur.")
            left = amount
            allocations = []
            for pid, rest in outstanding:
                if left <= 0:
                    break
                part = min(left, rest)
                allocations.append((pid, part))
                left -= part
            if left or not allocations:
                raise ValueError("Aucune facture impayée à régler.")

        payment_ids = []
        for pid, part in allocations:
            payment_id = conn.execute(
                'INSERT INTO supplier_payments(supplier_id,purchase_id,amount_cents,note) VALUES(?,?,?,?)',
                (supplier_id, pid, part, note.strip())).lastrowid
            audit(conn, 'SUPPLIER_PAYMENT', payment_id, str(part))
            payment_ids.append(payment_id)
        return payment_ids[0] if len(payment_ids) == 1 else payment_ids


def list_supplier_payments(supplier_id):
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT sp.*, p.supplier_invoice FROM supplier_payments sp
               LEFT JOIN purchases p ON p.id=sp.purchase_id
               WHERE sp.supplier_id=? ORDER BY sp.id DESC""",
            (supplier_id,))]


def supplier_credit_statement():
    """All suppliers with outstanding balance (we owe them)."""
    with connect() as conn:
        return [dict(r) for r in conn.execute("""
            SELECT s.id, s.name, s.phone,
                   COALESCE(b.billed, 0)  billed_cents,
                   COALESCE(p.paid,   0)  paid_cents,
                   COALESCE(b.billed, 0) - COALESCE(p.paid, 0) balance_cents
            FROM suppliers s
            LEFT JOIN (SELECT supplier_id, SUM(total_cents) billed
                       FROM purchases GROUP BY supplier_id) b ON b.supplier_id=s.id
            LEFT JOIN (SELECT supplier_id, SUM(amount_cents) paid
                       FROM supplier_payments GROUP BY supplier_id) p ON p.supplier_id=s.id
            WHERE s.active=1
              AND (COALESCE(b.billed,0) - COALESCE(p.paid,0)) > 0
            ORDER BY balance_cents DESC
        """)]


def supplier_purchases(supplier_id):
    with connect() as conn:
        return [dict(r) for r in conn.execute(
            """SELECT pu.id, pu.supplier_invoice, pu.total_cents, pu.created_at,
                      COALESCE((SELECT SUM(sp.amount_cents) FROM supplier_payments sp
                                WHERE sp.purchase_id=pu.id), 0) paid
               FROM purchases pu WHERE pu.supplier_id=? ORDER BY pu.id DESC""",
            (supplier_id,))]
