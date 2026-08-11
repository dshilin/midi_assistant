import sqlite3

import app.db as db


def _setup_db(path):
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT,
            price REAL,
            article TEXT
        );

        CREATE TABLE floor_covering_specs (
            id INTEGER PRIMARY KEY,
            product_id INTEGER NOT NULL,
            product_type TEXT,
            brand TEXT,
            collection TEXT,
            model TEXT,
            color TEXT,
            length_mm REAL,
            width_mm REAL,
            thickness_mm REAL,
            pieces_per_pack INTEGER,
            area_per_pack_m2 REAL,
            packs_per_pallet INTEGER,
            wear_class TEXT
        );

        CREATE TABLE stock (
            article TEXT PRIMARY KEY,
            name TEXT,
            unit TEXT,
            quantity REAL
        );
        """
    )
    products = [
        (1, "Ламинат доступный", 1000, "A-1"),
        (2, "Ламинат без остатка", 1100, "A-2"),
        (3, "Ламинат не в stock", 1200, "A-3"),
        (4, "Ламинат без артикула", 1300, None),
        (5, "Ламинат отрицательный остаток", 1400, "A-5"),
    ]
    specs = [
        (1, 1, "Ламинат", "Brand", None, None, "серый", None, None, None, None, 2.0, None, None),
        (2, 2, "Ламинат", "Brand", None, None, "серый", None, None, None, None, 2.0, None, None),
        (3, 3, "Ламинат", "Brand", None, None, "серый", None, None, None, None, 2.0, None, None),
        (4, 4, "Ламинат", "Brand", None, None, "серый", None, None, None, None, 2.0, None, None),
        (5, 5, "Ламинат", "Brand", None, None, "серый", None, None, None, None, 2.0, None, None),
    ]
    stock = [
        ("A-1", "Ламинат доступный", "уп", 5),
        ("A-2", "Ламинат без остатка", "уп", 0),
        ("A-5", "Ламинат отрицательный остаток", "уп", -1),
    ]
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", products)
    cursor.executemany(
        "INSERT INTO floor_covering_specs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        specs,
    )
    cursor.executemany("INSERT INTO stock VALUES (?, ?, ?, ?)", stock)
    conn.commit()
    conn.close()


def test_get_products_returns_only_positive_stock(tmp_path, monkeypatch):
    db_path = tmp_path / "products.db"
    _setup_db(db_path)
    monkeypatch.setattr(db, "DB_PATH", str(db_path))

    products = db.get_products(product_type="ламинат", limit=10)

    assert [p["id"] for p in products] == [1]
    assert 5 not in [p["id"] for p in products]
    assert products[0]["stock_quantity"] == 5


def test_color_matches_spec_and_name(tmp_path, monkeypatch):
    """Цвет ищется и в s.color, и в названии («Дуб Вэлли дымчатый» по «дуб»)."""
    db_path = tmp_path / "products.db"
    _setup_db(db_path)
    monkeypatch.setattr(db, "DB_PATH", str(db_path))

    assert [p["id"] for p in db.get_products(color="серый", use_stock=False, limit=10)] == [1, 2, 3, 4, 5]
    assert [p["id"] for p in db.get_products(color="доступный", limit=10)] == [1]
    assert [p["id"] for p in db.get_products(color="ламинат", use_stock=False, limit=10)] == [1, 2, 3, 4, 5]


def test_get_products_without_stock_returns_all_catalog(tmp_path, monkeypatch):
    db_path = tmp_path / "products.db"
    _setup_db(db_path)
    monkeypatch.setattr(db, "DB_PATH", str(db_path))

    products = db.get_products(product_type="ламинат", limit=10, use_stock=False)

    assert sorted(p["id"] for p in products) == [1, 2, 3, 4, 5]
    assert all(p["stock_quantity"] == 1 for p in products)
    assert db.get_product_by_id(3, use_stock=False)["stock_quantity"] == 1
    assert db.get_product_by_id(3, use_stock=True) is None


def test_get_product_by_id_requires_positive_stock(tmp_path, monkeypatch):
    db_path = tmp_path / "products.db"
    _setup_db(db_path)
    monkeypatch.setattr(db, "DB_PATH", str(db_path))

    assert db.get_product_by_id(1)["stock_quantity"] == 5
    assert db.get_product_by_id(2) is None
    assert db.get_product_by_id(3) is None
    assert db.get_product_by_id(4) is None
    assert db.get_product_by_id(5) is None


def test_db_path_isolation(tmp_path):
    db_a = tmp_path / "a.db"
    db_b = tmp_path / "b.db"
    _setup_db(db_a)
    _setup_db(db_b)

    pa = db.get_products(product_type="ламинат", db_path=str(db_a), limit=10)
    pb = db.get_products(product_type="ламинат", db_path=str(db_b), limit=10)

    assert [p["id"] for p in pa] == [p["id"] for p in pb] == [1]
    assert db.get_product_by_id(1, db_path=str(db_a))["stock_quantity"] == 5
    db_b.unlink()
    assert db.get_product_by_id(1, db_path=str(db_a)) is not None
