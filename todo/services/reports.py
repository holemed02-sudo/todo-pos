from database import connect
from services.money import rounded


def today_summary():
    with connect() as conn:
        sale=conn.execute("SELECT COALESCE(SUM(total_cents),0),COUNT(*) FROM sales WHERE status='COMPLETED' AND date(created_at,'localtime')=date('now','localtime')").fetchone()
        cost=conn.execute("SELECT COALESCE(SUM(si.cost_price_cents*si.qty),0) FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.status='COMPLETED' AND date(s.created_at,'localtime')=date('now','localtime')").fetchone()[0]
        refund=conn.execute("SELECT COALESCE(SUM(total_cents),0) FROM returns WHERE date(created_at,'localtime')=date('now','localtime')").fetchone()[0]
        recovered=conn.execute("SELECT COALESCE(SUM(si.cost_price_cents*ri.qty),0) FROM return_items ri JOIN returns r ON r.id=ri.return_id JOIN sale_items si ON si.id=ri.sale_item_id WHERE date(r.created_at,'localtime')=date('now','localtime')").fetchone()[0]
        alerts=conn.execute('SELECT COUNT(*) FROM products WHERE active=1 AND stock_qty<=alert_qty').fetchone()[0]
        held=conn.execute('SELECT COUNT(*) FROM held_sales').fetchone()[0]
        recent=conn.execute("SELECT sale_no document,total_cents amount,created_at,'Vente' kind FROM sales UNION ALL SELECT return_no,-total_cents,created_at,'Retour' FROM returns ORDER BY created_at DESC LIMIT 12").fetchall()
        return dict(net_sales=sale[0]-refund,gross_margin=rounded(sale[0]-cost-refund+recovered),tickets=sale[1],alerts=alerts,held=held,refunds=refund,recent=recent)
