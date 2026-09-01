---
name: mvls-order
description: >
  Fill in an MVLS Supplier Requisition Form (Excel) for a University of Glasgow lab.
  Trigger when the user explicitly says "mvls-order" or "mvls order", or when configuring/setting up order defaults.
---

# MVLS Order Form Skill

Fill the Excel requisition template from product details and deliver it as a download.

## Execution order — always follow this sequence

1. **First-Time Setup Guard** — Check if personal defaults are configured before placing orders
2. **Step 0** — Confirm the grant (can happen before fetching any product page)
3. **Step 1** — Fetch/extract product details from the URL or screenshot
4. **Post-fetch checks** — Quantity, price disambiguation, currency, and promo detection
   (all require the product page content; do **not** attempt these before Step 1)
5. **Step 2** — Assemble the `comments` string
6. **Step 3** — Run the fill script (one run per form; repeat for each batch if multiple forms are needed)
7. **Step 4** — Present all output files to the user

---

## First-Time Setup Guard

Before proceeding with an order, inspect the **User-configurable defaults** and **Grant dictionary** tables below:
- If `ordered_by` is still `[YOUR NAME]` (or any placeholder like `[YOUR EMAIL]`), or if the user asks to "setup mvls-order" / "configure mvls order":
  1. Prompt the user for their lab details:
     - Full Name
     - Email address (written to the "Extension & Email" field C23; phone extension is not needed)
     - Room / Building
     - Frequently used grant names & project codes (e.g. name: `labgrant`, code: `123456-01`)
     *(Note: School defaults to `254: School of Molecular Biosciences`, Payment Method to `Purchase Order`, and Tax Code to `AE - (Purchases - Exempt)`. Do NOT ask the user for School, Tax Code, or Payment Method during the initial setup unless they explicitly ask to change them).*
  2. Directly update the defaults table and grant dictionary in this `SKILL.md` file (and `scripts/fill_order.py`).
  3. Confirm the configuration to the user.
  4. If the user was in the middle of placing an order, immediately proceed to Step 0.
  *(Alternatively, users can run `python3 scripts/setup.py` from their terminal to run an interactive setup wizard).*

---

## User-configurable defaults

These are the personal defaults written into the form. The user can change any of them at any time by saying things like "change the name in the mvls order form to X" or "update my email to X".

| Field             | Cell | Current default                          | JSON field         |
|-------------------|------|------------------------------------------|--------------------|
| Ordered by (Name) | C22  | [YOUR NAME]                              | `ordered_by`       |
| Extension & Email | C23  | [YOUR EMAIL]                             | `extension_email`  |
| Room/Building     | C24  | [YOUR ROOM/BUILDING]                     | `room_building`    |
| School            | C21  | 254: School of Molecular Biosciences     | `school`           |
| Payment Method    | C27  | Purchase Order                           | `payment_method`   |
| Tax Code          | C35  | AE - (Purchases - Exempt)                | `tax_code`         |

To update: extract the new value from the user's message, update the table above in this SKILL.md, and confirm the change. No form needs to be generated just for a default update.

**School and Tax Code are dropdowns** — their values must match the form's allowed list exactly or Excel flags a validation error. Valid options live in the template's `Lists` sheet:
- **School** (`Lists!D2:D12`): `EQN: Equine Clinical Sciences`, `SAH: Small Animal Hospital`, `202: School of Medicine, Dentistry & Nursing`, `203: School of Biodiversity, One Health & Veterinary Medicine`, `251: School of Cancer Sciences`, `252: School of Cardiovascular & Metabolic Health`, `253: School of Infection & Immunity`, `254: School of Molecular Biosciences`, `255: School of Psychology & Neuroscience`, `256: School of Health & Wellbeing`, `299: MVLS College Support`
- **Tax Code** (`Lists!G2:G9`): `AE - (Purchases - Exempt)`, `AL - (Purchases - 5%)`, `AO - (Purchases - Outside the Scope)`, `AS - (Purchases - Standard Rated VAT)`, `AT - (Purchases - 12.5%)`, `AZ - (Purchases - 0%)`, `EF - [VAT Exemption Certificate (Purchases)]`, `EU - (Foreign orders - VAT charged later)`
- **Payment Method** (`C27` dropdown): `Purchase Order`, `Credit Card`

## Grant → Project Code Dictionary

| Grant name | Project code |
|------------|-------------|
| labgrant   | 123456-01   |

