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
    """Minimal valid .xlsx with inline strings for tests."""
    nss = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    body = []
    for ri, row in enumerate(rows, 1):
        cells = "".join(
            f'<c r="{_col_letter(ci)}{ri}" t="inlineStr"><is><t>{escape(str(v))}</t></is></c>'
            for ci, v in enumerate(row, 1)
        )
        body.append(f'<row r="{ri}">{cells}</row>')
    sheet = f'<worksheet xmlns="{nss}"><sheetData>{"".join(body)}</sheetData></worksheet>'

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
