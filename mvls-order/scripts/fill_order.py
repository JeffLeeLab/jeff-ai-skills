#!/usr/bin/env python3
"""
Fill the MVLS Supplier Requisition Form template with product data.

The 2026 redesigned template carries dropdowns (data validations), hover helper
boxes (cell comments + VML drawings), an embedded logo, and a Total column driven
by formulas. Loading the workbook through openpyxl and re-saving silently strips
the "extension" (x14) dropdowns — School, Tax Code, Radiation, the Agresso product
code — and can drop the comments and image. To keep the form intact we never parse
the workbook: we edit only the specific cell values inside xl/worksheets/sheet1.xml
and copy every other zip entry through byte-for-byte. Pure stdlib, no openpyxl.

JSON input schema (all fields optional except project_code + products):
{
    "project_code": "123456-01",          # -> C33 (required)
    "grant_label": "mygrant",             # filename only
    "school": "254: School of Molecular Biosciences",
    "ordered_by": "[YOUR NAME]",
    "extension_email": "[YOUR EMAIL]",
    "room_building": "[YOUR ROOM/BUILDING]",
    "payment_method": "Purchase Order",
    "quote_ref": "",
    "currency": "GBP",
    "split_subproject": "No",
    "budget_available": "Yes",
    "tax_code": "AE - (Purchases - Exempt)",
    "radiation_order": "No",
    "product_weight": "No",
    "products": [{"cat_no","name","price","supplier_name","url","quantity","promo_code"}],
    "comments": "pre-assembled string with \\n separators",
    "output_dir": "."
}
"""

import json
import re
import sys
import zipfile
from datetime import date, datetime
from pathlib import Path

SHEET = "xl/worksheets/sheet1.xml"
MAX_PRODUCTS = 11
PRODUCT_ROWS_START = 43          # rows 43..53 = 11 lines
EXCEL_EPOCH = date(1899, 12, 30)  # day 0 for Excel's 1900 date system

# Form field cells. Column I (Total) is a formula and is never written.
FIELD_CELLS = {
    "school":           "C21",
    "ordered_by":       "C22",
    "extension_email":  "C23",
    "room_building":    "C24",
    "supplier_name":    "C25",
    "payment_method":   "C27",
    "quote_ref":        "C28",
    "currency":         "C31",
    "split_subproject": "C32",
    "project_code":     "C33",
    "budget_available": "C34",
    "tax_code":         "C35",
    "radiation_order":  "C37",
    "product_weight":   "C38",
    "comments":         "B57",
}
DATE_CELL = "I21"

# Defaults applied when the JSON omits a field. These strings match the template's
# dropdown lists exactly (Lists!D9, Lists!G2, Lists!A1/A2, etc.) so Excel does not
# flag a validation error.
DEFAULTS = {
    "school":           "254: School of Molecular Biosciences",
    "ordered_by":       "[YOUR NAME]",
    "extension_email":  "[YOUR EMAIL]",
    "room_building":    "[YOUR ROOM/BUILDING]",
    "payment_method":   "Purchase Order",
    "currency":         "GBP",
    "split_subproject": "No",
    "budget_available": "Yes",
    "tax_code":         "AE - (Purchases - Exempt)",
    "radiation_order":  "No",
    "product_weight":   "No",
}


def parse_price(raw):
    if raw is None:
        return "NA"
    if isinstance(raw, str) and raw.strip().upper() == "NA":
        return "NA"
    if isinstance(raw, (int, float)):
        return float(raw)
    cleaned = re.sub(r"[£$€,\s]", "", str(raw))
    return float(cleaned) if cleaned else "NA"


def _xml_escape(text):
    return (str(text).replace("&", "&amp;")
                     .replace("<", "&lt;")
                     .replace(">", "&gt;"))


def set_total_cache(sheet_xml: str, row: int, total) -> str:
    """Refresh the cached value of the Total formula cell I{row}, keeping its `<f>`.

    Excel stores a cached `<v>` next to each formula so it can display a value
    without recalculating. When we change quantity/unit-cost we must refresh this
    cache (the workbook also has fullCalcOnLoad set, so Excel recomputes on open —
    but refreshing the cache keeps non-recalculating previews, e.g. Drive/Quick
    Look, correct too).
    """
    addr = f"I{row}"
    m = re.search(r'<c r="%s"([^>]*)>(.*?)</c>' % re.escape(addr), sheet_xml, re.S)
    if not m:
        return sheet_xml
    attrs, body = m.group(1), m.group(2)
    fm = re.search(r'<f[^>]*>.*?</f>|<f[^>]*/>', body)
    f_elem = fm.group(0) if fm else f"<f>G{row}*H{row}</f>"
    new = f'<c r="{addr}"{attrs}>{f_elem}<v>{total}</v></c>'
    return sheet_xml[:m.start()] + new + sheet_xml[m.end():]


