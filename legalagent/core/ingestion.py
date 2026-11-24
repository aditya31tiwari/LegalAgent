"""
Document ingestion: any contract file -> one canonical, normalised text.

  PDF   native text via PyMuPDF; pages with no usable text layer (scans) are rendered
        and OCR'd with Tesseract, in parallel across CPU cores
  DOCX  paragraphs + table cells, in document order
  image PNG/JPG/TIFF -> OCR
  TXT / MD  read as-is

Pages are joined with a form-feed so normalize() can recognise running headers and
footers (lines repeating on most pages) and drop them. Raw extraction is cached by
file content hash in data/cache/ingest/, so a 300-page scanned concession agreement is
OCR'd once (~3 min on 10 cores) and is instant afterwards.

The returned text is what every character offset in Clause/Finding refers to.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

# Form-feed marks a page boundary so normalize() can tell how many pages a
# header/footer actually repeats across.
PAGE_BREAK = "\f"
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "ingest"
MIN_NATIVE_CHARS = 80      # below this a page is treated as scanned
OCR_DPI = 200
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}


def _ocr_png(png: bytes, lang: str = "eng") -> str:
    """Tesseract via its CLI (stdin -> stdout); no Python binding needed."""
    if not shutil.which("tesseract"):
        raise RuntimeError("tesseract not installed (apt install tesseract-ocr)")
    proc = subprocess.run(
        ["tesseract", "stdin", "stdout", "-l", lang, "--psm", "3"],
        input=png, capture_output=True, timeout=180,
        env={**os.environ, "OMP_THREAD_LIMIT": "1"},  # we parallelise across pages instead
    )
    return proc.stdout.decode("utf-8", "replace")


def _ocr_pdf_page(args) -> tuple[int, str]:
    path, index = args
    import pymupdf
    with pymupdf.open(path) as doc:
        png = doc[index].get_pixmap(dpi=OCR_DPI, colorspace=pymupdf.csGRAY).tobytes("png")
    return index, _ocr_png(png)


def _page_native_text(page) -> str:
    """Native text, block by block in reading order; lines inside a block joined by newline."""
    blocks = page.get_text("blocks", sort=True)
    return "\n\n".join(b[4].strip() for b in blocks if b[6] == 0 and b[4].strip())


def _md_to_text(md: str) -> str:
    """Drop Markdown decoration that would break clause regexes; keep line structure."""
    md = re.sub(r"^#{1,6}\s*", "", md, flags=re.M)            # headings
    md = re.sub(r"(\*\*|__)(.*?)\1", r"\2", md)                 # bold
    md = re.sub(r"(?<!\w)[*_](\S.*?)[*_](?!\w)", r"\1", md)     # italics
    md = re.sub(r"^\s*[-|: ]{3,}\s*$", "", md, flags=re.M)     # table rules
    md = re.sub(r"<br\s*/?>", "\n", md)
    return md.strip()


def _workers() -> int:
    return max(1, (os.cpu_count() or 2) - 2)


def pdf_pages(file_path: str, use_ocr: bool = True, progress=None) -> tuple[list[str], dict]:
    """Per-page text of a PDF plus stats {pages, ocr_pages}. OCR runs in parallel."""
    import pymupdf
    with pymupdf.open(file_path) as doc:
        pages = [_page_native_text(p) for p in doc]
    scanned = [i for i, t in enumerate(pages) if len(t) < MIN_NATIVE_CHARS]
    native = [i for i in range(len(pages)) if i not in set(scanned)]
    # Born-digital pages: pymupdf4llm gives layout-aware Markdown (headings, lists,
    # tables as pipe tables) which keeps clause numbering and schedules intact.
    if native:
        try:
            import pymupdf4llm
            chunks = pymupdf4llm.to_markdown(file_path, pages=native, page_chunks=True, show_progress=False)
            for idx, chunk in zip(native, chunks):
                md = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                if len(md.strip()) >= MIN_NATIVE_CHARS:
                    pages[idx] = _md_to_text(md)
        except Exception:
            pass  # plain block extraction already in `pages`
    if use_ocr and scanned and shutil.which("tesseract"):
        done = 0
        with ProcessPoolExecutor(_workers()) as pool:
            for index, text in pool.map(_ocr_pdf_page, [(file_path, i) for i in scanned], chunksize=2):
                if len(text.strip()) > len(pages[index]):
                    pages[index] = text
                done += 1
                if progress:
                    progress(done, len(scanned))
    return pages, {"pages": len(pages), "ocr_pages": len(scanned) if use_ocr else 0}


def pdf_to_markdown(file_path: str, use_ocr: bool = True) -> str:
    """PDF -> lightly structured Markdown (page markers) for previews and scripts."""
    pages, _ = pdf_pages(file_path, use_ocr)
    return "\n\n".join(f"<!-- Page {i} -->\n\n{t}" for i, t in enumerate(pages, 1)).strip() + "\n"


def _docx_text(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    parts = []
    # Walk the body in order so tables stay where they are in the document.
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            parts.append("".join(t.text or "" for t in child.iter() if t.tag.endswith("}t")))
        elif tag == "tbl":
            for row in child.iter():
                if row.tag.endswith("}tr"):
                    cells = ["".join(t.text or "" for t in c.iter() if t.tag.endswith("}t")) for c in row if c.tag.endswith("}tc")]
                    parts.append(" | ".join(c.strip() for c in cells if c.strip()))
    return "\n\n".join(p for p in parts if p.strip())


def _cache_key(path: Path, use_ocr: bool) -> Path:
    h = hashlib.sha1(path.read_bytes()).hexdigest()
    return CACHE_DIR / f"{h}{'' if use_ocr else '.noocr'}.txt"


def extract_raw(file_path: str, use_ocr: bool = True, progress=None) -> tuple[str, dict]:
    """Raw text (pages joined by form-feed) + stats, cached by file content."""
    path = Path(file_path)
    suffix = path.suffix.lower()
    stats = {"format": suffix.lstrip("."), "pages": 1, "ocr_pages": 0, "cached": False}

    if suffix in {".pdf", *IMAGE_SUFFIXES}:
        key = _cache_key(path, use_ocr)
        meta = key.with_suffix(".meta")
        if key.exists():
            stats.update(json.loads(meta.read_text()) if meta.exists() else {})
            stats["cached"] = True
            return key.read_text(encoding="utf-8"), stats
        if suffix == ".pdf":
            pages, s = pdf_pages(str(path), use_ocr, progress)
            stats.update(s)
            raw = PAGE_BREAK.join(pages)
        else:
            raw = _ocr_png(path.read_bytes()) if suffix == ".png" else _ocr_image(path)
            stats["ocr_pages"] = 1
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        key.write_text(raw, encoding="utf-8")
        meta.write_text(json.dumps({k: stats[k] for k in ("pages", "ocr_pages")}))
        return raw, stats

    if suffix == ".docx":
        return _docx_text(str(path)), stats
    return path.read_text(encoding="utf-8", errors="replace"), stats


def _ocr_image(path: Path) -> str:
    import pymupdf
    pix = pymupdf.Pixmap(str(path))
    return _ocr_png(pix.tobytes("png"))


def ingest_with_stats(file_path: str, use_ocr: bool = True, progress=None) -> tuple[str, dict]:
    raw, stats = extract_raw(file_path, use_ocr, progress)
    if stats["format"] == "md":
        raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)
    text = normalize(raw)
    stats["chars"] = len(text)
    return text, stats


def ingest(file_path: str, use_ocr: bool = True) -> str:
    """
    Load and normalise contract text from PDF (incl. scanned), DOCX, image, TXT or MD.
    Returns normalized_text: canonical document for offsets.
    """
    return ingest_with_stats(file_path, use_ocr)[0]


def normalize(text: str) -> str:
    """
    Normalization in fixed order, applied exactly once:
    1. Strip repeating headers/footers (lines recurring on most pages)
    2. Drop standalone page numbers
    3. Rejoin hyphenated line breaks
    4. Collapse whitespace runs, preserve paragraph breaks
    """
    num_pages = max(1, text.count(PAGE_BREAK) + 1)
    text = text.replace(PAGE_BREAK, "\n\n")
    lines = text.split("\n")

    # 1. Strip repeating headers/footers: a line recurring on most PAGES
    #    (not most lines — a header appears once per page, not once per line).
    #    Meaningless with a single page — nothing "repeats across pages" then.
    if num_pages > 2:
        line_counts = {}
        for line in lines:
            stripped = line.strip()
            if 5 < len(stripped) < 100:  # Skip very short/long lines
                line_counts[stripped] = line_counts.get(stripped, 0) + 1

        threshold = max(3, num_pages * 0.5)
        headers_footers = {line for line, count in line_counts.items() if count > threshold}

        lines = [line for line in lines if line.strip() not in headers_footers]

    # 2. Drop standalone page numbers (e.g., "Page 5", "5", "[5]", "- 5 -", "Page 5 of 40")
    lines = [line for line in lines
             if not re.match(r'^\s*(?:page\s+)?[\[\-–]?\s*\d+\s*[\]\-–]?\s*(?:of\s+\d+)?\s*$', line, re.I)]

    # 3. Rejoin hyphenated line breaks (word- \n word -> word-word)
    text = "\n".join(lines)
    text = re.sub(r'([a-z])-\n\s*([a-z])', r'\1\2', text, flags=re.I)

    # 4. Collapse whitespace, preserve paragraph breaks (blank lines = \n\n).
    #    Inside a paragraph keep single newlines only where a new numbered clause
    #    starts, so extract() still sees "5.2 ..." at a line start.
    paragraphs = re.split(r'\n\s*\n', text)
    out = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        p = re.sub(r'[ \t]+', ' ', p)
        p = re.sub(r'\n(?!\s*(?:\d+(?:\.\d+)*\.?\s|ARTICLE|Article|SCHEDULE|Schedule|CHAPTER|PART|ANNEX))\s*', ' ', p)
        out.append(p)
    return "\n\n".join(out)
