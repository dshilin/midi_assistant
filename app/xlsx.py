"""Read the first .xlsx worksheet with the standard library."""
import re
import zipfile
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_first_sheet_rows(path: str) -> list[dict[str, str]]:
    """Return first-sheet rows as {column_letter: value}. Empty cells are omitted."""
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
