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
    assert conn.execute("SELECT article, quantity FROM stock WHERE article='A-2'").fetchone() == ("A-2", 0.0)


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
