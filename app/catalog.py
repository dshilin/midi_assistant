"""Catalog reader: xlsx or csv with header aliases, no per-client mapping."""
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
        if not rows:
            return []
        fields = {col: _field(h) for col, h in rows[0].items()}
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
