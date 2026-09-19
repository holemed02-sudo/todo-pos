from contextlib import contextmanager
from database import connect


@contextmanager
def _connection(conn=None):
    """Reuse a caller transaction when supplied; otherwise own a short read connection."""
    if conn is not None:
        yield conn
        return
    with connect() as owned:
        yield owned


def resolve_line_price(product_id, qty, barcode_id=None, conn=None):
    """
    Resolve a sale line using base-stock quantity.

    Unit barcode / product card:
      line_total = unit price * base quantity.

    Pack/carton barcode with price_override_cents:
      qty_multiplier is the number of base units in one pack and the override is
      the price of ONE pack, not the price of each base unit.
    """
    qty = float(qty)
    if qty <= 0:
        raise ValueError("Quantité invalide")

    with _connection(conn) as c:
        p = c.execute(
            "SELECT sale_price_cents FROM products WHERE id=? AND active=1",
            (product_id,),
        ).fetchone()
        if not p:
            raise ValueError("Article introuvable")

        multiplier = 1.0
        override = None
        barcode = ""
        if barcode_id:
            b = c.execute(
                """
                SELECT barcode, qty_multiplier, price_override_cents
                FROM product_barcodes
                WHERE id=? AND product_id=?
                """,
                (barcode_id, product_id),
            ).fetchone()
            if not b:
                raise ValueError("Barcode introuvable")
            barcode = b["barcode"] or ""
            multiplier = float(b["qty_multiplier"] or 1)
            if multiplier <= 0:
                raise ValueError("Multiplicateur barcode invalide")
            override = b["price_override_cents"]

        if override is not None:
            pack_count = qty / multiplier
            rounded = round(pack_count)
            if abs(pack_count - rounded) > 1e-9:
                raise ValueError("La quantité doit respecter le pack/carton")
            line_total = int(override) * int(rounded)
            return {
                "unit_price_cents": int(override),
                "line_total_cents": int(line_total),
                "qty_multiplier": multiplier,
                "pricing_mode": "PACK",
                "barcode": barcode,
            }

        rule = c.execute(
            """
            SELECT unit_price_cents
            FROM quantity_prices
            WHERE product_id=? AND active=1 AND min_qty<=?
            ORDER BY min_qty DESC
            LIMIT 1
            """,
            (product_id, qty),
        ).fetchone()
        unit = int(rule["unit_price_cents"] if rule else p["sale_price_cents"])
        return {
            "unit_price_cents": unit,
            "line_total_cents": int(round(unit * qty)),
            "qty_multiplier": multiplier,
            "pricing_mode": "UNIT",
            "barcode": barcode,
        }


def resolve_unit_price(product_id, qty, barcode_id=None, conn=None):
    """Compatibility helper. For a pack barcode this is the price of one pack."""
    return resolve_line_price(product_id, qty, barcode_id, conn)["unit_price_cents"]
