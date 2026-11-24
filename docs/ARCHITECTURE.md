# LegalAgent — architecture

LegalAgent reviews a contract the way a lawyer does: it reads clauses **against each other**.
The unit of analysis is a *clause pair*. Everything below runs on one laptop (RTX 4050, 6 GB);
no contract text leaves the machine unless the user presses an explicit cloud button.

```
 contract file
   │
   ▼
 1 INGEST         legalagent/core/ingestion.py
   PDF native pages → pymupdf4llm (layout-aware Markdown)        ┐ cached by file hash
   PDF scanned pages → Tesseract OCR, parallel over CPU cores    ┘ data/cache/ingest/
   DOCX (paragraphs + tables) · images (OCR) · TXT / MD
   normalise(): page breaks → strip running headers/footers, page numbers, hyphenation
   │
   ▼
 2 EXTRACT        legalagent/core/extraction.py
   numbered clauses (1. / 5.2 / 12.3.1), table-of-contents runs skipped,
   document parts (ARTICLE / SCHEDULE / PART / ANNEX), parent hierarchy (5.2.1 → 5.2),
   cross-references ("subject to Clause 10.3.1") resolved to clause ids
   │
   ▼
 3 CLASSIFY       legalagent/core/classification.py
   CLAUSE-22 multi-label: fine-tuned InLegalBERT (default) | MiniLM+LogReg | keywords
   + keyword backstop for safety-critical types (indemnity, liability cap, restraint)
   + 7 rule-based Indian types (force majeure, liquidated damages, DPDP data protection,
     stamp duty, performance security, change in law, step-in rights)
   │
   ▼
 4 SHORTLIST PAIRS legalagent/core/candidate_selection.py, retrieval.py, gnn.py
   always: cross-reference pairs + type-matrix pairs (40 weighted clash pairs, clause20/labels.yaml)
   fill:   BM25 | dense (MiniLM / InLegal-SBERT) | hybrid (reciprocal-rank fusion)
   option: GraphSAGE link prediction over the clause graph
   cap 30 pairs (or exhaustive) — a 600-clause concession has ~180,000 possible pairs
   │
   ▼
 5 JUDGE PAIRS    legalagent/core/pipeline.py → local_judge.py | analysis.py | gemini_analysis.py
   local (default): Kev-0.8B decision model, fine-tuned, served on 127.0.0.1:8008
       one forward pass per pair → P(relation), P(severity), choice of statute section
   rules: deterministic patterns (fallback, always available)
   gemini: cloud, only if explicitly selected
   chain: gemini → local → rules  (a missing model degrades, never crashes)
   │
   ▼
 6 INDIAN LAW     analysis.py, statutes.py
   statutory rules: ICA s.27 restraint, s.74 penalty damages, Stamp Act s.35, DPDP consent
   grounding: every finding gets India Code sections by hybrid retrieval over 3,142 sections
   (33 Acts); any model-written citation is verified against real section text
   │
   ▼
 7 OUTPUT         web/live.py → SQLite → dashboard (web/index.html)
   findings ranked by severity, clause graph, evidence offsets validated,
   "Expand with Gemini" (opt-in) for a plain-English explanation + suggested redline
```

## Why each design choice

| Choice | Reason |
|---|---|
| Clause *pairs*, shortlisted | Single-clause tools cannot see a cap undone by an indemnity. Exhaustive pairing is quadratic; three cheap signals (xrefs, type clashes, retrieval) keep the expensive judge to ~30 pairs. |
| Local Kev judge | Privacy (contracts are confidential; DPDP Act 2023), cost (no per-call fees), speed (one forward pass, no text generation), robustness (no outage dependency — Gemini returned 503s during development). |
| Gemini as teacher, not runtime | A large model labels *public* contracts once (distillation); the small model inherits the skill and runs privately. |
| Statute library, not model memory | LLMs cite plausible-but-wrong sections; here a citation either resolves to real India Code text or is shown as unverified. |
| Pluggable stages | Every stage reads/writes the same `Clause` / `Finding` dataclasses (`core/types.py`), so each method is swappable and separately measurable. |

## Code map

| Path | Role |
|---|---|
| `legalagent/core/` | pipeline stages (above) + `evaluation.py` (P/R@k), `gemini.py` (REST client) |
| `legalagent/__main__.py` | CLI: `analyse`, `eval` |
| `web/backend.py`, `web/live.py`, `web/index.html` | FastAPI app, live SSE analysis + upload, dashboard |
| `clause20/` | CLAUSE-22 dataset build (`build.py`), taxonomy (`labels.yaml`, `label_map.yaml`), baseline trainer |
| `train/` | fine-tuning: classifier, retriever, Kev, GNN; GPU queue scripts |
| `scripts/` | data fetch, teacher labelling (agy), validation, evaluation, demo seeding, gold review |
| `research/` | taxonomy research, teacher prompts/labels, gold set |
| `results/` | every reported number (JSON) + `REPORT_TABLES.md` |
| `data/statutes/` | India Code section library (committed) |