If the user names a grant not listed here, ask them to confirm the project code directly, then proceed. For any grant not in this table, set `grant_label` to `"custom"` in the JSON.

To add or update entries, the user can ask you to edit this table.

---

## Tool-Agnostic User Interaction Guidelines

When asking the user questions below (grant, quantity, multiple sizes, multiple prices, currency, promotions):
- **If an interactive UI question tool is available** (e.g. `ask_question`, `ask_user_input_v0`, or `AskUserQuestion`), call it with single-select options and support free-text answers.
- **Otherwise (e.g. VS Code Chat with DeepSeek API, Continue, standard LLM chat)**: Output the question in chat with clearly numbered choices:
  ```
  [Question text]
  1. Option A
  2. Option B
  3. Enter custom value
  ```
  Instruct the user they can reply with the number or enter their custom value.

---

## Step 0 — Confirm the grant

If the grant has not been specified in the user's message, ask **before** fetching any product page:

```
Question: "Which grant should this order be charged to?"
Options: [List configured grant names from dictionary above, plus "Other (enter project code)"]
```

If the user selects "Other", ask for the project code (free-text follow-up), then set `grant_label` to `"custom"` in the JSON.

If the grant was already provided, skip this question entirely.

---

## Step 1 — Collect product details

For each URL, retrieve the page content using available web fetch / HTTP reading tools (such as `read_url_content`, web fetch, or curl). For screenshots or pasted text, extract details directly from the provided content. Extract:

- **`cat_no`** – catalogue/SKU code
- **`name`** – product name
- **`price`** – ex-VAT if both ex-VAT and inc-VAT are shown; otherwise the visible price as-is. Never derive or calculate.
- **`supplier_name`** – exact brand name from the page (e.g. "Fisher Scientific" not "Thermo Fisher"). Must be a non-empty string.
- **`url`** – ONLY if the user explicitly provided a product URL. If information came from a screenshot or copy-paste, set `url` to `""`. **NEVER infer, guess, or construct URLs.**

**Override rule**: If the user explicitly states a product name, catalogue number, or price (e.g. "use product name X", "the catalogue number is Y"), use that value instead of whatever was extracted from the URL or screenshot.

**If web access fails or is unavailable**, ask:
> "I couldn't access that page — could you paste a screenshot or copy the product details (code, name, price) into the chat?"

When the user provides a screenshot or pasted text, set `url` to `""` (same rule as above). The post-fetch checks below still apply to user-provided content.

All products on one form must share the same supplier. If items span multiple suppliers, note the split and handle each supplier's products as a separate batch (see Step 3).

---

## Post-fetch checks (perform after Step 1, before Step 2)

**Do not attempt any of these checks before you have fetched or received the product details.**

### Quantity check

If quantity was not specified in the user's message, ask now that the actual product name is known:

```
Question: "How many [actual product name from Step 1] would you like to order?"
Options: ["1", "Enter a different quantity"]
```

If the user selects "Enter a different quantity", follow up to collect the number. The `quantity` value passed to the script must be a **plain integer** (e.g. `2`, not `"two"` or `"2 boxes"`).

For multiple products, ask about each missing quantity before moving on.

### Multiple quantities for same catalogue number (CRITICAL)

If the same catalogue number appears to be linked to more than one size option (e.g. 10 mg, 100 mg, 1000 mg), ask the user to clarify **before** extracting any fields for that product:

```
Question: "Catalogue number [X] appears in multiple sizes. Which do you want?"
Options: ["10 mg", "100 mg", "1000 mg"]   ← use actual sizes found
```

After the user selects a size, use that selection to pick the correct `cat_no`, `name`, and `price` from the page. Do not mix fields across sizes.

### Price detection — HANDLE BEFORE PROMOTION LOGIC

**Step A — Identify the relevant price(s) for the specific catalogue number being ordered.** Only look at prices attached to the exact catalogue/SKU code in scope. Ignore prices for other pack sizes, SKUs, or unrelated rows — even if they appear on the same page.

**Step B — If the user explicitly stated a price in their prompt**, use that price directly. Do not ask.

**Step C — If exactly one price is found for the relevant catalogue number**, use it. No question needed.

**Step D — If two or more prices are found for the same catalogue number** (e.g. a crossed-out original alongside a discounted/online price), ask:

