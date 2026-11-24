import re
from legalagent.core.types import Clause

# Clause numbering at the start of a line:
#   dotted   "5.2", "1.2.3"           (always a clause)
#   top-level "1. Definitions"        (only with a trailing dot + capitalised word,
#                                      so "1 kg" or numbered prose doesn't split clauses)
# Supports optional markdown '#' headings, bold markers, and
# 'Section'/'Clause'/'Article' prefixes.
CLAUSE_RE = re.compile(
    r'^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*|__)?(?:(?i:Section|Clause|Article)[ \t]+)?'
    r'(\d+(?:\.\d+)+|\d+(?=\.[ \t]+(?:\*\*|__)?[A-Z]))\.?[ \t]*',
    re.M,
)

# Cross-reference regex: "Section 5.2", "Clause 1.2", etc.
XREF_RE = re.compile(r'(?:Section|Clause|Article|clause|§)\s+(\d+(?:\.\d+)*)', re.I)

# A heading is only what's left of the first newline, and only if that first
# line is short — otherwise the "heading" is just the start of inline clause text.
_HEADING_MAX_LEN = 80


# Document parts: "ARTICLE 12 TERMINATION", "SCHEDULE - B", "PART II", "ANNEX 3".
# Upper-case or Title-case keyword at a line start; the rest of the line is its title.
PART_RE = re.compile(
    r'^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?((?:ARTICLE|Article|CHAPTER|Chapter|PART|Part|SCHEDULE|Schedule|'
    r'ANNEX(?:URE)?|Annex(?:ure)?|APPENDIX|Appendix)(?:[ \t]*[-–:][ \t]*|[ \t]+)(?:[IVXLCDM]+|\d+|[A-Z])'
    r'(?=[ \t]*(?:$|[:.\-–(]|[ \t]+[A-Z(]))[^\n]{0,80})',
    re.M,
)

# A table-of-contents entry looks like a clause ("28.1 Revenue Shortfall Loan .... 87")
# but is a title with no operative verb. Dropped so the real clause keeps the id.
_OPERATIVE_RE = re.compile(
    r'\b(shall|will|may|must|can|is|are|be|been|was|means|agrees?|agreed|includes?|has|have|not|appl(?:y|ies)|'
    r'govern(?:s|ed)?|survives?|deemed|hereby|entitled|required|constitutes?|pay|paid|terminate[sd]?)\b', re.I)
_TOC_TAIL_RE = re.compile(r'(\.{3,}|…|\s\d{1,4}\s*\.?\s*$)')


def _title_only(body: str) -> bool:
    words = body.split()
    return len(words) < 14 and not _OPERATIVE_RE.search(body)


def _toc_flags(bodies: list[str], run: int = 4) -> list[bool]:
    """
    A TOC entry is a title-only "clause" that either carries a dot leader / page
    number, or sits in a run of >= `run` consecutive title-only entries. An isolated
    title-only clause ("4.1 Conditions Precedent" followed by 4.1.1 ...) is a real
    section heading and is kept: other clauses cite it and its children hang off it.
    """
    title = [_title_only(b) for b in bodies]
    flags = [t and bool(_TOC_TAIL_RE.search(b)) and len(b.split()) < 10 for t, b in zip(title, bodies)]
    i = 0
    while i < len(title):
        if title[i]:
            j = i
            while j < len(title) and title[j]:
                j += 1
            if j - i >= run:
                for k in range(i, j):
                    flags[k] = True
            i = j
        else:
            i += 1
    return flags


def extract(text: str, contract_id: str = "local") -> list[Clause]:
    """
    Regex-based clause extraction.
    - numbered clauses ("1.", "5.2", "12.3.1"), table-of-contents entries skipped
    - each clause gets its enclosing document part (ARTICLE / SCHEDULE / ...) and a
      parent_id from its number ("5.2.1" -> "5.2" -> "5") when that clause exists
    - cross-references ("Section 5.2", "Clause 10.3.1") resolved within the contract
    Returns Clause objects with char_start/char_end offsets into normalized_text.
    """
    clauses = []
    seen_numbers: dict[str, int] = {}
    ordinal = 0
    all_matches = list(CLAUSE_RE.finditer(text))
    parts = [(m.start(), re.sub(r'\s+', ' ', m.group(1)).strip(" .*")) for m in PART_RE.finditer(text)]

    # Drop TOC-style matches first so ids/spans are assigned to real clauses only.
    bodies = [text[m.end():(all_matches[i + 1].start() if i + 1 < len(all_matches) else len(text))]
              for i, m in enumerate(all_matches)]
    matches = [m for m, toc in zip(all_matches, _toc_flags(bodies)) if not toc]

    for i, match in enumerate(matches):
        number = match.group(1)

        # Span starts at the clause number itself and runs to the next real clause.
        char_start = match.start()
        char_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # ...but never across a document-part heading.
        next_part = next((p for p, _ in parts if char_start < p < char_end), None)
        if next_part is not None:
            char_end = next_part

        clause_text = text[char_start:char_end].strip()
        part = next((title for p, title in reversed(parts) if p <= char_start), None)

        # Heading: first line after the number, only if short (else it's just
        # the start of inline clause text, not a real heading).
        rest = text[match.end():char_end]
        first_line = rest.split("\n", 1)[0].strip()
        heading = first_line if 0 < len(first_line) <= _HEADING_MAX_LEN else None

        seen_numbers[number] = seen_numbers.get(number, 0) + 1
        occurrence = seen_numbers[number]
        clause_id = f"{contract_id}::{number}"
        if occurrence > 1:
            clause_id = f"{clause_id}::{occurrence}"

        # Extract cross-references within this clause
        xrefs = []
        for xref_match in XREF_RE.finditer(clause_text):
            ref_number = xref_match.group(1)
            ref_id = f"{contract_id}::{ref_number}"
            xrefs.append({
                "raw": xref_match.group(0),
                "clause_id": ref_id,
                "resolved": False  # Will be resolved after all clauses extracted
            })

        clause = Clause(
            id=clause_id,
            contract_id=contract_id,
            number=number,
            heading=heading,
            text=clause_text,
            char_start=char_start,
            char_end=char_end,
            ordinal=ordinal,
            xrefs=xrefs,
            part=part,
        )
        clauses.append(clause)
        ordinal += 1

    # Hierarchy: nearest existing ancestor by number, within the same part.
    latest: dict[tuple[str | None, str], str] = {}
    for clause in clauses:
        bits = clause.number.split(".")
        for n in range(len(bits) - 1, 0, -1):
            parent = latest.get((clause.part, ".".join(bits[:n])))
            if parent:
                clause.parent_id = parent
                break
        latest[(clause.part, clause.number)] = clause.id

    # Resolve cross-references
    clause_ids = {c.id for c in clauses}
    first_clause_by_number = {}
    for clause in clauses:
        first_clause_by_number.setdefault(clause.number, clause.id)
    for clause in clauses:
        for xref in clause.xrefs:
            if xref["clause_id"] in clause_ids:
                xref["resolved"] = True
            elif xref["clause_id"].rsplit("::", 1)[-1] in first_clause_by_number:
                xref["clause_id"] = first_clause_by_number[xref["clause_id"].rsplit("::", 1)[-1]]
                xref["resolved"] = True

    return clauses
