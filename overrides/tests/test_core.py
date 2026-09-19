import os, tempfile, shutil, sys
from pathlib import Path

TMP=Path(tempfile.mkdtemp())/"test.db"
os.environ["TODO_DB_PATH"]=str(TMP)
BASE=Path(__file__).resolve().parents[1]/"todo"
sys.path.insert(0,str(BASE))

from database import init_db,connect
from services.bootstrap import ensure_defaults
from services.cash import open_session, close_session
from services.sales import complete_sale, create_return
from services.purchases import receive_purchase
from services.money import to_cents

def main():
    init_db();ensure_defaults()
    with connect() as c:
        uid=c.execute("SELECT id FROM users WHERE username='admin'").fetchone()["id"]
        cat=c.execute("SELECT id FROM categories WHERE name='Général'").fetchone()["id"]
        cur=c.execute("INSERT INTO products(name,category_id,purchase_price_cents,sale_price_cents,stock_qty) VALUES(?,?,?,?,?)",
                      ("Test Product",cat,300,500,0));pid=cur.lastrowid
        c.execute("INSERT INTO product_barcodes(product_id,barcode) VALUES(?,?)",(pid,"123"))
        c.execute("INSERT INTO quantity_prices(product_id,min_qty,unit_price_cents) VALUES(?,?,?)",(pid,2,450))
        c.commit()
    pur,total=receive_purchase(None,"F1",[dict(product_id=pid,qty=10,unit_cost_cents=300)])
    sid=open_session(uid,to_cents("100"))
    sale=complete_sale(sid,uid,[dict(product_id=pid,qty=2,unit_price_cents=450)],"CASH",to_cents("20"))
    assert sale["total_cents"]==900
    with connect() as c:
        stock=c.execute("SELECT stock_qty FROM products WHERE id=?",(pid,)).fetchone()["stock_qty"]
        line=c.execute("SELECT id FROM sale_items WHERE sale_id=?",(sale["id"],)).fetchone()["id"]
    assert abs(stock-8)<1e-9
    ret=create_return(sale["id"],sid,uid,[(line,1)],"test")
    assert ret["total_cents"]==450

    # Distinct unit/carton barcodes: carton barcode adds 6 base units but costs one pack price.
    with connect() as c:
        cur=c.execute("INSERT INTO products(name,category_id,purchase_price_cents,sale_price_cents,stock_qty) VALUES(?,?,?,?,?)",
                      ("Pack Product",cat,200,500,24));pack_pid=cur.lastrowid
        unit_bid=c.execute("INSERT INTO product_barcodes(product_id,barcode,qty_multiplier) VALUES(?,?,?)",
                           (pack_pid,"UNIT-001",1)).lastrowid
        carton_bid=c.execute("INSERT INTO product_barcodes(product_id,barcode,qty_multiplier,price_override_cents) VALUES(?,?,?,?)",
                             (pack_pid,"CARTON-006",6,2500)).lastrowid
        c.commit()
    pack_sale=complete_sale(sid,uid,[dict(product_id=pack_pid,qty=6,barcode_id=carton_bid)],"CASH",to_cents("25"))
    assert pack_sale["total_cents"]==2500
    with connect() as c:
        prow=c.execute("SELECT stock_qty FROM products WHERE id=?",(pack_pid,)).fetchone()
        pline=c.execute("SELECT * FROM sale_items WHERE sale_id=?",(pack_sale["id"],)).fetchone()
    assert abs(prow["stock_qty"]-18)<1e-9
    assert pline["barcode_used"]=="CARTON-006"
    assert pline["pricing_mode"]=="PACK"
    assert abs(pline["qty_multiplier"]-6)<1e-9
    assert pline["unit_price_cents"]==2500
    assert pline["line_total_cents"]==2500

    two_cartons=complete_sale(sid,uid,[dict(product_id=pack_pid,qty=12,barcode_id=carton_bid)],"CASH",to_cents("50"))
    assert two_cartons["total_cents"]==5000
    with connect() as c:
        prow=c.execute("SELECT stock_qty FROM products WHERE id=?",(pack_pid,)).fetchone()
    assert abs(prow["stock_qty"]-6)<1e-9
    with connect() as c:
        stock=c.execute("SELECT stock_qty FROM products WHERE id=?",(pid,)).fetchone()["stock_qty"]
    assert abs(stock-9)<1e-9
    expected,diff,t=close_session(sid,to_cents("179.50"))
    assert diff==0
    print("CORE TESTS PASSED")
    shutil.rmtree(TMP.parent,ignore_errors=True)

if __name__=="__main__":
    main()
