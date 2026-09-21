"""Build an optional demo alongside the executable, never seed the shop database."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'todo'))
import database
from services.bootstrap import ensure_defaults
from services.security import current_user
from services.inventory import apply_stock_movement
from services.clients import save_client
from services.cash import open_session
from PIL import Image,ImageDraw

root=Path(sys.argv[1]).resolve()
database.DB_PATH=root/'demo'/'demo.db'
if database.DB_PATH.exists():raise SystemExit('Refusing to overwrite an existing demo database')
database.init_db();ensure_defaults()
with database.connect() as conn:
    uid=conn.execute('SELECT id FROM users').fetchone()[0]
current_user.set(uid)
for name,price,color,family,barcode in [
    ('Riz TEST',1200,'#2563EB','Epicerie','990001'),
    ('Croquettes TEST',1500,'#16A34A','Animaux',''),
    ('Produit TEST 5 DH',500,'#F59E0B','Epicerie',''),
]:
    rel=''
    if not barcode:
        rel=f'assets/demo/{price}.png'
        dest=root/'todo'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        im=Image.new('RGB',(240,180),color);draw=ImageDraw.Draw(im)
        draw.text((20,45),'DEMO',fill='white',font_size=32)
        draw.text((20,100),f'{price//100} DH',fill='white',font_size=32);im.save(dest)
    with database.connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('INSERT OR IGNORE INTO categories(name) VALUES(?)',(family,))
        cat=conn.execute('SELECT id FROM categories WHERE name=?',(family,)).fetchone()[0]
        pid=conn.execute('INSERT INTO products(name,category_id,purchase_price_cents,sale_price_cents,image_path) VALUES(?,?,?,?,?)',(name,cat,price//2,price,rel)).lastrowid
        if barcode:conn.execute('INSERT INTO product_barcodes(product_id,barcode) VALUES(?,?)',(pid,barcode))
        apply_stock_movement(conn,pid,5,'OPENING',note='DEMO',user_id=uid)
save_client('Client TEST','0600000000')
database.set_setting('shop_name','ToDo - DEMO')
database.set_setting('print_mode','never')
open_session(uid,10000)
(root/'TEST_TODO.bat').write_text('@echo off\nsetlocal\nset "TODO_DB_PATH=%~dp0demo\\demo.db"\nstart "" "%~dp0ToDo.exe"\n',encoding='ascii')
print('Optional demo created:',database.DB_PATH)