def set_cell(sheet_xml: str, addr: str, value, kind: str = "str") -> str:
    """Replace the value of cell `addr`, preserving its style (s=) attribute.

    Matches both self-closing (`<c r="C28" s="54"/>`) and populated
    (`<c r="C22" ...>...</c>`) cell elements. `kind` is "str" or "num".
    An empty/None value clears the cell to a styled blank.
    """
    pat = re.compile(r'<c r="%s"(?: [^>]*?)?(?:/>|>.*?</c>)' % re.escape(addr), re.S)
    m = pat.search(sheet_xml)
    if not m:
        raise ValueError(f"cell {addr} not found in template sheet")
    old = m.group(0)
    sm = re.search(r'\bs="(\d+)"', old)
    sattr = f' s="{sm.group(1)}"' if sm else ""

    if value is None or value == "":
        new = f'<c r="{addr}"{sattr}/>'
    elif kind == "num":
        new = f'<c r="{addr}"{sattr}><v>{value}</v></c>'
    else:
        new = (f'<c r="{addr}"{sattr} t="inlineStr">'
               f'<is><t xml:space="preserve">{_xml_escape(value)}</t></is></c>')
    return sheet_xml[:m.start()] + new + sheet_xml[m.end():]


def build_sheet(sheet_xml: str, data: dict) -> str:
    products = data["products"]
    if not products:
        raise ValueError("products list is empty")
    if len(products) > MAX_PRODUCTS:
        raise ValueError(f"Max {MAX_PRODUCTS} product lines per form; got {len(products)}")

    project_code = (data.get("project_code") or "").strip()
    if not project_code:
        raise ValueError("project_code is required and must not be empty")

    values = {
        "school":           data.get("school") or DEFAULTS["school"],
        "ordered_by":       data.get("ordered_by") or DEFAULTS["ordered_by"],
        "extension_email":  data.get("extension_email") or DEFAULTS["extension_email"],
        "room_building":    data.get("room_building") or DEFAULTS["room_building"],
        "supplier_name":    (products[0].get("supplier_name") or "").strip() or "Unknown",
        "payment_method":   data.get("payment_method") or DEFAULTS["payment_method"],
        "quote_ref":        (data.get("quote_ref") or "").strip(),
        "currency":         data.get("currency") or DEFAULTS["currency"],
        "split_subproject": data.get("split_subproject") or DEFAULTS["split_subproject"],
        "project_code":     project_code,
        "budget_available": data.get("budget_available") or DEFAULTS["budget_available"],
        "tax_code":         data.get("tax_code") or DEFAULTS["tax_code"],
        "radiation_order":  data.get("radiation_order") or DEFAULTS["radiation_order"],
        "product_weight":   data.get("product_weight") or DEFAULTS["product_weight"],
        "comments":         (data.get("comments") or "").strip(),
    }
    for key, addr in FIELD_CELLS.items():
        sheet_xml = set_cell(sheet_xml, addr, values[key], "str")

    # Date -> today as an Excel serial (cell style already renders DD/MM/YYYY).
    serial = (date.today() - EXCEL_EPOCH).days
    sheet_xml = set_cell(sheet_xml, DATE_CELL, serial, "num")

    # Product rows: B=cat_no, C=name, G=quantity, H=unit cost.
    # D (Agresso) stays blank. I (Total) is a G*H formula whose cached value we
    # must refresh so the total is correct on open and in non-recalc previews.
    for i, p in enumerate(products):
        row = PRODUCT_ROWS_START + i
        qty = int(p["quantity"])
        sheet_xml = set_cell(sheet_xml, f"B{row}", (p.get("cat_no") or "").strip(), "str")
        sheet_xml = set_cell(sheet_xml, f"C{row}", (p.get("name") or "").strip(), "str")
        sheet_xml = set_cell(sheet_xml, f"G{row}", qty, "num")
        price = parse_price(p.get("price"))
        if price == "NA":
            # No price yet: show NA for unit cost, and make the total NA too
            # (a numeric formula × "NA" text would surface a #VALUE! error).
            sheet_xml = set_cell(sheet_xml, f"H{row}", "NA", "str")
            sheet_xml = set_cell(sheet_xml, f"I{row}", "NA", "str")
        else:
            sheet_xml = set_cell(sheet_xml, f"H{row}", price, "num")
            sheet_xml = set_total_cache(sheet_xml, row, round(qty * price, 2))

    return sheet_xml


def fill_order(data: dict, skill_assets_dir: str) -> str:
    template_path = Path(skill_assets_dir) / "mvls_requisition_template.xlsx"
    output_dir = Path(data.get("output_dir") or Path.cwd())

    with zipfile.ZipFile(template_path) as zin:
        names = zin.namelist()
        infos = {n: zin.getinfo(n) for n in names}
        blobs = {n: zin.read(n) for n in names}

    sheet_xml = blobs[SHEET].decode("utf-8")
    blobs[SHEET] = build_sheet(sheet_xml, data).encode("utf-8")

    date_str = datetime.now().strftime("%Y%m%d")
    supplier_word = re.sub(
        r"[^\w]", "",
        (data["products"][0].get("supplier_name") or "Unknown").split()[0],
    ).lower()
    grant = data.get("grant_label", "order")
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{date_str}_{supplier_word}_{grant}_RequisitionForm.xlsx"

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            zout.writestr(infos[n], blobs[n])
    return str(out_path.resolve())


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fill_order.py '<json>'", file=sys.stderr)
        sys.exit(1)
    try:
        payload = json.loads(sys.argv[1])
        skill_root = Path(__file__).parent.parent
        print(f"SUCCESS: {fill_order(payload, str(skill_root / 'assets'))}")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
