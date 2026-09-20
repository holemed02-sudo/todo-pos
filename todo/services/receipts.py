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
        lines += [i["name_snapshot"], f"  Qté {i['qty']:g} | Brut {fmt(i['line_total_cents'],cur)} | Net {fmt(i['net_total_cents'],cur)}"]
        if i['pricing_mode']=='PACK':
            lines.append(f"  {i['qty']/i['qty_multiplier']:g} pack(s) x {fmt(i['unit_price_cents'],cur)} ({i['qty_multiplier']:g} unités/pack)")
    lines += ["-"*32, f"Remise ticket: {fmt(s['discount_cents'],cur)}", f"TOTAL: {fmt(s['total_cents'],cur)}", f"Paiement: {s['payment_method']}", f"Reçu: {fmt(s['paid_cents'],cur)}", f"Monnaie: {fmt(s['change_cents'],cur)}", "="*32, get_setting("receipt_footer","Merci")]
    if s['client_id'] is not None:
        with connect() as conn:
            client=conn.execute('SELECT name FROM clients WHERE id=?',(s['client_id'],)).fetchone()
        lines.insert(4,'Client: '+client['name'])
    if s['payment_method']=='CREDIT':
        lines.insert(-2,'Dette initiale: '+fmt(s['total_cents']-s['paid_cents'],cur))
    return "\n".join(lines)

def print_receipt_windows(sale_id):
    text=build_receipt(sale_id)
    path=Path(tempfile.gettempdir())/f"todo_receipt_{sale_id}.txt"
    path.write_text(text,encoding="utf-8")
    if os.name=="nt":
        printer=get_setting('printer_name','').strip()
        if printer:
            from subprocess import list2cmdline
            os.startfile(str(path),'printto',list2cmdline([printer]))
        else:
            os.startfile(str(path),"print")
    return path



def export_receipt_pdf(sale_id, destination):
    """Create a paginated, printable receipt without sending a printer job."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from textwrap import wrap
    path = Path(destination)
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle(f"ToDo ticket {sale_id}")
    y = 800
    pdf.setFont("Helvetica", 10)
    for line in build_receipt(sale_id).splitlines():
        for part in wrap(line, 82) or [""]:
            if y < 45:
                pdf.showPage()
                pdf.setFont("Helvetica", 10)
                y = 800
            pdf.drawString(40, y, part)
            y -= 15
    pdf.save()
    return path
