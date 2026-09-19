from decimal import Decimal
from database import connect
from services.money import rounded
import math

def resolve_unit_price(product_id, qty, barcode_id=None, conn=None):
    if conn is None:
        with connect() as db:
            return resolve_unit_price(product_id,qty,barcode_id,db)
    p=conn.execute('SELECT sale_price_cents FROM products WHERE id=? AND active=1',(product_id,)).fetchone()
    if not p:
        raise ValueError('Article introuvable')
    if barcode_id:
        b=conn.execute('SELECT * FROM product_barcodes WHERE id=? AND product_id=?',(barcode_id,product_id)).fetchone()
        if not b:
            raise ValueError('Barcode incompatible')
        if b['price_override_cents'] is not None:
            if not math.isfinite(b['qty_multiplier']) or b['qty_multiplier']<=0:
                raise ValueError('Quantité pack invalide')
            packs=float(qty)/b['qty_multiplier']
            if not math.isfinite(packs) or abs(packs-round(packs))>1e-9:
                raise ValueError('La quantité doit respecter le pack/carton.')
            return Decimal(b['price_override_cents'])/Decimal(str(b['qty_multiplier']))
    rule=conn.execute('SELECT unit_price_cents FROM quantity_prices WHERE product_id=? AND active=1 AND min_qty<=? ORDER BY min_qty DESC,id DESC LIMIT 1',(product_id,float(qty))).fetchone()
    return Decimal(rule[0] if rule else p[0])

def line_total(unit,qty):
    return rounded(Decimal(str(unit))*Decimal(str(qty)))


def resolve_line_price(product_id,qty,barcode_id=None,conn=None):
    if conn is None:
        with connect() as db:return resolve_line_price(product_id,qty,barcode_id,db)
    unit=resolve_unit_price(product_id,qty,barcode_id,conn)
    b=conn.execute('SELECT * FROM product_barcodes WHERE id=? AND product_id=?',(barcode_id,product_id)).fetchone() if barcode_id else None
    pack=bool(b and b['price_override_cents'] is not None)
    return dict(unit_price_cents=int(b['price_override_cents']) if pack else rounded(unit),
                line_total_cents=line_total(unit,qty),qty_multiplier=b['qty_multiplier'] if b else 1,
                pricing_mode='PACK' if pack else 'UNIT',barcode=b['barcode'] if b else '',base_unit_price_cents=unit)
