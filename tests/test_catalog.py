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
