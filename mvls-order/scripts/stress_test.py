#!/usr/bin/env python3
"""
Stress-test harness for fill_order.py.

Throws a large battery of adversarial payloads at the fill engine and validates
every output against the invariants that matter for this form:

  1. All XML parts are well-formed (parse without error).
  2. Every zip part EXCEPT sheet1.xml is byte-identical to the template — this is
     the proof that the dropdowns' backing sheets, the comment/VML hover boxes,
     the logo image, styles, sharedStrings and printer settings all survive.
  3. Inside sheet1.xml, the dropdown blocks (<dataValidations> and the x14 extLst)
     are byte-identical to the template — the exact thing openpyxl destroys.
  4. No calcChain.xml is present (its staleness is what corrupted earlier files).
  5. Totals: each product row's cached <v> equals round(qty*price, 2), or "NA".
  6. The field cells hold exactly the values we asked for (round-trip check).
  7. The output filename follows YYYYMMDD_{supplier}_{grant}_RequisitionForm.xlsx.
  8. Bad input (no products, >11 products, missing project_code) raises, not writes.

Run:  python3 stress_test.py
Exit code is non-zero if any case fails.
"""

import html
import io
import re
import sys
import traceback
import xml.dom.minidom as minidom
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fill_order as fo  # noqa: E402

SKILL_ROOT = Path(__file__).parent.parent
ASSETS = SKILL_ROOT / "assets"
TEMPLATE = ASSETS / "mvls_requisition_template.xlsx"
OUT_DIR = Path("/tmp/mvls_stress")


# ----------------------------------------------------------------------------- helpers

def template_parts():
    with zipfile.ZipFile(TEMPLATE) as z:
        return {n: z.read(n) for n in z.namelist()}


def dropdown_blocks(sheet_xml: str):
    """Return the concatenated dropdown markup we require to stay byte-identical:
    the standard <dataValidations>...</dataValidations> block and the x14 extLst."""
    blocks = []
    dv = re.search(r"<dataValidations[ >].*?</dataValidations>", sheet_xml, re.S)
    blocks.append(dv.group(0) if dv else "")
    ext = re.search(r"<extLst>.*</extLst>", sheet_xml, re.S)
    blocks.append(ext.group(0) if ext else "")
    return blocks


def cell_value(sheet_xml: str, addr: str):
    """Read back a cell's logical value (inlineStr text or numeric/cached <v>)."""
    m = re.search(r'<c r="%s"(?: [^>]*?)?(?:/>|>(.*?)</c>)' % re.escape(addr),
                  sheet_xml, re.S)
    if not m or m.group(1) is None:
        return None
    body = m.group(1)
    t = re.search(r"<t[^>]*>(.*?)</t>", body, re.S)
    if t:
        return html.unescape(t.group(1))
    v = re.search(r"<v>(.*?)</v>", body, re.S)
    return html.unescape(v.group(1)) if v else None


