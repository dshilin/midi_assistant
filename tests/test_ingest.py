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
