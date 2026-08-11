# Мультитенантная архитектура — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Один код, разворачиваемый для множества магазинов (клиентов): у каждого клиента свой каталог, свои остатки, свой канал (Telegram/сайт), своя БД `clients/<slug>/products.db`.

**Architecture:** Клиент = папка `clients/<slug>/` с `config.toml` и своей БД. Агент и БД-запросы scoped по `client_slug`; каталог в систему попадает одним форматом «xlsx/csv с шапкой» (колонки по алиасам, без маппинга); скрейп вынесен из ядра в одноразовый скрипт клиента; загрузка — CLI `python -m app.ingest <slug>`.

**Tech Stack:** Python 3.14 (tomllib в stdlib), SQLite, FastAPI, aiogram 3, stdlib zipfile+xml для xlsx. Новых зависимостей не добавляем.

## Global Constraints

- Python 3.14 (`requires-python = ">=3.14"`), `tomllib` и `csv` из stdlib.
- Ноль новых runtime-зависимостей. Всё новое — через stdlib.
- Тестовый прогон `python3 -m pytest tests/ -v`; тесты зелёные перед коммитом.
- Коммиты по конвенции репозитория: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`.
- В git НЕ попадают: `*.db` (уже игнорируется) и прогоновые артефакты `clients/*/catalog.csv`, `clients/*/stock.xlsx` (добавляем в `.gitignore` в Task 10).

## Deliberate deviations from spec

1. Конфиг клиента — `config.toml` (stdlib `tomllib`) вместо `config.yml` — иначе нужен PyYAML, а зависимостей не добавляем. Спека упоминает yml; в Task 11 спеку правим под факт.
2. Входной каталог — `catalog.csv` ИЛИ `catalog.xlsx` с шапкой; скрейпер midi пишет CSV (запись xlsx stdlib'ом — ~40 строк zip-плюмбинга, а CSV хватает).
3. Прямой приём доп-колонок спек из файла каталога — НЕ делаем (V1). Спеки заполняет GPT-разбор `parse_products_gpt`, общий для всех клиентов.

---

### Task 1: Реестр клиентов — `app/clients.py`

**Files:**
- Create: `app/clients.py`
- Test: `tests/test_clients.py`

**Interfaces:**
- Produces: `list_clients() -> list[str]`, `get_client(slug) -> dict | None`, `require_client(slug) -> dict` (бросает `ValueError`), `get_db_path(slug) -> str`, константа `CLIENTS_DIR = "clients"`.

Каждый клиент — директория `clients/<slug>/config.toml`. tomllib stdlib, только чтение.

- [ ] **Step 1: пишем падающий тест**

`tests/test_clients.py`:

```python
import os

import pytest

from app import clients


def _make_client(root: str, slug: str, bot_token: str = "") -> None:
    d = os.path.join(root, slug)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "config.toml"), "w", encoding="utf-8") as f:
        f.write(f'name = "{slug}"\n')
        f.write(f'bot_token = "{bot_token}"\n')


