"""Create a clearly labelled Indian-law demo contract PDF from seeded SQLite clauses."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pymupdf

from legalagent.db import fetch_contract_graph_json, init_db


def main() -> None:
    init_db()
    data = fetch_contract_graph_json("tech_msa")
    if not data:
        raise SystemExit("Seed the database before creating the demo PDF")

    output = Path("data/demo/india/indian_tech_msa_demo.pdf")
    output.parent.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open()
    page = document.new_page()
    y = 54
    for heading, body, size in [
        ("LEGALAGENT INDIAN TECH SERVICES MSA", "Synthetic Indian-law demonstration contract", 16),
        ("Notice", "This generated document is a prototype fixture, not an executed agreement.", 10),
    ]:
        page.insert_text((54, y), heading, fontsize=size, fontname="hebo" if size > 12 else "heit", color=(0.1, 0.14, 0.2))
        y += 24 if size > 12 else 20

    for clause in data["clauses"]:
        text = f"{clause['clause_num']} {clause['title']}\n{clause['text']}"
        height = max(70, 16 * (len(text) // 92 + 2))
        if y + height > page.rect.height - 54:
            page = document.new_page()
            y = 54
        page.insert_textbox((54, y, page.rect.width - 54, y + height), text, fontsize=10, lineheight=1.35, fontname="helv", color=(0.1, 0.14, 0.2))
        y += height + 18

    document.save(output)
    document.close()
    print(output)


if __name__ == "__main__":
    main()