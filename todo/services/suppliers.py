from database import connect
from services.security import require_admin, audit


def save_supplier(name, phone='', notes='', supplier_id=None):
    name, phone, notes = name.strip(), phone.strip(), notes.strip()
    if not name:
        raise ValueError('Le nom du fournisseur est obligatoire.')
    if len(name) > 150 or len(phone) > 60 or len(notes) > 2000:
        raise ValueError('Nom, téléphone ou notes trop longs.')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        require_admin(conn)
        if supplier_id is None:
            supplier_id = conn.execute(
                'INSERT INTO suppliers(name,phone,notes) VALUES(?,?,?)',
                (name, phone, notes)).lastrowid
            action = 'SUPPLIER_CREATE'
        else:
            result = conn.execute(
                'UPDATE suppliers SET name=?,phone=?,notes=? WHERE id=? AND active=1',
                (name, phone, notes, supplier_id))
            if result.rowcount != 1:
                raise ValueError('Fournisseur introuvable.')
            action = 'SUPPLIER_UPDATE'
        audit(conn, action, supplier_id, name)
        return supplier_id


def list_suppliers(query=''):
    with connect() as conn:
        return [dict(row) for row in conn.execute(
            "SELECT * FROM suppliers WHERE active=1 AND (instr(lower(name),lower(?))>0 OR instr(phone,?)>0) ORDER BY name,id",
            (query.strip(), query.strip()))]
