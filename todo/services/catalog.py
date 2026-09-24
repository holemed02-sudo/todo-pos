from database import connect, get_setting


def search_products(query='', category=None, limit=None, images_only=False, offset=0):
    query = query.strip()
    with connect() as conn:
        limit = max(1, min(1000, int(limit or get_setting('search_limit', '60', conn))))
        args  = []
        # Multi-category: filter via product_categories junction table
        if category is not None:
            cat_filter = (
                'AND p.id IN (SELECT product_id FROM product_categories WHERE category_id=?)'
            )
            args.append(category)
        else:
            cat_filter = ''

        if images_only:cat_filter+=" AND trim(p.image_path)<>''"
        offset=max(0,int(offset))
        if not query:
            return conn.execute(
                f'SELECT p.* FROM products p WHERE p.active=1 {cat_filter} ORDER BY p.name,p.id LIMIT ? OFFSET ?',
                (*args, limit, offset)
            ).fetchall()

        # Exact barcode / SKU first
        exact = conn.execute(f'''
            SELECT DISTINCT p.* FROM products p NOT INDEXED
            WHERE p.active=1 {cat_filter}
              AND p.id IN (SELECT id FROM products WHERE sku=?
                           UNION SELECT product_id FROM product_barcodes WHERE barcode=?)
            ORDER BY p.name,p.id LIMIT ? OFFSET ?
        ''', (*args, query, query, limit, offset)).fetchall()
        if exact:
            return exact

        fts = conn.execute("SELECT 1 FROM sqlite_master WHERE name='product_search'").fetchone()
        if fts and len(query) >= 3:
            match = '"' + query.replace('"', '""')+'"' 
            rows = conn.execute(f'''
                SELECT p.* FROM products p NOT INDEXED
                WHERE p.active=1 {cat_filter}
                  AND p.id IN (
                      SELECT rowid FROM product_search WHERE product_search MATCH ?
                      UNION SELECT product_id FROM product_barcodes WHERE barcode LIKE ? ESCAPE '\\'
                  )
                ORDER BY p.name,p.id LIMIT ? OFFSET ?
            ''', (*args, match, _pattern(query), limit, offset)).fetchall()
        else:
            pattern = _pattern(query)
            rows = conn.execute(f'''
                SELECT p.* FROM products p
                WHERE p.active=1 {cat_filter}
                  AND (p.name LIKE ? ESCAPE '\\'
                    OR p.sku  LIKE ? ESCAPE '\\'
                    OR p.alias LIKE ? ESCAPE '\\'
                    OR p.supplier_code LIKE ? ESCAPE '\\'
                    OR p.id IN (SELECT product_id FROM product_barcodes WHERE barcode LIKE ? ESCAPE '\\'))
                ORDER BY p.name,p.id LIMIT ? OFFSET ?
            ''', (*args, *([pattern]*5), limit, offset)).fetchall()

        ids = {r['id'] for r in exact}
        return (list(exact) + [r for r in rows if r['id'] not in ids])[:limit]


def _pattern(q):
    escape = chr(92)
    return '%' + q.replace(escape, escape*2).replace('%', escape+'%').replace('_', escape+'_') + '%'


def scan_barcode(code):
    with connect() as conn:
        return conn.execute('''
            SELECT p.*, b.id barcode_id, b.qty_multiplier, b.barcode
            FROM product_barcodes b JOIN products p ON p.id = b.product_id
            WHERE b.barcode=? AND p.active=1 ORDER BY p.name
        ''', (code,)).fetchall()


def list_categories():
    """Return all active categories with color and icon."""
    with connect() as conn:
        return conn.execute(
            'SELECT id, name, color, icon FROM categories WHERE active=1 ORDER BY sort_order, name'
        ).fetchall()


def get_product_categories(product_id):
    """Return list of category ids assigned to a product."""
    with connect() as conn:
        return [r['category_id'] for r in conn.execute(
            'SELECT category_id FROM product_categories WHERE product_id=?',
            (product_id,)
        ).fetchall()]


def set_product_categories(conn, product_id, category_ids):
    """Replace all category assignments for a product (within open transaction)."""
    category_ids=list(dict.fromkeys(category_ids))
    conn.execute('UPDATE products SET category_id=? WHERE id=?',
                 (category_ids[0] if category_ids else None, product_id))
    conn.execute('DELETE FROM product_categories WHERE product_id=?', (product_id,))
    conn.executemany('INSERT INTO product_categories(product_id,category_id) VALUES(?,?)',
                     [(product_id,cid) for cid in category_ids])
