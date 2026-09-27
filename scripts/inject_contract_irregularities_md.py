"""Convert an official Indian contract PDF to Markdown and append test clauses."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from legalagent.core.ingestion import pdf_to_markdown

from inject_contract_irregularities import INJECTIONS, MANIFEST, ROOT, SOURCE

OUTPUT = ROOT / "data/demo/india/adversarial/pune_metro_adversarial_15_changes.md"


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source PDF: {SOURCE}")

    source_markdown = pdf_to_markdown(str(SOURCE))
    additions = [
        "# SYNTHETIC ADVERSARIAL AMENDMENTS",
        "",
        "This section was appended for robustness testing. It is not part of the official agreement.",
        "",
    ]
    for number, title, text in INJECTIONS:
        additions.extend([f"{number} {title}", "", text, ""])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(source_markdown.rstrip() + "\n\n" + "\n".join(additions), encoding="utf-8")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.exists() else {}
    manifest["source_markdown"] = str(OUTPUT.relative_to(ROOT))
    manifest["input_mode"] = "source PDF converted with PyMuPDF, then synthetic clauses appended as Markdown"
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(OUTPUT)
    print(MANIFEST)


if __name__ == "__main__":
    main()