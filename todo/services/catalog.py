from database import connect, get_setting


def search_products(query='', category=None, limit=None):
    query=query.strip()
    with connect() as conn:
        limit=max(1,min(200,int(limit or get_setting('search_limit','60',conn))))
        args=[]
        where='p.active=1'
        if category is not None:
            where+=' AND p.category_id=?';args.append(category)
        if not query:
            return conn.execute(f'SELECT p.* FROM products p WHERE {where} ORDER BY p.name LIMIT ?',(*args,limit)).fetchall()
        exact=conn.execute(f'''SELECT DISTINCT p.* FROM products p NOT INDEXED
            WHERE {where} AND p.id IN (SELECT id FROM products WHERE sku=? UNION SELECT product_id FROM product_barcodes WHERE barcode=?)
            ORDER BY p.name LIMIT ?''',(*args,query,query,limit)).fetchall()
        if exact:return exact
        fts=conn.execute("SELECT 1 FROM sqlite_master WHERE name='product_search'").fetchone()
        if fts and len(query)>=3:
            match='"'+query.replace('"','""')+'"'
            rows=conn.execute(f'''SELECT p.* FROM products p NOT INDEXED WHERE {where}
                AND p.id IN (SELECT rowid FROM product_search WHERE product_search MATCH ?
                     UNION SELECT product_id FROM product_barcodes WHERE barcode LIKE ? ESCAPE '\\')
                ORDER BY p.name LIMIT ?''',(*args,match,_pattern(query),limit)).fetchall()
        else:
            pattern=_pattern(query)
            rows=conn.execute(f'''SELECT p.* FROM products p WHERE {where} AND
                (p.name LIKE ? ESCAPE '\\' OR p.sku LIKE ? ESCAPE '\\' OR p.alias LIKE ? ESCAPE '\\'
                 OR p.supplier_code LIKE ? ESCAPE '\\' OR p.id IN
                 (SELECT product_id FROM product_barcodes WHERE barcode LIKE ? ESCAPE '\\'))
                 ORDER BY p.name LIMIT ?''',(*args,*([pattern]*5),limit)).fetchall()
        ids={r['id'] for r in exact}
        return (list(exact)+[r for r in rows if r['id'] not in ids])[:limit]


def _pattern(q):
    return '%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'


def scan_barcode(code):
    with connect() as conn:
        return conn.execute('''SELECT p.*,b.id barcode_id,b.qty_multiplier,b.barcode
            FROM product_barcodes b JOIN products p ON p.id=b.product_id
            WHERE b.barcode=? AND p.active=1 ORDER BY p.name''',(code,)).fetchall()
