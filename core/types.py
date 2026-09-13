from dataclasses import dataclass, field


@dataclass
class Clause:
    id: str                          # "acme_msa::5.2" in v0, becomes public_id
    contract_id: str
    parent_id: str | None = None
    number: str | None = None        # "5.2", "(a)"
    heading: str | None = None
    text: str = ""
    char_start: int = 0              # offset into normalized_text
    char_end: int = 0
    ordinal: int = 0                 # document order
    labels: list[dict] = field(default_factory=list)  # [{"label": "...", "confidence": 0.9}]
    xrefs: list[dict] = field(default_factory=list)   # [{"raw": "Section 8.2", "clause_id": "...", "resolved": True}]


@dataclass
class Finding:
    id: str
    target_clause_id: str
    related_clause_ids: list[str]
    relation_type: str               # conflict | dependency | overlap | ambiguity | no_issue
    severity: str                    # low | medium | high
    risk_score: float
    rationale: str
    surfaced_by: list[str]           # ["bm25", "type_matrix", "xref"]
    evidence: list[dict] = field(default_factory=list)  # [{"clause_id": "...", "start": 0, "end": 0}]
    refs: list[dict] = field(default_factory=list)      # RAG sources, empty in v0
    scores: dict = field(default_factory=dict)          # {"retrieval": 0.62, "analysis_confidence": 0.88}


@dataclass
class Run:
    id: str
    contract_id: str
    config: dict = field(default_factory=dict)  # {"retrieval_method": "bm25", "top_k": 5}
    stats: dict = field(default_factory=dict)   # {"clauses": 47, "pairs": 28, "findings": 6, "no_issue": 22}
