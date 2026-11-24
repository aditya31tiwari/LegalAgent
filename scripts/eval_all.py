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


def save(name, obj, merge=False):
    """merge=True keeps entries from earlier runs that this run did not produce (e.g. the
    base-Kev row measured while only the base server was up)."""
    path = RES / f"{name}.json"
    if merge and path.exists():
        old = json.loads(path.read_text())
        obj = {**old, **obj}
    path.write_text(json.dumps(obj, indent=2, default=str))
    print("wrote", path)


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
    # Gold #2 (independent): the statute each Supreme Court judgment actually applied.
    lit = []
    lp = ROOT / "research/litigated_clauses/cases.jsonl"
    if lp.exists():
        for c in map(json.loads, lp.read_text(encoding="utf-8").splitlines()):
            golds = [s for part in c.get("statute", "").split(";") for s in [verify_citation(part.strip())] if s]
            if golds:
                q = c["clause_a"]["text"] + " " + ((c.get("clause_b") or {}).get("text") or "")
                lit.append((q[:1500], {(g["act"], g["section"]) for g in golds}))
    out = {"queries": len(qs), "litigated_queries": len(lit),
           "note": "teacher-citation gold is ~94% Indian Contract Act (s.37 over-cited) - see always_ica baseline; "
                   "the litigated gold (statute applied by the Supreme Court) is the independent test"}
    ica = "The Indian Contract Act, 1872"
    out["always_ica_baseline"] = {"act_recall@3": sum(g[0] == ica for _, g, _ in qs) / max(1, len(qs)),
                                  "litigated_act_recall@3": sum(any(a == ica for a, _ in gs) for _, gs in lit) / max(1, len(lit))}
    for name, kw in configs.items():
        if lit:
            hit_s = {1: 0, 3: 0, 5: 0}
            hit_a = 0
            for q, gs in lit:
                res = [(s["act"], s["section"]) for s, _ in retrieve_sections(q, k=5, **kw)]
                for k in hit_s:
                    hit_s[k] += any(r in gs for r in res[:k])
                hit_a += any(a in {g[0] for g in gs} for a, _ in res[:3])
            out.setdefault("litigated", {})[name] = {f"recall@{k}": v / len(lit) for k, v in hit_s.items()} | {"act_recall@3": hit_a / len(lit)}
            print("litigated", name, out["litigated"][name], flush=True)
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


def _judge_predictions(rows, which):
    """Relation predictions of each available judge on `rows` (pairs with a/b text).
    Clause types come from the current CLAUSE-22 classifier, as at inference."""
    from legalagent.core.analysis import analyse_pair
    from legalagent.core import local_judge
    from legalagent.core.local_judge import pair_request, statute_options, _post
    sys.path.insert(0, str(ROOT / "train"))
    from export_kev_data import current_types
    types = current_types(rows)
    mk = lambda r, s: _clause(r[f"{s}_id"], r[f"{s}_text"], types[(r[f"{s}_id"], r[f"{s}_text"])])
    preds, latency = {}, {}
    t0 = time.time()
    preds["rules"] = []
    for r in rows:
        f = analyse_pair(mk(r, "a"), mk(r, "b"), r["surfaced_by"])
        preds["rules"].append(f.relation_type if f else "no_issue")
    latency["rules"] = 1000 * (time.time() - t0) / max(1, len(rows))
    from legalagent.core.local_judge import decide
    for name, url in which:
        local_judge.KEV_URL = url
        if not local_judge.available():
            print("skip", name, "(server not running at", url, ")")
            continue
        probs, t0 = [], time.time()
        for r in rows:
            a, b = mk(r, "a"), mk(r, "b")
            probs.append(_post(pair_request(a, b, r["surfaced_by"], statute_options(a, b)))["answers"]["relation"]["probabilities"])
        latency[name] = latency[name + "_tau"] = 1000 * (time.time() - t0) / max(1, len(rows))
        preds[name] = [decide(p, None) for p in probs]                     # argmax
        tau = _kev_threshold(name)
        if tau is not None:                                                 # calibrated on training contracts
            preds[name + "_tau"] = [decide(p, tau) for p in probs]
    return preds, latency


KEV_SERVERS = (("kev_base_zero_shot", "http://127.0.0.1:8009/v1/systemone"), ("kev_finetuned", "http://127.0.0.1:8008/v1/systemone"))
THRESHOLD_FILES = {"kev_base_zero_shot": ROOT / "models" / "kev_base_threshold.json",
                   "kev_finetuned": ROOT / "models" / "kev_judge" / "threshold.json"}


def _kev_threshold(name):
    p = THRESHOLD_FILES.get(name)
    try:
        return float(json.loads(p.read_text())["threshold"]) if p and p.exists() else None
    except Exception:
        return None


