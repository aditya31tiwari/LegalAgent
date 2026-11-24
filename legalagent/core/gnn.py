"""
Clause-graph GNN: link prediction of risky clause pairs.

Graph per contract
  nodes  clauses; features = sentence embedding (MiniLM, 384) ⊕ CLAUSE-20 multi-hot ⊕ relative position
  edges  (message passing) resolved cross-references, kNN semantic neighbours (k=5),
         document order (i, i+1) and hierarchy (clause -> parent clause)
Model
  2-layer GraphSAGE encoder -> per-pair scorer MLP([h_a, h_b, |h_a-h_b|, h_a*h_b, w_type])
  where w_type is the CLAUSE-20 type-matrix weight of the pair. Trained with BCE on
  teacher-labelled pairs (risky = relation != no_issue), split by contract.
Ablation
  `use_graph=False` runs the same scorer on raw node features (no message passing),
  so the evaluation isolates what the graph structure itself contributes.

Used in candidate selection as an extra signal (config["use_gnn"]): gnn_pairs()
returns the top-scoring pairs of a contract.
"""
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "models" / "clause_gnn.pt"
EMBED_MODEL = "all-MiniLM-L6-v2"
KNN = 5


def label_vocab() -> list[str]:
    import yaml
    spec = yaml.safe_load((ROOT / "clause20" / "labels.yaml").read_text(encoding="utf-8"))
    return [*spec["labels"], *spec.get("known_gaps", [])]


def type_weight(la: list[str], lb: list[str]) -> float:
    from legalagent.core.candidate_selection import TYPE_MATRIX
    best = 0.0
    for x in la:
        for y in lb:
            best = max(best, TYPE_MATRIX.get((x, y), 0.0), TYPE_MATRIX.get((y, x), 0.0))
    return best


def build_graph(clauses: list[dict], embed=None):
    """clauses: [{id, text, labels: [str], xrefs: [id], parent_id?}] in document order.
    Returns (x [n,F] float32, edge_index [2,E] int64, ids)."""
    from legalagent.core.retrieval import _load_model
    vocab = {l: i for i, l in enumerate(label_vocab())}
    ids = [c["id"] for c in clauses]
    pos = {cid: i for i, cid in enumerate(ids)}
    n = len(ids)
    if embed is None:
        from legalagent.core.retrieval import safe_encode
        embed = safe_encode(_load_model(EMBED_MODEL), [c["text"][:1500] for c in clauses], normalize_embeddings=True, batch_size=64)
    multi = np.zeros((n, len(vocab)), dtype=np.float32)
    for i, c in enumerate(clauses):
        for l in c["labels"]:
            if l in vocab:
                multi[i, vocab[l]] = 1
    position = (np.arange(n, dtype=np.float32) / max(1, n - 1))[:, None]
    x = np.hstack([embed.astype(np.float32), multi, position])

    edges = set()
    for i, c in enumerate(clauses):
        for t in c.get("xrefs", []):
            if t in pos and pos[t] != i:
                edges.add((i, pos[t]))
        if c.get("parent_id") in pos:
            edges.add((i, pos[c["parent_id"]]))
        if i + 1 < n:
            edges.add((i, i + 1))
    if n > 1:
        sims = embed @ embed.T
        np.fill_diagonal(sims, -1)
        for i in range(n):
            for j in np.argsort(-sims[i])[:min(KNN, n - 1)]:
                edges.add((i, int(j)))
    edges |= {(b, a) for a, b in edges}
    edge_index = np.array(sorted(edges), dtype=np.int64).T if edges else np.zeros((2, 0), dtype=np.int64)
    return x, edge_index, ids


def make_model(in_dim: int, hidden: int = 128, use_graph: bool = True):
    import torch
    from torch import nn
    from torch_geometric.nn import SAGEConv

    class PairGNN(nn.Module):
        def __init__(self):
            super().__init__()
            self.use_graph = use_graph
            self.inp = nn.Linear(in_dim, hidden)
            self.conv1 = SAGEConv(hidden, hidden)
            self.conv2 = SAGEConv(hidden, hidden)
            self.drop = nn.Dropout(0.2)
            self.scorer = nn.Sequential(nn.Linear(4 * hidden + 1, hidden), nn.ReLU(), nn.Dropout(0.2), nn.Linear(hidden, 1))

        def encode(self, x, edge_index):
            h = torch.relu(self.inp(x))
            if self.use_graph and edge_index.numel():
                h = h + self.drop(torch.relu(self.conv1(h, edge_index)))
                h = h + self.drop(torch.relu(self.conv2(h, edge_index)))
            return h

        def score(self, h, a, b, w):
            ha, hb = h[a], h[b]
            return self.scorer(torch.cat([ha, hb, (ha - hb).abs(), ha * hb, w[:, None]], dim=1)).squeeze(1)

    return PairGNN()


@lru_cache(maxsize=1)
def _load():
    import torch
    if not MODEL_PATH.exists():
        return None
    bundle = torch.load(MODEL_PATH, map_location="cpu", weights_only=False)
    model = make_model(bundle["in_dim"], bundle["hidden"], True)
    model.load_state_dict(bundle["state_dict"])
    return model.eval()


def gnn_pairs(clauses, k: int = 5) -> list[tuple[str, str, float]]:
    """Top pairs of a contract by predicted risk: about k per clause / 2, highest first."""
    import torch
    model = _load()
    if model is None or len(clauses) < 2:
        return []
    cl = [{"id": c.id, "text": c.text, "labels": [l["label"] for l in c.labels],
           "xrefs": [x["clause_id"] for x in c.xrefs if x["resolved"]], "parent_id": c.parent_id} for c in clauses]
    x, ei, ids = build_graph(cl)
    n = len(ids)
    a, b = np.triu_indices(n, 1)
    w = np.array([type_weight(cl[i]["labels"], cl[j]["labels"]) for i, j in zip(a, b)], dtype=np.float32)
    with torch.no_grad():
        h = model.encode(torch.tensor(x), torch.tensor(ei))
        p = torch.sigmoid(model.score(h, torch.tensor(a), torch.tensor(b), torch.tensor(w))).numpy()
    top = np.argsort(-p)[: max(1, k * n // 2)]
    return [(ids[a[t]], ids[b[t]], float(p[t])) for t in top]
