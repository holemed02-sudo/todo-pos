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
        return start.isoformat(), end.isoformat(), [d.strftime('%-d') for d in days]
    if period == 'year':
        months = []
        for m in range(1, 13):
            months.append(datetime.date(today.year, m, 1).strftime('%b'))
        return f'{today.year}-01-01', f'{today.year}-12-31', months
    # default: today only
    return today.isoformat(), today.isoformat(), [today.strftime('%H:00')]


def sales_evolution(period='month'):
    """Daily/monthly sales totals for bar chart."""
    from_d, to_d, labels = _date_range(period)
    with connect() as conn:
        if period == 'year':
            rows = conn.execute("""
                SELECT strftime('%m', created_at, 'localtime') mon,
                       COALESCE(SUM(total_cents),0) total
                FROM sales WHERE status='COMPLETED'
                  AND date(created_at,'localtime') BETWEEN ? AND ?
                GROUP BY mon ORDER BY mon
            """, (from_d, to_d)).fetchall()
            by_key = {r['mon']: r['total'] for r in rows}
            values = [by_key.get(f'{m:02d}', 0) for m in range(1, 13)]
        else:
            rows = conn.execute("""
                SELECT date(created_at,'localtime') day,
                       COALESCE(SUM(total_cents),0) total
                FROM sales WHERE status='COMPLETED'
                  AND date(created_at,'localtime') BETWEEN ? AND ?
                GROUP BY day ORDER BY day
            """, (from_d, to_d)).fetchall()
            by_key = {r['day']: r['total'] for r in rows}
            import datetime as dt
            start = dt.date.fromisoformat(from_d)
            end   = dt.date.fromisoformat(to_d)
            values = []
            cur = start
            while cur <= end:
                values.append(by_key.get(cur.isoformat(), 0))
                cur += dt.timedelta(days=1)
    return labels, values


def top_products(limit=10, period='month'):
    """Top selling products by revenue."""
    from_d, to_d, _ = _date_range(period)
    with connect() as conn:
        rows = conn.execute("""
            SELECT p.name, COALESCE(SUM(si.qty),0) qty,
                   COALESCE(SUM(si.line_total_cents),0) revenue
            FROM sale_items si
            JOIN sales s   ON s.id  = si.sale_id
            JOIN products p ON p.id = si.product_id
            WHERE s.status='COMPLETED'
              AND date(s.created_at,'localtime') BETWEEN ? AND ?
            GROUP BY si.product_id ORDER BY revenue DESC LIMIT ?
        """, (from_d, to_d, limit)).fetchall()
    return [dict(r) for r in rows]


def top_cashiers(period='month'):
    """Top cashiers by sales count."""
    from_d, to_d, _ = _date_range(period)
    with connect() as conn:
        rows = conn.execute("""
            SELECT u.display_name name,
                   COUNT(*) tickets,
                   COALESCE(SUM(s.total_cents),0) revenue
            FROM sales s JOIN users u ON u.id=s.cashier_user_id
            WHERE s.status='COMPLETED'
              AND date(s.created_at,'localtime') BETWEEN ? AND ?
            GROUP BY s.cashier_user_id ORDER BY revenue DESC LIMIT 10
        """, (from_d, to_d)).fetchall()
    return [dict(r) for r in rows]


def category_breakdown(period='month'):
    """Sales by category for pie/bar."""
    from_d, to_d, _ = _date_range(period)
    with connect() as conn:
        rows = conn.execute("""
            SELECT COALESCE(c.name,'Sans famille') name,
                   COALESCE(SUM(si.line_total_cents),0) revenue
            FROM sale_items si
            JOIN sales s    ON s.id   = si.sale_id
            JOIN products p ON p.id   = si.product_id
            LEFT JOIN categories c ON c.id = p.category_id
            WHERE s.status='COMPLETED'
              AND date(s.created_at,'localtime') BETWEEN ? AND ?
            GROUP BY p.category_id ORDER BY revenue DESC LIMIT 8
        """, (from_d, to_d)).fetchall()
    return [dict(r) for r in rows]