def test_list_clients(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    _make_client(str(tmp_path), "midi")
    _make_client(str(tmp_path), "store2")
    (tmp_path / "broken").mkdir()  # нет config.toml — не клиент
    assert clients.list_clients() == ["midi", "store2"]


def test_get_client_returns_config(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    _make_client(str(tmp_path), "midi", bot_token="t1")
    cfg = clients.get_client("midi")
    assert cfg["name"] == "midi"
    assert cfg["bot_token"] == "t1"
    assert cfg["slug"] == "midi"


def test_get_client_unknown_is_none(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    assert clients.get_client("nope") is None


def test_require_client_raises_for_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="nope"):
        clients.require_client("nope")


def test_get_db_path(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    assert clients.get_db_path("midi") == os.path.join(str(tmp_path), "midi", "products.db")
```

- [ ] **Step 2: Run → FAIL**

Run: `python3 -m pytest tests/test_clients.py -v`
Expected: `ModuleNotFoundError: No module named 'app.clients'`

- [ ] **Step 3: реализация**

`app/clients.py`:

```python
"""Реестр клиентов: каждая папка clients/<slug>/ с config.toml — отдельный магазин."""
import os
import tomllib

CLIENTS_DIR = "clients"


def list_clients() -> list[str]:
    if not os.path.isdir(CLIENTS_DIR):
        return []
    return [
        d
        for d in os.listdir(CLIENTS_DIR)
        if os.path.isfile(os.path.join(CLIENTS_DIR, d, "config.toml"))
    ]


def get_client(slug: str) -> dict | None:
    path = os.path.join(CLIENTS_DIR, slug, "config.toml")
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    cfg.setdefault("slug", slug)
    return cfg


def require_client(slug: str) -> dict:
    cfg = get_client(slug)
    if cfg is None:
        raise ValueError(f"Unknown client slug: {slug}")
    return cfg


def get_db_path(slug: str) -> str:
    return os.path.join(CLIENTS_DIR, slug, "products.db")
```

- [ ] **Step 4: Run → PASS**

Run: `python3 -m pytest tests/test_clients.py -v`
Expected: PASS (5)

- [ ] **Step 5: коммит**

```bash
git add app/clients.py tests/test_clients.py
git commit -m "feat: реестр клиентов (список, конфиг, путь к БД)"
```

---

### Task 2: Чтение первого листа xlsx + остатки по колонкам клиента

**Files:**
- Create: `app/xlsx.py`
- Modify: `app/load_stock.py`
- Create: `tests/xlsx_fixtures.py`
- Test: `tests/test_load_stock.py`

**Interfaces:**
- Produces: `app.xlsx.read_first_sheet_rows(path) -> list[dict[str, str]]` (ключи — буквы колонок `A`, `B`, ..., значения — текст);
  `app.load_stock.load_stock(xlsx_path, db_path, col_article="A", col_name="C", col_unit="G", col_qty="K") -> int`.

- [ ] **Step 1: фикстура xlsx для тестов**

`tests/xlsx_fixtures.py`:

```python
import os
import zipfile
from xml.sax.saxutils import escape


def _col_letter(ci: int) -> str:
    s = ""
    while ci > 0:
        ci, r = divmod(ci - 1, 26)
        s = chr(65 + r) + s
    return s


def write_minimal_xlsx(path: str, rows: list[list[str]]) -> None:
    """Минимальный валидный .xlsx с инлайн-строками — для тестов."""
    NSS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    body = []
    for ri, row in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{_col_letter(ci)}{ri}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
            for ci, v in enumerate(row, 1)
        )
        body.append(f'<row r="{ri}">{cells}</row>')
    sheet = f'<worksheet xmlns="{NSS}"><sheetData>{"".join(body)}</sheetData></worksheet>'

    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "xl/workbook.xml",
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            "</Relationships>",
        )
        z.writestr("xl/worksheets/sheet1.xml", sheet)
```

- [ ] **Step 2: падающие тесты**

`tests/test_load_stock.py`:

```python
import sqlite3

from app import xlsx
from app.load_stock import load_stock
from tests.xlsx_fixtures import write_minimal_xlsx


def test_read_first_sheet_rows(tmp_path):
    p = tmp_path / "t.xlsx"
    write_minimal_xlsx(str(p), [["Артикул", "Название"], ["A-1", "Ламинат"], []])
    rows = xlsx.read_first_sheet_rows(str(p))
    assert rows[0] == {"A": "Артикул", "B": "Название"}
    assert rows[1] == {"A": "A-1", "B": "Ламинат"}
    assert rows[2] == {}


_STOCK_DEFAULT = [
    ["Артикул", "", "Номенклатура", "", "", "", "Ед", "", "", "", "Остаток"],
    ["A-1", "", "Ламинат", "", "", "", "уп", "", "", "", "5"],
    ["A-2", "", "Ковролин", "", "", "", "уп", "", "", "", "0"],
]


def _make_stock(tmp_path, rows):
    p = tmp_path / "stock.xlsx"
    write_minimal_xlsx(str(p), rows)
    return str(p)


def test_load_stock_default_columns(tmp_path):
    db = str(tmp_path / "products.db")
    n = load_stock(_make_stock(tmp_path, _STOCK_DEFAULT), db)
    assert n == 2
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT article, quantity FROM stock WHERE article='A-1'").fetchone() == ("A-1", 5.0)
    assert conn.execute("SELECT article, quantity FROM stock WHERE article='A-2'").fetchone() == ("A-2", 2.0)


def test_load_stock_custom_columns(tmp_path):
    p = _make_stock(tmp_path, [
        ["SKU", "Остаток", "Имя"],
        ["S-9", "3", "Ковролин"],
    ])
    db = str(tmp_path / "products.db")
    n = load_stock(p, db, col_article="A", col_qty="B", col_name="C")
    assert n == 1
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT article, quantity FROM stock").fetchone() == ("S-9", 3.0)
```

- [ ] **Step 3: Run → FAIL**

Expected: `ModuleNotFoundError: No module named 'app.xlsx'`

- [ ] **Step 4: реализация**

`app/xlsx.py`:

```python
"""Чтение первого листа .xlsx стандартной библиотекой (zip+xml)."""
import re
import zipfile
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_first_sheet_rows(path: str) -> list[dict[str, str]]:
    """Строки первого листа: {буква_колонки: значение}. Пустые ячейки пропущены."""
    z = zipfile.ZipFile(path)
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        shared = ["".join(t.text or "" for t in si.iter(f"{NS}t")) for si in root.findall(f"{NS}si")]
    else:
        shared = []

    ws = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

    def value(cell) -> str:
        t = cell.get("t")
        if t == "inlineStr":
            return "".join(t.text or "" for t in cell.iter(f"{NS}t"))
        v = cell.find(f"{NS}v")
        if t == "s":
            return shared[int(v.text)] if v is not None else ""
        return v.text if v is not None else ""

    rows = []
    for row in ws.iter(f"{NS}row"):
        cells = {}
        for c in row.findall(f"{NS}c"):
            m = re.match(r"[A-Z]+", c.get("r", ""))
            if m:
                cells[m.group()] = value(c)
        rows.append(cells)
    return rows
```

`app/load_stock.py` — переписываем (убрать zipfile/ET/re импорт и константы):

```python
"""Загрузка остатков со склада (выгрузка 1С в .xlsx) в таблицу stock.

Колонки по умолчанию: A — артикул, C — номенклатура, G — ед. изм., K — конечный
остаток. Задать свои — параметрами col_* или из config клиента (ingest).
"""
import sqlite3
import sys

from app import xlsx

DB_PATH = "products.db"


def _read_rows(xlsx_path: str, col_article="A", col_name="C", col_unit="G", col_qty="K"):
    rows = []
    for cells in xlsx.read_first_sheet_rows(xlsx_path):
        article = (cells.get(col_article) or "").strip()
        name = (cells.get(col_name) or "").strip()
        unit = (cells.get(col_unit) or "").strip()
        qty_raw = (cells.get(col_qty) or "").strip()
        if not article or not name or article == "Артикул":
            continue
        try:
            quantity = float(qty_raw.replace(",", ".")) if qty_raw else None
        except ValueError:
            quantity = None
        rows.append((article, name, unit, quantity))
    return rows


def load_stock(xlsx_path: str, db_path: str = DB_PATH,
               col_article="A", col_name="C", col_unit="G", col_qty="K") -> int:
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
```

- [ ] **Step 5: Run → PASS**

Run: `python3 -m pytest tests/test_load_stock.py -v`
Expected: PASS (3)

- [ ] **Step 6: полный прогон + коммит**

Run: `python3 -m pytest tests/ -v`
Expected: зелёный (остальные тесты не менялись).

```bash
git add app/xlsx.py app/load_stock.py tests/test_load_stock.py tests/xlsx_fixtures.py
git commit -m "feat: читаем первый лист xlsx stdlib, остатки с колонками из конфига"
```

---

### Task 3: Чтение каталога — `app/catalog.py`

**Files:**
- Create: `app/catalog.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Consumes: `app.xlsx.read_first_sheet_rows`
- Produces: `read_catalog(path: str) -> list[dict]` — товары с ключами `article`, `name`, `price`, `url` (пустые не включаются), колонки распознаются по алиасам шапки.

- [ ] **Step 1: падающий тест**

`tests/test_catalog.py`:

```python
from pathlib import Path

from app.catalog import read_catalog
from tests.xlsx_fixtures import write_minimal_xlsx


def test_catalog_csv(tmp_path):
    p = Path(tmp_path) / "catalog.csv"
    p.write_text(
        "Артикул,Наименование,Цена,Ссылка\n"
        "A-1,Ламинат дуб викинг,1500,http://ex.ru/1\n",
        encoding="utf-8-sig",
    )
    assert read_catalog(str(p)) == [{
        "article": "A-1",
        "name": "Ламинат дуб викинг",
        "price": "1500",
        "url": "http://ex.ru/1",
    }]


def test_catalog_aliases(tmp_path: Path):
    p = Path(tmp_path) / "catalog.csv"
    p.write_text("sku,name,price,url\nS1,Линолеум,200,http://ex.ru/2\n", encoding="utf-8-sig")
    rows = read_catalog(str(p))
    assert rows[0]["article"] == "S1"
    assert rows[0]["name"] == "Линолеум"


def test_catalog_skips_unknown_columns(tmp_path: Path):
    p = Path(tmp_path) / "catalog.csv"
    p.write_text("Артикул,Мусор,Наименование,Цена\nA-2,x,Винил,300\n", encoding="utf-8-sig")
    rows = read_catalog(str(p))
    assert rows == [{"article": "A-2", "name": "Винил", "price": "300"}]


def test_catalog_xlsx(tmp_path: Path):
    p = Path(tmp_path) / "catalog.xlsx"
    write_minimal_xlsx(str(p), [
        ["Артикул", "Наименование", "Цена", "Ссылка"],
        ["K-1", "Ковролин", "11.5", "http://ex.ru/k1"],
    ])
    assert read_catalog(str(p)) == [
        {"article": "K-1", "name": "Ковролин", "price": "11.5", "url": "http://ex.ru/k1"}
    ]
```

- [ ] **Step 2: Run → FAIL**

Run: `python3 -m pytest tests/test_catalog.py -v`
Expected: `ModuleNotFoundError: No module named 'app.catalog'`

- [ ] **Step 3: реализация**

`app/catalog.py`:

```python
"""Каталог: xlsx или csv с шапкой; колонки узнаём по алиасам — маппинга не нужно."""
import csv

from app import xlsx

HEADER_ALIASES = {
    "article": ("артикул", "код", "sku", "article"),
    "name": ("наименование", "название", "name", "товар"),
    "price": ("цена", "price", "стоимость"),
    "url": ("ссылка", "url", "адрес"),
}


def _field(header):
    key = (header or "").strip().lower()
    for field, aliases in HEADER_ALIASES.items():
        if key in aliases:
            return field
    return None


def _clean_item(data):
    return {k: v for k, v in data.items() if v not in (None, "")}


def read_catalog(path: str) -> list[dict]:
    if path.lower().endswith(".xlsx"):
        rows = xlsx.read_first_sheet_rows(path)
        header = rows[0]
        fields = {col: _field(h) for col, h in header.items()}
        out = []
        for r in rows[1:]:
            item = {}
            for col, fld in fields.items():
                if fld:
                    item[fld] = (r.get(col) or "").strip()
            out.append(_clean_item(item))
        return out

    with open(path, newline="", encoding="utf-8-sig") as fp:
        reader = list(csv.reader(fp))
    if not reader:
        return []
    fields = [_field(c) for c in reader[0]]
    out = []
    for row in reader[1:]:
        item = {}
        for i, fld in enumerate(fields):
            if fld and i < len(row):
                item[fld] = row[i].strip()
        out.append(_clean_item(item))
    return out
```

- [ ] **Step 4: Run → PASS**

Run: `python3 -m pytest tests/test_catalog.py -v`
Expected: PASS (4)

- [ ] **Step 5: коммит**

```bash
git add app/catalog.py tests/test_catalog.py
git commit -m "feat: чтение каталога по алиасам шапки (xlsx/csv)"
```

---

### Task 4: `app/db.py` — БД по клиенту

**Files:**
- Modify: `app/db.py`
- Test: `tests/test_db.py` (добавить тест)

**Interfaces:**
- Produces: у всех функций добавляется опциональный `db_path: str | None = None`, по умолчанию `None` → текущий `DB_PATH`: `get_conn`, `get_products`, `get_distinct_product_types`, `get_product_by_id`, `calculate_material`.

- [ ] **Step 1: падающий тест**

Добавить в `tests/test_db.py`:

```python
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
```

- [ ] **Step 2: Run → FAIL**

Run: `python3 -m pytest tests/test_db.py::test_db_path_isolation -v`
Expected: `TypeError: get_products() got an unexpected keyword argument 'db_path'`

- [ ] **Step 3: реализация**

Правим `app/db.py`:

```python
def get_conn(db_path=None):
    conn = sqlite3.connect(db_path or DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
```

и в каждой функции заменяем `get_conn()` → `get_conn(db_path)`, добавляя параметр:

- `def get_products(..., limit=10, db_path=None):` → `conn = get_conn(db_path)`.
- `def get_distinct_product_types(db_path=None):` → `conn = get_conn(db_path)` (внутри try).
- `def get_product_by_id(product_id, db_path=None):` → `conn = get_conn(db_path)`.
- `def calculate_material(area, product_id, db_path=None):` → `product = get_product_by_id(product_id, db_path=db_path)` (остальное не меняется).

- [ ] **Step 4: Run → PASS**

Run: `python3 -m pytest tests/test_db.py -v`
Expected: PASS (3)

- [ ] **Step 5: коммит**

```bash
git add app/db.py tests/test_db.py
git commit -m "feat: db.py принимает db_path (клиентская БД)"
```

---

### Task 5: `app/agent_fsm.py` — scoped по клиенту

**Files:**
- Modify: `app/agent_fsm.py`
- Test: `tests/test_agent_fsm.py` (не меняется, должен остаться зелёным)

**Interfaces:**
- Consumes: `app.clients.get_db_path`
- Produces: `run_fsm_agent(user_id, message, client_slug="midi") -> (str, dict)`. В начале резолвится `db_path = get_db_path(client_slug)` и прокидывается во все db-вызовы.

- [ ] **Step 1: реализация**

В `app/agent_fsm.py`:

- добавить импорт: `from app.clients import get_db_path`
- сигнатура `run_fsm_agent`:

```python
async def run_fsm_agent(user_id: str, message: str, client_slug: str = "midi") -> Tuple[str, Dict]:
    db_path = get_db_path(client_slug)
```

- `_fetch_products_by_criteria`:

```python
def _fetch_products_by_criteria(state, db_path):
    return get_products(
        product_type=state.get("type"),
        brand=state.get("brand"),
        color=state.get("color"),
        db_path=db_path,
    )
```

- вызовы внутри `run_fsm_agent`:
  - `shown_products = [p for p in (get_product_by_id(pid, db_path=db_path) for pid in shown_ids) if p]`
  - `_fetch_products_by_criteria(state, db_path)`
  - блок no-products: `available = get_distinct_product_types(db_path=db_path)`
  - `product = get_product_by_id(state.get("selected_product"), db_path=db_path)`
  - `calc = calculate_material(area, pid, db_path=db_path)`

- [ ] **Step 2: Run → PASS**

Run: `python3 -m pytest tests/test_agent_fsm.py tests/test_fsm.py -v`
Expected: PASS (тесты мокают db-функции, от реального пути не зависят).

- [ ] **Step 3: полный run**

Run: `python3 -m pytest tests/ -v` → зелёный.

- [ ] **Step 4: коммит**

```bash
git add app/agent_fsm.py
git commit -m "feat: agent_fsm scoped по клиенту (client_slug → db_path)"
```

---

### Task 6: `parse_products_gpt` — параметр `db_path`

**Files:**
- Modify: `app/parse_products_gpt.py`
- Test: `tests/test_parse_products.py` (+1 тест)

**Interfaces:**
- Produces: `main_async(product_ids=None, db_path=None)`; `db_path=None` → текущий `DB_PATH`. Используется `app.ingest`.

- [ ] **Step 1: тест**

Добавить в `tests/test_parse_products.py` (в класс `TestIntegration` уже есть `db_connection`; новый тест — с файловой БД):

```python
@pytest.mark.asyncio
async def test_main_async_writes_to_custom_db(tmp_path):
    db = tmp_path / "p.db"
    conn = sqlite3.connect(str(db))
    conn.execute("""CREATE TABLE products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        url TEXT, price TEXT, created_at TIMESTAMP)""")
    conn.execute("INSERT INTO products (name, price) VALUES ('Ламинат X', '100')")
    conn.commit()
    conn.close()

    with patch("app.parse_products_gpt.parse_product_name_with_gpt", new_callable=AsyncMock) as m:
        m.return_value = {"product_type": "Ламинат", "color": "белый"}
        await main_async(db_path=str(db))

    conn = sqlite3.connect(str(db))
    assert conn.execute("SELECT COUNT(*) FROM floor_covering_specs").fetchone()[0] == 1
    conn.close()
```

(импорты `main_async`, `sqlite3` уже есть в файле — проверить и добавить `main_async` в импорты)

- [ ] **Step 2: Run → FAIL**

Run: `python3 -m pytest tests/test_parse_products.py::test_main_async_writes_to_custom_db -v`
Expected: `TypeError` или AttributeError — `main_async` не принимает `db_path`.

- [ ] **Step 3: реализация**

В `app/parse_products_gpt.py`:

```python
async def main_async(product_ids=None, db_path=None):
    """..."""
    db_path = db_path or DB_PATH
    logger.info("Starting YandexGPT product parsing...")
    logger.info("Database: {}", db_path)
    ...
    conn = sqlite3.connect(db_path)
```

Прочее без изменений.

- [ ] **Step 4: Run → PASS**

Run: `python3 -m pytest tests/test_parse_products.py -v`
Expected: PASS

- [ ] **Step 5: коммит**

```bash
git add app/parse_products_gpt.py tests/test_parse_products.py
git commit -m "feat: parse_products_gpt принимает db_path клиента"
```

---

### Task 7: `app/ingest.py` — загрузка каталога клиента

**Files:**
- Create: `app/ingest.py`
- Test: `tests/test_ingest.py`

**Interfaces:**
- Consumes: `app.clients.get_db_path`/`require_client`, `app.catalog.read_catalog`, `app.load_stock.load_stock`, `app.parse_products_gpt.main_async` (если `parse=True`).
- Produces: `ingest(slug, parse=True) -> int` (число товаров) и CLI `python -m app.ingest <slug> [--no-parse]`. Пересобирает `products` и `stock` клиента; при `parse=True` зовёт GPT-разбор спек.

- [ ] **Step 1: падающий тест**

`tests/test_ingest.py`:

```python
import sqlite3
from unittest.mock import AsyncMock, patch

import pytest

import app.ingest as ingest
from app import clients
from tests.xlsx_fixtures import write_minimal_xlsx


def _make_client(tmp_path, slug="demo"):
    d = tmp_path / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.toml").write_text(f'name = "{slug}"\n', encoding="utf-8")
    return d


def test_ingest_catalog_and_stock(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    cdir = _make_client(tmp_path, "demo")

    write_minimal_xlsx(str(cdir / "catalog.xlsx"), [
        ["Артикул", "Наименование", "Цена", "Ссылка"],
        ["A-1", "Ламинат дуб викинг", "1500", "http://ex.ru/1"],
        ["A-2", "Винил кварц", "1100", "http://ex.ru/2"],
    ])
    write_minimal_xlsx(str(cdir / "stock.xlsx"), [
        ["Артикул", "", "Номенклатура", "", "", "", "Ед", "", "", "", "Остаток"],
        ["A-1", "", "Ламинат", "", "", "", "уп", "", "", "", "7"],
    ])

    ingest.ingest("demo", parse=False)

    conn = sqlite3.connect(str(cdir / "products.db"))
    got = conn.execute("SELECT article, name, price FROM products ORDER BY article").fetchall()
    assert [tuple(r) for r in got] == [
        ("A-1", "Ламинат дуб викинг", "1500"),
        ("A-2", "Винил кварц", "1100"),
    ]
    assert conn.execute("SELECT quantity FROM stock WHERE article='A-1'").fetchone()[0] == 7.0
    conn.close()


def test_ingest_missing_catalog_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    _make_client(tmp_path, "demo")
    n = ingest.ingest("demo", parse=False)
    assert n == 0
    conn = sqlite3.connect(str(tmp_path / "demo" / "products.db"))
    assert conn.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0
    conn.close()


def test_ingest_unknown_slug_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    with pytest.raises(ValueError, match="Unknown client"):
        ingest.ingest("nope", parse=False)


def test_ingest_runs_parse_when_requested(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    cdir = _make_client(tmp_path, "demo")
    (cdir / "catalog.csv").write_text("sku,name,price\nS1,Винил,900\n", encoding="utf-8-sig")

    with patch("app.ingest.main_async", new_callable=AsyncMock) as parse:
        ingest.ingest("demo", parse=True)
        parse.assert_awaited_once()
```

- [ ] **Step 2: Run → FAIL**

Run: `python3 -m pytest tests/test_ingest.py -v`
Expected: `ModuleNotFoundError: No module named 'app.ingest'`

- [ ] **Step 3: реализация**

`app/ingest.py`:

```python
"""python -m app.ingest <slug> — пересборка каталога клиента.

Читает clients/<slug>/catalog.csv|xlsx (колонки по алиасам шапки), затем
clients/<slug>/stock.xlsx (колонки из config.stock или стандартные 1С), затем
опционально GPT-разбор названий в спеки.
"""
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
        p = os.path.join(client_root, name)
        if os.path.isfile(p):
            return p
    return None


def _load_catalog(cfg: dict, db_path: str) -> int:
    client_root = os.path.join(clients.CLIENTS_DIR, cfg["slug"])
    path = _find_catalog(client_root)
    if path is None:
        logger.warning("нет catalog.csv/xlsx в {}", client_root)
        return 0
    products = catalog.read_catalog(path)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM products")
    rows = [
        (p.get("name"), p.get("url"), p.get("price"), p.get("article"))
        for p in products
        if p.get("name")
    ]
    c.executemany(
        "INSERT INTO products (name, url, price, article) VALUES (?, ?, ?, ?)",
        rows,
    )
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

    sc = cfg.get("stock") or {}
    stock_file = os.path.join(clients.CLIENTS_DIR, slug, "stock.xlsx")
    if os.path.isfile(stock_file):
        n = load_stock(
            stock_file, db_path,
            col_article=sc.get("article", "A"),
            col_name=sc.get("name", "C"),
            col_unit=sc.get("unit", "G"),
            col_qty=sc.get("qty", "K"),
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
```

- [ ] **Step 4: Run → PASS**

Run: `python3 -m pytest tests/test_ingest.py -v`
Expected: PASS (4)

- [ ] **Step 5: коммит**

```bash
git add app/ingest.py tests/test_ingest.py
git commit -m "feat: CLI-загрузка каталога + остатков клиента (app.ingest)"
```

---

### Task 8: Telegram-бот — несколько клиентов

**Files:**
- Modify: `app/tg_bot.py`
- Test: `tests/test_tg_bot.py`

**Interfaces:**
- Consumes: `app.clients.list_clients`, `app.clients.get_client`
- Produces: `get_telegram_token(slug="midi") -> str` (из `config.bot_token`, иначе env `TELEGRAM_BOT_TOKEN`); `build_bots() -> list[Bot]` (по одному на клиента с токеном, атрибут `client_slug`); `handle_text` адресует `run_fsm_agent(f"tg:{slug}:{user_id}", msg, client_slug=slug)`; `main()` — `asyncio.gather` по всем ботам.

- [ ] **Step 1: тесты**

`tests/test_tg_bot.py` — заменить содержимое:

```python
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import clients
from app.tg_bot import get_telegram_token, handle_start, handle_text, build_bots


class FakeBot:
    client_slug = "store"


def _make_client(root, slug, token="t1"):
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.toml").write_text(f'bot_token = "{token}"\n', encoding="utf-8")


def test_get_telegram_token_uses_client_config(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    d = tmp_path / "cfg"
    d.mkdir()
    (d / "config.toml").write_text('bot_token = "cfg-token"\n', encoding="utf-8")
    assert get_telegram_token("cfg") == "cfg-token"


def test_get_telegram_token_falls_back_to_env(monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", "/nonexistent")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
    assert get_telegram_token("midi") == "env-token"


def test_get_telegram_token_requires_value(monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", "/nonexistent")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.setattr("app.tg_bot.load_dotenv", lambda: None)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        get_telegram_token("midi")


@pytest.mark.asyncio
async def test_handle_start_replies_with_greeting():
    message = SimpleNamespace(answer=AsyncMock())
    await handle_start(message)
    message.answer.assert_awaited_once()
    assert "Здравствуйте" in message.answer.await_args.args[0]


@pytest.mark.asyncio
async def test_handle_text_routes_by_bot_client(monkeypatch):
    message = SimpleNamespace(
        text="нужен светлый ламинат",
        from_user=SimpleNamespace(id=42),
        answer=AsyncMock(),
        bot=FakeBot(),
    )
    run_agent = AsyncMock(return_value=("Вот варианты", {"stage": "selection"}))
    monkeypatch.setattr("app.tg_bot.run_fsm_agent", run_agent)

    await handle_text(message)

    run_agent.assert_awaited_once_with("tg:store:42", "нужен светлый ламинат", client_slug="store")
    message.answer.assert_awaited_once_with("Вот варианты")


def test_build_bots_returns_one_per_token(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    for slug in ("a", "b", "c"):
        d = tmp_path / slug
        d.mkdir()
        token = f"{slug}-tok"
        (d / "config.toml").write_text(f'bot_token = "{token}"\n', encoding="utf-8")
    bots = build_bots()
    assert {b.client_slug for b in bots} == {"a", "b", "c"}


def test_build_bots_raises_without_clients(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    with pytest.raises(RuntimeError, match="bot_token"):
        build_bots()
```

`get_telegram_token` сначала смотрит `config.bot_token` — тест с токенами в конфиге не зависит от env.

- [ ] **Step 2: Run → FAIL**

Run: `python3 -m pytest tests/test_tg_bot.py -v`
Expected: fail на новых сигнатурах/атрибутах.

- [ ] **Step 3: реализация**

`app/tg_bot.py` (заменить):

```python
import asyncio
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
from loguru import logger

from app.agent_fsm import run_fsm_agent
from app import clients


def get_telegram_token(slug: str = "midi") -> str:
    load_dotenv()
    cfg = clients.get_client(slug)
    token = (cfg or {}).get("bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")
    return token


def client_slug_for(message: Message) -> str:
    bot = getattr(message, "bot", None)
    return getattr(bot, "client_slug", "midi")


async def handle_start(message: Message) -> None:
    await message.answer(
        "Здравствуйте! Я AI-консультант по напольным покрытиям. "
        "Напишите, что ищете: тип покрытия, цвет, помещение или площадь."
    )


async def handle_text(message: Message) -> None:
    if not message.text:
        await message.answer("Пока я понимаю только текстовые сообщения.")
        return

    slug = client_slug_for(message)
    user_id = f"tg:{slug}:{message.from_user.id}"
    logger.info("telegram client={} user={} msg_preview={}...", slug, message.text[:60])

    try:
        response, state = await run_fsm_agent(user_id, message.text, client_slug=slug)
    except Exception:
        logger.exception("telegram handler failed user={}", user_id)
        await message.answer("Извините, произошла ошибка. Попробуйте ещё раз.")
        return

    await message.answer(response)


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.register(handle_start, CommandStart())
    dp.message.register(handle_text, F.text)
    dp.message.register(handle_text)
    return dp


def build_bots() -> list[Bot]:
    bots = []
    for slug in clients.list_clients():
        try:
            token = get_telegram_token(slug)
        except RuntimeError:
            continue
        bot = Bot(token)
        bot.client_slug = slug
        bots.append(bot)
    if not bots:
        raise RuntimeError("нет ни одного клиента с bot_token")
    return bots


async def main() -> None:
    bots = build_bots()
    dp = build_dispatcher()
    await asyncio.gather(*(dp.start_polling(bot) for bot in bots))


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run → PASS**

Run: `python3 -m pytest tests/test_tg_bot.py -v`
Expected: PASS

- [ ] **Step 5: коммит**

```bash
git add app/tg_bot.py tests/test_tg_bot.py
git commit -m "feat: телеграм-бот обслуживает несколько клиентов"
```

---

### Task 9: `app/main.py` — сайт по клиентам

**Files:**
- Modify: `app/main.py`, `static/chat.html`
- Test: `tests/test_main.py`

**Interfaces:**
- Routes: `GET /` и `POST /chat` (legacy → клиент `midi`); `GET /{slug}` (404 если клиента нет) → `static/chat.html`; `POST /{slug}/chat`.
- `chat.html` шлёт fetch на относительный `chat` (работает из `/` и `/{slug}/`).

- [ ] **Step 1: тест**

`tests/test_main.py`:

```python
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app import clients
from app.main import app


def _reg(tmp_path, monkeypatch):
    monkeypatch.setattr(clients, "CLIENTS_DIR", str(tmp_path))
    for slug in ("midi", "store"):
        d = tmp_path / slug
        d.mkdir()
        (d / "config.toml").write_text(f'name = "{slug}"\n', encoding="utf-8")


def test_legacy_root(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    r = TestClient(app).get("/")
    assert r.status_code == 200


def test_site_index_unknown_client_404(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    assert TestClient(app).get("/missing").status_code == 404


def test_site_index_serves_html(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    r = TestClient(app).get("/midi")
    assert r.status_code == 200


def test_legacy_chat_routes_to_midi(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    with patch("app.main.run_fsm_agent", new_callable=AsyncMock) as agent:
        agent.return_value = ("ответ", {"stage": "discovery"})
        r = TestClient(app).post("/chat", json={"user_id": "u1", "message": "привет"})
    assert r.status_code == 200
    agent.assert_awaited_once_with("web:midi:u1", "привет", client_slug="midi")


def test_site_chat_routes_by_slug(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    # добавляем клиента store в реестр (в _reg создаются midi и store)
    with patch("app.main.run_fsm_agent", new_callable=AsyncMock) as agent:
        agent.return_value = ("ответ", {"stage": "selection"})
        r = TestClient(app).post("/store/chat", json={"user_id": "u2", "message": "хочу"})
    assert r.status_code == 200
    agent.assert_awaited_once_with("web:store:u2", "хочу", client_slug="store")


def test_site_chat_unknown_client_404(tmp_path, monkeypatch):
    _reg(tmp_path, monkeypatch)
    with patch("app.main.run_fsm_agent", new_callable=AsyncMock) as agent:
        r = TestClient(app).post("/missing/chat", json={"user_id": "u3", "message": "привет"})
    assert r.status_code == 404
    agent.assert_not_called()
```

`_reg` создаёт и `midi`, и `store`:

- [ ] **Step 2: Run → FAIL**

- [ ] **Step 3: реализация**

`app/main.py`:

```python
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from loguru import logger

from app.clients import get_client

app = FastAPI(title="multi-client assistant", description="AI-консультант по напольным покрытиям")

logger.info("starting multi-client server")


class ChatRequest(BaseModel):
    user_id: str
    message: str


async def _run(user_id: str, message: str, slug: str):
    from app.agent_fsm import run_fsm_agent
    return await run_fsm_agent(f"web:{slug}:{user_id}", message, client_slug=slug)


@app.get("/")
async def index():
    logger.debug("serving chat.html")
    return FileResponse("static/chat.html")


@app.post("/chat")
async def chat_legacy(req: ChatRequest):
    logger.info("legacy chat user={}", req.user_id)
    response, state = await _run(req.user_id, req.message, "midi")
    return {"response": response, "state": state}


@app.get("/{slug}")
async def site_index(slug: str):
    if get_client(slug) is None:
        return JSONResponse({"detail": "client not found"}, status_code=404)
    return FileResponse("static/chat.html")


@app.post("/{slug}/chat")
async def site_chat(slug: str, req: ChatRequest):
    logger.info("chat slug={} user={}", slug, req.user_id)
    if get_client(slug) is None:
        return JSONResponse({"detail": "client not found"}, status_code=404)
    response, state = await _run(req.user_id, req.message, slug)
    return {"response": response, "state": state}
```

Одна загвоздка: `GET /{slug}` перехватит любой GET-путь, включая `/jerks` и т.д. OK (ничего статического нет). Но `GET /` зарегистрирован раньше — ок.

`static/chat.html`, строка 132:

```js
    const res = await fetch('chat', {
```

(убрать ведущий `/` — работает на `/` и `/{slug}/` ).

- [ ] **Step 4: Run → PASS**

Run: `python3 -m pytest tests/test_main.py -v` и `python3 -m pytest tests/ -v`
Expected: PASS

- [ ] **Step 5: коммит**

```bash
git add app/main.py static/chat.html tests/test_main.py
git commit -m "feat: веб-канал по клиентам (/{slug} и /{slug}/chat)"
```

---

### Task 10: Миграция существующего клиента в `clients/midi`

**Files:**
- Create: `clients/midi/config.toml`
- Create: `clients/midi/scrape.py` (перенос логики из `app/scrape_products.py`, пишет `clients/midi/catalog.csv`)
- Modify: `.gitignore` — `clients/*/catalog.csv`, `clients/*/stock.xlsx`, `clients/*/products.db`
- Modify: `README.md`
- Delete: `app/scrape_products.py` (код переехал в `clients/midi/scrape.py`)

**Interfaces:**
- `clients/midi/scrape.py` — standalone-скрипт: скрейпит midiltd.ru по `site_url`, пишет `clients/midi/catalog.csv` (UTF-8 BOM), колонки: `Артикул,Наименование,Цена,Ссылка`.
- `clients/midi/config.toml`:

```toml
name = "MIDI"
slug = "midi"
bot_token = ""
site_url = "https://midiltd.ru/catalog/napolnye_pokrytiya/filter/in_stock-is-y/apply/?SHOWALL_1=1"
```

- [ ] **Step 1: создаём `clients/midi/config.toml`** (содержимое выше)

- [ ] **Step 2: создаём `clients/midi/scrape.py`** (порт `app/scrape_products.py` + запись CSV):

```python
"""Одноразовый скрейпер каталога midiltd.ru (Bitrix) -> clients/midi/catalog.csv.

Скрипт вне ядра: его можно править под изменение структуры сайта — на агента
это не влияет. Запуск: python3 clients/midi/scrape.py
"""
import csv
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

URL = "https://midiltd.ru/catalog/napolnye_pokrytiya/filter/in_stock-is-y/apply/?SHOWALL_1=1"
OUT = os.path.join(os.path.dirname(__file__), "catalog.csv")


def scrape(url: str) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return [
        {
            "article": (el.get("data-value") or "").strip() if el else "",
            "name": n.get_text(strip=True),
            "price": p.get_text(strip=True) if p else "",
            "url": urljoin(url, a.get("href", "")) if a else "",
        }
        for n, p, a, el in zip(
            soup.select(".catalog-block__info-title"),
            soup.select(".price__new-val"),
            soup.select(".dark_link.switcher-title"),
            soup.select(".js-replace-article"),
        )
    ]


def main():
    products = scrape(URL)
    print(f"Найдено: {len(products)}")
    with open(OUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Артикул", "Наименование", "Цена", "Ссылка"])
        for p in products:
            if p["name"]:
                w.writerow([p["article"] or "", p["name"], p["price"] or "", p["url"] or ""])
    print(f"Каталог сохранён: {OUT}")


if __name__ == "__main__":
    main()
```

ВНИМАНИЕ: селектор цены `.price__new-val` в репо был `.price__new-val` (см. старый код) — менять не надо.

- [ ] **Step 3: удаляем `app/scrape_products.py`**

```bash
git rm app/scrape_products.py
```

- [ ] **Step 4: `.gitignore`** — добавить в конец:

```
# Каталоги клиентов: данные и генерируемые файлы
clients/*/products.db
clients/*/catalog.csv
clients/*/catalog.xlsx
clients/*/stock.xlsx
```

- [ ] **Step 5: README** — заменить раздел «Подготовка базы»:

```markdown
## Подготовка базы клиента

Каждый клиент — папка `clients/<slug>` с `config.toml`, каталогом
(`catalog.csv` или `catalog.xlsx` с шапкой: артикул/код, наименование/название,
цена, ссылка), остатками `stock.xlsx` и своей БД. Загрузка клиента целиком:

```bash
python3 -m app.ingest midi            # каталог + остатки + GPT-разбор спек
python3 -m app.ingest midi --no-parse # без вызова YandexGPT
```

Как формируется каталог — зависит от клиента: скрейп сайта или экспорт из
админки. Скрейп midiltd.ru: `python3 clients/midi/scrape.py`.
```

- [ ] **Step 6: смоук-тест**

```bash
python3 -m pytest tests/ -v
python3 -m app.ingest midi --no-parse
```
Expected: pytest зелёный; ingest либо пишет каталог/остатки, либо лог «нет stock.xlsx»/«нет каталога» — не падает.

- [ ] **Step 7: коммит**

```bash
```bash
# Step 3 уже убрал app/scrape_products.py из индекса
git add clients/midi/config.toml clients/midi/scrape.py .gitignore README.md
git commit -m "feat: миграция клиента midi, скрейп вне ядра (clients/midi/scrape.py)"
```
```

---

### Task 11: Финализация

**Files:**
- Modify: `docs/superpowers/specs/2026-08-03-multi-client-architecture-design.md` (правим под факт: `config.toml`, csv-вход, без доп. колонок, скрейпер `clients/*/scrape.py`)
- Modify: `docs/AGENTS.md` (структура: папка `clients/`, модули `app/clients.py`, `app/catalog.py`, `app/xlsx.py`, `app/ingest.py`; раздел «Клиенты и загрузка»)

- [ ] **Step 1: прогон всех тестов**

```bash
python3 -m pytest tests/ -v
```
Зелёный.

- [ ] **Step 2: правим спеку и AGENTS.md** (только doc, без кода, короткими правками — согласуется с планом и фактикой).

- [ ] **Step 3: коммит**

```bash
git add docs/
git commit -m "chore: спека и AGENTS.md под фактическую архитектуру клиентов"
```

---
## Self-Review

**Покрытие спеки (2026-08-03):**
- Клиент = папка с конфигом + своя БД → Task 1, Task 10.
- Единый вход каталога по алиасам шапки → Task 3.
- Скрейп вне ядра → Task 10.
- Остатки с маппингом колонок из конфига → Task 2, используются в Task 7.
- `app.ingest` (каталог → остатки → GPT-разбор) → Task 7.
- Агент scoped по клиенту → Task 4 (db.py), Task 5 (agent_fsm).
- Telegram: Task 8. Сайт: Task 9.
- Отложено (YAGNI, из спеки): админка, доп-колонки спек из файла, дедуп — в плане нет.

**Мелочи плоскости:**
- Все сигнатуры согласованы (db_path в db.py/parse/agent_fsm; client_slug в run_fsm_agent).
- `tests/xlsx_fixtures.py` используется из Task 2 и Task 3/7.
- `client.fact` — нет; везде `client_slug`.