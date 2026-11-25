#!/bin/sh
''''exec "$(dirname "$0")/../venv/bin/python" "$0" "$@" #'''
"""
One static page with every comparison we measured, including time/speed columns.

    venv/bin/python scripts/build_report.py     -> results/REPORT.html   (also served at /report)

Reads results/*.json (written by scripts/eval_all.py, train/*, scripts/bench_kev.py), the per-contract
runs in results/demo_runs.json / logs/seed_demo*.log, and the independent statute-retrieval rows in
/tmp/eval_statutes.log if present (saved to results/eval_statutes_independent.json).
"""
import html
import json
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / "results"


def load(name):
    p = R / name
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def f3(x):
    return "—" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def pct(x):
    return "—" if x is None else f"{100 * x:.1f} %"


def table(headers, rows, best_col=None, note=""):
    if not rows:
        return ""
    best = None
    if best_col is not None:
        vals = [r[best_col] for r in rows if isinstance(r[best_col], (int, float))]
        best = max(vals) if vals else None
    out = ["<table><thead><tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr></thead><tbody>"]
    for r in rows:
        cells = []
        for i, v in enumerate(r):
            cls = ' class="best"' if best_col == i and v == best and best is not None else ""
            if v is None:
                v = "—"
            elif isinstance(v, float):
                v = pct(v) if headers[i].endswith("%") else f3(v)
            cells.append(f"<td{cls}>{html.escape(str(v))}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</tbody></table>")
    if note:
        out.append(f'<p class="note">{note}</p>')
    return "".join(out)


def section(title, body, why=""):
    if not body:
        return ""
    return f'<section><h2>{html.escape(title)}</h2>{f"<p class=why>{why}</p>" if why else ""}{body}</section>'


def independent_statutes():
    log = Path("/tmp/eval_statutes.log")
    rows = {}
    if log.exists():
        for line in log.read_text(errors="ignore").splitlines():
            m = re.match(r"^litigated (\S+) (\{.*\})", line)
            if m:
                try:
                    rows[m.group(1)] = json.loads(m.group(2).replace("'", '"'))
                except Exception:
                    pass
    if rows:
        (R / "eval_statutes_independent.json").write_text(json.dumps(rows, indent=2))
        return rows
    return load("eval_statutes_independent.json") or {}


def demo_runs():
    runs = {r["id"]: r for r in (load("demo_runs.json") or [])}
    pat = re.compile(r"^(demo_\d+)\s+(\d+) clauses\s+(\d+) pairs\s+(\d+) findings\s+judge=(\w+)\s+([\d.]+)s\s+(.*)$")
    for log in sorted((ROOT / "logs").glob("seed_demo*.log"), key=lambda p: p.stat().st_mtime):
        for line in log.read_text(errors="ignore").splitlines():
            m = pat.match(line.strip())
            if m and (m.group(1) not in runs or runs[m.group(1)].get("source") == "log"):
                runs[m.group(1)] = {"id": m.group(1), "title": m.group(7), "clauses": int(m.group(2)), "pairs": int(m.group(3)),
                                    "findings": int(m.group(4)), "judge": m.group(5), "seconds": float(m.group(6)), "source": "log"}
    return [runs[k] for k in sorted(runs)]


