import sys,tempfile,time,json,statistics
from pathlib import Path
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
import database as db
from services.bootstrap import ensure_defaults
from services.security import current_user
from services.cash import open_session
from services.sales import complete_sale
from services.catalog import search_products,scan_barcode
from services.pricing import resolve_unit_price

tmp=tempfile.TemporaryDirectory()
db.DB_PATH=Path(tmp.name)/'benchmark.db'
start=time.perf_counter();db.init_db();ensure_defaults();cold_init=(time.perf_counter()-start)*1000
with db.connect() as c:
 uid=c.execute('SELECT id FROM users LIMIT 1').fetchone()[0]
 c.executemany('INSERT INTO products(id,name,sku,alias,supplier_code,sale_price_cents,stock_qty) VALUES(?,?,?,?,?,1200,1000)',[(i,f'Article Maroc {i:06}',f'REF{i:06}',f'Alias{i:06}',f'SUP{i:06}') for i in range(1,100001)])
 c.executemany('INSERT INTO product_barcodes(product_id,barcode) VALUES(?,?)',[(i,f'200{i:010}') for i in range(1,100001)])
current_user.set(uid);sid=open_session(uid,0)
def timing(fn,n=12):
 values=[]
 for _ in range(n):
  start=time.perf_counter();fn();values.append((time.perf_counter()-start)*1000)
 return {'median_ms':round(statistics.median(values),2),'max_ms':round(max(values),2)}
result={'products':100000,'fresh_database_init_ms':round(cold_init,2)}
for name,query in [('exact_reference','REF050000'),('substring_name','Maroc 050'),('alias','Alias050000'),('barcode','2000000050000'),('short_query','Ma')]:
 result[name]=timing(lambda q=query:search_products(q))
result['scan_lookup']=timing(lambda:scan_barcode('2000000050000'))
cart=[dict(product_id=i,qty=1,unit_price_cents=1200) for i in range(1,101)]
result['commit_100_items']=timing(lambda:complete_sale(sid,uid,cart,'CASH',120000),5)
result['notes']='Local synthetic database; includes connect/query or commit, excludes rendering, scanner hardware, printer and full application startup. Short search uses LIKE fallback.'
print(json.dumps(result,indent=2))
(Path.cwd()/'benchmark_results.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
tmp.cleanup()