def validate(out_path: str, payload: dict, tmpl: dict):
    """Run all structural + value invariants on one generated file. Returns []
    on success or a list of human-readable failure strings."""
    fails = []
    with zipfile.ZipFile(out_path) as z:
        names = z.namelist()
        out = {n: z.read(n) for n in names}

    # (4) no calcChain
    if "xl/calcChain.xml" in names:
        fails.append("calcChain.xml present")

    # (1) every XML part well-formed
    for n in names:
        if n.endswith((".xml", ".vml", ".rels")):
            try:
                minidom.parseString(out[n])
            except Exception as e:
                fails.append(f"malformed XML: {n} ({e})")

    # (2) every part except sheet1.xml byte-identical to template
    SHEET = fo.SHEET
    for n in tmpl:
        if n == SHEET:
            continue
        if n not in out:
            fails.append(f"missing part vs template: {n}")
        elif out[n] != tmpl[n]:
            fails.append(f"part changed vs template: {n}")
    for n in names:
        if n not in tmpl:
            fails.append(f"unexpected new part: {n}")

    sheet = out[SHEET].decode("utf-8")
    tmpl_sheet = tmpl[SHEET].decode("utf-8")

    # (3) dropdown markup inside sheet1 byte-identical
    if dropdown_blocks(sheet) != dropdown_blocks(tmpl_sheet):
        fails.append("dropdown (dataValidations/x14 extLst) markup changed")

    # (5) totals correct
    for i, p in enumerate(payload["products"]):
        row = fo.PRODUCT_ROWS_START + i
        price = fo.parse_price(p.get("price"))
        got = cell_value(sheet, f"I{row}")
        if price == "NA":
            if got != "NA":
                fails.append(f"row {row}: total should be NA, got {got!r}")
        else:
            want = round(int(p["quantity"]) * price, 2)
            if got is None or abs(float(got) - want) > 1e-6:
                fails.append(f"row {row}: total {got!r} != {want}")

    # (6) field round-trip (the ones we can predict exactly)
    expected = {
        fo.FIELD_CELLS["project_code"]: (payload.get("project_code") or "").strip(),
        fo.FIELD_CELLS["currency"]: payload.get("currency") or fo.DEFAULTS["currency"],
        fo.FIELD_CELLS["school"]: payload.get("school") or fo.DEFAULTS["school"],
    }
    if payload.get("quote_ref"):
        expected[fo.FIELD_CELLS["quote_ref"]] = payload["quote_ref"].strip()
    for addr, want in expected.items():
        got = cell_value(sheet, addr)
        if got != want:
            fails.append(f"cell {addr}: {got!r} != {want!r}")

    # (7) filename convention
    name = Path(out_path).name
    if not re.fullmatch(r"\d{8}_[\w]+_[\w]+_RequisitionForm\.xlsx", name):
        fails.append(f"filename off-convention: {name}")

    return fails


# ----------------------------------------------------------------------------- payloads

