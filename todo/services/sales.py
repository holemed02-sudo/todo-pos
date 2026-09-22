import json, math
from decimal import Decimal
from datetime import datetime
from uuid import uuid4
from database import connect
from services.inventory import apply_stock_movement
from services.pricing import resolve_unit_price, resolve_line_price, line_total
from services.money import allocate, rounded
from services.security import audit, current_user

def sale_number():
    return 'V-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:12].upper()

def return_number():
    return 'R-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid4().hex[:12].upper()

def validate_session(conn,session_id,user_id):
    if not conn.execute("SELECT id FROM cash_sessions WHERE id=? AND status='OPEN'",(session_id,)).fetchone():
        raise ValueError('Ouvrez la caisse avant cette opération.')
    if not conn.execute('SELECT id FROM users WHERE id=? AND active=1',(user_id,)).fetchone():
        raise ValueError('Utilisateur invalide')
    if current_user.get() is not None and current_user.get()!=user_id:
        raise PermissionError('Utilisateur incompatible')

def complete_sale(session_id,user_id,cart,payment_method,paid_cents,discount_cents=0,held_id=None,client_id=None,payments=None):
    if not cart:
        raise ValueError('Ticket vide')
    if payment_method not in ('CASH','CARD','CREDIT'):
        raise ValueError('Mode de paiement invalide')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        validate_session(conn,session_id,user_id)
        if held_id is not None and not conn.execute('SELECT id FROM held_sales WHERE id=?',(held_id,)).fetchone():
            raise ValueError('Ce ticket en attente a déjà été encaissé ou supprimé.')
        if client_id is not None and not conn.execute('SELECT id FROM clients WHERE id=? AND active=1',(client_id,)).fetchone():
            raise ValueError('Client introuvable.')
        if payment_method=='CREDIT' and client_id is None:
            raise ValueError('Choisissez un client pour une vente à crédit.')
        normalized=[]
        for line in cart:
            pid=int(line['product_id']);qty=float(line['qty'])
            if not math.isfinite(qty) or qty<=0:
                raise ValueError('Quantité invalide')
            p=conn.execute('SELECT * FROM products WHERE id=? AND (active=1 OR is_misc=1)',(pid,)).fetchone()
            if not p:
                raise ValueError('Article introuvable')
            if p['is_misc']:
                p=dict(p)
                p['name']=str(line.get('name','')).strip()
                if not p['name'] or len(p['name'])>150:raise ValueError('Libellé Divers invalide')
            if not p['allow_fraction'] and not qty.is_integer():
                raise ValueError('Cet article se vend en unités entières.')
            unit=line.get('unit_price_cents')
            pricing=None
            if line.get('barcode_id'):
                pricing=resolve_line_price(pid,qty,line['barcode_id'],conn)
                if pricing['pricing_mode']=='PACK':unit=pricing['base_unit_price_cents']
            if unit is None:
                unit=resolve_unit_price(pid,qty,line.get('barcode_id'),conn)
            unit=Decimal(str(unit))
            if not unit.is_finite() or unit<0:
                raise ValueError('Prix invalide')
            gross=line_total(unit,qty)
            discount=int(line.get('discount_cents',0))
            if discount<0 or discount>gross:
                raise ValueError('Remise ligne invalide')
            normalized.append((p,qty,unit,gross,discount,pricing['barcode'] if pricing else line.get('barcode',''),pricing))
        weights=[x[3]-x[4] for x in normalized]
        subtotal=sum(weights);discount=int(discount_cents)
        if discount<0 or discount>subtotal:
            raise ValueError('La remise dépasse le montant du ticket.')
        total=subtotal-discount;paid=int(paid_cents)
        if payment_method=='CASH' and paid<total:
            raise ValueError('Montant reçu insuffisant.')
        if payment_method=='CARD':paid=total
        if paid<0 or (payment_method=='CREDIT' and paid>total):
            raise ValueError('Acompte invalide.')
        change=max(0,paid-total)
        no=sale_number()
        sid=conn.execute('INSERT INTO sales(sale_no,session_id,cashier_user_id,subtotal_cents,discount_cents,total_cents,payment_method,paid_cents,change_cents,client_id) VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (no,session_id,user_id,subtotal,discount,total,payment_method,paid,change,client_id)).lastrowid
        if split is None:
            settled=paid-change if payment_method=='CASH' else paid
            conn.execute('INSERT INTO sale_payments(sale_id,payment_method,amount_cents) VALUES(?,?,?)',(sid,payment_method,settled))
        else:
            conn.executemany('INSERT INTO sale_payments(sale_id,payment_method,amount_cents) VALUES(?,?,?)',[(sid,method,amount) for method,amount in split])
        nets=allocate(total,weights)
        for (p,qty,unit,gross,line_discount,barcode,pricing),net in zip(normalized,nets):
            pack=pricing and pricing['pricing_mode']=='PACK'
            conn.execute('INSERT INTO sale_items(sale_id,product_id,barcode_used,name_snapshot,qty,unit_price_cents,cost_price_cents,discount_cents,line_total_cents,net_total_cents,qty_multiplier,pricing_mode) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                         (sid,p['id'],barcode,p['name'],qty,pricing['unit_price_cents'] if pack else rounded(unit),p['purchase_price_cents'],gross-net,gross,net,pricing['qty_multiplier'] if pricing else 1,'PACK' if pack else 'UNIT'))
            if not p['is_misc']:
                apply_stock_movement(conn,p['id'],-qty,'SALE',p['purchase_price_cents'],'sale',sid,no,user_id)
        if held_id is not None:
            conn.execute('DELETE FROM held_sales WHERE id=?',(held_id,))
        audit(conn,'SALE',sid,no,user_id)
        return dict(id=sid,sale_no=no,subtotal_cents=subtotal,discount_cents=discount,total_cents=total,paid_cents=paid,change_cents=change)

def hold_sale(user_id,cart,label='',discount_cents=0,held_id=None,client_id=None):
    if not cart:raise ValueError('Ticket vide')
    payload=json.dumps(cart,ensure_ascii=False,default=str)
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if held_id is None:
            held_id=conn.execute('INSERT INTO held_sales(label,cashier_user_id,payload_json,discount_cents,client_id) VALUES(?,?,?,?,?)',(label or 'Ticket en attente',user_id,payload,int(discount_cents),client_id)).lastrowid
        else:
            cur=conn.execute('UPDATE held_sales SET label=?,payload_json=?,discount_cents=?,client_id=? WHERE id=?',(label or 'Ticket en attente',payload,int(discount_cents),client_id,held_id))
            if cur.rowcount!=1:raise ValueError('Ticket en attente introuvable')
        audit(conn,'HOLD',held_id,user_id=user_id)
        return held_id

def list_held():
    with connect() as conn:
        return conn.execute('SELECT * FROM held_sales ORDER BY id DESC').fetchall()

def resume_held(held_id):
    with connect() as conn:
        row=conn.execute('SELECT * FROM held_sales WHERE id=?',(held_id,)).fetchone()
        if not row:raise ValueError('Ticket introuvable')
        cart=json.loads(row['payload_json'])
        for line in cart:
            if line.get('pricing_mode')=='PACK':
                price=resolve_line_price(line['product_id'],line['qty'],line.get('barcode_id'),conn)
                line['unit_price_cents']=str(price['base_unit_price_cents'])
                line['qty_multiplier']=price['qty_multiplier']
                line.pop('pricing_mode',None)
        return dict(cart=cart,discount_cents=row['discount_cents'],held_id=row['id'],client_id=row['client_id'])

def create_return(sale_id,session_id,user_id,items,reason='',refund_method='CASH'):
    if not items:raise ValueError('Aucun article à retourner')
    if refund_method not in ('CASH','CARD'):raise ValueError('Mode de remboursement invalide')
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE');validate_session(conn,session_id,user_id)
        sale=conn.execute('SELECT * FROM sales WHERE id=?',(sale_id,)).fetchone()
        if not sale:raise ValueError('Vente introuvable')
        requested={}
        for item,qty in items:
            qty=Decimal(str(qty))
            if not qty.is_finite() or qty<=0:raise ValueError('Quantité retour invalide')
            requested[int(item)]=requested.get(int(item),Decimal(0))+qty
        validated=[]
        for item,qty in requested.items():
            si=conn.execute('SELECT * FROM sale_items WHERE id=? AND sale_id=?',(item,sale_id)).fetchone()
            if not si:raise ValueError('Ligne introuvable')
            if si['pricing_mode']=='PACK':
                packs=qty/Decimal(str(si['qty_multiplier']))
                if abs(packs-packs.to_integral_value())>Decimal('0.000000001'):
                    raise ValueError('Le retour doit respecter la quantité du pack/carton.')
            old=conn.execute('SELECT COALESCE(SUM(qty),0),COALESCE(SUM(line_total_cents),0) FROM return_items WHERE sale_item_id=?',(item,)).fetchone()
            cumulative=Decimal(str(old[0]))+qty;sold=Decimal(str(si['qty']))
            if cumulative>sold+Decimal('0.000000001'):raise ValueError('Quantité retour invalide')
            # Cumulative rounding guarantees that final partial return refunds the exact residual cent.
            due=max(0,rounded(Decimal(si['net_total_cents'])*min(cumulative,sold)/sold)-old[1])
            validated.append((si,float(qty),due))
        total=sum(x[2] for x in validated)
        refunded=conn.execute('SELECT COALESCE(SUM(total_cents),0) FROM returns WHERE sale_id=?',(sale_id,)).fetchone()[0]
        remaining=max(0,sale['total_cents']-refunded)
        if total>remaining:
            raise ValueError('Les anciens remboursements dépassent le solde. Vérification administrateur requise.')
        refund_paid=total
        if sale['client_id'] is not None and sale['payment_method']=='CREDIT':
            from services.clients import client_sales
            balance=next(r['balance_cents'] for r in client_sales(sale['client_id'],conn) if r['id']==sale_id)
            refund_paid=max(0,total-max(0,balance))
        no=return_number()
        rid=conn.execute('INSERT INTO returns(return_no,sale_id,session_id,cashier_user_id,total_cents,refund_method,reason,refund_paid_cents) VALUES(?,?,?,?,?,?,?,?)',(no,sale_id,session_id,user_id,total,refund_method,reason,refund_paid)).lastrowid
        for si,qty,due in validated:
            conn.execute('INSERT INTO return_items(return_id,sale_item_id,product_id,qty,unit_price_cents,line_total_cents) VALUES(?,?,?,?,?,?)',(rid,si['id'],si['product_id'],qty,si['unit_price_cents'],due))
            misc=conn.execute('SELECT is_misc FROM products WHERE id=?',(si['product_id'],)).fetchone()[0]
            if not misc:
                apply_stock_movement(conn,si['product_id'],qty,'RETURN',si['cost_price_cents'],'return',rid,reason or no,user_id)
        audit(conn,'RETURN',rid,reason,user_id)
        return dict(id=rid,return_no=no,total_cents=total,refund_paid_cents=refund_paid,debt_reduction_cents=total-refund_paid)

