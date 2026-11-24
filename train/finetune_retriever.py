"""
Contrastive fine-tuning of InLegal-SBERT (bhavyagiri/InLegal-Sbert) for the two retrieval
problems in LegalAgent.

    venv/bin/python train/finetune_retriever.py clauses    -> models/inlegal_sbert_clauses
    venv/bin/python train/finetune_retriever.py statutes   -> models/inlegal_sbert_statutes

clauses
  Positive pairs = (clause, clause it cross-references) from CUAD contracts that are NOT in
  the retrieval evaluation set (scripts/eval_all.py uses the first 120 qualifying contracts
  after a seeded shuffle; those are excluded here, as are all Indian evaluation documents).
  Text is index_text(): clause numbers and xref phrases removed, exactly what the retriever
  sees, so the model cannot learn to match on the citation itself.
statutes
  Positive pairs = (clause-pair text, Indian statute section) where the teacher's citation
  resolves to a real section in the library (train split only), plus (section heading,
  section text) pairs for every section so the encoder adapts to statutory language.
Loss: CachedMultipleNegativesRankingLoss (in-batch negatives, GradCache), batch 64, 1 epoch, fp16.
"""
import json
import random
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = "bhavyagiri/InLegal-Sbert"


def clause_pairs(n_eval=120):
    from legalagent.core.ingestion import normalize
    from legalagent.core.extraction import extract
    from legalagent.core.retrieval import index_text
    docs = json.loads(zipfile.ZipFile(ROOT / "dataset" / "data.zip").read("CUADv1.json"))["data"]
    random.Random(1).shuffle(docs)          # same shuffle as eval_all.contracts_for_retrieval
    seen_eval, pairs = 0, []
    for d in docs:
        cl = extract(normalize(d["paragraphs"][0]["context"]), "c")
        n_x = sum(x["resolved"] for c in cl for x in c.xrefs)
        if n_x >= 3 and seen_eval < n_eval:
            seen_eval += 1                  # evaluation contract: skip
            continue
        by = {c.id: c for c in cl}
        for c in cl:
            for x in c.xrefs:
                if x["resolved"] and x["clause_id"] in by and x["clause_id"] != c.id:
                    a, b = index_text(c), index_text(by[x["clause_id"]])
                    if len(a.split()) > 5 and len(b.split()) > 5:
                        pairs.append((a[:1500], b[:1500]))
    return pairs


def statute_pairs():
    from legalagent.core.statutes import load_library, verify_citation, _doc_text
    pairs = []
    path = ROOT / "data" / "derived" / "judge_pairs.jsonl"
    if path.exists():
        for l in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(l)
            if r["split"] != "train" or r["relation"] == "no_issue":
                continue
            s = verify_citation(r.get("citation", ""))
            if s:
                pairs.append((f"{r['a_text'][:600]} {r['b_text'][:600]}", _doc_text(s)))
    for s in load_library():
        if s["heading"]:
            pairs.append((f"{s['heading']} ({s['act']})", _doc_text(s)))
    return pairs


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "clauses"
    from sentence_transformers import SentenceTransformer, InputExample, losses
    from torch.utils.data import DataLoader

    pairs = clause_pairs() if what == "clauses" else statute_pairs()
    random.Random(0).shuffle(pairs)
    print(f"{what}: {len(pairs)} positive pairs", flush=True)
    model = SentenceTransformer(BASE)
    model.max_seq_length = 256
    examples = [InputExample(texts=[a, b]) for a, b in pairs]
    # GradCache variant of MNRL: effective batch 64 (more in-batch negatives) computed in
    # mini-batches of 8, so it fits a 6 GB laptop GPU next to nothing else.
    loader = DataLoader(examples, shuffle=True, batch_size=64)
    loss = losses.CachedMultipleNegativesRankingLoss(model, mini_batch_size=8)
    t0 = time.time()
    model.fit(train_objectives=[(loader, loss)], epochs=1, warmup_steps=int(0.1 * len(loader)), use_amp=True, show_progress_bar=False)
    out = ROOT / "models" / f"inlegal_sbert_{what}"
    model.save(str(out))
    meta = {"base": BASE, "pairs": len(pairs), "epochs": 1, "batch_size": 64, "loss": "CachedMultipleNegativesRankingLoss (mini-batch 8)",
            "train_seconds": round(time.time() - t0)}
    (out / "finetune_meta.json").write_text(json.dumps(meta, indent=2))
    (ROOT / "results").mkdir(exist_ok=True)
    (ROOT / "results" / f"retriever_{what}.json").write_text(json.dumps(meta, indent=2))
    print("saved", out, meta, flush=True)


if __name__ == "__main__":
    main()
