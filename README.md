# LegalAgent

**Local-first cross-clause risk detection for Indian contracts** · B.Tech major project, JIIT

LegalAgent reads a contract (including scanned PDFs), finds the clauses that create risk **together** (a liability
cap undone by an uncapped indemnity, a non-compete that survives termination) and the clauses that **Indian law**
makes void or risky (e.g. ICA s.27, s.74, A&C Act s.12), and attaches the actual India Code text. Everything runs on
one laptop GPU (RTX 4050, 6 GB); no contract text leaves the machine.

## Pipeline

```
PDF / DOCX / TXT
  → ingest      pymupdf4llm (digital pages) · Tesseract OCR, parallel + cached (scanned pages)
  → extract     numbered clauses, ARTICLE/SCHEDULE parts, parent links, resolved cross-references
  → classify    fine-tuned InLegalBERT over CLAUSE-22 (22 types) + 7 rule-based Indian labels
  → shortlist   cross-references + 40-pair clause-type clash matrix + hybrid BM25/dense retrieval (RRF)
  → judge       Kev-0.8B decision model, served locally: relation · severity · statute choice
  → law check   Kev single-clause check over 7 Indian-law risk categories + regex rules
  → ground      RAG over 4,408 India Code sections (BM25 + fine-tuned InLegal-SBERT + Act prior), citations verified
  → store/show  SQLite → FastAPI (live progress) → dashboard
```

## Results (all measured; details in `/report` or `results/REPORT.html`)

| What | Result |
|---|---|
| Clause classification (CLAUSE-22) | InLegalBERT micro-F1 **0.931** test, **0.750** out-of-domain (MiniLM baseline 0.828 / 0.590) |
| Pair judge, 28 bad/fixed checklist twins | Kev **71 %** · rules 46 % |
| Pair judge, 280 lawyer-annotated CUAD interactions (recall) | Kev **75 %** · rules 7.5 % |
| Clause vs law, clauses struck down by the Supreme Court | Kev **6 / 9** · regex 0 / 9 (Kev also flags upheld clauses → confidence labels) |
| Statute retrieval, exact section in top 5 | **0.32** (BM25 0.11); right Act in top 3: 0.53 |
| Teacher (Gemini 4) vs independent truth | 92.9 % checklist · 85.7 % real citations · κ 0.57 with Claude |
| Speed (RTX 4050) | Kev ~11 decisions/s, ~3,500 input tokens/s, 1.8 GB; 305-page scan end to end in 4.4 min |
| GNN (GraphSAGE) ablation | ROC-AUC 0.742 vs 0.748 without the graph: no gain, off by default |

## Run it

```bash
bash scripts/start_demo.sh            # Kev judge on :8008 (GPU) + web app on :8080 (+ Workbench window)
# http://localhost:8080/app      dashboard: upload & analyse, findings, clause graph
# http://localhost:8080/scores   under the hood: every score behind every finding
# http://localhost:8080/report   every comparison with timings
venv/bin/python scripts/show_steps.py data/demo/generated/supreme_court_casebook.md   # pipeline stage by stage
venv/bin/python -m pytest -q tests clause20
```

## Documentation

Start at **[docs/final_viva_docs/README.md](docs/final_viva_docs/README.md)**:
process and failed attempts, design decisions, every concept explained, the final report text, the demo script.

## Repository map

| Path | Contents |
|---|---|
| `legalagent/core/` | ingestion, extraction, classification, retrieval, candidate selection, Kev judge, Indian-law check, statute RAG, GNN, pipeline |
| `web/` | FastAPI server, dashboard (`index.html`), under-the-hood page (`scores.html`) |
| `train/` | classifier, retriever, Kev (LoRA) and GNN training |
| `scripts/` | evaluation (`eval_all.py`), judge selection, demo seeding, step viewer, report builder, benchmarks |
| `clause20/` | CLAUSE-22 dataset build and label definitions (`labels.yaml`) |
| `research/` | taxonomy research, teacher labels and validation, Supreme Court litigated clauses |
| `results/` | every measured number (JSON) + `REPORT.html` |

## Scope

LegalAgent is an assistive tool that surfaces clauses worth a closer look. It does not replace a lawyer's review.
Main limitation: training labels for clause pairs come from an LLM teacher (validated, but not lawyer-verified),
and the judge favours recall over precision.
