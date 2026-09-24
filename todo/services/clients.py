from database import connect
from services.security import require_admin, audit, current_user


def save_client(name, phone='', notes='', client_id=None):
    name, phone, notes = name.strip(), phone.strip(), notes.strip()
    if not name or len(name)>150 or len(phone)>60 or len(notes)>2000:
        raise ValueError('Nom obligatoire ; vérifiez la longueur des champs.')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        require_admin(conn)
        if client_id is None:
            client_id=conn.execute('INSERT INTO clients(name,phone,notes) VALUES(?,?,?)',(name,phone,notes)).lastrowid
        elif conn.execute('UPDATE clients SET name=?,phone=?,notes=? WHERE id=? AND active=1',(name,phone,notes,client_id)).rowcount!=1:
            raise ValueError('Client introuvable.')
        audit(conn,'CLIENT_SAVE',client_id,name)
        return client_id


def client_sales(client_id, conn=None):
    if conn is None:
        with connect() as db:
            return client_sales(client_id,db)
    rows=[dict(r) for r in conn.execute('''
        SELECT s.*,
          COALESCE((SELECT SUM(total_cents) FROM returns WHERE sale_id=s.id),0) returned,
          COALESCE((SELECT SUM(COALESCE(refund_paid_cents,total_cents)) FROM returns WHERE sale_id=s.id),0) refunded,
          COALESCE((SELECT SUM(amount_cents) FROM client_payments WHERE sale_id=s.id AND client_id=?),0) subsequent
        FROM sales s WHERE s.client_id=? AND s.status='COMPLETED' ORDER BY s.id
    ''',(client_id,client_id))]
    # Preserve old unallocated payments, assigning them oldest invoice first.
    unallocated=conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM client_payments WHERE client_id=? AND sale_id IS NULL',(client_id,)).fetchone()[0]
    for r in rows:
        r['original_total_cents']=r['total_cents']
        r['total_cents']-=r['returned']
        r['paid']=min(r['paid_cents'],r['original_total_cents'])+r['subsequent']-r['refunded']
        allocation=min(unallocated,max(0,r['total_cents']-r['paid']))
        r['paid']+=allocation
        unallocated-=allocation
        r['balance_cents']=r['total_cents']-r['paid']
    return rows


def _client(conn, row):
    result=dict(row)
    invoices=client_sales(row['id'],conn)
    result['billed_cents']=sum(r['total_cents'] for r in invoices)
    # Include all legacy payments, even an unallocated overpayment.
    later=conn.execute('SELECT COALESCE(SUM(amount_cents),0) FROM client_payments WHERE client_id=?',(row['id'],)).fetchone()[0]
    result['paid_cents']=sum(min(r['paid_cents'],r['original_total_cents'])-r['refunded'] for r in invoices)+later
    result['balance_cents']=result['billed_cents']-result['paid_cents']
    return result


def list_clients(query=''):
    with connect() as conn:
        rows=conn.execute('SELECT * FROM clients WHERE active=1 AND (instr(lower(name),lower(?))>0 OR instr(phone,?)>0) ORDER BY name,id',(query.strip(),query.strip())).fetchall()
        return [_client(conn,r) for r in rows]


def get_client(client_id):
    with connect() as conn:
        row=conn.execute('SELECT * FROM clients WHERE id=?',(client_id,)).fetchone()
        if row is None:raise ValueError('Client introuvable.')
        return _client(conn,row)


def deactivate_client(client_id):
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE');require_admin(conn)
        row=conn.execute('SELECT * FROM clients WHERE id=?',(client_id,)).fetchone()
        if row is None:raise ValueError('Client introuvable.')
        if _client(conn,row)['balance_cents']!=0:
            raise ValueError('Le solde doit être nul avant archivage.')
        conn.execute('UPDATE clients SET active=0 WHERE id=?',(client_id,))
        audit(conn,'CLIENT_DELETE',client_id)


def add_payment(client_id, amount_cents, note='', sale_id=None, payment_method='CASH'):
    amount=int(amount_cents)
    if amount!=amount_cents or amount<=0 or payment_method not in ('CASH','CARD'):
        raise ValueError('Montant ou mode de paiement invalide.')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE');uid=require_admin(conn)
        session=conn.execute("SELECT id FROM cash_sessions WHERE status='OPEN' AND user_id=? ORDER BY id DESC LIMIT 1",(uid,)).fetchone()
        if session is None:raise ValueError('Ouvrez votre caisse avant un règlement.')
        client=conn.execute('SELECT * FROM clients WHERE id=? AND active=1',(client_id,)).fetchone()
        if client is None:raise ValueError('Client introuvable.')
        rows=client_sales(client_id,conn)
        if sale_id is not None:
            rows=[r for r in rows if r['id']==sale_id]
            if not rows:raise ValueError('Vente introuvable pour ce client.')
        capacity=min(_client(conn,client)['balance_cents'],sum(max(0,r['balance_cents']) for r in rows))
        if amount>capacity:raise ValueError('Le règlement dépasse le solde dû.')
        first=None;remaining=amount
        for row in rows:
            allocated=min(remaining,max(0,row['balance_cents']))
            if not allocated:continue
            pid=conn.execute('INSERT INTO client_payments(client_id,sale_id,amount_cents,note,session_id,user_id,payment_method) VALUES(?,?,?,?,?,?,?)',(client_id,row['id'],allocated,note.strip(),session['id'],uid,payment_method)).lastrowid
            first=first or pid;remaining-=allocated
            audit(conn,'CLIENT_PAYMENT',pid,str(allocated))
            if remaining==0:break
        return first


def list_payments(client_id):
    with connect() as conn:
        return [dict(r) for r in conn.execute('SELECT cp.*,s.sale_no FROM client_payments cp LEFT JOIN sales s ON s.id=cp.sale_id WHERE cp.client_id=? ORDER BY cp.id DESC',(client_id,))]


def credit_statement():
    return sorted((r for r in list_clients() if r['balance_cents']>0),key=lambda r:-r['balance_cents'])
