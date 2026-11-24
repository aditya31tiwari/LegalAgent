"""
Reproduce every number in the report.

    venv/bin/python scripts/eval_all.py classifier     # Table 5.1/5.2  -> results/eval_classifier.json
    venv/bin/python scripts/eval_all.py retrieval      # Table 5.3      -> results/eval_retrieval.json
    venv/bin/python scripts/eval_all.py statutes       # statute RAG    -> results/eval_statutes.json
    venv/bin/python scripts/eval_all.py judge          # judge compare  -> results/eval_judge.json  (needs Kev servers)
    venv/bin/python scripts/eval_all.py e2e            # Table 5.4/5.5/5.6 -> results/eval_e2e.json
    venv/bin/python scripts/eval_all.py tables         # -> results/REPORT_TABLES.md (from whatever exists)

Kev servers for `judge`: base model on :8009, fine-tuned on :8008 (see train/finetune_kev.sh).
"""
import argparse
import csv
import json
import random
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RES = ROOT / "results"
DERIVED = ROOT / "data" / "derived"
RES.mkdir(exist_ok=True)


def save(name, obj):
    (RES / f"{name}.json").write_text(json.dumps(obj, indent=2, default=str))
    print("wrote", RES / f"{name}.json")


def load(name):
    p = RES / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


# ---------------------------------------------------------------- classifier

