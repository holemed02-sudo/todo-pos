"""services/clients.py — Clients, règlements, état des crédits."""
from database import connect
from services.security import require_admin, audit
from services.money import to_cents


# ── CRUD clients ──────────────────────────────────────────────────────────────

def save_client(name, phone='', notes='', client_id=None):
    name, phone, notes = name.strip(), phone.strip(), notes.strip()
    if not name:
        raise ValueError('Le nom du client est obligatoire.')
    if len(name) > 150 or len(phone) > 60 or len(notes) > 2000:
        raise ValueError('Nom, téléphone ou notes trop longs.')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if client_id is None:
            client_id = conn.execute(
                'INSERT INTO clients(name,phone,notes) VALUES(?,?,?)',
                (name, phone, notes)).lastrowid
            action = 'CLIENT_CREATE'
        else:
            result = conn.execute(
                'UPDATE clients SET name=?,phone=?,notes=? WHERE id=? AND active=1',
                (name, phone, notes, client_id))
            if result.rowcount != 1:
                raise ValueError('Client introuvable.')
            action = 'CLIENT_UPDATE'
        audit(conn, action, client_id, name)
        return client_id


def list_clients(query=''):
    q = query.strip()
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT c.*, "
            "  COALESCE((SELECT SUM(amount_cents) FROM client_payments WHERE client_id=c.id),0) paid_cents, "
            "  COALESCE((SELECT SUM(total_cents)  FROM sales WHERE client_id=c.id AND status='COMPLETED'),0) billed_cents "
            "FROM clients c "
            "WHERE c.active=1 AND (instr(lower(c.name),lower(?))>0 OR instr(c.phone,?)>0) "
            "ORDER BY c.name, c.id",
            (q, q))]


def get_client(client_id):
    with connect() as conn:
        row = conn.execute(
            "SELECT c.*, "
            "  COALESCE((SELECT SUM(amount_cents) FROM client_payments WHERE client_id=c.id),0) paid_cents, "
            "  COALESCE((SELECT SUM(total_cents)  FROM sales WHERE client_id=c.id AND status='COMPLETED'),0) billed_cents "
            "FROM clients c WHERE c.id=?", (client_id,)).fetchone()
        if not row:
            raise ValueError('Client introuvable.')
        return dict(row)


def deactivate_client(client_id):
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        require_admin(conn)
        balance = conn.execute(
            "SELECT COALESCE(SUM(total_cents),0) - COALESCE((SELECT SUM(amount_cents) FROM client_payments WHERE client_id=?),0) "
            "FROM sales WHERE client_id=? AND status='COMPLETED'", (client_id, client_id)).fetchone()[0]
        if balance > 0:
            raise ValueError('Ce client a un solde impayé. Réglez sa dette avant de le supprimer.')
        conn.execute('UPDATE clients SET active=0 WHERE id=?', (client_id,))
        audit(conn, 'CLIENT_DELETE', client_id)


# ── Ventes liées à un client ──────────────────────────────────────────────────

def client_sales(client_id):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT s.id, s.sale_no, s.total_cents, s.payment_method, s.created_at, "
            "  COALESCE((SELECT SUM(cp.amount_cents) FROM client_payments cp WHERE cp.sale_id=s.id),0) paid "
            "FROM sales s WHERE s.client_id=? AND s.status='COMPLETED' ORDER BY s.id DESC",
            (client_id,))]


# ── Règlements ────────────────────────────────────────────────────────────────

def add_payment(client_id, amount_cents, note='', sale_id=None):
    amount = int(amount_cents)
    if amount <= 0:
        raise ValueError('Montant invalide.')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if not conn.execute('SELECT id FROM clients WHERE id=? AND active=1', (client_id,)).fetchone():
            raise ValueError('Client introuvable.')
        if sale_id is not None:
            si = conn.execute('SELECT id,total_cents FROM sales WHERE id=? AND client_id=? AND status=\'COMPLETED\'',
                              (sale_id, client_id)).fetchone()
            if not si:
                raise ValueError('Vente introuvable pour ce client.')
        pid = conn.execute(
            'INSERT INTO client_payments(client_id,sale_id,amount_cents,note) VALUES(?,?,?,?)',
            (client_id, sale_id, amount, note.strip())).lastrowid
        audit(conn, 'CLIENT_PAYMENT', pid, f'{amount} — {note}')
        return pid


def list_payments(client_id):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT cp.*, s.sale_no FROM client_payments cp "
            "LEFT JOIN sales s ON s.id=cp.sale_id "
            "WHERE cp.client_id=? ORDER BY cp.id DESC",
            (client_id,))]


# ── État des crédits ──────────────────────────────────────────────────────────

def credit_statement():
    """All clients with outstanding balance > 0, ordered by debt desc."""
    with connect() as conn:
        return [dict(row) for row in conn.execute("""
            SELECT c.id, c.name, c.phone,
                   COALESCE(s.billed,0)  billed_cents,
                   COALESCE(p.paid,0)    paid_cents,
                   COALESCE(s.billed,0) - COALESCE(p.paid,0) balance_cents
            FROM clients c
            LEFT JOIN (SELECT client_id, SUM(total_cents) billed
                       FROM sales WHERE status='COMPLETED' GROUP BY client_id) s ON s.client_id=c.id
            LEFT JOIN (SELECT client_id, SUM(amount_cents) paid
                       FROM client_payments GROUP BY client_id)              p ON p.client_id=c.id
            WHERE c.active=1
              AND (COALESCE(s.billed,0) - COALESCE(p.paid,0)) > 0
            ORDER BY balance_cents DESC
        """)]
