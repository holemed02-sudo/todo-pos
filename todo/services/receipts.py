from pathlib import Path
import os, tempfile
from database import connect, get_setting
from services.money import fmt


def _receipt_width():
    try:
        width=int(get_setting('receipt_chars','42'))
    except (TypeError,ValueError):
        width=42
    return max(32,min(width,64))


def _payment_label(method):
    lang=get_setting('language','fr')
    labels={
        'CASH':('Espèces','نقداً'),
        'CARD':('Carte','بطاقة'),
        'CREDIT':('Crédit','دين'),
        'MIXED':('Mixte','مختلط'),
    }
    fr,ar=labels.get(method,(method or '',method or ''))
    return ar if lang=='ar' else fr


def build_receipt(sale_id):
    with connect() as conn:
        s=conn.execute("SELECT s.*,u.display_name FROM sales s JOIN users u ON u.id=s.cashier_user_id WHERE s.id=?",(sale_id,)).fetchone()
        items=conn.execute("SELECT * FROM sale_items WHERE sale_id=? ORDER BY id",(sale_id,)).fetchall()
        payments=conn.execute("SELECT payment_method,amount_cents FROM sale_payments WHERE sale_id=? ORDER BY id",(sale_id,)).fetchall()
        client=conn.execute('SELECT name FROM clients WHERE id=?',(s['client_id'],)).fetchone() if s and s['client_id'] is not None else None
    if not s: raise ValueError("Vente introuvable")
    lang=get_setting('language','fr');ar=lang=='ar'
    tr=lambda fr,arabic: arabic if ar else fr
    cur=get_setting("currency","DH");width=_receipt_width();rule="="*width;dash="-"*width
    lines=[
        get_setting("shop_name","ToDo"),
        rule,
        f"{tr('Ticket','التذكرة')}: {s['sale_no']}",
        f"{tr('Caissier','الكاشير')}: {s['display_name']}",
    ]
    if client:lines.append(f"{tr('Client','الزبون')}: {client['name']}")
    lines.append(dash)
    for i in items:
        lines += [
            i["name_snapshot"],
            f"  {tr('Qté','الكمية')} {i['qty']:g} | {tr('Brut','الإجمالي')} {fmt(i['line_total_cents'],cur)} | {tr('Net','الصافي')} {fmt(i['net_total_cents'],cur)}",
        ]
        if i['pricing_mode']=='PACK':
            lines.append(f"  {i['qty']/i['qty_multiplier']:g} {tr('pack(s)','علبة')} x {fmt(i['unit_price_cents'],cur)} ({i['qty_multiplier']:g} {tr('unités','وحدات')})")
    lines += [
        dash,
        f"{tr('Remise ticket','تخفيض التذكرة')}: {fmt(s['discount_cents'],cur)}",
        f"{tr('TOTAL','المجموع')}: {fmt(s['total_cents'],cur)}",
        f"{tr('Paiement','الأداء')}: {_payment_label(s['payment_method'])}",
    ]
    if s['payment_method']=='MIXED':
        for p in payments:lines.append(f"  {_payment_label(p['payment_method'])}: {fmt(p['amount_cents'],cur)}")
    lines += [
        f"{tr('Reçu','المؤدى')}: {fmt(s['paid_cents'],cur)}",
        f"{tr('Monnaie','الباقي')}: {fmt(s['change_cents'],cur)}",
    ]
    if s['payment_method']=='CREDIT':
        lines.append(f"{tr('Dette initiale','الدين الأولي')}: {fmt(s['total_cents']-s['paid_cents'],cur)}")
    lines += [rule,get_setting("receipt_footer",tr("Merci","شكراً"))]
    return "\n".join(lines)


def build_escpos_receipt(sale_id, cut=True, open_drawer=False):
    """Return a complete UTF-8 ESC/POS RAW job for a thermal receipt printer."""
    text=build_receipt(sale_id)
    payload=bytearray(b'\x1b@')                         # initialise printer
    payload.extend(b'\x1ba\x01')                     # centre shop header
    first,*rest=text.splitlines()
    payload.extend(b'\x1bE\x01'+first.encode('utf-8')+b'\n\x1bE\x00')
    payload.extend(b'\x1ba\x00')                     # left align body
    if rest:payload.extend(('\n'.join(rest)+'\n').encode('utf-8'))
    payload.extend(b'\n\n')
    if open_drawer:
        pin=get_setting('drawer_pin','0')
        if pin not in ('0','1'):raise ValueError('Connecteur tiroir invalide.')
        payload.extend(bytes((27,112,int(pin),50,250)))
    if cut:payload.extend(b'\x1dV\x00')
    return bytes(payload)


def _send_raw_windows(printer, payload, title):
    if os.name!='nt':raise OSError('Impression thermique RAW disponible sous Windows.')
    import win32print
    handle=win32print.OpenPrinter(printer)
    try:
        job=win32print.StartDocPrinter(handle,1,(title,None,'RAW'))
        try:
            win32print.StartPagePrinter(handle)
            try:
                if win32print.WritePrinter(handle,payload)!=len(payload):
                    raise OSError('Impression thermique incomplète.')
            finally:win32print.EndPagePrinter(handle)
            win32print.EndDocPrinter(handle)
        except Exception:
            win32print.AbortPrinter(handle);raise
    finally:win32print.ClosePrinter(handle)
    return job


def print_receipt_windows(sale_id):
    printer=get_setting('printer_name','').strip()
    raw=get_setting('thermal_raw','0')=='1'
    if raw:
        if not printer:raise ValueError('Sélectionnez une imprimante de ticket dans les paramètres.')
        return _send_raw_windows(
            printer,
            build_escpos_receipt(sale_id,cut=True,open_drawer=get_setting('drawer_enabled','0')=='1'),
            f"ToDo - Ticket {sale_id}",
        )
    text=build_receipt(sale_id)
    path=Path(tempfile.gettempdir())/f"todo_receipt_{sale_id}.txt"
    path.write_text(text,encoding="utf-8")
    if os.name=="nt":
        if printer:
            from subprocess import list2cmdline
            os.startfile(str(path),'printto',list2cmdline([printer]))
        else:os.startfile(str(path),"print")
    return path


def export_receipt_pdf(sale_id, destination):
    """Create a paginated, printable receipt without sending a printer job."""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from textwrap import wrap
    path=Path(destination);pdf=canvas.Canvas(str(path),pagesize=A4);pdf.setTitle(f"ToDo ticket {sale_id}")
    y=800;pdf.setFont("Helvetica",10)
    for line in build_receipt(sale_id).splitlines():
        for part in wrap(line,82) or [""]:
            if y<45:pdf.showPage();pdf.setFont("Helvetica",10);y=800
            pdf.drawString(40,y,part);y-=15
    pdf.save();return path