def main():
    parts = []

    # ── classifier
    ec = load("eval_classifier.json") or {}
    rows = []
    for name, splits in ec.items():
        if not isinstance(splits, dict):
            continue
        t, o, i = splits.get("test", {}), splits.get("test_ood", {}), splits.get("india_silver", {})
        rows.append([name, t.get("micro_f1"), t.get("macro_f1"), o.get("micro_f1"), i.get("micro_f1"),
                     t.get("ms_per_clause") or o.get("ms_per_clause")])
    gpu_ms = ((load("classifier_clause20_inlegalbert.json") or {}).get("splits", {}).get("test", {}) or {}).get("ms_per_clause")
    parts.append(section("1 · Clause classification (CLAUSE-22)", table(
        ["classifier", "test micro-F1", "test macro-F1", "out-of-domain micro-F1", "Indian silver micro-F1", "ms / clause"], rows, 1,
        f"ms/clause in this table was measured on CPU (the GPU is kept for Kev). InLegalBERT on the GPU: {gpu_ms} ms/clause."),
        "Tests: given one clause, does the model name its type(s) correctly? (Types decide which pairs are worth checking.) "
        "Same splits for every method. Test n=8,415 (CUAD/LEDGAR), out-of-domain n=703, Indian silver n=220 (teacher-labelled)."))
    iv = load("eval_india_variants.json") or {}
    rows = [[k, v.get("silver", {}).get("micro_f1"), v.get("silver", {}).get("macro_f1"), v.get("gemini4", {}).get("micro_f1"),
             v.get("gemini4", {}).get("macro_f1")] for k, v in iv.items() if isinstance(v, dict)]
    parts.append(section("1b · Indian contracts: classifier variants", table(
        ["variant", "silver micro-F1", "silver macro-F1", "Gemini-4 labels micro-F1", "Gemini-4 labels macro-F1"], rows, 2),
        "Tests: does the classifier still work on real Indian contracts (OCR noise, PPP drafting)? Compares the model alone, "
        "an ensemble with MiniLM-LR, and adding the clause heading as a hint."))

    # ── retrieval
    er = load("eval_retrieval.json") or {}
    rows = []
    for m, corp in er.items():
        for c, v in (corp or {}).items():
            if isinstance(v, dict):
                rows.append([m, c, v.get("precision@1"), v.get("recall@3"), v.get("recall@5"), v.get("recall@10")])
    parts.append(section("2 · Related-clause retrieval (shortlisting)", table(
        ["method", "corpus", "P@1", "R@3", "R@5", "R@10"], rows, 4),
        "Tests: for each clause, does the search method find the clause it is actually linked to? Gold = the clauses it cross-references, "
        "with the clause numbers hidden so the method must match on meaning/words. BM25 holds up best on OCR'd Indian text."))

    # ── judges
    ej, ck, cu = load("eval_judge.json") or {}, load("eval_checklist.json") or {}, load("eval_cuadpairs.json") or {}
    names = [k for k in {**ck, **cu, **ej} if isinstance((ck.get(k) or cu.get(k) or ej.get(k)), dict) and not k.startswith("teacher")]
    rows = []
    for k in names:
        c, u, j = ck.get(k) or {}, cu.get(k) or {}, ej.get(k) or {}
        if not any(isinstance(x, dict) and x for x in (c, u, j)):
            continue
        ms = c.get("ms_per_pair") or u.get("ms_per_pair") or j.get("ms_per_pair")
        if c.get("binary_accuracy") is None and u.get("recall") is None and j.get("risky_f1") is None:
            continue
        rows.append([k, c.get("binary_accuracy"), c.get("risky_detected_on_bad"), c.get("no_issue_on_fixed"), u.get("recall"),
                     j.get("risky_f1"), ms])
    sel = load("judge_selection.json") or {}
    parts.append(section("3 · Clause ↔ clause judge", table(
        ["judge", "checklist acc %", "bad caught %", "fixed cleared %", "CUAD lawyer recall %", "teacher risky-F1", "ms / pair"], rows, 1,
        f"Selected: <b>{html.escape(str(sel.get('judge')))}</b> — {html.escape(str(sel.get('criterion', '')))}. "
        "Teacher agreement is reported, never used to choose."),
        "Tests: given two clauses, does the judge say correctly whether they create a risk together? "
        "Checklist = 28 bad/fixed clause twins (measures catches AND false alarms). CUAD = 280 pairs whose lawyer labels interact by definition. "
        "Teacher risky-F1 = agreement with Gemini 4 on 172 held-out pairs."))

    # ── clause vs law
    st = load("eval_statutory.json") or {}
    items = st.get("items", [])
    if items:
        rows = []
        for src in sorted({i["source"] for i in items}):
            its = [i for i in items if i["source"] == src]
            risky = [i for i in its if i.get("risky")]
            safe = [i for i in its if not i.get("risky")]
            for meth, key in (("regex rules", "regex"), ("Kev (P(risk) ≥ 0.5)", "kev_tau0.5")):
                hit = lambda i: bool(i.get(key)) and i.get(key) not in ("none", False)
                rows.append([src, meth, f"{sum(hit(i) for i in risky)} / {len(risky)}", f"{sum(hit(i) for i in safe)} / {len(safe)}"])
        parts.append(section("4 · Clause ↔ Indian law (single clause)", table(
            ["test set", "method", "risky clauses caught", "safe clauses flagged (false alarms)"], rows),
            "Tests: looking at ONE clause, can the method tell it breaks Indian law? Supreme Court items: clauses quoted in judgments, court "
            "outcome = ground truth. Pune injections: our planted illegal clauses. CUAD ordinary: normal clauses (any flag is a false alarm). "
            "Kev over-flags, so the product shows confidence labels."))

    lp = load("eval_lawcheck_pipeline.json") or []
    if lp:
        order = ["low", "medium", "high"]

        def tier(r):
            if not r["gated"] or r["p"] < 0.30:
                return None
            base = "high" if r["p"] >= 0.7 else "medium" if r["p"] >= 0.45 else "low"
            return order[min(order.index(base) + int(r["corr"]) + int(r["regex"]), 2)]
        rules = [("regex rules only", lambda r: r["regex"]),
                 ("Kev on every clause, P(risk) ≥ 0.5", lambda r: r["p"] >= 0.5),
                 ("as deployed: type gate + Kev, any confidence", lambda r: tier(r) is not None),
                 ("as deployed: medium or high", lambda r: tier(r) in ("medium", "high")),
                 ("as deployed: high (incl. law-/rule-confirmed)", lambda r: tier(r) == "high"),
                 ("law-confirmed by RAG (retrieval finds Kev's section)", lambda r: r["gated"] and r["p"] >= 0.3 and r["corr"])]
        rows = []
        for name, f in rules:
            cell = []
            for src in ("supreme_court", "pune_injection", "cuad_ordinary"):
                x = [r for r in lp if r["src"] == src]
                cell.append(f"{sum(f(r) for r in x if r['risky'])}/{sum(r['risky'] for r in x)} · {sum(f(r) for r in x if not r['risky'])}/{sum(not r['risky'] for r in x)}")
            tp = sum(f(r) for r in lp if r["risky"]); fp = sum(f(r) for r in lp if not r["risky"])
            rows.append([name, *cell, f"{tp}/{tp + fp}" if tp + fp else "—"])
        parts.append(section("4b · Clause ↔ Indian law as deployed (type gate + Kev + RAG and rule corroboration)", table(
            ["rule", "Supreme Court: caught · false", "Pune planted: caught · false", "ordinary clauses: caught · false", "precision"], rows),
            "Tests the full law check the dashboard runs: InLegalBERT decides which clauses could carry a legal risk; Kev names the risk type "
            "(→ mapped section); a finding is LAW-CONFIRMED when the India Code search independently retrieves the same section and "
            "RULE-CONFIRMED when the regex rules also fire; each confirmation raises confidence one level. "
            "Same ground truth as table 4 (results/eval_lawcheck_pipeline.json, scripts/eval_rag_check.py)."))

    # ── statute retrieval
    ind = independent_statutes()
    rows = [[m, v.get("recall@1"), v.get("recall@3"), v.get("recall@5"), v.get("act_recall@3")] for m, v in ind.items()]
    parts.append(section("5 · Statute retrieval (RAG over 4,408 India Code sections)", table(
        ["retriever", "R@1", "R@3", "R@5 (exact section)", "Act in top 3"], rows, 3,
        "Default in the product: hybrid_ft+act_prior (fine-tuned InLegal-SBERT + BM25, RRF, Act prior). The cross-encoder reranker was worse and costs GPU memory, so it is off."),
        "Tests: given a risky clause, does the search return the exact Indian law section that applies? "
        "Gold = the section a court actually applied, plus our planted injections (19 queries). R@5 = the right section is in the top 5; "
        "Act in top 3 = at least the right Act is in the top 3."))

    # ── GNN
    g = load("gnn.json") or {}
    rows = [[k, v.get("roc_auc"), v.get("avg_precision"), v.get("p_at_5")] for k, v in g.items() if isinstance(v, dict)]
    parts.append(section("6 · GNN ablation (risky-pair ranking)", table(["ranker", "ROC-AUC", "avg precision", "P@5"], rows, 1,
                                                                          f"GNN training time {g.get('train_seconds', '—')} s. No gain over the same features without the graph."),
        "Tests: does using the clause graph (who cites whom) help rank risky pairs above safe ones? ROC-AUC 0.5 = random, 1.0 = perfect. "
        "Same 172 held-out pairs for every ranker."))

    # ── teacher
    tv = load("teacher_validation.json") or {}
    rows = []
    for k, v in tv.items():
        if isinstance(v, dict):
            what, teacher = (k.split("|") + [""])[:2]
            val = v.get("binary_accuracy") or v.get("first_type_correct") or v.get("verified_rate") \
                or next((x for kk, x in v.items() if "kappa" in kk and isinstance(x, (int, float))), None)
            rows.append([what, teacher, val, v.get("pairs") or v.get("clauses") or v.get("flagged_pairs") or ""])
    parts.append(section("7 · Teacher validation (Gemini 4 / Claude vs independent truth)", table(["check", "teacher", "score", "n"], rows),
        "Tests: can we trust the big model that labelled our training pairs? Checklist = known answers; clause types = CUAD lawyer labels; "
        "citations = share of cited sections that really exist in India Code; agreement = Cohen's κ between the two teachers."))

    # ── training cost
    rows = []
    for name in ("classifier_clause20_inlegalbert.json", "classifier_clause20_inlegalbert_v1_clause20.json",
                 "retriever_clauses.json", "retriever_statutes.json", "kev_train_v1_imbalanced.json", "kev_train.json"):
        v = load(name)
        if v:
            rows.append([name.replace(".json", ""), v.get("model") or v.get("base"), v.get("train_records") or v.get("pairs") or "",
                         v.get("epochs", ""), round(v.get("train_seconds", 0) / 60, 1)])
    if g.get("train_seconds"):
        rows.append(["gnn", "GraphSAGE", "", "", round(g["train_seconds"] / 60, 1)])
    parts.append(section("8 · Training runs (RTX 4050 6 GB)", table(["run", "base model", "examples", "epochs", "minutes"], rows),
        "Not a test: the cost of every model we trained, all on the laptop GPU."))

    # ── Kev throughput
    kt = load("kev_throughput.json")
    if kt:
        rows = [[r["workers"], r["requests"], r["decisions_per_s"], r["input_tokens_per_s"], r["avg_input_tokens"],
                 r["latency_ms_p50"], r["latency_ms_p95"], r["wall_s"]] for r in kt["runs"]]
        parts.append(section("9 · Kev speed on the laptop GPU", table(
            ["parallel requests", "requests", "decisions / s", "input tokens / s", "tokens / request", "p50 ms", "p95 ms", "total s"], rows, 3,
            html.escape(kt.get("note", "")) + (f" · GPU memory in use: {kt.get('gpu_memory_mib')} MiB" if kt.get("gpu_memory_mib") else "")),
            "Kev reads clauses and points at one of the given answers, so speed is tokens read per second, not tokens generated."))

    # ── end to end
    runs = demo_runs()
    st_keys = ("ingest_s", "classify_s", "candidates_s", "judge_s", "kev_statutory_s")
    rows = [[r["title"][:60], r["clauses"], r["pairs"], r["findings"], r["judge"],
             *[r.get(k) for k in st_keys], r["seconds"]] for r in runs]
    parts.append(section("10 · End-to-end runs (whole pipeline, everything local)", table(
        ["contract", "clauses", "pairs judged", "findings", "judge", "ingest s", "classify s", "shortlist s", "Kev pairs s", "Kev law s", "total s"], rows),
        "Wall time per contract for ingest → extract → classify → shortlist → Kev judge → Kev law check → statute RAG → store. "
        "Scanned PDFs include OCR on first run (cached afterwards). Encoders run on CPU so the GPU stays free for Kev."))

    css = """
:root{--bg:#f8fafc;--fg:#0f172a;--mut:#64748b;--card:#fff;--line:#e2e8f0;--acc:#1d4ed8;--best:#dcfce7}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 Inter,system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:24px;margin:0 0 4px} h2{font-size:17px;margin:0 0 6px}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;margin:14px 0;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px} th,td{padding:6px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--mut);font-weight:600;font-size:12px} td.best{background:var(--best);font-weight:700}
.why,.note,.sub{color:var(--mut);font-size:12.5px} a{color:var(--acc)}
"""
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>LegalAgent Results</title><style>{css}</style></head><body><main>
<h1>LegalAgent — every comparison we measured</h1>
<p class="sub">Generated {time.strftime('%Y-%m-%d %H:%M')} by scripts/build_report.py from results/*.json. Green = best in column.
Everything ran locally on one RTX 4050 laptop (6 GB). <a href="/app">Dashboard</a> · <a href="/scores">Under the hood</a></p>
{''.join(parts)}
</main></body></html>"""
    (R / "REPORT.html").write_text(page, encoding="utf-8")
    print("wrote", R / "REPORT.html")


if __name__ == "__main__":
    main()
