#!/usr/bin/env python3
"""
Interactive setup wizard for MVLS Order Form Skill.
Configures personal defaults (name, email, room, school, tax code, grants)
in SKILL.md and scripts/fill_order.py.
"""

import re
import sys
from pathlib import Path

SCHOOL_OPTIONS = [
    "254: School of Molecular Biosciences",
    "251: School of Cancer Sciences",
    "252: School of Cardiovascular & Metabolic Health",
    "253: School of Infection & Immunity",
    "255: School of Psychology & Neuroscience",
    "256: School of Health & Wellbeing",
    "202: School of Medicine, Dentistry & Nursing",
    "203: School of Biodiversity, One Health & Veterinary Medicine",
    "EQN: Equine Clinical Sciences",
    "SAH: Small Animal Hospital",
    "299: MVLS College Support",
]

TAX_OPTIONS = [
    "AE - (Purchases - Exempt)",
    "AS - (Purchases - Standard Rated VAT)",
    "AL - (Purchases - 5%)",
    "AT - (Purchases - 12.5%)",
    "AZ - (Purchases - 0%)",
    "AO - (Purchases - Outside the Scope)",
    "EF - [VAT Exemption Certificate (Purchases)]",
    "EU - (Foreign orders - VAT charged later)",
]

PAYMENT_OPTIONS = [
    "Purchase Order",
    "Credit Card",
]


def prompt_select(prompt: str, options: list[str], default_idx: int = 0) -> str:
    print(f"\n{prompt}")
    for i, opt in enumerate(options, 1):
        indicator = " (default)" if i - 1 == default_idx else ""
        print(f"  [{i}] {opt}{indicator}")
    while True:
        choice = input(f"Choose [1-{len(options)}] (Enter for default): ").strip()
        if not choice:
            return options[default_idx]
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1]
        print("Invalid choice, please try again.")


def prompt_text(prompt: str, default: str = "") -> str:
    default_hint = f" [{default}]" if default else ""
    val = input(f"{prompt}{default_hint}: ").strip()
    return val if val else default


def main():
    print("=" * 60)
    print("  MVLS Order Form Skill — Personal Setup Wizard")
    print("=" * 60)
    print("This will configure your personal defaults and grant project codes.\n")

    # Locate skill root directory
    script_dir = Path(__file__).resolve().parent
    skill_root = script_dir.parent if script_dir.name == "scripts" else script_dir
    skill_md_path = skill_root / "SKILL.md"
    fill_order_path = skill_root / "scripts" / "fill_order.py"

    if not skill_md_path.exists():
        print(f"Error: Could not locate SKILL.md at {skill_md_path}", file=sys.stderr)
        sys.exit(1)

    # 1. Personal details
    name = prompt_text("Your Full Name (Ordered by)")
    email = prompt_text("Email address (e.g. user@glasgow.ac.uk)")
    room = prompt_text("Room / Building (e.g. Lab 253 Wolfson Link Building)")
    school = prompt_select("School", SCHOOL_OPTIONS, default_idx=0)
    tax_code = prompt_select("Tax Code", TAX_OPTIONS, default_idx=0)
    payment = prompt_select("Payment Method", PAYMENT_OPTIONS, default_idx=0)
    
    # Defaults (School: 254: School of Molecular Biosciences)
    school = "254: School of Molecular Biosciences"
    tax_code = "AE - (Purchases - Exempt)"
    payment = "Purchase Order"
    if "--advanced" in sys.argv or "-a" in sys.argv:
        school = prompt_select("School", SCHOOL_OPTIONS, default_idx=0)
        tax_code = prompt_select("Tax Code", TAX_OPTIONS, default_idx=0)
        payment = prompt_select("Payment Method", PAYMENT_OPTIONS, default_idx=0)
    else:
        print(f"School: {school} (default)")

    # 2. Grant dictionary
    print("\n--- Grant / Sub-Project Dictionary ---")
    print("Enter the grants you frequently charge (e.g. name: 'labgrant', project code: '123456-01').")
    print("Press Enter without input when finished.")
    grants = []
    while True:
        gname = input("Grant label/short name (or press Enter to finish): ").strip().lower()
        if not gname:
            break
        gcode = input(f"Project code for '{gname}' (e.g. 123456-01): ").strip()
        if gcode:
            grants.append((gname, gcode))

    # Read SKILL.md
    md_content = skill_md_path.read_text(encoding="utf-8")

    # Replace defaults table in SKILL.md
    if name:
        md_content = re.sub(
            r"(\| Ordered by \(Name\) \| C22\s+\|)[^|]+(\|)",
            rf"\g<1> {name:<40} \2",
            md_content,
        )
    if email:
        md_content = re.sub(
            r"(\| Extension & Email \| C23\s+\|)[^|]+(\|)",
            rf"\g<1> {email:<40} \2",
            md_content,
        )
    if room:
        md_content = re.sub(
            r"(\| Room/Building\s+\| C24\s+\|)[^|]+(\|)",
            rf"\g<1> {room:<40} \2",
            md_content,
        )
    md_content = re.sub(
        r"(\| School\s+\| C21\s+\|)[^|]+(\|)",
        rf"\g<1> {school:<40} \2",
        md_content,
    )
    md_content = re.sub(
        r"(\| Payment Method\s+\| C27\s+\|)[^|]+(\|)",
        rf"\g<1> {payment:<40} \2",
        md_content,
    )
    md_content = re.sub(
        r"(\| Tax Code\s+\| C35\s+\|)[^|]+(\|)",
        rf"\g<1> {tax_code:<40} \2",
        md_content,
    )

    # Replace grants table in SKILL.md if any were entered
    if grants:
        table_rows = ["| Grant name | Project code |", "|------------|-------------|"]
        for gname, gcode in grants:
            table_rows.append(f"| {gname:<10} | {gcode:<11} |")
        grants_table_str = "\n".join(table_rows)
        md_content = re.sub(
            r"\| Grant name \| Project code \|\n\|[-| ]+\|\n(?:\|[^|\n]+\|[^|\n]+\|\n?)*",
            grants_table_str + "\n",
            md_content,
        )

    skill_md_path.write_text(md_content, encoding="utf-8")
    print(f"\n Updated {skill_md_path.relative_to(skill_root.parent)}")

    # Update fill_order.py DEFAULTS block if it exists
    if fill_order_path.exists():
        py_content = fill_order_path.read_text(encoding="utf-8")
        def_match = re.search(r"(DEFAULTS\s*=\s*\{[^}]+\})", py_content)
        if def_match:
            def_block = def_match.group(1)
            if name:
                def_block = re.sub(r'("ordered_by":\s*)"[^"]*"', rf'\1"{name}"', def_block)
            if email:
                def_block = re.sub(r'("extension_email":\s*)"[^"]*"', rf'\1"{email}"', def_block)
            if room:
                def_block = re.sub(r'("room_building":\s*)"[^"]*"', rf'\1"{room}"', def_block)
            def_block = re.sub(r'("school":\s*)"[^"]*"', rf'\1"{school}"', def_block)
            def_block = re.sub(r'("tax_code":\s*)"[^"]*"', rf'\1"{tax_code}"', def_block)
            def_block = re.sub(r'("payment_method":\s*)"[^"]*"', rf'\1"{payment}"', def_block)
            py_content = py_content[:def_match.start()] + def_block + py_content[def_match.end():]
            fill_order_path.write_text(py_content, encoding="utf-8")
            print(f" Updated {fill_order_path.relative_to(skill_root.parent)}")

    print("\nSetup complete! You can now run the mvls-order skill.")


if __name__ == "__main__":
    main()

