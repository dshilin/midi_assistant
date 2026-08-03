"""python -m app.ingest <slug> — rebuild a client's catalog database."""
import argparse
import asyncio
import os
import sqlite3

from loguru import logger

from app import catalog, clients
from app.load_stock import load_stock
from app.parse_products_gpt import main_async


def _ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT,
            price TEXT,
            article TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS floor_covering_specs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            product_type TEXT, brand TEXT, collection TEXT, model TEXT, color TEXT,
            length_mm REAL, width_mm REAL, thickness_mm REAL, length_m REAL,
            pieces_per_pack INTEGER, area_per_pack_m2 REAL, packs_per_pallet INTEGER,
            wear_class TEXT, article TEXT,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS stock (
            article TEXT PRIMARY KEY,
            name TEXT, unit TEXT, quantity REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def _find_catalog(client_root: str):
    for name in ("catalog.csv", "catalog.xlsx"):
        path = os.path.join(client_root, name)
        if os.path.isfile(path):
            return path
    return None


def _load_catalog(cfg: dict, db_path: str) -> int:
    client_root = os.path.join(clients.CLIENTS_DIR, cfg["slug"])
    path = _find_catalog(client_root)
    if path is None:
        logger.warning("нет catalog.csv/xlsx в {}", client_root)
        return 0
    products = catalog.read_catalog(path)
    rows = [
        (p.get("name"), p.get("url"), p.get("price"), p.get("article"))
        for p in products
        if p.get("name")
    ]
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM products")
    c.executemany("INSERT INTO products (name, url, price, article) VALUES (?, ?, ?, ?)", rows)
    conn.commit()
    conn.close()
    logger.info("каталог {}: {} товаров", cfg["slug"], len(rows))
    return len(rows)


def ingest(slug: str, parse: bool = True) -> int:
    cfg = clients.require_client(slug)
    db_path = clients.get_db_path(slug)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    _ensure_schema(db_path)

    loaded = _load_catalog(cfg, db_path)

    stock_cfg = cfg.get("stock") or {}
    stock_file = os.path.join(clients.CLIENTS_DIR, slug, "stock.xlsx")
    if os.path.isfile(stock_file):
        n = load_stock(
            stock_file,
            db_path,
            col_article=stock_cfg.get("article", "A"),
            col_name=stock_cfg.get("name", "C"),
            col_unit=stock_cfg.get("unit", "G"),
            col_qty=stock_cfg.get("qty", "K"),
        )
        logger.info("остатки {}: {} строк", slug, n)
    else:
        logger.warning("нет stock.xlsx для {}", slug)

    if parse:
        asyncio.run(main_async(product_ids=None, db_path=db_path))
    return loaded


def main():
    parser = argparse.ArgumentParser(description="Пересборка каталога клиента")
    parser.add_argument("slug")
    parser.add_argument("--no-parse", action="store_true", help="не запускать GPT-разбор спек")
    args = parser.parse_args()
    try:
        n = ingest(args.slug, parse=not args.no_parse)
        print(f"Загружено товаров: {n}")
    except ValueError as e:
        print(f"Ошибка: {e}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
