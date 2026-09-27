"""Optional local dense retrieval using InLegal-SBERT."""

from functools import lru_cache

import numpy as np


@lru_cache(maxsize=2)
def load_model(model_name: str = "bhavyagiri/InLegal-Sbert"):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def embed_texts(texts: list[str], model_name: str = "bhavyagiri/InLegal-Sbert") -> np.ndarray:
    """Encode texts as normalized vectors for retrieval and persistence."""
    if not texts:
        return np.empty((0, 0), dtype=np.float32)
    vectors = load_model(model_name).encode(texts, normalize_embeddings=True)
    return np.asarray(vectors, dtype=np.float32)


def related_pairs(clauses, top_k: int = 5, model_name: str = "bhavyagiri/InLegal-Sbert"):
    """Return dense similarity pairs as ``(id_a, id_b, score)`` tuples."""
    if len(clauses) < 2:
        return []
    model = load_model(model_name)
    vectors = model.encode([clause.text for clause in clauses], normalize_embeddings=True)
    scores = np.asarray(vectors) @ np.asarray(vectors).T
    pairs = []
    for index, clause in enumerate(clauses):
        ranked = np.argsort(scores[index])[::-1]
        added = 0
        for candidate_index in ranked:
            if candidate_index == index:
                continue
            pairs.append((clause.id, clauses[candidate_index].id, float(scores[index][candidate_index])))
            added += 1
            if added >= top_k:
                break
    return pairs