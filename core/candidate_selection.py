from core.types import Clause

# Type matrix: which label pairs are conflict candidates
TYPE_MATRIX = {
    ("limitation_of_liability", "indemnification"): True,
    ("termination", "survival"): True,
    ("assignment", "confidentiality"): True,
    ("governing_law", "payment"): False,  # Usually no conflict
    ("exclusivity", "assignment"): True,
    ("warranty", "limitation_of_liability"): True,
}


def bm25_score(query_tokens: list[str], doc_tokens: list[str], num_docs: int = 100) -> float:
    """
    Naive BM25-like score: penytail simplification.
    ponytail: naive TF-IDF, good enough for v0 to surface integration issues.
    """
    # ponytail: O(n²) candidate pairs, but only ~30 candidates per contract in v0, acceptable
    if not query_tokens or not doc_tokens:
        return 0.0

    # Count term matches
    matches = sum(1 for token in query_tokens if token in doc_tokens)
    if matches == 0:
        return 0.0

    # Simple TF weighting
    doc_freq = len([t for t in doc_tokens if t in query_tokens])
    term_freq = matches / len(query_tokens)
    idf = 1 + (num_docs / (doc_freq + 1))  # Avoid division by zero

    return term_freq * idf


def select_candidates(clauses: list[Clause], config: dict) -> list[tuple[str, str, list[str]]]:
    """
    Candidate selection v0: BM25 + xref + type_matrix.
    Returns list of (clause_a_id, clause_b_id, ["bm25", "type_matrix", ...])
    """
    k = config.get("top_k", 5)
    pairs = {}

    def add_pair(a_id: str, b_id: str, method: str):
        key = tuple(sorted((a_id, b_id)))
        if key not in pairs:
            pairs[key] = set()
        pairs[key].add(method)

    # Tokenize all clauses once
    clause_tokens = {}
    for clause in clauses:
        tokens = clause.text.lower().split()
        clause_tokens[clause.id] = tokens

    # 1. BM25: each clause against all others
    for i, clause_a in enumerate(clauses):
        scores = []
        for clause_b in clauses:
            if clause_a.id == clause_b.id:
                continue
            score = bm25_score(clause_tokens[clause_a.id], clause_tokens[clause_b.id])
            scores.append((score, clause_b.id))

        # Top k by BM25
        scores.sort(reverse=True)
        for score, clause_b_id in scores[:k]:
            if score > 0:
                add_pair(clause_a.id, clause_b_id, "bm25")

    # 2. Cross-references
    for clause in clauses:
        for xref in clause.xrefs:
            if xref["resolved"]:
                add_pair(clause.id, xref["clause_id"], "xref")

    # 3. Type matrix: label pairs that often conflict
    labels_to_clauses = {}
    for clause in clauses:
        for label_obj in clause.labels:
            label = label_obj["label"]
            if label not in labels_to_clauses:
                labels_to_clauses[label] = []
            labels_to_clauses[label].append(clause.id)

    for (label_a, label_b), is_candidate in TYPE_MATRIX.items():
        if is_candidate and label_a in labels_to_clauses and label_b in labels_to_clauses:
            for clause_a_id in labels_to_clauses[label_a]:
                for clause_b_id in labels_to_clauses[label_b]:
                    add_pair(clause_a_id, clause_b_id, "type_matrix")

    # Cap candidates at ~30
    result = [(a, b, sorted(hows)) for (a, b), hows in list(pairs.items())[:30]]
    return result
