from functools import lru_cache
from pathlib import Path

from legalagent.core.types import Clause

# Trained by clause20/train.py. When it is missing the keyword fallback below is
# used, so the pipeline still runs on a fresh checkout.
LABELLER_PATH = Path(__file__).resolve().parents[2] / "models" / "clause20_labeller.joblib"

# A label is kept when its probability clears this. Tuned on the validation
# split (micro-F1: 0.3 -> 0.758, 0.5 -> 0.746). The lower end is taken because a
# missed label means a missed type_matrix pair downstream.
THRESHOLD = 0.3

# Keyword fallback. Names follow CLAUSE-20 so downstream code sees one vocabulary.
KEYWORDS = {
    "indemnification": ["indemnif", "hold harmless", "defend"],
    "limitation_of_liability": ["limitation of liability", "in no event shall", "aggregate liability", "consequential damages"],
    "termination": ["terminate", "termination", "following termination", "post-termination", "termination rights"],
    "confidentiality": ["confidential information", "non-disclosure", "nda"],
    "governing_law": ["governed by the laws", "governing law", "jurisdiction"],
    "assignment_change_of_control": ["assign", "successors and assigns", "assignment and delegation"],
    "survival": ["survive", "shall survive termination"],
    "exclusivity_and_restraint": ["exclusive", "sole and exclusive", "exclusive license"],
    "warranty": ["warranty", "warranties", "represent and warrant"],
    "payment_and_fees": ["payment", "invoice", "compensation", "fee"],
    "ip_ownership": ["intellectual property", "patent", "trademark", "copyright"],
}


@lru_cache(maxsize=1)
def _load_labeller():
    if not LABELLER_PATH.exists():
        return None
    import joblib
    from sentence_transformers import SentenceTransformer
    bundle = joblib.load(LABELLER_PATH)
    return bundle, SentenceTransformer(bundle["model_name"])


def _classify_keywords(clauses: list[Clause]) -> None:
    for clause in clauses:
        text_lower = clause.text.lower()
        for label_name, keywords in KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                clause.labels.append({"label": label_name, "confidence": 1.0, "source": "keyword"})


def _classify_model(clauses: list[Clause], labeller) -> None:
    from legalagent.core.retrieval import _LEADING_NUMBER_RE

    bundle, encoder = labeller
    # Same text shape the labeller was trained on: clause body without its own number.
    texts = [_LEADING_NUMBER_RE.sub("", c.text).strip() for c in clauses]
    probs = bundle["clf"].predict_proba(encoder.encode(texts, normalize_embeddings=True))
    for clause, row in zip(clauses, probs):
        for label_name, p in sorted(zip(bundle["labels"], row), key=lambda lp: -lp[1]):
            if p >= THRESHOLD and label_name != "other":
                clause.labels.append({"label": label_name, "confidence": round(float(p), 3), "source": "clause20"})


def classify(clauses: list[Clause], use_model: bool = True) -> list[Clause]:
    """
    Label each clause with CLAUSE-20 types: the trained labeller when present,
    keyword matching otherwise.
    """
    labeller = _load_labeller() if use_model else None
    if labeller and clauses:
        _classify_model(clauses, labeller)
    else:
        _classify_keywords(clauses)
    return clauses
