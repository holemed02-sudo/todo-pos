from database import connect
from services.money import to_cents
from decimal import Decimal

def misc_line(name,price,quantity='1'):
    name=name.strip()
    unit=to_cents(price)
    qty=Decimal(str(quantity).replace(',','.'))
    if not name or len(name)>150:raise ValueError('Libellé obligatoire (150 caractères maximum)')
    if unit<0 or not qty.is_finite() or qty<=0:raise ValueError('Montant ou quantité invalide')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        row=conn.execute('SELECT id FROM products WHERE is_misc=1 LIMIT 1').fetchone()
        pid=row['id'] if row else conn.execute("INSERT INTO products(name,active,is_misc,allow_fraction) VALUES('Divers',0,1,1)").lastrowid
    return dict(product_id=pid,name=name,qty=float(qty),unit_price_cents=str(unit),
                manual_unit_price=True,is_misc=True,qty_multiplier=1,base_price_cents=unit,
                image_path='',allow_fraction=True,discount_cents=0)
