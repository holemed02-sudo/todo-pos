from database import connect
from services.money import rounded
import datetime


def today_summary():
    with connect() as conn:
        sale     = conn.execute("SELECT COALESCE(SUM(total_cents),0),COUNT(*) FROM sales WHERE status='COMPLETED' AND date(created_at,'localtime')=date('now','localtime')").fetchone()
        cost     = conn.execute("SELECT COALESCE(SUM(si.cost_price_cents*si.qty),0) FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.status='COMPLETED' AND date(s.created_at,'localtime')=date('now','localtime')").fetchone()[0]
        refund   = conn.execute("SELECT COALESCE(SUM(total_cents),0) FROM returns WHERE date(created_at,'localtime')=date('now','localtime')").fetchone()[0]
        recovered= conn.execute("SELECT COALESCE(SUM(si.cost_price_cents*ri.qty),0) FROM return_items ri JOIN returns r ON r.id=ri.return_id JOIN sale_items si ON si.id=ri.sale_item_id WHERE date(r.created_at,'localtime')=date('now','localtime')").fetchone()[0]
        alerts   = conn.execute("SELECT COUNT(*) FROM products WHERE active=1 AND stock_qty<=alert_qty").fetchone()[0]
        held     = conn.execute("SELECT COUNT(*) FROM held_sales").fetchone()[0]
        recent   = conn.execute("SELECT sale_no document,total_cents amount,created_at,'Vente' kind FROM sales UNION ALL SELECT return_no,-total_cents,created_at,'Retour' FROM returns ORDER BY created_at DESC LIMIT 12").fetchall()
        return dict(net_sales=sale[0]-refund, gross_margin=rounded(sale[0]-cost-refund+recovered),
                    tickets=sale[1], alerts=alerts, held=held, refunds=refund, recent=recent)


def _date_range(period):
    """Return (from_date, to_date, label_list) for a given period key."""
    today = datetime.date.today()
    if period == 'week':
        start = today - datetime.timedelta(days=6)
        days  = [(start + datetime.timedelta(i)) for i in range(7)]
        return start.isoformat(), today.isoformat(), [d.strftime('%a') for d in days]
    if period == 'month':
        start = today.replace(day=1)
        end   = today
        days  = [(start + datetime.timedelta(i)) for i in range((end - start).days + 1)]
        return start.isoformat(), end.isoformat(), [str(d.day) for d in days]
    if period == 'year':
        months = []
        for m in range(1, 13):
            months.append(datetime.date(today.year, m, 1).strftime('%b'))
        return f'{today.year}-01-01', f'{today.year}-12-31', months
    # default: today only
    return today.isoformat(), today.isoformat(), [today.strftime('%H:00')]


# Net revenue is recognized on sale/return date; categories use the primary family
# so a product assigned to several families is never counted twice.
EVENTS = """WITH events AS (
 SELECT si.product_id, si.name_snapshot name, p.category_id,
        s.cashier_user_id, s.created_at, si.qty,
        COALESCE(si.net_total_cents,si.line_total_cents) revenue,
        si.cost_price_cents*si.qty cost
 FROM sale_items si JOIN sales s ON s.id=si.sale_id
 LEFT JOIN products p ON p.id=si.product_id WHERE s.status='COMPLETED'
 UNION ALL
 SELECT ri.product_id,si.name_snapshot,p.category_id,s.cashier_user_id,
        r.created_at,-ri.qty,-ri.line_total_cents,-si.cost_price_cents*ri.qty
 FROM return_items ri JOIN returns r ON r.id=ri.return_id
 JOIN sale_items si ON si.id=ri.sale_item_id JOIN sales s ON s.id=si.sale_id
 LEFT JOIN products p ON p.id=ri.product_id
), period_events AS (
 SELECT * FROM events WHERE date(created_at,'localtime') BETWEEN ? AND ?
) """

def period_summary(period='month'):
    start,end,_=_date_range(period)
    with connect() as c:
        row=c.execute(EVENTS+'SELECT COALESCE(SUM(revenue),0),COALESCE(SUM(cost),0) FROM period_events',(start,end)).fetchone()
        tickets=c.execute("SELECT COUNT(*) FROM sales WHERE status='COMPLETED' AND date(created_at,'localtime') BETWEEN ? AND ?",(start,end)).fetchone()[0]
        alerts=c.execute('SELECT COUNT(*) FROM products WHERE active=1 AND stock_qty<=alert_qty').fetchone()[0]
    return dict(net_sales=row[0],gross_margin=rounded(row[0]-row[1]),tickets=tickets,alerts=alerts)

