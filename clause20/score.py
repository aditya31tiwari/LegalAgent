"""
Score the saved step-3 labeller on a CLAUSE-20 split.

    python clause20/score.py                      # test split
    python clause20/score.py --split test_ood     # unseen CUAD contracts
    python clause20/score.py --split test --baseline keywords

Prints, for the 20 real labels ("other" is the catch-all and is left out):
  - precision / recall / F1 per label, plus micro and macro averages
  - exact-match accuracy (every label on a clause right) and per-label accuracy
  - top-1 accuracy and a confusion matrix over single-label clauses

A clause can carry several labels, so a single confusion matrix does not fit
the whole set. The matrix uses only single-label clauses (~98% of CLAUSE-20)
and each one's highest-scoring prediction. It is written in full to
clause20/data/confusion_<split>.csv, and the biggest mix-ups are printed.
"""
import argparse
import csv
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from legalagent.core.classification import LABELLER_PATH, THRESHOLD, _classify_keywords
from legalagent.core.types import Clause
from train import HERE, embed, load_rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", default="test", choices=["validation", "test", "test_ood"])
    parser.add_argument("--baseline", choices=["keywords"], help="score the keyword fallback instead")
    args = parser.parse_args()

    bundle = joblib.load(LABELLER_PATH)
    labels = bundle["labels"]
    real = [i for i, name in enumerate(labels) if name != "other"]
    rows = [r for r in load_rows() if r["split"] == args.split]
    y = np.array([[name in r["labels"].split("|") for name in labels] for r in rows], dtype=int)

    if args.baseline == "keywords":
        clauses = [Clause(id=str(i), contract_id="score", text=r["text"]) for i, r in enumerate(rows)]
        _classify_keywords(clauses)
        pred = np.array([[any(l["label"] == name for l in c.labels) for name in labels] for c in clauses], dtype=int)
        # No probabilities: top-1 is the first keyword hit, or "other" when none hit.
        scores = pred.astype(float)
        scores[:, labels.index("other")] = pred.sum(axis=1) == 0
        what = "keyword fallback"
    else:
        scores = bundle["clf"].predict_proba(embed([r["text"] for r in rows], bundle["model_name"], args.split))
        pred = (scores >= THRESHOLD).astype(int)
        what = f"labeller ({bundle['model_name']}, threshold {THRESHOLD})"

    print(f"\n{what} on '{args.split}': {len(rows)} clauses\n")
    print(classification_report(
        y[:, real], pred[:, real], target_names=[labels[i] for i in real], digits=3, zero_division=0))

    print(f"exact-match accuracy  {accuracy_score(y[:, real], pred[:, real]):.3f}   (all labels on a clause right)")
    print(f"per-label accuracy    {(y[:, real] == pred[:, real]).mean():.3f}   (inflated: most answers are an easy 'no')")

    # Single-label clauses: one true label, compare against the top prediction.
    single = y.sum(axis=1) == 1
    true_1 = y[single].argmax(axis=1)
    pred_1 = scores[single].argmax(axis=1)
    print(f"top-1 accuracy        {(true_1 == pred_1).mean():.3f}   ({single.sum()} single-label clauses, incl. 'other')")

    cm = confusion_matrix(true_1, pred_1, labels=range(len(labels)))
    out = HERE / "data" / f"confusion_{args.split}{'_keywords' if args.baseline else ''}.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["true \\ predicted", *labels])
        writer.writerows([labels[i], *cm[i]] for i in range(len(labels)))

    off = [(cm[i, j], labels[i], labels[j]) for i in range(len(labels)) for j in range(len(labels)) if i != j and cm[i, j]]
    print("\nbiggest mix-ups (true -> predicted):")
    for count, true_name, pred_name in sorted(off, reverse=True)[:10]:
        print(f"  {count:>5}  {true_name} -> {pred_name}")
    print(f"\nfull confusion matrix: {out}")


if __name__ == "__main__":
    main()
