from pathlib import Path
import os, tempfile
from database import connect, get_setting
from services.money import fmt

def build_receipt(sale_id):
    with connect() as conn:
        s=conn.execute("SELECT s.*,u.display_name FROM sales s JOIN users u ON u.id=s.cashier_user_id WHERE s.id=?",(sale_id,)).fetchone()
        items=conn.execute("SELECT * FROM sale_items WHERE sale_id=? ORDER BY id",(sale_id,)).fetchall()
    if not s: raise ValueError("Vente introuvable")
    cur=get_setting("currency","DH")
    lines=[get_setting("shop_name","ToDo"), "="*32, f"Ticket: {s['sale_no']}", f"Caissier: {s['display_name']}", "-"*32]
    for i in items:
        if i["pricing_mode"] == "PACK":
            mult=float(i["qty_multiplier"] or 1);packs=float(i["qty"])/mult
            detail=f"  {packs:g} pack x {fmt(i['unit_price_cents'],cur)} ({i['qty']:g} u) = {fmt(i['line_total_cents'],cur)}"
        else:
            detail=f"  {i['qty']:g} x {fmt(i['unit_price_cents'],cur)} = {fmt(i['line_total_cents'],cur)}"
        lines += [i["name_snapshot"], detail]
    lines += ["-"*32, f"TOTAL: {fmt(s['total_cents'],cur)}", f"Paiement: {s['payment_method']}", f"Reçu: {fmt(s['paid_cents'],cur)}", f"Monnaie: {fmt(s['change_cents'],cur)}", "="*32, get_setting("receipt_footer","Merci")]
    return "\n".join(lines)

def print_receipt_windows(sale_id):
    text=build_receipt(sale_id)
    path=Path(tempfile.gettempdir())/f"todo_receipt_{sale_id}.txt"
    path.write_text(text,encoding="utf-8")
    if os.name=="nt":
        os.startfile(str(path),"print")
    return path
