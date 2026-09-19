import hashlib, hmac, secrets
from contextvars import ContextVar
from database import connect

current_user=ContextVar('todo_user',default=None)

def hash_pin(pin):
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',str(pin).encode(),salt.encode(),120000).hex()
    return f'pbkdf2$120000${salt}${digest}'

def verify_pin(pin, stored):
    if not stored.startswith('pbkdf2$'):
        return hmac.compare_digest(hashlib.sha256(str(pin).encode()).hexdigest(),stored)
    _,iterations,salt,digest=stored.split('$')
    actual=hashlib.pbkdf2_hmac('sha256',str(pin).encode(),salt.encode(),int(iterations)).hex()
    return hmac.compare_digest(actual,digest)

def require_admin(conn):
    uid=current_user.get()
    user=conn.execute("SELECT role FROM users WHERE id=? AND active=1",(uid,)).fetchone()
    if not user or user['role']!='admin':
        raise PermissionError('Action réservée à un administrateur.')
    return uid

def audit(conn,action,document,details='',user_id=None):
    conn.execute('INSERT INTO audit_log(user_id,action,document,details) VALUES(?,?,?,?)',(user_id or current_user.get(),action,str(document),str(details)))