```
Question: "I can see multiple prices for [cat_no]. Which should I use on the form?"
Options: ["£127.65 (Online Exclusive)", "£145.00 (original)", "Enter manually"]
```

Use the actual figures and any labels visible on the page (e.g. "Online Exclusive", "was", "save"). If no label is readable, use "Price A", "Price B" etc.

**If price is not found anywhere** (page or screenshot), ask:

```
Question: "I couldn't find a price for [product name]. What would you like to do?"
Options: ["Leave it as 0", "Leave it as NA", "Type in the price now"]
```

- "Leave it as 0" → set `"price": 0` in the JSON (the number zero)
- "Leave it as NA" → set `"price": "NA"` in the JSON (the **string** `"NA"`, not JSON null)
- "Type in the price now" → collect the value from the user

### Currency handling — APPLY AFTER THE CORRECT PRICE IS IDENTIFIED

The form has a dedicated **Currency of Order** dropdown (cell C31, JSON field `currency`), so the currency is recorded on the form itself, not just buried in the comments. Default is `GBP`. Allowed values (must match the dropdown exactly): `GBP, EUR, USD, AUD, CAD, CNY, CYP, CZK, DKK, HKD, JPY, MXP, NOK, NZD, PLN, SEK, SGD, THB, ZAR`.

**If the price is in GBP (£)**, leave `currency` as `"GBP"` and proceed. No question needed.

**If the price is in any other currency** (e.g. USD $, EUR €), ask:

```
Question: "The listed price for [cat_no] is [amount] [currency]. How should I record it?"
Options: ["Use as-is ([amount] [currency] — admin will convert)", "Convert to GBP ([converted amount] at today's rate)", "Enter manually"]
```

- For "Use as-is": record the numeric value as given (e.g. `95.00` for $95.00) **and set the `currency` JSON field to the matching code** (e.g. `"USD"`) so cell C31 reflects it.
- For "Convert to GBP": search or compute the GBP equivalent at current exchange rates, round to 2 decimal places, and use that figure with `currency` left as `"GBP"`. Add a comment noting the conversion (e.g. `Price converted from $95.00 USD at 0.79 on 2026-09-01`).
- For "Enter manually": prompt the user to type the value, then collect it before proceeding. Confirm which currency C31 should show.

### Promotion code detection — HANDLE SEPARATELY AFTER PRICE IS CONFIRMED

Scan the fetched page or provided screenshot for promotion codes (e.g. "Promo code: P6171678", "Step into wonderful savings", discount banners). This is a separate question from the price above.

**Override rule**: If the user explicitly states a promotion code in their prompt (e.g. "use promo P6171678"), use that code and skip the question below.

**When one or more promotion codes are detected** and the user has NOT already specified one, ask:

```
Question: "I also spotted promotion code(s) for this product. Would you like to apply one?"
Options: ["P6171678 – Get 3 for the price of 2", "P6154481 – Step into wonderful savings", "No promotion"]
```

Use the actual code identifiers and descriptions found on the page.

If no promotion codes are found, proceed without asking.

---

## Step 2 — Build comments content

Populate the `comments` field in the JSON from these sources, each on its own line. **Only include items that are actually relevant:**

1. Promo code, if any — format: `Promo code: <code>`
2. Product URL(s), **one per line only if the user explicitly provided them**. Do NOT add URLs that were inferred, constructed, or sourced from screenshots.
3. Any other explicit instructions or requirements from the user — one item per line

**Note on quote reference**: the `quote_ref` JSON field already writes the quote reference to cell C28. Do not also add it to `comments` — it would appear in both C28 and the comments cell B57. Only include it in `comments` if the user specifically asks to have it in the notes cell as well.

Use `\n` as the line separator — the two-character escape sequence (backslash + n), **not** a literal newline character. Example: `"Promo code: P123\nhttps://example.com"`.

---

## Step 3 — Run the fill script

`{skill_dir}` is the directory containing this SKILL.md file. Output defaults dynamically to the current working directory (`.`).

Write the JSON to a temp file first, then pass it to the script. This safely handles apostrophes, special characters, and multi-line comments in any field value:

```bash
cat > /tmp/mvls_order.json << 'PAYLOAD'
{paste the complete JSON here}
PAYLOAD
python3 {skill_dir}/scripts/fill_order.py "$(cat /tmp/mvls_order.json)"
```

**JSON schema:**

