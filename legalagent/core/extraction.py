import re
from legalagent.core.types import Clause

# Decimal numbering (e.g., "5.2", "1.2.3"). Supports optional markdown '#' headings,
# bold markers, and 'Section'/'Clause'/'Article' prefixes.
CLAUSE_RE = re.compile(
    r'^\s*(?:#{1,6}\s*)?(?:\*\*|__)?(?:Section|Clause|Article)?\s*(\d+(?:\.\d+)+)\.?\s*',
    re.M | re.I,
)

# Cross-reference regex: "Section 5.2", "Clause 1.2", etc.
XREF_RE = re.compile(r'(?:Section|Clause|Article|clause|§)\s+(\d+(?:\.\d+)*)', re.I)

# A heading is only what's left of the first newline, and only if that first
# line is short — otherwise the "heading" is just the start of inline clause text.
_HEADING_MAX_LEN = 80


def extract(text: str, contract_id: str = "local") -> list[Clause]:
    """
    Regex-based clause extraction: decimal numbering only, flat list.
    Returns list of Clause objects with char_start/char_end from normalized_text.
    """
    clauses = []
    seen_numbers: dict[str, int] = {}
    ordinal = 0
    matches = list(CLAUSE_RE.finditer(text))

    for i, match in enumerate(matches):
        number = match.group(1)

        # Span starts at the clause number itself, so spans tile the document.
        char_start = match.start()
        char_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

        clause_text = text[char_start:char_end].strip()

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
        )
        clauses.append(clause)
        ordinal += 1

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
