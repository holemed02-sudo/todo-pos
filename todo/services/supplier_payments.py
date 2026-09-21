"""services/supplier_payments.py — Règlements fournisseurs + état crédits."""
from database import connect
from services.security import require_admin, audit


def add_supplier_payment(supplier_id, amount_cents, note='', purchase_id=None):
    amount = int(amount_cents)
    if amount <= 0:
        raise ValueError('Montant invalide.')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT id FROM suppliers WHERE id=? AND active=1', (supplier_id,)).fetchone():
            raise ValueError('Fournisseur introuvable.')
        pid = conn.execute(
            'INSERT INTO supplier_payments(supplier_id,purchase_id,amount_cents,note) VALUES(?,?,?,?)',
            (supplier_id, purchase_id, amount, note.strip())).lastrowid
        audit(conn, 'SUPPLIER_PAYMENT', pid, str(amount))
        return pid


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
