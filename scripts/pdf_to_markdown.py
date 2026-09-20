"""Convert a PDF contract to Markdown using PyMuPDF."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from legalagent.core.ingestion import pdf_to_markdown


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit("Usage: python scripts/pdf_to_markdown.py INPUT.pdf [OUTPUT.md]")
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2]) if len(sys.argv) == 3 else source.with_suffix(".md")
    destination.write_text(pdf_to_markdown(str(source)), encoding="utf-8")
    print(destination)


if __name__ == "__main__":
    main()