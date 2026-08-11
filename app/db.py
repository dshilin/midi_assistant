import sqlite3
from typing import Dict, List, Optional
from loguru import logger

DB_PATH = "products.db"


def get_conn(db_path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _clean(val):
    if val is None or str(val).lower() == "null":
        return None
    return str(val).replace("ё", "е").replace("Ё", "Е")


COLOR_GROUPS = {
    "темный": ["темный", "черный", "коричневый", "венге", "графит", "вишневый", "шоколадный"],
    "черный": ["черный", "темный", "венге", "графит"],
    "коричневый": ["коричневый", "венге", "шоколадный", "темный", "дуб"],
    "светлый": ["светлый", "белый", "желтый", "золотой", "серебристый", "песочный", "солнечный"],
    "белый": ["белый", "светлый", "серебристый"],
    "серый": ["серый", "графит", "серебристый"],
    "золотой": ["золотой", "желтый", "светлый"],
}


def _expand_colors(colors: List[str]) -> List[str]:
    expanded = set(colors)
    for c in colors:
        if c in COLOR_GROUPS:
            expanded.update(COLOR_GROUPS[c])
    return list(expanded)


def get_products(
    product_type: Optional[str] = None,
    brand: Optional[str] = None,
    color: Optional[str] = None,
    limit: int = 10,
    db_path=None,
    use_stock: bool = True,
) -> List[Dict]:
    product_type = _clean(product_type)
    brand = _clean(brand)
    color = _clean(color)
    logger.debug("db.get_products type={} brand={} color={}", product_type, brand, color)
    conn = get_conn(db_path)
    cursor = conn.cursor()
    stock_join = (
        "INNER JOIN stock st ON st.article = p.article AND st.quantity > 0"
        if use_stock else ""
    )
    stock_expr = "st.quantity" if use_stock else "1"
    query = f"""
        SELECT p.id, p.name, p.price, s.product_type, s.brand, s.collection, s.model, s.color,
               s.length_mm, s.width_mm, s.thickness_mm, s.pieces_per_pack,
               s.area_per_pack_m2, s.packs_per_pallet, s.wear_class,
               {stock_expr} AS stock_quantity
        FROM products p
        {stock_join}
        LEFT JOIN floor_covering_specs s ON p.id = s.product_id
        WHERE 1=1
    """
    params = []

    if product_type:
        raw = product_type.strip()
        # Каждый термин ищем и в product_type, и в названии, в двух регистрах:
        # LIKE в SQLite для кириллицы регистрозависим, поэтому нужен и капитализированный
        # вариант. Помимо полной строки берём отдельные слова ("кварц винил" → "кварц", "винил";
        # "кварцвинил" целиком найдёт "Кварц-виниловое").
        seen = set()
        terms = []
        for t in [raw] + raw.replace('-', ' ').replace(',', ' ').split():
            t = t.strip()
            if len(t) >= 2 and t.lower() not in seen:
                seen.add(t.lower())
                terms.append(t)
        conds = []
        for term in terms:
            cap = term[0].upper() + term[1:]
            for field in ("s.product_type", "p.name"):
                for value in (f"%{term}%", f"%{cap}%"):
                    conds.append(f"{field} LIKE ?")
                    params.append(value)
        if conds:
            query += " AND (" + " OR ".join(conds) + ")"
    if brand:
        query += " AND (s.brand LIKE ? OR s.brand LIKE ?)"
        b = brand.strip()
        capitalized = b[0].upper() + b[1:] if b else b
        params.append(f"%{b}%")
        params.append(f"%{capitalized}%")
    if color:
        colors = COLOR_GROUPS.get(color, [color])
        colors = _expand_colors(colors)
        colors = list(set(colors + [color]))
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


def get_distinct_product_types(db_path=None) -> List[str]:
    try:
        conn = get_conn(db_path)
        cursor = conn.cursor()
        types = set()
        cursor.execute("""
            SELECT DISTINCT s.product_type
            FROM floor_covering_specs s
            INNER JOIN products p ON p.id = s.product_id
            WHERE s.product_type IS NOT NULL
        """)
        types.update(r[0] for r in cursor.fetchall())
        # Also derive types from product names for products without parsed specs
        keywords = {"ламинат": "Ламинат", "линолеум": "Линолеум", "ковролин": "Ковролин",
                     "паркет": "Паркет", "винил": "Винил/SPC", "spc": "Винил/SPC",
                     "пвх": "ПВХ", "террасн": "Террасная доска", "дпк": "ДПК",
                     "кварц": "Кварц-винил", "пробк": "Пробка"}
        for kw, label in keywords.items():
            cursor.execute("""
                SELECT 1 FROM products p
                WHERE LOWER(p.name) LIKE ? LIMIT 1
            """, (f"%{kw}%",))
            if cursor.fetchone():
                types.add(label)
        conn.close()
        result = sorted(types)
        logger.debug("db.get_distinct_product_types found={}", len(result))
        return result
    except Exception as e:
        logger.warning("db.get_distinct_product_types error: {}", e)
        return []


def get_product_by_id(product_id: int, db_path=None, use_stock: bool = True) -> Optional[Dict]:
    logger.debug("db.get_product_by_id id={}", product_id)
    conn = get_conn(db_path)
    cursor = conn.cursor()
    stock_join = (
        "INNER JOIN stock st ON st.article = p.article AND st.quantity > 0"
        if use_stock else ""
    )
    stock_expr = "st.quantity" if use_stock else "1"
    cursor.execute(f"""
        SELECT p.id, p.name, p.price, s.product_type, s.brand, s.collection, s.model, s.color,
               s.length_mm, s.width_mm, s.thickness_mm, s.pieces_per_pack,
               s.area_per_pack_m2, s.packs_per_pallet, s.wear_class,
               {stock_expr} AS stock_quantity
        FROM products p
        {stock_join}
        LEFT JOIN floor_covering_specs s ON p.id = s.product_id
        WHERE p.id = ?
    """, (product_id,))
    row = cursor.fetchone()
    conn.close()
    found = row is not None
    logger.debug("db.get_product_by_id found={}", found)
    return dict(row) if row else None


def calculate_material(area: float, product_id: int, db_path=None, use_stock: bool = True) -> Optional[Dict]:
    area = _clean(area)
    if area is not None:
        try:
            area = float(area)
        except (ValueError, TypeError):
            logger.warning("db.calculate_material invalid area={}", area)
            return None
    product_id = _clean(product_id)
    logger.debug("db.calculate_material area={} product_id={}", area, product_id)
    product = get_product_by_id(product_id, db_path=db_path, use_stock=use_stock)
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
