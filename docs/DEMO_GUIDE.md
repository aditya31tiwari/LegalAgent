# Demo guide (viva)

## Before the viva (5 min)
```bash
cd ~/Projects/LegalAgent/LegalAgent
nvidia-smi                       # GPU visible
bash scripts/start_demo.sh       # Kev judge on :8008 + dashboard on :8080
```
Open `http://localhost:8080/app` (or the LAN address the script prints). In the upload dialog,
the status line must read *Kev judge: running · GPU: NVIDIA GeForce RTX 4050*.

If the demo DB is empty or stale: `venv/bin/python scripts/seed_demo.py` (real pipeline runs).

## Script (8–10 min)

1. **The problem (30 s).** Open *Pune Metro — 15 planted irregularities*. "A single-clause
   tool sees 91.1 as a normal liability cap. Read with 91.2, it is undone by an indemnity
   that applies *notwithstanding Clause 91.1*."
2. **Live upload (2 min).** *Run Live Analysis* → drag in
   `data/demo/india/adversarial/pune_metro_adversarial_15_changes.pdf` (305 scanned pages).
   Judge: *Local Kev model*. Narrate the stages as they stream:
   - Ingestion: "300 pages OCR'd with Tesseract in parallel — cached, so seconds now."
   - Extraction: "~570 clauses, Articles and Schedules recognised, cross-references resolved."
   - Classification: "fine-tuned InLegalBERT, 22 clause types + 7 Indian rule types."
   - Shortlisting: "≈160,000 possible pairs → 30–60 examined; xrefs + clash matrix + hybrid retrieval."
   - Judge: "Kev, a 0.8B decision model running on this laptop's GPU — no text left the machine."
   - Statutes: "every finding linked to real India Code sections."
3. **Findings (2 min).** Open a high-severity cap-vs-indemnity finding → both clauses, ICA s.124
   with India Code link. Open the s.27 non-compete and the s.74 75%-penalty finding.
4. **Graph (1 min).** Clause graph: red = conflict, blue = dependency/xref.
5. **Cloud assist, opt-in (1 min).** *Expand with Gemini* → confirm prompt → explanation +
   redline, citations restricted to the locally retrieved sections (✓ verified).
   If offline: "the local finding stands on its own; cloud is optional."
6. **Results (2 min).** `results/REPORT_TABLES.md`: classifier, retrieval, judge
   (rules vs Kev base vs Kev fine-tuned vs Gemini teacher), checklist, Pune Metro recall, teacher validation.

## Fallbacks
| Problem | Do |
|---|---|
| Kev down | judge selector → *Deterministic rules*; or `bash scripts/start_demo.sh` again |
| GPU missing | everything still runs on CPU (slower classification); judge falls back to rules |
| Upload slow | use a cached document (any of the three PDFs above) or paste a sample (buttons in dialog) |
| No internet | only *Expand with Gemini* is affected |
