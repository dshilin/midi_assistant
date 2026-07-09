"""Загрузка остатков со склада (выгрузка 1С в .xlsx) в таблицу stock.

Файл — «Ведомость по товарам на складах»: шапка в первых строках, далее строки
товаров. Значимые колонки: A — Артикул, C — Номенклатура, G — Ед. изм.,
K — Конечный остаток. Связь с товарами каталога идёт по артикулу.

Зависимостей нет: .xlsx это zip+xml, читаем стандартной библиотекой (openpyxl/
pandas в окружении не установлены).

    python -m app.load_stock "Остатки на 09.08.26.xlsx"
"""
import sqlite3
import sys
import zipfile
import re
from xml.etree import ElementTree as ET

DB_PATH = "products.db"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Колонки листа выгрузки 1С.
COL_ARTICLE = "A"
COL_NAME = "C"
COL_UNIT = "G"
COL_QTY = "K"  # Конечный остаток


def _read_rows(xlsx_path: str):
    """Вернуть список (article, name, unit, quantity) из первого листа."""
    z = zipfile.ZipFile(xlsx_path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))

    ws = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    def value(cell):
        t = cell.get("t")
        v = cell.find(f"{NS}v")
        if t == "s":
            return shared[int(v.text)] if v is not None else ""
        return v.text if v is not None else ""

    def column(ref):
        return re.match(r"[A-Z]+", ref).group()

    rows = []
    for row in ws.iter(f"{NS}row"):
        cells = {column(c.get("r")): value(c) for c in row.findall(f"{NS}c")}
        article = (cells.get(COL_ARTICLE) or "").strip()
        name = (cells.get(COL_NAME) or "").strip()
        unit = (cells.get(COL_UNIT) or "").strip()
        qty_raw = (cells.get(COL_QTY) or "").strip()
        # Строки данных: есть артикул и название, пропускаем шапку.
        if not article or not name or article == "Артикул":
            continue
        try:
            quantity = float(qty_raw.replace(",", ".")) if qty_raw else None
        except ValueError:
            quantity = None
        rows.append((article, name, unit, quantity))
    return rows


def load_stock(xlsx_path: str, db_path: str = DB_PATH) -> int:
    rows = _read_rows(xlsx_path)
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
    print(f"Загружено остатков: {count} (таблица stock в {DB_PATH})")


if __name__ == "__main__":
    main()