def eval_checklist(args):
    """Known-answer minimal pairs: independent of any teacher label."""
    rows = [json.loads(l) for l in (ROOT / "research/teacher_labels/checklist_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    preds, latency = _judge_predictions(rows, KEV_SERVERS)
    out = {"pairs": len(rows)}
    for name, p in preds.items():
        risky = [x != "no_issue" for x in p]
        exp = [r["expected_risky"] for r in rows]
        bad = [i for i, e in enumerate(exp) if e]
        fixed = [i for i, e in enumerate(exp) if not e]
        out[name] = {"binary_accuracy": float(np.mean([a == b for a, b in zip(risky, exp)])),
                     "risky_detected_on_bad": float(np.mean([risky[i] for i in bad])),
                     "no_issue_on_fixed": float(np.mean([not risky[i] for i in fixed])),
                     "ms_per_pair": round(latency[name], 1),
                     "misses": [rows[i]["case"] for i in range(len(rows)) if risky[i] != exp[i]]}
        print(name, out[name], flush=True)
    for f in sorted((ROOT / "research/teacher_labels/labels").glob("checklist_agy_*.jsonl")):
        labs = {json.loads(l)["pair_id"]: json.loads(l)["relation"] for l in f.read_text(encoding="utf-8").splitlines() if l.strip()}
        got = [(labs[r["pair_id"]] != "no_issue", r["expected_risky"]) for r in rows if r["pair_id"] in labs]
        if got:
            out[f"teacher:{f.stem.replace('checklist_agy_', '')}"] = {"binary_accuracy": float(np.mean([a == b for a, b in got])), "pairs": len(got)}
    save("eval_checklist", out, merge=True)


def eval_cuadpairs(args):
    """Recall on lawyer-grounded CUAD interaction pairs (scripts/make_cuad_pairs.py); no LLM labels."""
    rows = [json.loads(l) for l in (ROOT / "research/teacher_labels/cuad_interaction_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    preds, latency = _judge_predictions(rows, KEV_SERVERS)
    out = {"pairs": len(rows)}
    for name, p in preds.items():
        by_case = defaultdict(list)
        for r, x in zip(rows, p):
            by_case[r["case"]].append(x != "no_issue")
        out[name] = {"recall": float(np.mean([x != "no_issue" for x in p])), "ms_per_pair": round(latency[name], 1),
                     "by_case": {k: round(float(np.mean(v)), 3) for k, v in by_case.items()}}
        print(name, out[name], flush=True)
    save("eval_cuadpairs", out, merge=True)


def eval_litigated(args):
    """
    Real clauses from Indian Supreme Court judgments (research/litigated_clauses/cases.jsonl);
    the court's decision is the ground truth. Cross-clause cases go to every pair judge;
    single-clause cases go to the Indian statutory rules (the component meant to catch them).
    Upheld clauses are negatives (a flag there is a false alarm).
    """
    from legalagent.core.types import Clause
    from legalagent.core.analysis import analyse_statutory
    from legalagent.core.classification import classify
    cases = [json.loads(l) for l in (ROOT / "research/litigated_clauses/cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pair_rows = [{"pair_id": c["case_id"], "a_id": f"lit::{c['case_id']}::a", "b_id": f"lit::{c['case_id']}::b",
                  "a_text": c["clause_a"]["text"], "b_text": c["clause_b"]["text"], "surfaced_by": ["xref"]}
                 for c in cases if c["kind"] == "cross_clause" and c.get("clause_b") and c["clause_b"].get("text")]
    preds, _lat = _judge_predictions(pair_rows, KEV_SERVERS) if pair_rows else ({}, {})
    by_pair = {r["pair_id"]: {name: p[i] for name, p in preds.items()} for i, r in enumerate(pair_rows)}
    out = {"cases": []}
    for c in cases:
        row = {"case": c["case_name"], "year": c["year"], "kind": c["kind"], "court": c["outcome"],
               "statute": c.get("statute", ""), "expected_flag": c["expected_flag"]}
        if c["kind"] == "cross_clause" and c["case_id"] in by_pair:
            for name, rel in by_pair[c["case_id"]].items():
                row[name] = rel
        cl = classify([Clause(id="lit::1", contract_id="lit", number="1", text=c["clause_a"]["text"])])
        stat = analyse_statutory(cl, "India")
        row["statutory_rule"] = ", ".join(r["section"] for f in stat for r in f.refs) or "no_flag"
        row["clause_types"] = [l["label"] for l in cl[0].labels]
        out["cases"].append(row)
        print(row, flush=True)
    # summary per component: agreement with the court's expected flag
    summ = {}
    for name in ["statutory_rule", *preds.keys()]:
        rows = [r for r in out["cases"] if name in r]
        if not rows:
            continue
        flagged = lambda v: v not in ("no_issue", "no_flag")
        tp = sum(flagged(r[name]) and r["expected_flag"] for r in rows)
        fp = sum(flagged(r[name]) and not r["expected_flag"] for r in rows)
        fn = sum(not flagged(r[name]) and r["expected_flag"] for r in rows)
        tn = sum(not flagged(r[name]) and not r["expected_flag"] for r in rows)
        summ[name] = {"cases": len(rows), "caught": tp, "missed": fn, "false_alarms": fp, "correctly_quiet": tn}
    out["summary"] = summ
    print(summ)
    save("eval_litigated", out, merge=True)


def eval_judge(args):
    from sklearn.metrics import f1_score, precision_recall_fscore_support

    gold_path = ROOT / "research" / "gold_set" / "gold.jsonl"
    rows = [json.loads(l) for l in (DERIVED / "judge_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = [r for r in rows if r["split"] == "test"]
    if args.limit:
        rows = rows[: args.limit]
    references = {"teacher_gemini": [r["relation"] for r in rows]}
    gold_note, human = None, {}
    if gold_path.exists():
        human = {g["pair_id"]: g["human_relation"] for g in map(json.loads, gold_path.read_text(encoding="utf-8").splitlines()) if g.get("human_relation")}
        gold_note = f"{sum(r.get('pair_id') in human for r in rows)} held-out pairs human-verified"

    preds, latency = _judge_predictions(rows, KEV_SERVERS)

    # Human gold on held-out pairs only (no leakage): judges and the teacher vs humans.
    hg = [i for i, r in enumerate(rows) if r.get("pair_id") in human]
    if hg:
        hrel = [human[rows[i]["pair_id"]] for i in hg]
        vs_human = {"pairs": len(hg)}
        for name, p in {**preds, "teacher_gemini": references["teacher_gemini"]}.items():
            vs_human[name] = {"accuracy": float(np.mean([p[i] == h for i, h in zip(hg, hrel)])),
                              "risky_accuracy": float(np.mean([(p[i] != "no_issue") == (h != "no_issue") for i, h in zip(hg, hrel)]))}
        save("eval_judge_vs_human", vs_human, merge=True)

    res ={"n_pairs": len(rows), "reference": "teacher_gemini", "gold": gold_note, "label_dist": Counter(references["teacher_gemini"])}
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
    save("eval_judge", res, merge=True)


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
            if isinstance(v, dict) and "recall@1" in v:
                lines.append(f"| {k} | {fmt(v['recall@1'])} | {fmt(v['recall@3'])} | {fmt(v['recall@5'])} | {fmt(v['act_recall@3'])} |")
        b = s.get("always_ica_baseline", {})
        lines += [f"| *always answer Indian Contract Act* (baseline) | — | — | — | {fmt(b.get('act_recall@3'))} |", "",
                  f"⚠ {s.get('note', '')}", ""]
        if s.get("litigated"):
            lines += [f"### Statute retrieval vs the statute the Supreme Court applied ({s.get('litigated_queries')} cases; independent gold)", "",
                      "| retriever | section R@1 | section R@3 | section R@5 | correct Act in top-3 |", "|---|---|---|---|---|"]
            for k, v in s["litigated"].items():
                lines.append(f"| {k} | {fmt(v['recall@1'])} | {fmt(v['recall@3'])} | {fmt(v['recall@5'])} | {fmt(v['act_recall@3'])} |")
            lines += [f"| *always answer Indian Contract Act* (baseline) | — | — | — | {fmt(b.get('litigated_act_recall@3'))} |", ""]
    j = load("eval_judge")
    if j:
        lines += [f"## Pair judge comparison ({j['n_pairs']} held-out pairs, reference = {j['reference']}; {j.get('gold') or 'no human gold yet'})", "",
                  "| judge | accuracy | macro-F1 | risky P | risky R | risky F1 | ms/pair | data leaves machine |", "|---|---|---|---|---|---|---|---|"]
        for k, v in j.items():
            if isinstance(v, dict) and "accuracy" in v:
                lines.append(f"| {k} | {fmt(v['accuracy'])} | {fmt(v['macro_f1'])} | {fmt(v['risky_precision'])} | {fmt(v['risky_recall'])} | {fmt(v['risky_f1'])} | {v['ms_per_pair']} | {'yes' if v['data_leaves_machine'] else 'no'} |")
        lines += ["| teacher_gemini (reference) | 1.000 | 1.000 | — | — | — | API | yes |", ""]
    ck = load("eval_checklist")
    if ck:
        lines += [f"## Known-answer checklist ({ck['pairs']} minimal pairs: 12 risky/fixed twins + 4 planted injections) — independent of teacher labels", "",
                  "| judge | binary accuracy | risky caught (bad pairs) | correctly clear (fixed pairs) | ms/pair | misses |", "|---|---|---|---|---|---|"]
        for k, v in ck.items():
            if isinstance(v, dict) and "risky_detected_on_bad" in v:
                lines.append(f"| {k} | {fmt(v['binary_accuracy'])} | {fmt(v['risky_detected_on_bad'])} | {fmt(v['no_issue_on_fixed'])} | {v['ms_per_pair']} | {', '.join(v['misses'][:6])} |")
            elif isinstance(v, dict) and k.startswith("teacher:"):
                lines.append(f"| {k} | {fmt(v['binary_accuracy'])} | — | — | API | |")
        lines.append("")
    cp = load("eval_cuadpairs")
    if cp:
        lines += [f"## CUAD lawyer-grounded interaction pairs ({cp['pairs']} pairs; no LLM labels) — recall of each judge", "",
                  "| judge | recall | ms/pair | per category pair |", "|---|---|---|---|"]
        for k, v in cp.items():
            if isinstance(v, dict) and "recall" in v:
                lines.append(f"| {k} | {fmt(v['recall'])} | {v['ms_per_pair']} | " + "; ".join(f"{c}: {fmt(x)}" for c, x in v["by_case"].items()) + " |")
        lines.append("")
    lt = load("eval_litigated")
    if lt and lt.get("cases"):
        judges = [k for k in ("rules", "kev_base_zero_shot", "kev_finetuned") if any(k in r for r in lt["cases"])]
        lines += ["## Litigated clauses — Supreme Court of India decisions as ground truth (case study, not a statistic)", "",
                  "| case | year | kind | court held | should flag | statutory rule | " + " | ".join(judges) + " |",
                  "|---|---|---|---|---|---|" + "---|" * len(judges)]
        for r in lt["cases"]:
            lines.append(f"| {r['case']} | {r['year']} | {r['kind']} | {r['court']} | {'yes' if r['expected_flag'] else 'no'} | {r['statutory_rule']} | "
                         + " | ".join(str(r.get(j, '—')) for j in judges) + " |")
        lines += ["", "| component | cases | caught | missed | false alarms | correctly quiet |", "|---|---|---|---|---|---|"]
        for k, v in lt.get("summary", {}).items():
            lines.append(f"| {k} | {v['cases']} | {v['caught']} | {v['missed']} | {v['false_alarms']} | {v['correctly_quiet']} |")
        lines.append("")
    h = load("eval_judge_vs_human")
    if h:
        lines += [f"## Judges vs blind human labels ({h['pairs']} held-out pairs)", "", "| judge | relation accuracy | risky/not accuracy |", "|---|---|---|"]
        for k, v in h.items():
            if isinstance(v, dict):
                lines.append(f"| {k} | {fmt(v['accuracy'])} | {fmt(v['risky_accuracy'])} |")
        lines.append("")
    tv = load("teacher_validation")
    if tv:
        lines += ["## Teacher validation (ground truth not produced by the teacher)", ""]
        for k, v in tv.items():
            lines.append(f"- **{k}**: " + ", ".join(f"{kk}={fmt(vv) if isinstance(vv, float) else vv}" for kk, vv in v.items() if kk not in ("top_cited", "misses")))
        lines.append("")
    kt = load("kev_train")
    if kt:
        lines += ["## Kev judge fine-tuning", "", f"- base `{kt.get('base')}`, LoRA delta, lr {kt.get('lr')}, epochs {kt.get('epochs')}, "
                  f"grad-accum {kt.get('accum')}, {kt.get('train_records')} training pairs, {kt.get('train_seconds')} s on RTX 4050", ""]
    for name in ("retriever_clauses", "retriever_statutes"):
        rt = load(name)
        if rt:
            lines += [f"- **{name}**: base `{rt['base']}`, {rt['pairs']} positive pairs, {rt['loss']}, batch {rt['batch_size']}, {rt['train_seconds']} s"]
    lines.append("")
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
    ap.add_argument("what", choices=["classifier", "retrieval", "statutes", "judge", "checklist", "cuadpairs", "litigated", "e2e", "tables"])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--contracts", type=int, default=120)
    ap.add_argument("--judges", default="rules,local")
    ap.add_argument("--max-candidates", type=int, default=60)
    args = ap.parse_args()
    {"classifier": eval_classifier, "retrieval": eval_retrieval, "statutes": eval_statutes,
     "judge": eval_judge, "checklist": eval_checklist, "cuadpairs": eval_cuadpairs, "litigated": eval_litigated,
     "e2e": eval_e2e, "tables": tables}[args.what](args)


if __name__ == "__main__":
    main()
