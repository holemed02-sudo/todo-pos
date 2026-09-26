from database import connect
from services.security import audit, current_user

def get_open_session():
    with connect() as conn:
        return conn.execute(
            "SELECT * FROM cash_sessions WHERE status='OPEN' ORDER BY id DESC LIMIT 1"
        ).fetchone()

def open_session(user_id, opening_cash_cents):
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        active_user=current_user.get()
        if active_user is not None and int(active_user)!=int(user_id):
            raise PermissionError("Utilisateur incompatible avec cette caisse.")
        if not conn.execute("SELECT id FROM users WHERE id=? AND active=1",(user_id,)).fetchone():
            raise ValueError("Utilisateur invalide.")
        if int(opening_cash_cents)<0: raise ValueError("Montant invalide")
        if conn.execute("SELECT id FROM cash_sessions WHERE status='OPEN'").fetchone():
            raise ValueError("كاينة كيس مفتوحة دابا.")
        cur = conn.execute(
            "INSERT INTO cash_sessions(user_id,opening_cash_cents,expected_cash_cents) VALUES(?,?,?)",
            (user_id, int(opening_cash_cents), int(opening_cash_cents))
        )
        audit(conn,'CASH_OPEN',cur.lastrowid,user_id=user_id)
        return cur.lastrowid

def session_totals(conn, session_id):
    cash_sales = conn.execute(
        """SELECT COALESCE(SUM(CASE
                    WHEN sp.payment_method='CASH' THEN sp.amount_cents
                    WHEN sp.payment_method='CREDIT' THEN sp.amount_cents
                    ELSE 0 END),0) v
           FROM sale_payments sp JOIN sales s ON s.id=sp.sale_id
           WHERE s.session_id=? AND s.status='COMPLETED'""",
        (session_id,)
    ).fetchone()["v"]
    cash_returns = conn.execute(
        """SELECT COALESCE(SUM(rp.amount_cents),0) v
           FROM return_payments rp JOIN returns r ON r.id=rp.return_id
           WHERE r.session_id=? AND rp.payment_method='CASH'""",
        (session_id,)
    ).fetchone()["v"]
    expenses = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) v FROM expenses WHERE session_id=?",
        (session_id,)
    ).fetchone()["v"]
    cash_in = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) v FROM cash_movements WHERE session_id=? AND movement_type='IN'",
        (session_id,)
    ).fetchone()["v"]
    cash_out = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) v FROM cash_movements WHERE session_id=? AND movement_type='OUT'",
        (session_id,)
    ).fetchone()["v"]
    cash_in += conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM client_payments WHERE session_id=? AND payment_method='CASH'",(session_id,)).fetchone()[0]
    cash_out += conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM supplier_payments WHERE session_id=? AND payment_method='CASH'",(session_id,)).fetchone()[0]
    return dict(cash_sales=int(cash_sales), cash_returns=int(cash_returns),
                expenses=int(expenses), cash_in=int(cash_in), cash_out=int(cash_out))

def close_session(session_id, actual_cash_cents):
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        s = conn.execute("SELECT * FROM cash_sessions WHERE id=? AND status='OPEN'",(session_id,)).fetchone()
        if not s:
            raise ValueError("لا توجد كيس مفتوحة.")
        active_user=current_user.get()
        if active_user is not None and int(s["user_id"])!=int(active_user):
            raise PermissionError("هذه الكيس تخص مستخدما آخر.")
        t = session_totals(conn, session_id)
        expected = int(s["opening_cash_cents"]) + t["cash_sales"] - t["cash_returns"] - t["expenses"] + t["cash_in"] - t["cash_out"]
        diff = int(actual_cash_cents) - expected
        conn.execute(
            """
            UPDATE cash_sessions
            SET closed_at=CURRENT_TIMESTAMP, expected_cash_cents=?, actual_cash_cents=?,
                difference_cents=?, status='CLOSED'
            WHERE id=?
            """,
            (expected, int(actual_cash_cents), diff, session_id)
        )
        audit(conn,'CASH_CLOSE',session_id,f'Expected={expected}; actual={actual_cash_cents}')
        return expected, diff, t


def record_cash(session_id,user_id,amount_cents,kind,note):
    amount=int(amount_cents)
    if amount<=0 or kind not in ('IN','OUT','EXPENSE'):
        raise ValueError('Mouvement invalide')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        session=conn.execute("SELECT user_id FROM cash_sessions WHERE id=? AND status='OPEN'",(session_id,)).fetchone()
        if not session:
            raise ValueError('La caisse est fermée.')
        if int(session['user_id'])!=int(user_id):
            raise PermissionError('Cette caisse appartient à un autre utilisateur.')
        active_user=current_user.get()
        if active_user is not None and int(active_user)!=int(user_id):
            raise PermissionError('Utilisateur incompatible avec cette caisse.')
        if kind=='EXPENSE':
            conn.execute('INSERT INTO expenses(session_id,user_id,label,amount_cents) VALUES(?,?,?,?)',(session_id,user_id,note,amount))
        else:
            conn.execute('INSERT INTO cash_movements(session_id,user_id,movement_type,amount_cents,note) VALUES(?,?,?,?,?)',(session_id,user_id,kind,amount,note))
        audit(conn,'CASH_'+kind,session_id,f'{amount}: {note}',user_id)
