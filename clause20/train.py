"""
Train the step-3 clause labeller on CLAUSE-20.

A frozen sentence encoder turns each clause into a vector; one logistic
regression per label learns the 20 CLAUSE-20 types on top. Only the small
classifier is trained, so this runs on a laptop CPU.

    python clause20/train.py                                   # MiniLM
    python clause20/train.py --model bhavyagiri/InLegal-Sbert  # compare

Scores are printed for `test` (in-distribution) and `test_ood` (unseen CUAD
contracts -- the closer match to what the pipeline really meets). The trained
labeller is saved where legalagent.core.classification loads it from.
"""
import argparse
import csv
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from legalagent.core.classification import LABELLER_PATH, THRESHOLD

HERE = Path(__file__).parent
DATA = HERE / "data" / "CLAUSE20.csv"
CACHE = HERE / "data" / "embeddings"


def load_rows():
    csv.field_size_limit(10**9)
    with open(DATA, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def embed(texts, model_name, split):
    """Encode once per (model, split) and cache -- encoding is the slow part."""
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"{model_name.replace('/', '__')}.{split}.npy"
    if path.exists():
        return np.load(path)
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_name)
    vectors = model.encode(texts, batch_size=64, normalize_embeddings=True, show_progress_bar=True)
    np.save(path, vectors)
    return vectors


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    parser.add_argument("--no-save", action="store_true", help="score only, keep the current labeller")
    args = parser.parse_args()

    rows = load_rows()
    by_split = {}
    for row in rows:
        by_split.setdefault(row["split"], []).append(row)

    binarizer = MultiLabelBinarizer()
    binarizer.fit([r["labels"].split("|") for r in rows])

    def xy(split):
        part = by_split[split]
        x = embed([r["text"] for r in part], args.model, split)
        y = binarizer.transform([r["labels"].split("|") for r in part])
        return x, y

    x_train, y_train = xy("train")
    print(f"training on {len(x_train)} clauses, {len(binarizer.classes_)} labels ({args.model})")
    # No class_weight="balanced": it inflated rare-label probabilities until
    # unrelated clauses picked up 3-4 labels each (validation F1 0.69 vs 0.76).
    clf = OneVsRestClassifier(LogisticRegression(max_iter=2000, C=4.0), n_jobs=-1)
    clf.fit(x_train, y_train)

    # "other" is a catch-all, not a clause type anyone acts on -- score the 20 real labels.
    real = [i for i, name in enumerate(binarizer.classes_) if name != "other"]
    for split in ("test", "test_ood"):
        x, y = xy(split)
        pred = (clf.predict_proba(x) >= THRESHOLD).astype(int)
        micro = f1_score(y[:, real], pred[:, real], average="micro", zero_division=0)
        macro = f1_score(y[:, real], pred[:, real], average="macro", zero_division=0)
        print(f"{split:<9} {len(x):>6} clauses   micro-F1 {micro:.3f}   macro-F1 {macro:.3f}")

    if not args.no_save:
        LABELLER_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({"model_name": args.model, "labels": list(binarizer.classes_), "clf": clf}, LABELLER_PATH)
        print(f"saved {LABELLER_PATH}")


if __name__ == "__main__":
    main()