def sales_evolution(period='month'):
    start,end,labels=_date_range(period)
    key="strftime('%m',created_at,'localtime')" if period=='year' else "date(created_at,'localtime')"
    with connect() as c:
        rows=c.execute(EVENTS+f'SELECT {key} bucket,SUM(revenue) total FROM period_events GROUP BY bucket',(start,end)).fetchall()
    totals={r['bucket']:r['total'] for r in rows}
    keys=([f'{m:02d}' for m in range(1,13)] if period=='year' else
          [(datetime.date.fromisoformat(start)+datetime.timedelta(days=i)).isoformat() for i in range(len(labels))])
    return labels,[totals.get(k,0) for k in keys]

def top_products(limit=10,period='month'):
    start,end,_=_date_range(period)
    with connect() as c:
        rows=c.execute(EVENTS+"SELECT name,SUM(qty) qty,SUM(revenue) revenue FROM period_events GROUP BY product_id,name ORDER BY revenue DESC LIMIT ?",(start,end,limit)).fetchall()
    return [dict(r) for r in rows]

def top_cashiers(period='month'):
    start,end,_=_date_range(period)
    with connect() as c:
        rows=c.execute(EVENTS+"""SELECT u.display_name name,SUM(e.revenue) revenue,
           (SELECT COUNT(*) FROM sales s WHERE s.cashier_user_id=u.id AND s.status='COMPLETED'
            AND date(s.created_at,'localtime') BETWEEN ? AND ?) tickets
           FROM period_events e JOIN users u ON u.id=e.cashier_user_id
           GROUP BY u.id ORDER BY revenue DESC LIMIT 10""",(start,end,start,end)).fetchall()
    return [dict(r) for r in rows]

def category_breakdown(period='month'):
    start,end,_=_date_range(period)
    with connect() as c:
        rows=c.execute(EVENTS+"""SELECT COALESCE(c.name,'Sans famille') name,SUM(e.revenue) revenue
            FROM period_events e LEFT JOIN categories c ON c.id=e.category_id
            GROUP BY e.category_id ORDER BY revenue DESC LIMIT 8""",(start,end)).fetchall()
    return [dict(r) for r in rows]


def journal_tickets(start, end):
    """Ticket-level detail for the Journal screen, filtered to an explicit
    [start, end] date range (inclusive, local time)."""
    with connect() as c:
        rows = c.execute("""
            SELECT s.id, s.sale_no, s.created_at, u.display_name, s.payment_method,
              s.total_cents-COALESCE((SELECT SUM(r.total_cents) FROM returns r WHERE r.sale_id=s.id),0) total_cents,
              COALESCE((SELECT SUM(si.cost_price_cents*si.qty) FROM sale_items si WHERE si.sale_id=s.id),0)
              -COALESCE((SELECT SUM(ri.qty*si.cost_price_cents) FROM return_items ri JOIN sale_items si ON si.id=ri.sale_item_id WHERE si.sale_id=s.id),0) cost
            FROM sales s JOIN users u ON u.id=s.cashier_user_id
            WHERE date(s.created_at,'localtime') BETWEEN ? AND ?
            ORDER BY s.id DESC LIMIT 5000""", (start, end)).fetchall()
    return [dict(r) for r in rows]


def journal_by_family(start, end):
    with connect() as c:
        rows = c.execute(EVENTS + """
            SELECT COALESCE(cat.name,'Sans famille') name, SUM(e.qty) qty, SUM(e.revenue) revenue
            FROM period_events e LEFT JOIN categories cat ON cat.id=e.category_id
            GROUP BY e.category_id ORDER BY revenue DESC""", (start, end)).fetchall()
    return [dict(r) for r in rows]


def journal_by_article(start, end):
    with connect() as c:
        rows = c.execute(EVENTS + """
            SELECT name, SUM(qty) qty, SUM(revenue) revenue
            FROM period_events GROUP BY product_id, name ORDER BY revenue DESC""", (start, end)).fetchall()
    return [dict(r) for r in rows]


def journal_by_day(start, end):
    with connect() as c:
        rows = c.execute(EVENTS + """
            SELECT date(created_at,'localtime') day, SUM(revenue) revenue
            FROM period_events GROUP BY day ORDER BY day""", (start, end)).fetchall()
        tickets = c.execute("""
            SELECT date(created_at,'localtime') day, COUNT(*) tickets
            FROM sales WHERE status='COMPLETED' AND date(created_at,'localtime') BETWEEN ? AND ?
            GROUP BY day""", (start, end)).fetchall()
    ticket_by_day = {r['day']: r['tickets'] for r in tickets}
    return [dict(day=r['day'], revenue=r['revenue'], tickets=ticket_by_day.get(r['day'], 0)) for r in rows]



