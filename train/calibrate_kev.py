"""
Tune Kev's decision threshold τ on TRAINING contracts only (never the test split).

A pair is flagged when P(no_issue) < τ. We pick τ that maximises F1 of "risky vs no_issue"
against the teacher labels of a sample of training pairs, and save it next to the model.

    venv/bin/python train/calibrate_kev.py --url http://127.0.0.1:8008/v1/systemone --out models/kev_judge/threshold.json
    venv/bin/python train/calibrate_kev.py --url http://127.0.0.1:8009/v1/systemone --out models/kev_base_threshold.json
"""
import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "train"))
sys.path.insert(0, str(ROOT / "scripts"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=300)
    args = ap.parse_args()

    from sklearn.metrics import f1_score, roc_auc_score
    from legalagent.core import local_judge
    from legalagent.core.local_judge import pair_request, statute_options, _post
    from export_kev_data import current_types
    from eval_all import _clause

    local_judge.KEV_URL = args.url
    if not local_judge.available():
        sys.exit(f"no Kev server at {args.url}")
    rows = [json.loads(l) for l in (ROOT / "data/derived/judge_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    train = [r for r in rows if r["split"] == "train"]
    rnd = random.Random(0)
    risky = [r for r in train if r["relation"] != "no_issue"]
    clean = [r for r in train if r["relation"] == "no_issue"]
    k = min(args.n // 2, len(risky))
    sample = rnd.sample(risky, k) + rnd.sample(clean, min(len(clean), args.n - k))
    types = current_types(sample)
    p_none, y = [], []
    for r in sample:
        a = _clause(r["a_id"], r["a_text"], types[(r["a_id"], r["a_text"])])
        b = _clause(r["b_id"], r["b_text"], types[(r["b_id"], r["b_text"])])
        resp = _post(pair_request(a, b, r["surfaced_by"], statute_options(a, b)))
        p_none.append(float(resp["answers"]["relation"]["probabilities"]["no_issue"]))
        y.append(r["relation"] != "no_issue")
    p_none, y = np.array(p_none), np.array(y)
    # sample is ~50/50 by construction; re-weight to the real training prior when choosing τ
    prior = len(risky) / len(train)
    w = np.where(y, prior / max(y.mean(), 1e-9), (1 - prior) / max(1 - y.mean(), 1e-9))
    best = max(((f1_score(y, p_none < t, sample_weight=w, zero_division=0), t) for t in np.unique(np.round(p_none, 3))), default=(0, 0.5))
    out = {"threshold": round(float(best[1]) + 1e-4, 4), "weighted_f1_train": round(float(best[0]), 3),
           "auc_train": round(float(roc_auc_score(y, 1 - p_none)), 3), "n": int(len(y)), "url": args.url,
           "rule": "flag pair iff P(no_issue) < threshold", "tuned_on": "training contracts only"}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=2))
    print(json.dumps(out))


if __name__ == "__main__":
    main()
