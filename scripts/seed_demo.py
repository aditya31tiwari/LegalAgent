"""
Rebuild the demo database from REAL pipeline runs (replaces the hand-written showcase
findings that legalagent/db.py:seed_database used to insert).

    venv/bin/python scripts/seed_demo.py                 # judge=local (Kev) with fallback to rules
    venv/bin/python scripts/seed_demo.py --judge rules

Every contract on the dashboard is then exactly what `python -m legalagent analyse` produces;
the judge actually used is recorded in each contract's description.
"""
import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

DOCS = [
    ("Pune Metro Line-3 Concession — 15 planted irregularities (excerpt)", "Indian Infrastructure (PPP) · Adversarial test",
     "data/demo/samples/02_pune_metro_adversarial_15_injections.md"),
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
    args = ap.parse_args()

    from legalagent.db import get_db_connection, init_db
    from legalagent.core.pipeline import analyse
    from live import persist

    init_db()
    conn = get_db_connection()
    for table in ("findings", "graph_edges", "clauses", "clause_embeddings", "contracts"):
        try:
            conn.execute(f"DELETE FROM {table};")
        except Exception:
            pass
    conn.commit()
    conn.close()

    for i, (title, category, rel) in enumerate(DOCS, 1):
        if args.skip_pdfs and rel.endswith(".pdf"):
            continue
        path = ROOT / rel
        if not path.exists():
            print("missing", rel)
            continue
        t0 = time.time()
        cid = f"demo_{i:02d}"
        config = {"judge": args.judge, "retrieval_method": "hybrid", "top_k": 5, "max_candidates": args.max_candidates, "classifier": "auto"}
        run, clauses, findings = analyse(str(path), config, contract_id=cid)
        persist(cid, title, "India", category, clauses, findings, run)
        print(f"{cid}  {len(clauses):4d} clauses  {run.stats['pairs']:4d} pairs  {len(findings):3d} findings  "
              f"judge={run.stats['judge']}  {time.time() - t0:5.1f}s  {title}", flush=True)


if __name__ == "__main__":
    main()
