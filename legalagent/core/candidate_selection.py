from pathlib import Path

from legalagent.core.types import Clause
from legalagent.core.retrieval import retrieve, DEFAULT_MODEL

_LABELS_YAML = Path(__file__).resolve().parents[2] / "clause20" / "labels.yaml"

# Clash pairs for the rule-based known_gaps labels (research/clause_taxonomy/08_MIGRATION.md).
KNOWN_GAP_PAIRS = {
    ("force_majeure", "termination"): 0.60,
    ("force_majeure", "payment_and_fees"): 0.55,
    ("liquidated_damages", "limitation_of_liability"): 0.85,
    ("liquidated_damages", "payment_and_fees"): 0.70,
    ("data_protection", "limitation_of_liability"): 0.85,
    ("data_protection", "confidentiality"): 0.70,
    ("stamp_duty", "arbitration"): 0.80,
    ("performance_security", "termination"): 0.70,
    ("performance_security", "liquidated_damages"): 0.65,
    ("change_in_law", "payment_and_fees"): 0.70,
    ("change_in_law", "tax"): 0.65,
    ("step_in_rights", "termination"): 0.75,
    ("step_in_rights", "assignment_change_of_control"): 0.70,
}


def _load_type_matrix() -> dict[tuple[str, str], float]:
    """CLAUSE-20 label pairs that commonly clash, weighted by risk (clause20/labels.yaml,
    `conflict_pairs`, 17 pairs). Falls back to the core five if the file is absent."""
    try:
        import yaml
        spec = yaml.safe_load(_LABELS_YAML.read_text(encoding="utf-8"))
        matrix = {tuple(k.split("+")): float(v) for k, v in spec["conflict_pairs"].items()}
        matrix.update(KNOWN_GAP_PAIRS)
        return matrix
    except Exception:
        return {
            ("limitation_of_liability", "indemnification"): 0.9,
            ("termination", "survival"): 0.6,
            ("assignment_change_of_control", "confidentiality"): 0.5,
            ("exclusivity_and_restraint", "assignment_change_of_control"): 0.6,
            ("warranty", "limitation_of_liability"): 0.7,
        }


TYPE_MATRIX = _load_type_matrix()

MAX_CANDIDATES = 30


def _cap_unset(max_candidates) -> bool:
    """None / <=0 / "none" / "all" means: keep every candidate (exhaustive audit)."""
    if max_candidates is None:
        return True
    if isinstance(max_candidates, (int, float)) and max_candidates <= 0:
        return True
    return str(max_candidates).lower() in {"none", "unset", "all"}


def select_candidates(clauses: list[Clause], config: dict) -> list[tuple[str, str, list[str]]]:
    """
    Candidate selection: xref + type_matrix (always kept) + retrieval (fills
    remaining slots), where retrieval is config["retrieval_method"]
    (bm25 | dense | hybrid). Optional config["use_gnn"] adds pairs scored by
    the clause-graph GNN (legalagent.core.gnn).

    Returns list of (clause_a_id, clause_b_id, ["bm25", "type_matrix", ...]).
    """
    k = config.get("top_k", 5)
    pairs: dict[tuple[str, str], set[str]] = {}
    weight: dict[tuple[str, str], float] = {}   # clash weight from the type matrix
    sim: dict[tuple[str, str], float] = {}      # best retrieval score seen for the pair

    def add_pair(a_id: str, b_id: str, method: str, w: float = 0.0, s: float = 0.0):
        if a_id == b_id:
            return
        key = tuple(sorted((a_id, b_id)))
        pairs.setdefault(key, set()).add(method)
        weight[key] = max(weight.get(key, 0.0), float(w or 0.0))
        sim[key] = max(sim.get(key, 0.0), float(s or 0.0))

    # Explicit cross-references are never dropped by the cap.
    for clause in clauses:
        for xref in clause.xrefs:
            if xref["resolved"]:
                add_pair(clause.id, xref["clause_id"], "xref")

    labels_to_clauses: dict[str, list[str]] = {}
    for clause in clauses:
        for label_obj in clause.labels:
            labels_to_clauses.setdefault(label_obj["label"], []).append(clause.id)

    for (label_a, label_b), w in TYPE_MATRIX.items():
        for clause_a_id in labels_to_clauses.get(label_a, []):
            for clause_b_id in labels_to_clauses.get(label_b, []):
                add_pair(clause_a_id, clause_b_id, "type_matrix", w=w)

    # Retrieval (bm25 | dense | hybrid) fills whatever slots remain. Same
    # retrieve() the evaluation harness scores, so the reported numbers describe
    # the code that actually ships.
    method = config.get("retrieval_method", "bm25")
    model_name = config.get("embedding_model", DEFAULT_MODEL)
    for clause_a_id, neighbours in retrieve(clauses, method=method, k=k, model_name=model_name).items():
        for rank, (clause_b_id, _score) in enumerate(neighbours):
            add_pair(clause_a_id, clause_b_id, method, s=1.0 / (1 + rank))

    if config.get("use_gnn"):
        try:
            from legalagent.core.gnn import gnn_pairs
            for a_id, b_id, _p in gnn_pairs(clauses, k=k):
                add_pair(a_id, b_id, "gnn")
        except Exception:  # model missing / torch_geometric absent: retrieval alone
            pass

    max_candidates = config.get("max_candidates", MAX_CANDIDATES)
    if _cap_unset(max_candidates):
        return [(a, b, sorted(hows)) for (a, b), hows in pairs.items()]

    # Cap: cross-reference pairs are always kept. The rest are ranked by how many signals agree
    # (type matrix AND retrieval beats either alone), then by clash weight, then by retrieval rank.
    # (Before: every type-matrix pair was kept, which on the 580-clause Pune Metro PDF meant
    # 13,940 pairs ≈ 1 hour of judging instead of ~1 minute.)
    xref_pairs = {key: hows for key, hows in pairs.items() if "xref" in hows}
    rest = sorted((key for key in pairs if key not in xref_pairs),
                  key=lambda key: (-len(pairs[key]), -weight.get(key, 0.0), -sim.get(key, 0.0)))
    kept = dict(xref_pairs)
    for key in rest[: max(0, int(max_candidates))]:
        kept[key] = pairs[key]

    return [(a, b, sorted(hows)) for (a, b), hows in kept.items()]
