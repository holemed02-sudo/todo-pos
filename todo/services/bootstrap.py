from database import connect
from services.security import hash_pin

def ensure_defaults():
    with connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO users(username,display_name,pin_hash,role) VALUES(?,?,?,?)",
            ("admin","Administrateur",hash_pin("1234"),"admin")
        )
        conn.execute("INSERT OR IGNORE INTO categories(name,sort_order) VALUES('Général',0)")
        marker = conn.execute("SELECT value FROM settings WHERE key='starter_catalog_v1'").fetchone()
        has_products = conn.execute("SELECT 1 FROM products LIMIT 1").fetchone()
        if not marker and not has_products:
            for name, order in [('Aliments chats',1),('Boissons',2),('Épicerie',3)]:
                conn.execute("INSERT OR IGNORE INTO categories(name,sort_order) VALUES(?,?)", (name,order))
            cats = {r['name']: r['id'] for r in conn.execute("SELECT id,name FROM categories WHERE name IN (?,?,?)", ('Aliments chats','Boissons','Épicerie'))}
            demo = [
                ('DEMO-CHAT-01','Produit démo - Croquettes chat',cats['Aliments chats'],1800,2500,12,2),
                ('DEMO-CHAT-02','Produit démo - Pâtée chat',cats['Aliments chats'],900,1400,8,2),
                ('DEMO-BOIS-01','Produit démo - Eau 1.5L',cats['Boissons'],250,400,24,6),
                ('DEMO-EPIC-01','Produit démo - Sucre 1kg',cats['Épicerie'],700,950,10,2),
            ]
            for sku,name,cat,cost,price,stock,alert in demo:
                cur=conn.execute("INSERT INTO products(sku,name,category_id,purchase_price_cents,sale_price_cents,stock_qty,alert_qty) VALUES(?,?,?,?,?,?,?)",(sku,name,cat,cost,price,stock,alert))
                if name == 'Produit démo - Croquettes chat':
                    conn.execute("INSERT INTO quantity_prices(product_id,min_qty,unit_price_cents,pricing_mode) VALUES(?,?,?,?)",(cur.lastrowid,3,2200,'UNIT'))
            conn.execute("INSERT INTO settings(key,value) VALUES('starter_catalog_v1','1')")
        conn.commit()
