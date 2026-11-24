"""
Build the distillation sets used to train the local models.

    python scripts/build_judge_set.py pairs   --contracts 220 --per-contract 14
    python scripts/build_judge_set.py india-clauses --max 220

pairs
  Clause pairs shortlisted by LegalAgent's own candidate selector (xref + 17-pair type
  matrix + hybrid retrieval) over public contracts: CUAD v1 (US, SEC filings) and the
  Indian contracts in data/demo that are NOT used for evaluation. Each pair is
  labelled by Gemini (teacher) with relation / severity / risk / citation using the
  same prompt as the online judge. Split by CONTRACT (no contract in both splits).
  -> data/derived/judge_pairs.jsonl, data/derived/judge_contracts.jsonl (graphs for the GNN)

india-clauses
  Clauses from Indian government contracts (NHAI model concession, Pune Metro
  concession) labelled with CLAUSE-20 types by Gemini -> silver test set for the
  Indian transfer of the clause classifier. Spot-check with --review.
  -> data/derived/india_clause_eval.jsonl

Held out from ALL training: data/demo/samples/02_*adversarial*, data/demo/india/adversarial/,
data/demo/india/custom_benchmark/ (those are the end-to-end detection tests).
Gemini responses are cached per batch in data/derived/cache/ so runs resume.
"""
import argparse
import hashlib
import json
import random
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from legalagent.core.ingestion import ingest, normalize  # noqa: E402
from legalagent.core.extraction import extract  # noqa: E402
from legalagent.core.classification import classify  # noqa: E402
from legalagent.core.candidate_selection import select_candidates  # noqa: E402

OUT = ROOT / "data" / "derived"
CACHE = OUT / "cache"
INDIAN_TRAIN = [
    "data/demo/india/official/model_concession_4_laning.pdf",
    "data/demo/samples/03_indian_tech_services_msa.md",
    "data/demo/samples/04_executive_employment_agreement.md",
    "data/demo/samples/05_commercial_vendor_supply_agreement.md",
    "data/demo/india/indian_tech_msa_demo.md",
]
INDIAN_CLAUSE_EVAL = [
    "data/demo/india/official/model_concession_4_laning.pdf",
    "data/demo/india/official/pune_metro_signed_concession.pdf",
]
RELATIONS = ["conflict", "dependency", "overlap", "ambiguity", "no_issue"]
SEVERITIES = ["low", "medium", "high"]


def cuad_contracts():
    payload = json.loads(zipfile.ZipFile(ROOT / "dataset" / "data.zip").read("CUADv1.json"))
    for doc in payload["data"]:
        yield "cuad:" + doc["title"][:80], normalize(doc["paragraphs"][0]["context"])


FALLBACK_MODELS = ["gemini-3-flash-preview", "gemini-3.5-flash-lite", "gemini-3-flash-preview", "gemini-3.5-flash"]


