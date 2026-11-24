"""
Clause classification into CLAUSE-20 types. Three interchangeable backends:

  keyword     substring rules (fallback, no model needed)
  minilm_lr   frozen sentence encoder + one-vs-rest logistic regression
              (clause20/train.py -> models/clause20_labeller.joblib)
  inlegalbert law-ai/InLegalBERT fully fine-tuned, multi-label head
              (train/finetune_inlegalbert.py -> models/clause20_inlegalbert/)

backend="auto" picks the strongest one present on disk.
"""
import json
from functools import lru_cache
from pathlib import Path

from legalagent.core.types import Clause

MODELS_DIR = Path(__file__).resolve().parents[2] / "models"
LABELLER_PATH = MODELS_DIR / "clause20_labeller.joblib"
INLEGALBERT_DIR = MODELS_DIR / "clause20_inlegalbert"

BACKENDS = ("auto", "keyword", "minilm_lr", "inlegalbert")

# A label is kept when its probability clears this. Tuned on the validation
# split for minilm_lr (micro-F1: 0.3 -> 0.758, 0.5 -> 0.746). The lower end is
# taken because a missed label means a missed type_matrix pair downstream.
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
    "exclusivity_and_restraint": ["exclusive", "sole and exclusive", "exclusive license", "non-compete", "non-solicit"],
    "warranty": ["warranty", "warranties", "represent and warrant"],
    "payment_and_fees": ["payment", "invoice", "compensation", "fee"],
    "ip_ownership": ["intellectual property", "patent", "trademark", "copyright"],
}


def _strip_number(text: str) -> str:
    from legalagent.core.retrieval import _LEADING_NUMBER_RE
    return _LEADING_NUMBER_RE.sub("", text).strip()


@lru_cache(maxsize=1)
def _load_minilm_lr():
    if not LABELLER_PATH.exists():
        return None
    import joblib
    from sentence_transformers import SentenceTransformer
    bundle = joblib.load(LABELLER_PATH)
    return bundle, SentenceTransformer(bundle["model_name"])


@lru_cache(maxsize=1)
def _load_inlegalbert():
    if not (INLEGALBERT_DIR / "config.json").exists():
        return None
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(INLEGALBERT_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(INLEGALBERT_DIR).to(device).eval()
    if device == "cuda":
        model = model.half()
    meta_path = INLEGALBERT_DIR / "clause20_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    labels = [model.config.id2label[i] for i in range(model.config.num_labels)]
    return tok, model, labels, float(meta.get("threshold", THRESHOLD)), device


def available_backend(backend: str = "auto") -> str:
    """Resolve "auto" to the best backend that can actually load."""
    if backend != "auto":
        return backend
    if (INLEGALBERT_DIR / "config.json").exists():
        return "inlegalbert"
    if LABELLER_PATH.exists():
        return "minilm_lr"
    return "keyword"


def _classify_keywords(clauses: list[Clause]) -> None:
    for clause in clauses:
        text_lower = clause.text.lower()
        for label_name, keywords in KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                clause.labels.append({"label": label_name, "confidence": 1.0, "source": "keyword"})


def _apply_probs(clauses, labels, probs, threshold, source):
    for clause, row in zip(clauses, probs):
        for label_name, p in sorted(zip(labels, row), key=lambda lp: -lp[1]):
            if p >= threshold and label_name != "other":
                clause.labels.append({"label": label_name, "confidence": round(float(p), 3), "source": source})


def predict_proba(texts: list[str], backend: str) -> tuple[list[str], "list"]:
    """Raw per-label probabilities for evaluation code. Returns (labels, n x L array)."""
    import numpy as np
    if backend == "minilm_lr":
        bundle, encoder = _load_minilm_lr()
        return list(bundle["labels"]), bundle["clf"].predict_proba(encoder.encode(texts, normalize_embeddings=True, batch_size=64))
    if backend == "inlegalbert":
        import torch
        tok, model, labels, _thr, device = _load_inlegalbert()
        out = []
        with torch.no_grad():
            for i in range(0, len(texts), 64):
                enc = tok(texts[i:i + 64], truncation=True, max_length=256, padding=True, return_tensors="pt").to(device)
                out.append(torch.sigmoid(model(**enc).logits.float()).cpu().numpy())
        return labels, (np.vstack(out) if out else np.zeros((0, len(labels))))
    raise ValueError(f"predict_proba not supported for backend {backend!r}")


def classify(clauses: list[Clause], use_model: bool = True, backend: str = "auto") -> list[Clause]:
    """
    Label each clause with CLAUSE-20 types using the requested backend
    (falling back to keywords if the model is missing).
    """
    if not clauses:
        return clauses
    backend = available_backend(backend) if use_model else "keyword"
    texts = [_strip_number(c.text) for c in clauses]

    if backend == "inlegalbert" and _load_inlegalbert():
        labels, probs = predict_proba(texts, "inlegalbert")
        _apply_probs(clauses, labels, probs, _load_inlegalbert()[3], "inlegalbert")
    elif backend in ("minilm_lr", "inlegalbert") and _load_minilm_lr():
        labels, probs = predict_proba(texts, "minilm_lr")
        _apply_probs(clauses, labels, probs, THRESHOLD, "clause20")
    else:
        _classify_keywords(clauses)
    return clauses