def eval_classifier(args):
    from sklearn.metrics import f1_score
    from legalagent.core.types import Clause
    from legalagent.core.classification import predict_proba, classify, available_backend, THRESHOLD, _load_inlegalbert

    csv.field_size_limit(10**9)
    rows = list(csv.DictReader(open(ROOT / "clause20" / "data" / "CLAUSE20.csv", encoding="utf-8")))
    sets = {s: [(r["text"], set(r["labels"].split("|"))) for r in rows if r["split"] == s] for s in ("test", "test_ood")}
    india = [json.loads(l) for l in (DERIVED / "india_clause_eval.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    sets["india_silver"] = [(r["text"], set(r["labels"])) for r in india]
    if args.limit:
        sets = {k: random.Random(0).sample(v, min(args.limit, len(v))) for k, v in sets.items()}

    backends = ["keyword", "minilm_lr"] + (["inlegalbert"] if available_backend("auto") == "inlegalbert" else [])
    out = {}
    for backend in backends:
        out[backend] = {}
        for split, data in sets.items():
            texts = [t for t, _ in data]
            gold = [g for _, g in data]
            t0 = time.time()
            if backend == "keyword":
                cl = classify([Clause(id=str(i), contract_id="e", text=t) for i, t in enumerate(texts)], backend="keyword")
                labels = sorted({l for g in gold for l in g} | {l["label"] for c in cl for l in c.labels})
                pred = [{l["label"] for c_ in [c] for l in c_.labels} for c in cl]
                top1 = [next(iter(p), "other") for p in pred]
            else:
                labels, probs = predict_proba(texts, backend)
                thr = _load_inlegalbert()[3] if backend == "inlegalbert" else THRESHOLD
                pred = [{labels[j] for j in np.where(row >= thr)[0]} for row in probs]
                top1 = [labels[int(np.argmax(row))] for row in probs]
            ms = 1000 * (time.time() - t0) / max(1, len(texts))
            real = sorted(({l for g in gold for l in g} | {l for p in pred for l in p}) - {"other"})
            Y = np.array([[l in g for l in real] for g in gold], dtype=int)
            P = np.array([[l in p for l in real] for p in pred], dtype=int)
            out[backend][split] = {
                "n": len(texts),
                "micro_f1": float(f1_score(Y, P, average="micro", zero_division=0)),
                "macro_f1": float(f1_score(Y, P, average="macro", zero_division=0)),
                "top1_acc": float(np.mean([t in g for t, g in zip(top1, gold)])),
                "exact_match": float(np.mean([(p - {"other"}) == (g - {"other"}) for p, g in zip(pred, gold)])),
                "ms_per_clause": round(ms, 2),
            }
            print(backend, split, out[backend][split], flush=True)
    save("eval_classifier", out)


# ---------------------------------------------------------------- retrieval

def contracts_for_retrieval(n):
    from legalagent.core.ingestion import normalize, ingest
    from legalagent.core.extraction import extract
    payload = json.loads(zipfile.ZipFile(ROOT / "dataset" / "data.zip").read("CUADv1.json"))
    docs = payload["data"]
    random.Random(1).shuffle(docs)
    out = []
    for d in docs:
        cl = extract(normalize(d["paragraphs"][0]["context"]), "c")
        if sum(x["resolved"] for c in cl for x in c.xrefs) >= 3:
            out.append(("cuad", cl))
        if len(out) >= n:
            break
    for p in ["data/demo/india/official/model_concession_4_laning.pdf", "data/demo/india/official/pune_metro_signed_concession.pdf",
              "data/demo/samples/03_indian_tech_services_msa.md"]:
        out.append(("india", extract(ingest(str(ROOT / p)), "i")))
    return out


def eval_retrieval(args):
    from legalagent.core.evaluation import score_method
    configs = [("bm25", "bm25", None), ("dense_minilm", "dense", "all-MiniLM-L6-v2"),
               ("dense_inlegal_sbert", "dense", "bhavyagiri/InLegal-Sbert"), ("dense_bge_small", "dense", "BAAI/bge-small-en-v1.5"),
               ("hybrid_minilm", "hybrid", "all-MiniLM-L6-v2"), ("hybrid_inlegal_sbert", "hybrid", "bhavyagiri/InLegal-Sbert")]
    ft = ROOT / "models" / "inlegal_sbert_clauses"
    if (ft / "config.json").exists():
        configs += [("dense_inlegal_sbert_ft", "dense", str(ft)), ("hybrid_inlegal_sbert_ft", "hybrid", str(ft))]
    docs = contracts_for_retrieval(args.contracts)
    print(f"{len(docs)} contracts, {sum(len(c) for _, c in docs)} clauses", flush=True)
    out = {}
    for name, method, model in configs:
        agg = defaultdict(lambda: defaultdict(list))
        for src, cl in docs:
            r = score_method(cl, method, (1, 3, 5, 10), model or "all-MiniLM-L6-v2")
            for k, v in r["at_k"].items():
                for metric in ("precision", "recall"):
                    agg[src][f"{metric}@{k}"] += [v[metric]] * r["queries"]  # query-weighted macro
        out[name] = {src: {m: float(np.mean(v)) for m, v in d.items()} for src, d in agg.items()}
        print(name, json.dumps(out[name]), flush=True)
    save("eval_retrieval", out)


# ---------------------------------------------------------------- statutes

def eval_statutes(args):
    """Queries: teacher findings whose citation resolves to a library section. Gold = that section."""
    from legalagent.core.statutes import retrieve_sections, verify_citation
    rows = [json.loads(l) for l in (DERIVED / "judge_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    qs = []
    for r in rows:
        if r["relation"] == "no_issue":
            continue
        s = verify_citation(r.get("citation", ""))
        if s:
            qs.append((f"{r['a_text'][:600]} {r['b_text'][:600]}", (s["act"], s["section"]), r["split"]))
    qs = [q for q in qs if q[2] == "test"] or qs
    print(len(qs), "statute queries", Counter(g[0] for _, g, _ in qs).most_common(5), flush=True)
    configs = {"bm25": dict(method="bm25", act_prior=False), "dense_inlegal_sbert": dict(method="dense", act_prior=False, model_name="bhavyagiri/InLegal-Sbert"),
               "hybrid": dict(method="hybrid", act_prior=False, model_name="bhavyagiri/InLegal-Sbert"),
               "hybrid+act_prior": dict(method="hybrid", act_prior=True, model_name="bhavyagiri/InLegal-Sbert")}
    ft = ROOT / "models" / "inlegal_sbert_statutes"
    if (ft / "config.json").exists():
        configs["hybrid_ft+act_prior"] = dict(method="hybrid", act_prior=True, model_name=str(ft))
    out = {"queries": len(qs)}
    for name, kw in configs.items():
        hits = {1: 0, 3: 0, 5: 0}
        act_hits = 0
        for q, gold, _ in qs:
            res = [(s["act"], s["section"]) for s, _ in retrieve_sections(q, k=5, **kw)]
            for k in hits:
                hits[k] += gold in res[:k]
            act_hits += gold[0] in [a for a, _ in res[:3]]
        out[name] = {f"recall@{k}": v / max(1, len(qs)) for k, v in hits.items()} | {"act_recall@3": act_hits / max(1, len(qs))}
        print(name, out[name], flush=True)
    save("eval_statutes", out)


# ---------------------------------------------------------------- judge

def _clause(cid, text, labels):
    from legalagent.core.types import Clause
    return Clause(id=cid, contract_id="e", number=cid.split("::")[-1], text=text, labels=[{"label": l} for l in labels])


def eval_judge(args):
    from sklearn.metrics import f1_score, precision_recall_fscore_support
    from legalagent.core.analysis import analyse_pair
    from legalagent.core import local_judge
    from legalagent.core.local_judge import pair_request, statute_options, _post

    gold_path = ROOT / "research" / "gold_set" / "gold.jsonl"
    rows = [json.loads(l) for l in (DERIVED / "judge_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r["split"] == "test"]
    if args.limit:
        rows = rows[: args.limit]
    references = {"teacher_gemini": [r["relation"] for r in rows]}
    gold_note = None
    if gold_path.exists():
        gold = {(g["a_id"], g["b_id"]): g["relation"] for g in map(json.loads, gold_path.read_text(encoding="utf-8").splitlines()) if g.get("relation")}
        gold_note = f"{sum((r['a_id'], r['b_id']) in gold for r in rows)} pairs human-verified"

    preds, latency = {}, {}
    preds["rules"] = []
    t0 = time.time()
    for r in rows:
        f = analyse_pair(_clause(r["a_id"], r["a_text"], r["a_labels"]), _clause(r["b_id"], r["b_text"], r["b_labels"]), r["surfaced_by"])
        preds["rules"].append(f.relation_type if f else "no_issue")
    latency["rules"] = 1000 * (time.time() - t0) / len(rows)

    for name, url in (("kev_base_zero_shot", "http://127.0.0.1:8009/v1/systemone"), ("kev_finetuned", "http://127.0.0.1:8008/v1/systemone")):
        local_judge.KEV_URL = url
        if not local_judge.available():
            print("skip", name, "(server not running at", url, ")")
            continue
        out, t0 = [], time.time()
        for r in rows:
            a, b = _clause(r["a_id"], r["a_text"], r["a_labels"]), _clause(r["b_id"], r["b_text"], r["b_labels"])
            resp = _post(pair_request(a, b, r["surfaced_by"], statute_options(a, b)))
            out.append(resp["answers"]["relation"]["choice"])
        preds[name] = out
        latency[name] = 1000 * (time.time() - t0) / len(rows)

    res = {"n_pairs": len(rows), "reference": "teacher_gemini", "gold": gold_note, "label_dist": Counter(references["teacher_gemini"])}
    ref = references["teacher_gemini"]
    for name, p in preds.items():
        risky_ref = [x != "no_issue" for x in ref]
        risky_p = [x != "no_issue" for x in p]
        pr, rc, f1, _ = precision_recall_fscore_support(risky_ref, risky_p, average="binary", zero_division=0)
        res[name] = {"accuracy": float(np.mean([a == b for a, b in zip(ref, p)])),
                     "macro_f1": float(f1_score(ref, p, average="macro", zero_division=0)),
                     "risky_precision": float(pr), "risky_recall": float(rc), "risky_f1": float(f1),
                     "ms_per_pair": round(latency[name], 1), "data_leaves_machine": False}
        print(name, res[name], flush=True)
    save("eval_judge", res)


# ---------------------------------------------------------------- end to end

def eval_e2e(args):
    from legalagent.core.pipeline import analyse
    from legalagent.core.classification import classify
    from legalagent.core.extraction import extract
    from legalagent.core.ingestion import ingest
    from legalagent.core.analysis import analyse_statutory

    inj = json.loads((ROOT / "data/demo/india/adversarial/INJECTIONS.json").read_text())["injections"]
    inj_nums = {i["number"] for i in inj}
    docs = {"adversarial_pdf_305p": "data/demo/india/adversarial/pune_metro_adversarial_15_changes.pdf",
            "control_pdf_300p": "data/demo/india/official/pune_metro_signed_concession.pdf",
            "adversarial_md": "data/demo/samples/02_pune_metro_adversarial_15_injections.md"}
    judges = args.judges.split(",")
    out = {"injections": len(inj_nums)}
    for doc, path in docs.items():
        for judge in judges:
            t0 = time.time()
            run, clauses, findings = analyse(str(ROOT / path), {"judge": judge, "retrieval_method": "hybrid", "top_k": 5,
                                                               "max_candidates": args.max_candidates, "classifier": "auto"}, doc)
            by = {c.id: c for c in clauses}
            flagged = {by[cid].number for f in findings for cid in [f.target_clause_id, *f.related_clause_ids] if cid in by}
            hit = flagged & inj_nums
            out[f"{doc}|{judge}"] = {
                "judge_used": run.stats["judge"], "clauses": len(clauses), "pairs": run.stats["pairs"],
                "findings": len(findings), "high": sum(f.severity == "high" for f in findings),
                "injection_recall": len(hit) / len(inj_nums) if "adversarial" in doc else None,
                "injected_flagged": sorted(hit), "findings_on_injected": sum(
                    any(by.get(c) and by[c].number in inj_nums for c in [f.target_clause_id, *f.related_clause_ids]) for f in findings),
                "seconds_total": round(time.time() - t0, 2), **{k: v for k, v in run.stats.items() if k.endswith("_s")},
            }
            print(doc, judge, out[f"{doc}|{judge}"], flush=True)
        # single-clause baseline: per-clause labels + statutory rules, no pairing at all
        cl = classify(extract(ingest(str(ROOT / path)), doc))
        risky_types = {"limitation_of_liability", "indemnification", "exclusivity_and_restraint"}
        single = {c.number for c in cl if any(l["label"] in risky_types for l in c.labels)}
        single |= {next(c.number for c in cl if c.id == f.target_clause_id) for f in analyse_statutory(cl)}
        out[f"{doc}|single_clause_baseline"] = {"flags": len(single),
                                                "injection_recall": len(single & inj_nums) / len(inj_nums) if "adversarial" in doc else None}
    save("eval_e2e", out)


# ---------------------------------------------------------------- tables

def fmt(x, pct=False):
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{100 * x:.1f}" if pct else f"{x:.3f}"
    return str(x)


def tables(args):
    lines = ["# LegalAgent — results (generated by scripts/eval_all.py; do not edit by hand)", ""]
    for name in sorted(RES.glob("classifier_*.json")):
        r = json.loads(name.read_text())
        lines += [f"## Fine-tuning run: {r['model']} ({name.name})", "",
                  f"epochs {r['epochs']}, lr {r['lr']}, batch {r['batch_size']}, max_len {r['max_len']}, threshold {r['threshold']} (tuned on validation), train time {r['train_seconds']} s", "",
                  "| split | n | micro-F1 | macro-F1 | top-1 acc | exact match | ms/clause |", "|---|---|---|---|---|---|---|"]
        for s, m in r["splits"].items():
            lines.append(f"| {s} | {m['n']} | {fmt(m['micro_f1'])} | {fmt(m['macro_f1'])} | {fmt(m['top1_acc'])} | {fmt(m['exact_match'])} | {m.get('ms_per_clause', '—')} |")
        lines.append("")
    c = load("eval_classifier")
    if c:
        lines += ["## Table 5.1/5.2 — Clause classification (CLAUSE-20)", "",
                  "| classifier | split | n | micro-F1 | macro-F1 | top-1 acc | exact match | ms/clause |", "|---|---|---|---|---|---|---|---|"]
        for b, d in c.items():
            for s, m in d.items():
                lines.append(f"| {b} | {s} | {m['n']} | {fmt(m['micro_f1'])} | {fmt(m['macro_f1'])} | {fmt(m['top1_acc'])} | {fmt(m['exact_match'])} | {m['ms_per_clause']} |")
        lines += ["", "india_silver = Indian government contract clauses labelled by the Gemini teacher (silver; see research/gold_set for human checks).", ""]
    r = load("eval_retrieval")
    if r:
        lines += ["## Table 5.3 — Related-clause retrieval (gold = resolved cross-references, clause numbers + xref phrases masked)", "",
                  "| method | corpus | P@1 | P@3 | P@5 | R@3 | R@5 | R@10 |", "|---|---|---|---|---|---|---|---|"]
        for m, d in r.items():
            for src, v in d.items():
                lines.append(f"| {m} | {src} | " + " | ".join(fmt(v.get(k)) for k in ("precision@1", "precision@3", "precision@5", "recall@3", "recall@5", "recall@10")) + " |")
        lines.append("")
    s = load("eval_statutes")
    if s:
        lines += [f"## Statute grounding — retrieving the cited Indian section ({s['queries']} queries)", "",
                  "| retriever | R@1 | R@3 | R@5 | correct Act in top-3 |", "|---|---|---|---|---|"]
        for k, v in s.items():
            if isinstance(v, dict):
                lines.append(f"| {k} | {fmt(v['recall@1'])} | {fmt(v['recall@3'])} | {fmt(v['recall@5'])} | {fmt(v['act_recall@3'])} |")
        lines.append("")
    j = load("eval_judge")
    if j:
        lines += [f"## Pair judge comparison ({j['n_pairs']} held-out pairs, reference = {j['reference']}; {j.get('gold') or 'no human gold yet'})", "",
                  "| judge | accuracy | macro-F1 | risky P | risky R | risky F1 | ms/pair | data leaves machine |", "|---|---|---|---|---|---|---|---|"]
        for k, v in j.items():
            if isinstance(v, dict) and "accuracy" in v:
                lines.append(f"| {k} | {fmt(v['accuracy'])} | {fmt(v['macro_f1'])} | {fmt(v['risky_precision'])} | {fmt(v['risky_recall'])} | {fmt(v['risky_f1'])} | {v['ms_per_pair']} | {'yes' if v['data_leaves_machine'] else 'no'} |")
        lines += ["| teacher_gemini (reference) | 1.000 | 1.000 | — | — | — | API | yes |", ""]
    g = load("gnn")
    if g:
        lines += ["## Clause-graph GNN — ranking risky pairs on held-out contracts", "",
                  "| scorer | ROC-AUC | avg precision | P@5 |", "|---|---|---|---|"]
        for k in ("gnn", "no_graph", "type_matrix", "cosine"):
            if k in g:
                lines.append(f"| {k} | {fmt(g[k]['roc_auc'])} | {fmt(g[k]['avg_precision'])} | {fmt(g[k]['p_at_5'])} |")
        lines.append("")
    e = load("eval_e2e")
    if e:
        lines += [f"## Table 5.4/5.5/5.6 — End-to-end on the Pune Metro concession ({e['injections']} planted irregularities)", "",
                  "| document | judge | clauses | pairs | findings | high | injection recall | findings on injected | total s | classify s | candidates s | judge s |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for k, v in e.items():
            if isinstance(v, dict) and "findings" in v:
                doc, judge = k.split("|")
                lines.append(f"| {doc} | {v['judge_used']} | {v['clauses']} | {v['pairs']} | {v['findings']} | {v['high']} | {fmt(v['injection_recall'], True) + '%' if v['injection_recall'] is not None else '—'} | {v['findings_on_injected']} | {v['seconds_total']} | {v.get('classify_s')} | {v.get('candidates_s')} | {v.get('judge_s')} |")
        lines += ["", "| document | single-clause baseline flags | injection recall |", "|---|---|---|"]
        for k, v in e.items():
            if k.endswith("single_clause_baseline"):
                lines.append(f"| {k.split('|')[0]} | {v['flags']} | {fmt(v['injection_recall'], True) + '%' if v['injection_recall'] is not None else '—'} |")
        lines.append("")
    (RES / "REPORT_TABLES.md").write_text("\n".join(lines), encoding="utf-8")
    print("wrote", RES / "REPORT_TABLES.md")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("what", choices=["classifier", "retrieval", "statutes", "judge", "e2e", "tables"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--contracts", type=int, default=120)
    ap.add_argument("--judges", default="rules,local")
    ap.add_argument("--max-candidates", type=int, default=60)
    args = ap.parse_args()
    {"classifier": eval_classifier, "retrieval": eval_retrieval, "statutes": eval_statutes,
     "judge": eval_judge, "e2e": eval_e2e, "tables": tables}[args.what](args)


if __name__ == "__main__":
    main()
