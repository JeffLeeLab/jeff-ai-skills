#!/usr/bin/env python3
"""
Derive the blank fill-in template (assets/mvls_requisition_template.xlsx) from a
raw University-issued MVLS requisition form.

Run this whenever MVLS issues a new template revision:

    python3 build_template.py /path/to/new_university_template.xlsx

It applies the small set of transformations the fill script relies on, editing the
XML directly so every dropdown (including the x14 ones that reference the Lists
sheet), cell-comment helper box, and the embedded logo survive untouched:

  1. Clear the sample data from every value cell the fill script writes.
  2. Add an explicit `dd/mm/yyyy` number format and point the Date cell (I21) at it,
     so the date is unambiguous regardless of the opener's locale.
  3. Set `fullCalcOnLoad` so Excel recomputes the Total column on open.
  4. Expand the Total column's shared formula into independent per-row `G*H`
     formulas, so an NA-price row can drop its formula without breaking the others.
  5. Remove calcChain.xml (Excel's formula-dependency cache) and its references —
     once formulas change it goes stale and Excel flags the file as corrupt;
     Excel rebuilds it automatically on open.

If MVLS moves fields to different cells, update the cell constants in fill_order.py
(FIELD_CELLS, DATE_CELL, the product columns/rows) AND re-check the values below.
"""

import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from fill_order import (  # noqa: E402
    set_cell, FIELD_CELLS, DATE_CELL, PRODUCT_ROWS_START, MAX_PRODUCTS, SHEET,
)

DATE_NUMFMT_ID = 167          # first free id after the template's existing custom formats
DATE_FORMAT_CODE = "dd/mm/yyyy"
# The Date cell's existing style (xf 87) copied verbatim but pointed at the new
# numFmt. If a template revision restyles the date cell, refresh this string.
DATE_XF = ('<xf numFmtId="167" fontId="16" fillId="0" borderId="10" xfId="0" '
           'applyNumberFormat="1" applyFont="1" applyBorder="1" '
           'applyAlignment="1" applyProtection="1">'
           '<alignment horizontal="left"/><protection locked="0"/></xf>')


def build(src_path: str, dst_path: str) -> None:
    with zipfile.ZipFile(src_path) as zin:
        names = zin.namelist()
        infos = {n: zin.getinfo(n) for n in names}
        blobs = {n: zin.read(n) for n in names}

    # 2. styles.xml — register dd/mm/yyyy and append a date cell style.
    styles = blobs["xl/styles.xml"].decode()
    styles = re.sub(
        r'(<numFmts count=")(\d+)(">)',
        lambda m: f'{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}'
                  f'<numFmt numFmtId="{DATE_NUMFMT_ID}" formatCode="{DATE_FORMAT_CODE}"/>',
        styles, count=1)
    date_style = int(re.search(r'<cellXfs count="(\d+)">', styles).group(1))
    styles = re.sub(r'(<cellXfs count=")(\d+)(">)',
                    lambda m: f'{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}',
                    styles, count=1)
    styles = styles.replace("</cellXfs>", DATE_XF + "</cellXfs>", 1)
    blobs["xl/styles.xml"] = styles.encode()

    # 3. workbook.xml — recalc on open.
    wb = blobs["xl/workbook.xml"].decode()
    wb = re.sub(r'<calcPr ([^>]*?)/>',
                lambda m: f'<calcPr {m.group(1)} fullCalcOnLoad="1"/>'
                          if "fullCalcOnLoad" not in m.group(1) else m.group(0),
                wb, count=1)
    blobs["xl/workbook.xml"] = wb.encode()

    # 1 + 4. sheet1.xml — clear values, repoint date cell, expand Total formulas.
    xml = blobs[SHEET].decode()
    for addr in FIELD_CELLS.values():
        xml = set_cell(xml, addr, "", "str")
    xml = re.sub(r'<c r="%s"[^>]*?(?:/>|>.*?</c>)' % re.escape(DATE_CELL),
                 f'<c r="{DATE_CELL}" s="{date_style}"/>', xml, count=1)
    for i in range(MAX_PRODUCTS):
        r = PRODUCT_ROWS_START + i
        for col in ("B", "C", "G", "H"):
            xml = set_cell(xml, f"{col}{r}", "", "str")
        xml = re.sub(r'<c r="I%d"([^>]*)>.*?</c>' % r,
                     lambda m: f'<c r="I{r}"{m.group(1)}><f>G{r}*H{r}</f><v>0</v></c>',
                     xml, count=1)
    blobs[SHEET] = xml.encode()

    # 5. Drop calcChain.xml and its two references.
    names = [n for n in names if n != "xl/calcChain.xml"]
    blobs.pop("xl/calcChain.xml", None)
    infos.pop("xl/calcChain.xml", None)
    blobs["[Content_Types].xml"] = re.sub(
        r'<Override PartName="/xl/calcChain.xml"[^>]*/>', "",
        blobs["[Content_Types].xml"].decode()).encode()
    blobs["xl/_rels/workbook.xml.rels"] = re.sub(
        r'<Relationship[^>]*calcChain[^>]*/>', "",
        blobs["xl/_rels/workbook.xml.rels"].decode()).encode()

    with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(infos[n], blobs[n])


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python build_template.py <raw_university_template.xlsx> "
              "[output.xlsx]", file=sys.stderr)
        sys.exit(1)
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else str(
        Path(__file__).parent.parent / "assets" / "mvls_requisition_template.xlsx")
    build(src, dst)
    print(f"Built blank template: {dst}")
