import re
from core.types import Clause

# Decimal numbering only (e.g., "5.2", "1.2.3")
CLAUSE_RE = re.compile(r'^\s*(\d+(?:\.\d+)*)\s*\.?\s+([^\n]{0,80}?)\n', re.M)

# Cross-reference regex: "Section 5.2", "Clause 1.2", etc.
XREF_RE = re.compile(r'(?:Section|Clause|Article|clause|§)\s+(\d+(?:\.\d+)*)', re.I)


def extract(text: str, contract_id: str = "local") -> list[Clause]:
    """
    Regex-based clause extraction: decimal numbering only, flat list.
    Returns list of Clause objects with char_start/char_end from normalized_text.
    """
    clauses = []
    ordinal = 0

    for match in CLAUSE_RE.finditer(text):
        number = match.group(1)
        heading = match.group(2).strip()

        # Find text run: from end of this match to start of next match
        char_start = match.end()
        remaining = text[char_start:]
        next_match = CLAUSE_RE.search(remaining)
        char_end = char_start + next_match.start() if next_match else len(text)

        clause_text = text[char_start:char_end].strip()
        clause_id = f"{contract_id}::{number}"

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
    for clause in clauses:
        for xref in clause.xrefs:
            xref["resolved"] = xref["clause_id"] in clause_ids

    return clauses