def make_payloads():
    """A spread of normal and adversarial cases."""
    P = []

    def base(**kw):
        d = {"project_code": "328584-01", "grant_label": "lee",
             "products": [{"cat_no": "X1", "name": "Widget",
                           "supplier_name": "Anthropic", "price": 44.99,
                           "quantity": 1}]}
        d.update(kw)
        return d

    # 1 normal single line
    P.append(("single_line", base()))
    # 2 the original Anthropic sample
    P.append(("anthropic_sample", base(products=[
        {"cat_no": "", "name": "Claude Code Max Subscription",
         "supplier_name": "Anthropic", "price": 44.99, "quantity": 1}])))
    # 3 full 11-line form (max)
    P.append(("max_11_lines", base(products=[
        {"cat_no": f"CAT-{i}", "name": f"Item {i}", "supplier_name": "Bulk Co",
         "price": round(1.1 * (i + 1), 2), "quantity": i + 1} for i in range(11)])))
    # 4 NA price mixed with priced rows
    P.append(("na_price_mix", base(products=[
        {"cat_no": "A", "name": "Quote pending", "supplier_name": "VWR",
         "price": "NA", "quantity": 3},
        {"cat_no": "B", "name": "Known price", "supplier_name": "VWR",
         "price": 12.50, "quantity": 4}])))
    # 5 all-NA
    P.append(("all_na", base(products=[
        {"cat_no": "Z", "name": "TBD", "supplier_name": "Sigma",
         "price": "NA", "quantity": 2}])))
    # 6 currency strings with symbols / commas / whitespace
    P.append(("messy_price_strings", base(products=[
        {"cat_no": "P", "name": "Pricey", "supplier_name": "Fisher",
         "price": "£1,299.99 ", "quantity": 2}])))
    P.append(("usd_price_string", base(currency="USD", products=[
        {"cat_no": "Q", "name": "US item", "supplier_name": "Addgene",
         "price": "$ 2,000.00", "quantity": 1}])))
    P.append(("euro_price_string", base(currency="EUR", products=[
        {"cat_no": "R", "name": "EU item", "supplier_name": "Eppendorf",
         "price": "€19,50".replace(",", "."), "quantity": 3}])))
    # 7 XML-hostile text in every string field
    nasty = "Tom & Jerry's <b>\"50%\"</b> >> 'widget' & co"
    P.append(("xml_injection", base(
        school='254: School of Molecular Biosciences',
        ordered_by=nasty, room_building=nasty, quote_ref=nasty,
        comments="line1 & <2>\nline2 'quoted' \"dq\"\nhttps://x.com?a=1&b=2",
        products=[{"cat_no": "<&>", "name": nasty, "supplier_name": "A & B Ltd",
                   "price": 9.99, "quantity": 1}])))
    # 8 unicode / accents / non-latin
    P.append(("unicode", base(
        ordered_by="José Müller-Łódź 北京 ✓",
        products=[{"cat_no": "Ω-1", "name": "Pipétte ±0.5µL café",
                   "supplier_name": "Größe Größe", "price": 5.0, "quantity": 2}])))
    # 9 very long strings
    P.append(("very_long_strings", base(
        comments="x" * 4000,
        products=[{"cat_no": "L" * 200, "name": "D" * 500,
                   "supplier_name": "S" * 200, "price": 1.0, "quantity": 1}])))
    # 10 high quantities / fractional prices (float rounding)
    P.append(("rounding", base(products=[
        {"cat_no": "F", "name": "Frac", "supplier_name": "Qiagen",
         "price": 0.1, "quantity": 3},                      # 0.30000000004
        {"cat_no": "G", "name": "Frac2", "supplier_name": "Qiagen",
         "price": 19.999, "quantity": 7}])))
    # 11 large numbers
    P.append(("big_numbers", base(products=[
        {"cat_no": "BIG", "name": "Instrument", "supplier_name": "Bruker",
         "price": 1234567.89, "quantity": 99}])))
    # 12 price given as int / quantity as string
    P.append(("type_coercion", base(products=[
        {"cat_no": "I", "name": "IntPrice", "supplier_name": "NEB",
         "price": 50, "quantity": "4"}])))
    # 13 currency change + school change together
    P.append(("school_and_currency", base(
        school="254: School of Molecular Biosciences", currency="JPY")))
    # 14 supplier name with leading punctuation / digits (filename sanitization)
    P.append(("supplier_filename", base(products=[
        {"cat_no": "S", "name": "X", "supplier_name": "3M  Scientific!!",
         "price": 1.0, "quantity": 1}])))
    # 15 empty optional fields explicitly blank
    P.append(("blank_optionals", base(quote_ref="", comments="",
                                      payment_method="", tax_code="")))
    # 16 missing cat_no / name (only price+qty)
    P.append(("sparse_rows", base(products=[
        {"supplier_name": "Generic", "price": 7.77, "quantity": 5}])))
    # 17 negative / zero quantity edge (should still compute)
    P.append(("zero_qty", base(products=[
        {"cat_no": "ZQ", "name": "Zero", "supplier_name": "T", "price": 5.0,
         "quantity": 0}])))

    return P


# ----------------------------------------------------------------------------- run

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tmpl = template_parts()
    payloads = make_payloads()

    passed = failed = 0
    for label, payload in payloads:
        payload = dict(payload, output_dir=str(OUT_DIR))
        try:
            out = fo.fill_order(payload, str(ASSETS))
            problems = validate(out, payload, tmpl)
        except Exception:
            problems = ["EXCEPTION:\n" + traceback.format_exc()]
        if problems:
            failed += 1
            print(f"  FAIL  {label}")
            for p in problems:
                print("        - " + p.replace("\n", "\n          "))
        else:
            passed += 1
            print(f"  ok    {label}")

    # Guard cases: these MUST raise.
    print("\n  -- guard cases (must raise) --")
    guards = [
        ("no_products", {"project_code": "1", "products": []}),
        ("over_11", {"project_code": "1", "products": [
            {"name": "x", "price": 1, "quantity": 1,
             "supplier_name": "s"} for _ in range(12)]}),
        ("no_project_code", {"products": [
            {"name": "x", "price": 1, "quantity": 1, "supplier_name": "s"}]}),
    ]
    for label, payload in guards:
        payload = dict(payload, output_dir=str(OUT_DIR))
        try:
            fo.fill_order(payload, str(ASSETS))
            failed += 1
            print(f"  FAIL  {label}: did NOT raise")
        except Exception as e:
            passed += 1
            print(f"  ok    {label}: raised {type(e).__name__}: {e}")

    print(f"\n{'=' * 48}\nPASSED {passed}   FAILED {failed}   "
          f"(outputs in {OUT_DIR})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
