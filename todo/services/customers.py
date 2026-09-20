from database import connect
from services.security import require_admin, audit


def save_customer(name, phone='', notes='', customer_id=None):
    name, phone, notes = name.strip(), phone.strip(), notes.strip()
    if not name:
        raise ValueError('Le nom du client est obligatoire.')
    if len(name) > 150 or len(phone) > 60 or len(notes) > 2000:
        raise ValueError('Nom, téléphone ou notes trop longs.')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        require_admin(conn)
        if customer_id is None:
            customer_id = conn.execute(
                'INSERT INTO customers(name,phone,notes) VALUES(?,?,?)',
                (name, phone, notes)).lastrowid
            action = 'CUSTOMER_CREATE'
        else:
            result = conn.execute(
                'UPDATE customers SET name=?,phone=?,notes=? WHERE id=? AND active=1',
                (name, phone, notes, customer_id))
            if result.rowcount != 1:
                raise ValueError('Client introuvable.')
            action = 'CUSTOMER_UPDATE'
        audit(conn, action, customer_id, name)
        return customer_id


def list_customers(query=''):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM customers WHERE active=1 AND (instr(lower(name),lower(?))>0 OR instr(phone,?)>0) ORDER BY name,id",
            (query.strip(), query.strip()))]