def gemini_with_backoff(prompt: str) -> dict:
    """503/429 are common under load: back off and rotate models before giving up."""
    import time
    from legalagent.core.gemini import generate_json
    last = None
    for attempt in range(8):
        model = FALLBACK_MODELS[attempt % len(FALLBACK_MODELS)]
        try:
            return generate_json(prompt, model=model)
        except Exception as exc:
            last = exc
            time.sleep(min(60, 3 * 2 ** (attempt // 2)) + random.random())
    raise last


def cached_gemini(prompt: str, prefix: str = "") -> dict:
    CACHE.mkdir(parents=True, exist_ok=True)
    key = CACHE / (prefix + hashlib.sha1(prompt.encode()).hexdigest() + ".json")
    if key.exists():
        return json.loads(key.read_text())
    raw = gemini_with_backoff(prompt)
    key.write_text(json.dumps(raw))
    return raw


def label_pairs(chunk):
    from legalagent.core.gemini_analysis import _build_prompt
    try:
        raw = cached_gemini(_build_prompt(chunk))
    except Exception as exc:  # keep going; failed batches simply aren't in the set
        print("batch failed:", exc, file=sys.stderr)
        return [None] * len(chunk)
    items = raw.get("findings", []) if isinstance(raw, dict) else []
    if len(items) != len(chunk):
        return [None] * len(chunk)  # misaligned batch: drop rather than guess
    out = []
    for it in items:
        rel = str(it.get("relation_type", "")).lower().strip()
        sev = str(it.get("severity", "")).lower().strip()
        if rel not in RELATIONS or sev not in SEVERITIES:
            out.append(None)
            continue
        try:
            risk = max(0.0, min(1.0, float(it.get("risk_score", 0))))
        except (TypeError, ValueError):
            risk = 0.0
        out.append({"relation": rel, "severity": sev, "risk": risk,
                    "rationale": str(it.get("rationale", ""))[:400],
                    "citation": str(it.get("statute_citation", ""))[:200]})
    return out


def build_pairs(args):
    rnd = random.Random(args.seed)
    docs = list(cuad_contracts())
    rnd.shuffle(docs)
    docs = docs[: args.contracts]
    for path in INDIAN_TRAIN:
        p = ROOT / path
        if p.exists():
            docs.append(("india:" + p.stem, ingest(str(p))))
    print(f"{len(docs)} contracts", flush=True)

    config = {"retrieval_method": "hybrid", "top_k": 3, "max_candidates": args.per_contract, "embedding_model": "all-MiniLM-L6-v2"}
    contracts, pairs = [], []
    for cid, text in docs:
        clauses = extract(text, cid)
        if len(clauses) < 4:
            continue
        clauses = classify(clauses, backend="minilm_lr")
        cands = select_candidates(clauses, config)
        by = {c.id: c for c in clauses}
        cap = args.india_per_contract if cid.startswith("india:") else args.per_contract
        if len(cands) > cap:
            # Stratified: half structural (xref / type-matrix) pairs, where most real
            # issues are, half retrieval-only pairs, so the judge also learns "no_issue".
            prio = [c for c in cands if {"xref", "type_matrix"} & set(c[2])]
            rest = [c for c in cands if c not in prio]
            take = rnd.sample(prio, min(len(prio), cap // 2))
            take += rnd.sample(rest, min(len(rest), cap - len(take)))
            cands = take
        contracts.append({"contract": cid, "clauses": [
            {"id": c.id, "number": c.number, "text": c.text[:2000], "labels": [l["label"] for l in c.labels],
             "xrefs": [x["clause_id"] for x in c.xrefs if x["resolved"]]} for c in clauses]})
        for a, b, how in cands:
            pairs.append({"contract": cid, "a": by[a], "b": by[b], "surfaced_by": how})
    print(f"{len(pairs)} candidate pairs from {len(contracts)} contracts", flush=True)

    # Contract-level split; Indian docs always train (they're few and are the domain we care about).
    cuad_ids = sorted({p["contract"] for p in pairs if p["contract"].startswith("cuad:")})
    rnd.shuffle(cuad_ids)
    test_ids = set(cuad_ids[: max(1, int(0.15 * len(cuad_ids)))])
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "judge_contracts.jsonl").open("w", encoding="utf-8") as f:
        for c in contracts:
            f.write(json.dumps({**c, "split": "test" if c["contract"] in test_ids else "train"}, ensure_ascii=False) + "\n")

    if args.export:
        # Unlabelled pairs for an external teacher (e.g. Antigravity CLI); see research/teacher_labels/.
        dest = ROOT / "research" / "teacher_labels"
        dest.mkdir(parents=True, exist_ok=True)
        with (dest / "pairs_to_label.jsonl").open("w", encoding="utf-8") as f:
            for i, p in enumerate(pairs):
                a, b = p["a"], p["b"]
                f.write(json.dumps({
                    "pair_id": f"p{i:05d}", "contract": p["contract"],
                    "split": "test" if p["contract"] in test_ids else "train",
                    "a_id": a.id, "b_id": b.id, "a_text": a.text[:1500], "b_text": b.text[:1500],
                    "a_labels": [l["label"] for l in a.labels], "b_labels": [l["label"] for l in b.labels],
                    "surfaced_by": p["surfaced_by"],
                }, ensure_ascii=False) + "\n")
        print("exported", len(pairs), "pairs ->", dest / "pairs_to_label.jsonl")
        return

    chunks =[[(p["a"], p["b"], p["surfaced_by"]) for p in pairs[i:i + 10]] for i in range(0, len(pairs), 10)]
    with ThreadPoolExecutor(args.workers) as pool:
        labels = [lab for batch in pool.map(label_pairs, chunks) for lab in batch]

    kept = 0
    with (OUT / "judge_pairs.jsonl").open("w", encoding="utf-8") as f:
        for p, lab in zip(pairs, labels):
            if lab is None:
                continue
            a, b = p["a"], p["b"]
            f.write(json.dumps({
                "contract": p["contract"], "split": "test" if p["contract"] in test_ids else "train",
                "a_id": a.id, "b_id": b.id, "a_text": a.text[:1500], "b_text": b.text[:1500],
                "a_labels": [l["label"] for l in a.labels], "b_labels": [l["label"] for l in b.labels],
                "surfaced_by": p["surfaced_by"], "teacher": "gemini", **lab,
            }, ensure_ascii=False) + "\n")
            kept += 1
    from collections import Counter
    dist = Counter(json.loads(l)["relation"] for l in (OUT / "judge_pairs.jsonl").read_text(encoding="utf-8").splitlines())
    print(f"kept {kept}/{len(pairs)} labelled pairs; relation distribution {dict(dist)}")


def build_india_clauses(args):
    import yaml
    labels = [l for l in yaml.safe_load((ROOT / "clause20" / "labels.yaml").read_text())["labels"]]
    rnd = random.Random(args.seed)
    clauses = []
    for path in INDIAN_CLAUSE_EVAL:
        text = ingest(str(ROOT / path))
        cl = [c for c in extract(text, Path(path).stem) if len(c.text.split()) >= 12]
        clauses += rnd.sample(cl, min(len(cl), args.max // len(INDIAN_CLAUSE_EVAL)))
    print(f"{len(clauses)} Indian clauses", flush=True)

    def run(batch):
        listing = "\n\n".join(f"[{i}] {c.text[:900]}" for i, c in enumerate(batch))
        prompt = (
            "You label clauses from Indian contracts with clause types. Allowed types: "
            + ", ".join(labels)
            + ". Give every type that applies (usually 1, at most 3); use \"other\" only if none applies.\n"
            'Return JSON {"items": [{"i": <index>, "labels": [..]}]} with one item per clause.\n\n' + listing)
        try:
            raw = cached_gemini(prompt, prefix="india_")
            got = {int(it["i"]): [l for l in it.get("labels", []) if l in labels] for it in raw.get("items", [])}
        except Exception as exc:
            print("batch failed:", exc, file=sys.stderr)
            got = {}
        return [(c, got.get(i)) for i, c in enumerate(batch)]

    batches = [clauses[i:i + 15] for i in range(0, len(clauses), 15)]
    with ThreadPoolExecutor(args.workers) as pool:
        results = [r for rs in pool.map(run, batches) for r in rs]
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "india_clause_eval.jsonl").open("w", encoding="utf-8") as f:
        for c, labs in results:
            if labs:
                f.write(json.dumps({"id": c.id, "text": c.text[:2000], "labels": labs, "teacher": "gemini", "reviewed": False}, ensure_ascii=False) + "\n")
    print("wrote", OUT / "india_clause_eval.jsonl")


def import_labels(args):
    """Merge external teacher labels (research/teacher_labels/labels/*.jsonl) into judge_pairs.jsonl."""
    src = ROOT / "research" / "teacher_labels"
    pairs = {json.loads(l)["pair_id"]: json.loads(l) for l in (src / "pairs_to_label.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    labels, bad = {}, 0
    # Only the primary teacher trains Kev; other model families (second opinion) and the
    # checklist are evaluation-only and live in the same folder.
    files = sorted({f for g in args.label_glob.split(",") for f in (src / "labels").glob(g.strip())})
    print("label files:", [f.name for f in files])
    for f in files:
        teacher = f.stem.replace("extra_", "").replace("agy_", "antigravity-")
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(l)
                if r.get("pair_id") in labels:   # first file wins (primary teacher listed first)
                    continue
                rel, sev = str(r["relation"]).lower(), str(r.get("severity", "low")).lower()
                assert r["pair_id"] in pairs and rel in RELATIONS and sev in SEVERITIES
                labels[r["pair_id"]] = {"relation": rel, "severity": sev, "risk": max(0.0, min(1.0, float(r.get("risk", 0)))),
                                        "rationale": str(r.get("rationale", ""))[:400], "citation": str(r.get("citation", ""))[:200],
                                        # optional richer fields (later runs); kept verbatim for audit and gold-set selection
                                        "teacher_file": teacher,
                                        **{k: r[k] for k in ("a_types", "b_types", "fix_clause", "suggested_fix", "confidence", "_provenance") if k in r}}
            except Exception:
                bad += 1
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / "judge_pairs.jsonl").open("w", encoding="utf-8") as f:
        for pid, p in pairs.items():
            if pid in labels:
                f.write(json.dumps({**p, "teacher": labels[pid].get("teacher_file", args.teacher), **labels[pid]}, ensure_ascii=False) + "\n")
    from collections import Counter
    print(f"imported {len(labels)}/{len(pairs)} labels ({bad} malformed lines skipped);",
          dict(Counter(l["relation"] for l in labels.values())))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["pairs", "india-clauses", "import-labels"])
    ap.add_argument("--export", action="store_true", help="pairs: write unlabelled pairs for an external teacher and stop")
    ap.add_argument("--teacher", default="antigravity-gemini-4")
    ap.add_argument("--label-glob", default="agy_gemini-4-hydrogen-high.jsonl")
    ap.add_argument("--contracts", type=int, default=220)
    ap.add_argument("--per-contract", type=int, default=14)
    ap.add_argument("--india-per-contract", type=int, default=150)
    ap.add_argument("--max", type=int, default=220)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    {"pairs": build_pairs, "india-clauses": build_india_clauses, "import-labels": import_labels}[args.what](args)


if __name__ == "__main__":
    main()
