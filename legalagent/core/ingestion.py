import re
from pathlib import Path

# Form-feed marks a page boundary. pdfplumber pages are joined with it so
# normalize() can tell how many pages a header/footer actually repeats across.
PAGE_BREAK = "\f"


def ingest(file_path: str) -> str:
    """
    Load and normalize contract text from PDF, DOCX, or TXT.
    Returns normalized_text: canonical document for offsets.
    """
    path = Path(file_path)

    if path.suffix.lower() == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                text = PAGE_BREAK.join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            raise ImportError("pdfplumber required for PDF ingestion")
    elif path.suffix.lower() == ".docx":
        try:
            from docx import Document
            doc = Document(file_path)
            text = "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            raise ImportError("python-docx required for DOCX ingestion")
    else:
        # TXT, plain read
        text = path.read_text(encoding="utf-8", errors="replace")

    return normalize(text)


def normalize(text: str) -> str:
    """
    Normalization in fixed order, applied exactly once:
    1. Strip repeating headers/footers (lines recurring on most pages)
    2. Drop standalone page numbers
    3. Rejoin hyphenated line breaks
    4. Collapse whitespace runs, preserve paragraph breaks
    """
    num_pages = max(1, text.count(PAGE_BREAK) + 1)
    text = text.replace(PAGE_BREAK, "\n")
    lines = text.split("\n")

    # 1. Strip repeating headers/footers: a line recurring on most PAGES
    #    (not most lines — a header appears once per page, not once per line).
    #    Meaningless with a single page — nothing "repeats across pages" then.
    if num_pages > 1:
        line_counts = {}
        for line in lines:
            stripped = line.strip()
            if 5 < len(stripped) < 100:  # Skip very short/long lines
                line_counts[stripped] = line_counts.get(stripped, 0) + 1

        threshold = num_pages * 0.8
        headers_footers = {line for line, count in line_counts.items() if count > threshold}

        lines = [line for line in lines if line.strip() not in headers_footers]

    # 2. Drop standalone page numbers (e.g., "Page 5", "5", "[5]")
    lines = [line for line in lines if not re.match(r'^\s*\[?\s*\d+\s*\]?\s*$', line)]

    # 3. Rejoin hyphenated line breaks (word- \n word -> word-word)
    text = "\n".join(lines)
    text = re.sub(r'([a-z])-\n\s*([a-z])', r'\1\2', text, flags=re.I)

    # 4. Collapse whitespace, preserve paragraph breaks (blank lines = \n\n)
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [re.sub(r'\s+', ' ', p.strip()) for p in paragraphs if p.strip()]
    text = "\n\n".join(paragraphs)

    return text
