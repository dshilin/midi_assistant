import sqlite3
from typing import Dict, List, Optional

DB_PATH = "products.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_products(
    product_type: Optional[str] = None,
    brand: Optional[str] = None,
    color: Optional[str] = None,
    limit: int = 5,
) -> List[Dict]:
    conn = get_conn()
    cursor = conn.cursor()
    query = """
        SELECT p.id, p.name, p.price, s.product_type, s.brand, s.collection, s.model,
               s.length_mm, s.width_mm, s.thickness_mm, s.pieces_per_pack,
               s.area_per_pack_m2, s.packs_per_pallet, s.wear_class
        FROM products p
        LEFT JOIN floor_covering_specs s ON p.id = s.product_id
        WHERE 1=1
    """
    params = []

    if product_type:
        query += " AND s.product_type LIKE ?"
        params.append(f"%{product_type}%")
    if brand:
        query += " AND s.brand LIKE ?"
        params.append(f"%{brand}%")
    if color:
        query += " AND (s.collection LIKE ? OR s.model LIKE ?)"
        params.append(f"%{color}%")
        params.append(f"%{color}%")

    query += " LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product_by_id(product_id: int) -> Optional[Dict]:
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.name, p.price, s.product_type, s.brand, s.collection, s.model,
               s.length_mm, s.width_mm, s.thickness_mm, s.pieces_per_pack,
               s.area_per_pack_m2, s.packs_per_pallet, s.wear_class
        FROM products p
        LEFT JOIN floor_covering_specs s ON p.id = s.product_id
        WHERE p.id = ?
    """, (product_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def calculate_material(area: float, product_id: int) -> Optional[Dict]:
    product = get_product_by_id(product_id)
    if not product or not product.get("area_per_pack_m2"):
        return None

    area_per_pack = product["area_per_pack_m2"]
    waste_factor = 1.1
    needed_packs = -(-int(area * waste_factor / area_per_pack) // 1)

    packs = int(area * waste_factor / area_per_pack)
    if packs * area_per_pack < area:
        packs += 1

    return {
        "product": product["name"],
        "area_m2": area,
        "area_per_pack_m2": area_per_pack,
        "packs_needed": packs,
        "total_area_with_waste": round(area * waste_factor, 2),
        "waste_factor": waste_factor,
    }
