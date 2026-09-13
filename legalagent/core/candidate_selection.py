from rank_bm25 import BM25Okapi
from legalagent.core.types import Clause

# Type matrix: label pairs that commonly conflict, weighted by risk.
# Only pairs worth surfacing are listed — omit a pair rather than marking it False.
TYPE_MATRIX = {
    ("limitation_of_liability", "indemnification"): 0.9,
    ("termination", "survival"): 0.6,
    ("assignment", "confidentiality"): 0.5,
    ("exclusivity", "assignment"): 0.6,
    ("warranty", "limitation_of_liability"): 0.7,
}

MAX_CANDIDATES = 30


def select_candidates(clauses: list[Clause], config: dict) -> list[tuple[str, str, list[str]]]:
    """
    Candidate selection v0: xref + type_matrix (always kept) + BM25 (fills remaining slots).
    Returns list of (clause_a_id, clause_b_id, ["bm25", "type_matrix", ...])
    """
    k = config.get("top_k", 5)
    pairs: dict[tuple[str, str], set[str]] = {}

    def add_pair(a_id: str, b_id: str, method: str):
        if a_id == b_id:
            return
        key = tuple(sorted((a_id, b_id)))
        pairs.setdefault(key, set()).add(method)

    # Priority pairs first: xref and type_matrix are never dropped by the cap.
    for clause in clauses:
        for xref in clause.xrefs:
            if xref["resolved"]:
                add_pair(clause.id, xref["clause_id"], "xref")

    labels_to_clauses: dict[str, list[str]] = {}
    for clause in clauses:
        for label_obj in clause.labels:
            labels_to_clauses.setdefault(label_obj["label"], []).append(clause.id)

    for (label_a, label_b) in TYPE_MATRIX:
        for clause_a_id in labels_to_clauses.get(label_a, []):
            for clause_b_id in labels_to_clauses.get(label_b, []):
                add_pair(clause_a_id, clause_b_id, "type_matrix")

    priority_pairs = dict(pairs)

    # BM25 (real implementation, via rank_bm25) fills whatever slots remain.
    if len(clauses) > 1:
        tokenized = [c.text.lower().split() for c in clauses]
        bm25 = BM25Okapi(tokenized)

        for i, clause_a in enumerate(clauses):
            scores = bm25.get_scores(tokenized[i])
            ranked = sorted(
                ((score, clauses[j].id) for j, score in enumerate(scores) if j != i and score > 0),
                reverse=True,
            )
            for score, clause_b_id in ranked[:k]:
                add_pair(clause_a.id, clause_b_id, "bm25")

    # Cap by priority: xref/type_matrix pairs are always kept; BM25-only pairs
    # fill whatever room is left.
    bm25_only = {key: hows for key, hows in pairs.items() if key not in priority_pairs}
    remaining_slots = max(0, MAX_CANDIDATES - len(priority_pairs))
    kept = dict(priority_pairs)
    kept.update(dict(list(bm25_only.items())[:remaining_slots]))

    return [(a, b, sorted(hows)) for (a, b), hows in kept.items()]
