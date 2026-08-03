"""Загрузка остатков со склада (выгрузка 1С в .xlsx) в таблицу stock.

Колонки по умолчанию: A — артикул, C — номенклатура, G — ед. изм., K — конечный
остаток. Для клиента можно передать свои col_*.
"""
import sqlite3
import sys

from app import xlsx

DB_PATH = "products.db"


def _read_rows(xlsx_path: str, col_article="A", col_name="C", col_unit="G", col_qty="K"):
    """Вернуть список (article, name, unit, quantity) из первого листа."""
    rows = []
    for cells in xlsx.read_first_sheet_rows(xlsx_path):
        article = (cells.get(col_article) or "").strip()
        name = (cells.get(col_name) or "").strip()
        unit = (cells.get(col_unit) or "").strip()
        qty_raw = (cells.get(col_qty) or "").strip()
        # Строки данных: есть артикул и название, пропускаем шапку.
        if not article or not name or article.strip().lower() in {"артикул", "код", "sku", "article"}:
            continue
        try:
            quantity = float(qty_raw.replace(",", ".")) if qty_raw else None
        except ValueError:
            quantity = None
        rows.append((article, name, unit, quantity))
    return rows


def load_stock(
    xlsx_path: str,
    db_path: str = DB_PATH,
    col_article="A",
    col_name="C",
    col_unit="G",
    col_qty="K",
) -> int:
    rows = _read_rows(xlsx_path, col_article, col_name, col_unit, col_qty)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            article TEXT PRIMARY KEY,
            name TEXT,
            unit TEXT,
            quantity REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("DELETE FROM stock")
    cursor.executemany(
        "INSERT OR REPLACE INTO stock (article, name, unit, quantity) VALUES (?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()
    return len(rows)


def main():
    if len(sys.argv) < 2:
        print("usage: python -m app.load_stock <файл_остатков.xlsx>")
        raise SystemExit(1)
    count = load_stock(sys.argv[1])
    print(f"Загружено остатков: {count}")


if __name__ == "__main__":
    main()
