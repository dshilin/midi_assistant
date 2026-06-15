import sqlite3
from typing import Dict, List, Optional
from loguru import logger

DB_PATH = "products.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _clean(val):
    if val is None or str(val).lower() == "null":
        return None
    return val


COLOR_GROUPS = {
    "темный": ["темный", "черный", "коричневый", "венге", "графит", "вишневый", "шоколадный"],
    "черный": ["черный", "темный", "венге", "графит"],
    "коричневый": ["коричневый", "венге", "шоколадный", "темный"],
    "светлый": ["светлый", "белый", "желтый", "золотой", "серебристый"],
    "белый": ["белый", "светлый", "серебристый"],
    "серый": ["серый", "графит", "серебристый"],
    "золотой": ["золотой", "желтый", "светлый"],
}


def get_products(
    product_type: Optional[str] = None,
    brand: Optional[str] = None,
    color: Optional[str] = None,
    limit: int = 10,
) -> List[Dict]:
    product_type = _clean(product_type)
    brand = _clean(brand)
    color = _clean(color)
    logger.debug("db.get_products type={} brand={} color={}", product_type, brand, color)
    conn = get_conn()
    cursor = conn.cursor()
    query = """
        SELECT p.id, p.name, p.price, s.product_type, s.brand, s.collection, s.model, s.color,
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
        colors = set(COLOR_GROUPS.get(color, [color]))
        colors.add(color)
        placeholders = " OR ".join(["s.color LIKE ?" for _ in colors])
        query += f" AND ({placeholders})"
        params.extend([f"%{c}%" for c in colors])

    query += " LIMIT ?"
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    logger.debug("db.get_products found={}", len(result))
    return result


def get_product_by_id(product_id: int) -> Optional[Dict]:
    logger.debug("db.get_product_by_id id={}", product_id)
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT p.id, p.name, p.price, s.product_type, s.brand, s.collection, s.model, s.color,
               s.length_mm, s.width_mm, s.thickness_mm, s.pieces_per_pack,
               s.area_per_pack_m2, s.packs_per_pallet, s.wear_class
        FROM products p
        LEFT JOIN floor_covering_specs s ON p.id = s.product_id
        WHERE p.id = ?
    """, (product_id,))
    row = cursor.fetchone()
    conn.close()
    found = row is not None
    logger.debug("db.get_product_by_id found={}", found)
    return dict(row) if row else None


def calculate_material(area: float, product_id: int) -> Optional[Dict]:
    area = _clean(area)
    product_id = _clean(product_id)
    logger.debug("db.calculate_material area={} product_id={}", area, product_id)
    product = get_product_by_id(product_id)
    if not product:
        logger.warning("db.calculate_material product not found id={}", product_id)
        return None

    area_per_pack = product.get("area_per_pack_m2")
    if not area_per_pack:
        logger.warning("db.calculate_material no area_per_pack for product id={}", product_id)
        return None

    waste_factor = 1.1
    packs = int(area * waste_factor / area_per_pack)
    if packs * area_per_pack < area:
        packs += 1

    result = {
        "product": product["name"],
        "area_m2": area,
        "area_per_pack_m2": area_per_pack,
        "packs_needed": packs,
        "total_area_with_waste": round(area * waste_factor, 2),
        "waste_factor": waste_factor,
    }
    logger.info("db.calculate_material product={} area={} packs={}", product["name"], area, packs)
    return result
