from database import connect
from services.security import hash_pin

def ensure_defaults():
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(username,display_name,pin_hash,role) VALUES(?,?,?,?)",
            ("admin","Administrateur",hash_pin("1234"),"admin")
        )
        conn.execute("INSERT OR IGNORE INTO categories(name,sort_order) VALUES('Général',0)")
        conn.commit()
