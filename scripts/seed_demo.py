"""
Rebuild the demo database from REAL pipeline runs (replaces the hand-written showcase
findings that legalagent/db.py:seed_database used to insert).

    venv/bin/python scripts/seed_demo.py                 # judge=local (Kev) with fallback to rules
    venv/bin/python scripts/seed_demo.py --judge rules

Every contract on the dashboard is then exactly what `python -m legalagent analyse` produces;
the judge actually used is recorded in each contract's description.
"""
import argparse
import json
import os
import sys

# Kev owns the GPU during seeding; the small encoders run on CPU (see legalagent/core/device.py).
os.environ.setdefault("LEGALAGENT_DEVICE", "cpu")
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

GEN = ROOT / "data" / "demo" / "generated"


def make_casebook() -> Path:
    """18 real clauses from Supreme Court of India judgments, one ARTICLE per case (court outcome in the heading)."""
    cases = [json.loads(l) for l in (ROOT / "research/litigated_clauses/cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    lines = ["SUPREME COURT CASEBOOK — real contract clauses quoted in judgments (court outcome = ground truth)", ""]
    for n, c in enumerate(cases, 1):
        lines += [f"ARTICLE {n} {c['case_name']} ({c['year']}) — court held: {c['outcome'].upper()}", ""]
        lines += [f"{n}.1 {c['clause_a']['text'].strip()}", ""]
        if c.get("clause_b") and c["clause_b"].get("text"):
            lines += [f"{n}.2 {c['clause_b']['text'].strip()} (read with Clause {n}.1)", ""]
    GEN.mkdir(parents=True, exist_ok=True)
    p = GEN / "supreme_court_casebook.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def make_cuad_example() -> Path | None:
    """One real CUAD contract where lawyers annotated both a liability cap and an uncapped-liability carve-out."""
    import csv
    pairs = [json.loads(l) for l in (ROOT / "research/teacher_labels/cuad_interaction_pairs.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    pick = next((p for p in pairs if p["case"].startswith("Cap On Liability x Uncapped")), None)
    if not pick:
        return None
    doc_id = pick["contract"].split(":", 1)[1]
    csv.field_size_limit(10**9)
    rows = [r for r in csv.DictReader(open(ROOT / "clause20/data/interim/cuad.csv", encoding="utf-8")) if r["doc_id"] == doc_id]
    if not rows:
        return None
    lines = []
    for r in rows:
        num = r["uid"].split("::")[-1]
        txt = r["text"].strip()
        lines += [txt if txt.startswith(num) else f"{num} {txt}", ""]
    GEN.mkdir(parents=True, exist_ok=True)
    p = GEN / "cuad_cap_vs_uncapped.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def make_clean_pune() -> Path:
    """The adversarial excerpt carries an italic answer-key note after each planted clause
    ("*(Statutory Conflict: …)*"). Strip them so the system sees only the contract text."""
    import re
    src = (ROOT / "data/demo/samples/02_pune_metro_adversarial_15_injections.md").read_text(encoding="utf-8")
    clean = re.sub(r"\s*\*\([^*]{0,600}?\)\.?\*", "", src)
    GEN.mkdir(parents=True, exist_ok=True)
    p = GEN / "pune_metro_15_planted_clean.md"
    p.write_text(clean, encoding="utf-8")
    return p


DOCS = [
    ("Pune Metro Line-3 Concession — 15 planted irregularities (excerpt)", "Indian Infrastructure (PPP) · Adversarial test",
     "data/demo/generated/pune_metro_15_planted_clean.md"),
    ("Indian Tech Services MSA", "Indian Commercial · IT Services", "data/demo/samples/03_indian_tech_services_msa.md"),
    ("Executive Employment Agreement", "Indian Employment", "data/demo/samples/04_executive_employment_agreement.md"),
    ("Commercial Vendor Supply Agreement", "Indian Commercial · Supply", "data/demo/samples/05_commercial_vendor_supply_agreement.md"),
    ("NHAI Highway Concession (excerpt)", "Indian Infrastructure (PPP)", "data/demo/samples/06_nhai_highway_concession_agreement.md"),
    ("Pune Metro Line-3 Concession (baseline excerpt)", "Indian Infrastructure (PPP)", "data/demo/samples/01_pune_metro_concession_baseline.md"),
    ("Pune Metro Line-3 Concession — full scanned PDF + 15 planted irregularities (305 pp, OCR)", "Indian Infrastructure (PPP) · Adversarial test",
     "data/demo/india/adversarial/pune_metro_adversarial_15_changes.pdf"),
    ("NHAI Model Concession Agreement — full scanned PDF (276 pp, OCR)", "Indian Infrastructure (PPP)",
     "data/demo/india/official/model_concession_4_laning.pdf"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default="local", choices=["local", "rules", "gemini"])
    ap.add_argument("--max-candidates", type=int, default=60)
    ap.add_argument("--skip-pdfs", action="store_true")
    ap.add_argument("--only", default="", help="comma list of ids (e.g. demo_01) to re-run without wiping the others")
    args = ap.parse_args()
    only = {x for x in args.only.split(",") if x}

    from legalagent.db import get_db_connection, init_db
    from legalagent.core.pipeline import analyse
    from live import persist

    make_clean_pune()
    casebook = make_casebook()
    DOCS.insert(1, ("Supreme Court casebook — 18 real clauses from judgments (court outcome in each heading)",
                    "Real cases · Supreme Court of India", str(casebook.relative_to(ROOT))))
    cuad = make_cuad_example()
    if cuad:
        DOCS.insert(2, ("Real US contract (CUAD, SEC filing) — lawyer-annotated liability cap vs uncapped carve-out",
                        "Real contract · CUAD", str(cuad.relative_to(ROOT))))

    init_db()
    conn = get_db_connection()
    for table in ("findings", "graph_edges", "clauses", "clause_embeddings", "contracts", "finding_details"):
        try:
            if only:
                col = "id" if table == "contracts" else "contract_id"
                conn.executemany(f"DELETE FROM {table} WHERE {col}=?;", [(x,) for x in only])
            else:
                conn.execute(f"DELETE FROM {table};")
        except Exception:
            pass
    conn.commit()
    conn.close()

    for i, (title, category, rel) in enumerate(DOCS, 1):
        if args.skip_pdfs and rel.endswith(".pdf"):
            continue
        if only and f"demo_{i:02d}" not in only:
            continue
        path = ROOT / rel
        if not path.exists():
            print("missing", rel)
            continue
        t0 = time.time()
        cid = f"demo_{i:02d}"
        config = {"judge": args.judge, "retrieval_method": "hybrid", "top_k": 5, "max_candidates": args.max_candidates, "classifier": "auto"}
        from legalagent.core.ingestion import ingest
        t_in = time.time()
        text = ingest(str(path))
        ingest_s = round(time.time() - t_in, 2)
        from legalagent.core.pipeline import analyse_text
        run, clauses, findings = analyse_text(text, config, contract_id=cid)
        persist(cid, title, "India", category, clauses, findings, run)
        # per-contract timings for results/REPORT.html (scripts/build_report.py)
        rp = ROOT / "results" / "demo_runs.json"
        try:
            runs = [r for r in json.loads(rp.read_text()) if r["id"] != cid]
        except Exception:
            runs = []
        runs.append({"id": cid, "title": title, "clauses": len(clauses), "pairs": run.stats["pairs"], "findings": len(findings),
                     "judge": run.stats["judge"], "seconds": round(time.time() - t0, 1), "ingest_s": ingest_s,
                     **{k: v for k, v in run.stats.items() if k.endswith("_s")}})
        rp.write_text(json.dumps(sorted(runs, key=lambda r: r["id"]), indent=2))
        print(f"{cid}  {len(clauses):4d} clauses  {run.stats['pairs']:4d} pairs  {len(findings):3d} findings  "
              f"judge={run.stats['judge']}  {time.time() - t0:5.1f}s  {title}", flush=True)


if __name__ == "__main__":
    main()
