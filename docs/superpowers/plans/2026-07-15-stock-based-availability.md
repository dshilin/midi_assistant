# Stock-Based Availability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make product search and product-by-ID lookup return only items that exist in `stock` with `quantity > 0`.

**Architecture:** Keep availability in `app/db.py`, where product reads already happen. Use `INNER JOIN stock st ON st.article = p.article AND st.quantity > 0` so products without article, without stock row, or with non-positive stock are excluded by SQLite.

**Tech Stack:** Python 3.14, sqlite3 stdlib, pytest, loguru.

---

## File Structure

- Create: `tests/test_db.py` - focused DB tests using a temporary SQLite database and monkeypatched `app.db.DB_PATH`.
- Modify: `app/db.py` - add the `stock` join and expose `stock_quantity` in `get_products()` and `get_product_by_id()`.

## Task 1: Add failing stock availability tests

**Files:**
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_db.py` with this content:

```python
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
    ]
    specs = [
        (1, 1, "Ламинат", "Brand", None, None, "серый", None, None, None, None, 2.0, None, None),
        (2, 2, "Ламинат", "Brand", None, None, "серый", None, None, None, None, 2.0, None, None),
        (3, 3, "Ламинат", "Brand", None, None, "серый", None, None, None, None, 2.0, None, None),
        (4, 4, "Ламинат", "Brand", None, None, "серый", None, None, None, None, 2.0, None, None),
    ]
    stock = [
        ("A-1", "Ламинат доступный", "уп", 5),
        ("A-2", "Ламинат без остатка", "уп", 0),
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
    assert products[0]["stock_quantity"] == 5


def test_get_product_by_id_requires_positive_stock(tmp_path, monkeypatch):
    db_path = tmp_path / "products.db"
    _setup_db(db_path)
    monkeypatch.setattr(db, "DB_PATH", str(db_path))

    assert db.get_product_by_id(1)["stock_quantity"] == 5
    assert db.get_product_by_id(2) is None
    assert db.get_product_by_id(3) is None
    assert db.get_product_by_id(4) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_db.py -v
```

Expected: FAIL. The first test returns IDs `[1, 2, 3, 4]` or errors on missing `stock_quantity`, and the second returns unavailable products instead of `None`.

- [ ] **Step 3: Leave the failing tests uncommitted**

Do not commit the failing tests alone. Keep `tests/test_db.py` in the working tree and continue to Task 2 so the next commit contains passing tests plus implementation.

## Task 2: Filter DB reads through stock

**Files:**
- Modify: `app/db.py:43-49`
- Modify: `app/db.py:128-135`
- Test: `tests/test_db.py`

- [ ] **Step 1: Update `get_products()` query**

In `app/db.py`, change the `get_products()` SELECT block to:

```python
    query = """
        SELECT p.id, p.name, p.price, s.product_type, s.brand, s.collection, s.model, s.color,
               s.length_mm, s.width_mm, s.thickness_mm, s.pieces_per_pack,
               s.area_per_pack_m2, s.packs_per_pallet, s.wear_class,
               st.quantity AS stock_quantity
        FROM products p
        INNER JOIN stock st ON st.article = p.article AND st.quantity > 0
        LEFT JOIN floor_covering_specs s ON p.id = s.product_id
        WHERE 1=1
    """
```

- [ ] **Step 2: Update `get_product_by_id()` query**

In `app/db.py`, change the `get_product_by_id()` SELECT to:

```python
    cursor.execute("""
        SELECT p.id, p.name, p.price, s.product_type, s.brand, s.collection, s.model, s.color,
               s.length_mm, s.width_mm, s.thickness_mm, s.pieces_per_pack,
               s.area_per_pack_m2, s.packs_per_pallet, s.wear_class,
               st.quantity AS stock_quantity
        FROM products p
        INNER JOIN stock st ON st.article = p.article AND st.quantity > 0
        LEFT JOIN floor_covering_specs s ON p.id = s.product_id
        WHERE p.id = ?
    """, (product_id,))
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
python -m pytest tests/test_db.py -v
```

Expected: PASS, both tests pass.

- [ ] **Step 4: Run the full test suite**

Run:

```bash
python -m pytest tests/ -v
```

Expected: PASS. Existing tests should not need changes because they mock DB reads or do not depend on `products.db` availability.

- [ ] **Step 5: Commit implementation**

Run:

```bash
git add app/db.py tests/test_db.py
git commit -m "feat: filter products by stock availability"
```

## Self-Review

- Spec coverage: `get_products()` and `get_product_by_id()` both filter on `products.article = stock.article` and `stock.quantity > 0`; tests cover positive, zero, missing stock row, and missing article.
- Placeholder scan: no TBD/TODO/fill-in steps remain.
- Type consistency: tests use `stock_quantity`; SQL aliases `st.quantity AS stock_quantity` in both reads.
