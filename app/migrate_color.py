import sqlite3
import re

DB_PATH = "products.db"

COLOR_RULES = [
    (10, "венге", "венге"),
    (9, "графит", "графит"), (9, "grafit", "графит"),
    (8, "золотой", "золотой"), (8, "золотистый", "золотой"),
    (8, "серебристый", "серебристый"), (8, "серебро", "серебристый"),
    (7, "шоколадный", "коричневый"), (7, "шоколад", "коричневый"),
    (7, "карамельный", "коричневый"),
    (6, "белый", "белый"),
    (6, "черный", "черный"),
    (5, "коричневый", "коричневый"), (5, "орех", "коричневый"),
    (5, "серый", "серый"), (5, "дымчатый", "серый"),
    (5, "герсбрук", "коричневый"),  # дуб герсбрук — коричневый дуб
    (5, "шервуд", "коричневый"),   # дуб шервуд — тёмный дуб
    (4, "красный", "красный"),
    (4, "синий", "синий"), (4, "голубой", "голубой"),
    (4, "зеленый", "зеленый"),
    (4, "желтый", "желтый"), (4, "солнечный", "желтый"),
    (4, "розовый", "розовый"),
    (4, "фиолетовый", "фиолетовый"),
    (4, "оранжевый", "оранжевый"),
    (4, "вишневый", "красный"),
    (4, "айсберг", "белый"), (4, "альпийский", "светлый"),
    (4, "песочный", "светлый"),
    (3, "светлый", "светлый"),
    (2, "темный", "темный"), (2, "тёмный", "темный"),
    (1, "бежевый", "бежевый"),
    (1, "натуральный", "светлый"),
    (1, "дуб", "коричневый"),      # fallback: любое упоминание дуба
    (1, "сосна", "светлый"),       # fallback: сосна → светлый
    (1, "кляймер", "серый"),      # монтажные клипсы — серый металл
]


def infer_color(text: str) -> str | None:
    if not text:
        return None
    text_lower = text.lower()
    best_priority = 0
    best_color = None
    for priority, keyword, color_value in COLOR_RULES:
        if keyword in text_lower and priority > best_priority:
            best_priority = priority
            best_color = color_value
    return best_color


def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("PRAGMA table_info(floor_covering_specs)")
    cols = {row[1] for row in c.fetchall()}

    if "color" not in cols:
        c.execute("ALTER TABLE floor_covering_specs ADD COLUMN color TEXT")
        print("Added color column")

    # Join with products to also search in product name
    c.execute("""
        SELECT s.id, s.model, s.collection, s.product_type, s.brand, p.name
        FROM floor_covering_specs s
        LEFT JOIN products p ON p.id = s.product_id
    """)
    rows = c.fetchall()

    updated = 0
    for row_id, model, collection, product_type, brand, product_name in rows:
        # Only update if color is currently NULL or 'null' — don't overwrite existing colors
        cur = c.execute("SELECT color FROM floor_covering_specs WHERE id = ?", (row_id,))
        current_color = cur.fetchone()
        if current_color and current_color[0] is not None and str(current_color[0]).lower() != "null":
            continue
        text_parts = []
        for v in (model, collection, product_type, brand, product_name):
            if v and str(v).lower() != "null":
                text_parts.append(str(v))
        text = " ".join(text_parts)
        color = infer_color(text)
        if color:
            c.execute("UPDATE floor_covering_specs SET color = ? WHERE id = ?", (color, row_id))
            updated += 1

    conn.commit()
    conn.close()
    print(f"Updated {updated} / {len(rows)} rows")


if __name__ == "__main__":
    migrate()
