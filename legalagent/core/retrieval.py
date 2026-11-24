"""
Related-clause retrieval: three interchangeable methods, one interface.

This is the arm of the project that gets measured (see legalagent.core.evaluation),
so the three methods must see *exactly* the same input text and differ only in how
they score it. Anything else makes the comparison meaningless.
"""
import re
from functools import lru_cache

from legalagent.core.types import Clause
from legalagent.core.extraction import XREF_RE

METHODS = ("bm25", "dense", "hybrid")

# Small, fast, CPU-friendly. 384-dim; good enough for clause-level similarity and
# it downloads in seconds rather than minutes.
DEFAULT_MODEL = "all-MiniLM-L6-v2"

# Reciprocal Rank Fusion constant. 60 is the value from the original RRF paper;
# it damps the top ranks so one method can't dominate the fusion outright.
RRF_K = 60

# extract() starts a clause span at its own number, so clause "1.1" literally
# begins with the token "1.1" — and a clause citing "Section 1.1" contains that
# same token. Left in, BM25 scores an exact keyword hit on the very signal the
# gold set is derived from, and the evaluation measures nothing but leakage.
_LEADING_NUMBER_RE = re.compile(r'^\s*\d+(?:\.\d+)*\.?\s+')


def index_text(clause: Clause) -> str:
    """
    The text a retriever is allowed to see: clause body with its own number and
    any cross-reference phrases removed.

    Cross-references are stripped in production too, not just under evaluation —
    they already have their own dedicated channel in candidate_selection, so
    leaving them here would double-count the same signal.
    """
    text = _LEADING_NUMBER_RE.sub("", clause.text)
    return XREF_RE.sub(" ", text).strip()


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise ImportError(
            "Dense retrieval needs sentence-transformers: pip install sentence-transformers"
        ) from exc
    return SentenceTransformer(model_name)


def _bm25_matrix(texts: list[str]):
    """Full n x n score matrix; row i = clause i used as the query."""
    import numpy as np
    from rank_bm25 import BM25Okapi

    tokenized = [t.lower().split() for t in texts]
    bm25 = BM25Okapi(tokenized)
    # ponytail: O(n^2) — one query per clause. Fine to a few hundred clauses;
    # switch to a sparse inverted-index pass if contracts get much bigger.
    return np.vstack([bm25.get_scores(t) for t in tokenized])


def _dense_matrix(texts: list[str], model_name: str):
    """Cosine similarity matrix from normalized embeddings."""
    emb = _load_model(model_name).encode(texts, normalize_embeddings=True)
    return emb @ emb.T


def _rank_rows(matrix, ids: list[str], k: int) -> dict[str, list[tuple[str, float]]]:
    """Top-k per row, excluding self. Ties broken by id so runs are reproducible."""
    out = {}
    for i, qid in enumerate(ids):
        scored = [
            (ids[j], float(matrix[i][j]))
            for j in range(len(ids))
            if j != i and matrix[i][j] > 0
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))
        out[qid] = scored[:k]
    return out


def _rrf_matrix(matrices: list, n: int):
    """
    Fuse score matrices by rank, not by value.

    BM25 scores are unbounded and cosine scores live in [-1, 1]; summing them
    directly would let whichever method happens to have the larger scale decide
    every pair. RRF only ever looks at position, so no normalization to tune.
    """
    import numpy as np

    fused = np.zeros((n, n), dtype=float)
    for matrix in matrices:
        for i in range(n):
            # argsort descending -> order[r] is the column ranked r-th for row i
            order = np.argsort(-matrix[i], kind="stable")
            for rank, j in enumerate(order):
                fused[i][j] += 1.0 / (RRF_K + rank + 1)
    return fused


def retrieve(
    clauses: list[Clause],
    method: str = "bm25",
    k: int = 5,
    model_name: str = DEFAULT_MODEL,
) -> dict[str, list[tuple[str, float]]]:
    """
    Rank every other clause against each clause.

    Returns {clause_id: [(other_clause_id, score), ...]} ordered best-first,
    at most k per clause. Score scales differ between methods by design — only
    the ordering is comparable across them.
    """
    if method not in METHODS:
        raise ValueError(f"unknown retrieval method {method!r}, expected one of {METHODS}")
    if len(clauses) < 2:
        return {c.id: [] for c in clauses}

    ids = [c.id for c in clauses]
    texts = [index_text(c) for c in clauses]

    if method == "bm25":
        matrix = _bm25_matrix(texts)
    elif method == "dense":
        matrix = _dense_matrix(texts, model_name)
    else:
        matrix = _rrf_matrix([_bm25_matrix(texts), _dense_matrix(texts, model_name)], len(ids))

    return _rank_rows(matrix, ids, k)