```json
{
  "project_code": "123456-01",
  "grant_label": "labgrant",
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
  "products": [
    {
      "cat_no": "AGL4250",
      "name": "Five slide mailer",
      "price": 2.12,
      "supplier_name": "Agar Scientific",
      "url": "https://www.agarscientific.com/five-slide-mailer",
      "quantity": 10
    }
  ],
  "comments": "Promo code: SAVE10\nhttps://www.agarscientific.com/five-slide-mailer",
  "output_dir": "."
}
```

**Field notes:**
- `project_code` — **required**, never omit; look up from the grant dictionary above. Populates the **Sub-Project(s)** cell C33.
- `grant_label` — used in the output filename only (e.g. `labgrant`); use `"custom"` for any grant not in the dictionary
- `ordered_by`, `extension_email`, `room_building`, `school`, `payment_method`, `tax_code` — **omit them to use the configured defaults** in the defaults table above. Only set them to override for a one-off order. The dropdown fields (`school`, `tax_code`, `payment_method`) must use an exact value from the allowed lists above.
- `currency` — the order currency dropdown (C31); default `"GBP"`. See currency handling above.
- `split_subproject`, `budget_available`, `radiation_order`, `product_weight` — dropdowns with sensible defaults (`No`/`Yes`/`No`/`No`); only override if the user says otherwise.
- `quote_ref` — populates cell C28; leave as `""` if not provided
- `comments` — pre-assembled string for cell B57; use `""` if none; use the `\n` escape (not a real newline) as separator
- `quantity` — must be a **plain integer** (e.g. `10`, not `"10 units"` or `10.0`)
- `price` — use a number (e.g. `2.12`) or the string `"NA"`; **never use JSON null**. The form's Total column is a quantity × unit-cost formula; the script refreshes its cached result so the total shows correctly the moment the file opens (no need to supply a total). An `"NA"` price shows `NA` for both unit cost and total.
- `output_dir` — output folder path. Defaults to `.` (current working directory) if omitted.

**Handling multiple forms (>11 items or multiple suppliers):**

The form holds a maximum of 11 product lines. When you need more than one form:
1. Split products into batches: first by supplier, then into groups of ≤11 within each supplier.
2. Run the script once per batch, each time with its own complete JSON payload.
3. Collect every output path that appears after `SUCCESS:`.
4. After all batches are done, present all generated forms together.

---

## Step 4 — Share the file

After each script run, capture the path from the `SUCCESS: <path>` output.
When all forms have been generated:
- If an environment-specific presentation tool like `present_files` is available, call it with all generated paths.
- Otherwise, provide clickable markdown links (e.g. `[Download Requisition Form](file:///path/to/file.xlsx)`) and display the full absolute file paths so the user can easily open or locate their file.

---

## Cell reference

| Cell    | Content |
|---------|---------|
| C21     | School (dropdown) |
| I21     | Date — auto-filled to today, formatted dd/mm/yyyy |
| C22     | Ordered by (Name) |
| C23     | Extension & Email |
| C24     | Room/Building |
| C25     | Supplier name |
| C27     | Payment Method (dropdown) |
| C28     | Quote Ref |
| C31     | Currency of Order (dropdown) |
| C32     | Split Sub-Project (dropdown) |
| C33     | Sub-Project(s) / project code |
| C34     | Sub-Project Budget Available (dropdown) |
| C35     | Tax Code (dropdown) |
| C37     | Radiation Order (dropdown) |
| C38     | Product Weight >25KG (dropdown) |
| B43–B53 | Catalogue No. (`cat_no`) |
| C43–C53 | Description (`name`) |
| D43–D53 | Agresso Product Code — always blank |
| G43–G53 | Quantity |
| H43–H53 | Unit cost (excl VAT) |
| I43–I53 | Total — `G×H` formula; the script refreshes its cached value so the total is correct on open |
| B57     | Comments (promo code, URLs, any user instructions) |

The fill script (`scripts/fill_order.py`) edits only these cell values directly inside the `.xlsx` XML, leaving every dropdown, hover helper box, the embedded logo, styles, and the Total formulas untouched. It does **not** use openpyxl (which would strip the form's School/Tax Code/Radiation dropdowns on save). The blank template lives at `assets/mvls_requisition_template.xlsx`.

Output filename: `YYYYMMDD_{supplier}_{grant_label}_RequisitionForm.xlsx` (supplier = first word of the supplier name, lowercased).
Max 11 product lines per form — create multiple forms if needed.
