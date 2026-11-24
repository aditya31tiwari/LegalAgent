"""
Train + evaluate the clause-graph GNN (legalagent.core.gnn) on teacher-labelled pairs.

    venv/bin/python train/train_gnn.py
    -> models/clause_gnn.pt, results/gnn.json

Compares, on held-out contracts (same split as the judge set):
  gnn          GraphSAGE message passing + pair scorer
  no_graph     identical scorer, message passing disabled (ablation)
  type_matrix  CLAUSE-20 type-matrix weight alone (the hand-built prior)
  cosine       embedding similarity alone (what dense retrieval ranks by)
Metrics: ROC-AUC, average precision, and P@5 per contract (are the top-5 ranked
labelled pairs actually risky?).
"""
import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalagent.core.gnn import build_graph, make_model, type_weight, MODEL_PATH  # noqa: E402

DERIVED = ROOT / "data" / "derived"


def load():
    contracts = {json.loads(l)["contract"]: json.loads(l) for l in (DERIVED / "judge_contracts.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    pairs = defaultdict(list)
    for l in (DERIVED / "judge_pairs.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            pairs[r["contract"]].append((r["a_id"], r["b_id"], int(r["relation"] != "no_issue")))
    graphs = []
    from legalagent.core.retrieval import _load_model
    enc = _load_model("all-MiniLM-L6-v2")
    for cid, c in contracts.items():
        if cid not in pairs:
            continue
        cl = c["clauses"]
        emb = enc.encode([x["text"][:1500] for x in cl], normalize_embeddings=True, batch_size=64)
        x, ei, ids = build_graph(cl, embed=emb)
        pos = {i: k for k, i in enumerate(ids)}
        trip = [(pos[a], pos[b], y) for a, b, y in pairs[cid] if a in pos and b in pos]
        if not trip:
            continue
        a, b, y = map(np.array, zip(*trip))
        w = np.array([type_weight(cl[i]["labels"], cl[j]["labels"]) for i, j in zip(a, b)], dtype=np.float32)
        cos = np.array([float(emb[i] @ emb[j]) for i, j in zip(a, b)], dtype=np.float32)
        graphs.append({"contract": cid, "split": c.get("split", "train"), "x": torch.tensor(x), "ei": torch.tensor(ei),
                       "a": torch.tensor(a), "b": torch.tensor(b), "y": torch.tensor(y, dtype=torch.float32),
                       "w": torch.tensor(w), "cos": cos})
    return graphs


def metrics(groups):
    """groups: list of (scores, labels) per contract."""
    from sklearn.metrics import average_precision_score, roc_auc_score
    s = np.concatenate([g[0] for g in groups])
    y = np.concatenate([g[1] for g in groups])
    p5 = [float(np.mean(lab[np.argsort(-sc)[:5]])) for sc, lab in groups if len(lab) >= 5]
    return {"roc_auc": float(roc_auc_score(y, s)) if 0 < y.sum() < len(y) else None,
            "avg_precision": float(average_precision_score(y, s)) if y.sum() else None,
            "p_at_5": float(np.mean(p5)) if p5 else None, "pairs": int(len(y)), "positives": int(y.sum())}


def train(graphs, use_graph, epochs=60, seed=0):
    torch.manual_seed(seed)
    random.seed(seed)
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = make_model(graphs[0]["x"].shape[1], 128, use_graph).to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    train_g = [g for g in graphs if g["split"] == "train"]
    pos = sum(float(g["y"].sum()) for g in train_g)
    neg = sum(len(g["y"]) for g in train_g) - pos
    lossf = torch.nn.BCEWithLogitsLoss(pos_weight=torch.tensor(neg / max(pos, 1), device=dev))
    for _ in range(epochs):
        model.train()
        random.shuffle(train_g)
        for g in train_g:
            h = model.encode(g["x"].to(dev), g["ei"].to(dev))
            loss = lossf(model.score(h, g["a"].to(dev), g["b"].to(dev), g["w"].to(dev)), g["y"].to(dev))
            opt.zero_grad()
            loss.backward()
            opt.step()
    return model.cpu().eval()


def scores(model, g):
    with torch.no_grad():
        return torch.sigmoid(model.score(model.encode(g["x"], g["ei"]), g["a"], g["b"], g["w"])).numpy()


def main():
    t0 = time.time()
    graphs = load()
    test = [g for g in graphs if g["split"] == "test"]
    print(f"{len(graphs)} contracts ({len(test)} test), "
          f"{sum(len(g['y']) for g in graphs)} labelled pairs, {sum(int(g['y'].sum()) for g in graphs)} risky", flush=True)
    results = {}
    gnn = train(graphs, True)
    results["gnn"] = metrics([(scores(gnn, g), g["y"].numpy()) for g in test])
    results["no_graph"] = metrics([(scores(train(graphs, False), g), g["y"].numpy()) for g in test])
    results["type_matrix"] = metrics([(g["w"].numpy() + 1e-6 * g["cos"], g["y"].numpy()) for g in test])
    results["cosine"] = metrics([(g["cos"], g["y"].numpy()) for g in test])
    for k, v in results.items():
        print(f"{k:12s} {v}")
    MODEL_PATH.parent.mkdir(exist_ok=True)
    torch.save({"state_dict": gnn.state_dict(), "in_dim": graphs[0]["x"].shape[1], "hidden": 128}, MODEL_PATH)
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / "gnn.json").write_text(json.dumps({**results, "train_seconds": round(time.time() - t0)}, indent=2))
    print("saved", MODEL_PATH)


if __name__ == "__main__":
    main()
