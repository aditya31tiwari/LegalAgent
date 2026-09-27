# LegalAgent — Project Map

> Every file in the project, what it does, and where to find more detail.
> Use this as the index when asking another model about any specific file.

---

## Directory Tree

```
LegalAgent/
├── DEMO_GUIDE.md                   ← Panelist demo walkthrough (read this first)
├── CONTEXT.md                      ← Architecture overview and design rationale
├── HANDOFF.md                      ← Developer/agent session handoff state
├── ARCHITECTURE_FLOW.md            ← Detailed SBERT + pipeline data-flow diagram
├── UPDATE.md                       ← Chronological session log of what was built
├── README.md                       ← Project introduction
├── pyproject.toml                  ← Python package metadata and entry points
├── requirements.txt                ← Pip dependencies
├── .env                            ← GEMINI_API_KEY (gitignored, never commit)
├── .env.example                    ← Safe template for .env
├── contracts.db                    ← SQLite database (gitignored)
│
├── legalagent/                     ← Core Python package
│   ├── __init__.py
│   ├── __main__.py                 ← CLI entry point (`python -m legalagent`)
│   ├── db.py                       ← SQLite schema, seeding, and query layer
│   └── core/
│       ├── types.py                ← Dataclasses: Clause, Finding, Run
│       ├── ingestion.py            ← Load TXT/DOCX/PDF; normalize text
│       ├── extraction.py           ← Regex clause extraction with offsets
│       ├── classification.py       ← Keyword clause labelling
│       ├── candidate_selection.py  ← BM25 + dense + xref + type-matrix pair selection
│       ├── embeddings.py           ← InLegal-SBERT loader, cosine retrieval
│       ├── analysis.py             ← Deterministic cross-clause and statutory checks
│       ├── gemini.py               ← Gemini API client (model discovery + JSON output)
│       └── pipeline.py             ← End-to-end orchestration (ingest → findings)
│
├── web/
│   ├── server.py                   ← Uvicorn launcher (port 8080)
│   ├── backend.py                  ← FastAPI REST API (all endpoints)
│   ├── index.html                  ← Main 3-panel dashboard (single-page app)
│   └── landing.html                ← Marketing/intro landing page
│
├── data/
│   ├── demo/india/
│   │   ├── indian_tech_msa_demo.pdf        ← Synthetic Indian MSA used in CLI demo
│   │   ├── indian_tech_msa_demo.md         ← Markdown extraction of above
│   │   ├── official/
│   │   │   ├── SOURCES.md                  ← Provenance of real PPP contracts
│   │   │   ├── pune_metro_signed_concession.pdf   ← Real Pune Metro concession (2019)
│   │   │   ├── pune_metro_signed_concession.md    ← OCR extraction of above
│   │   │   ├── model_concession_4_laning.pdf      ← NHAI 4-laning model concession
│   │   │   ├── model_concession_4_laning.md       ← OCR extraction of above
│   │   │   └── samples/
│   │   │       ├── pune_metro_first_20_pages.pdf  ← 20-page OCR test sample
│   │   │       └── pune_metro_first_20_pages.md   ← Markdown of above
│   │   ├── custom_benchmark/
│   │   │   ├── MANIFEST.json               ← Test contract list with expected findings
│   │   │   ├── README.md                   ← Benchmark description
│   │   │   ├── 01_msa_cap_indemnity.txt    ← Planted: liability cap + indemnity conflict
│   │   │   ├── 02_employment_non_compete.txt ← Planted: Section 27 void non-compete
│   │   │   └── 03_clean_services_control.txt ← Clean: should produce 0 findings
│   │   └── adversarial/
│   │       ├── INJECTIONS.json             ← 15 adversarial clauses and their expected detection
│   │       ├── source_pune_metro_signed_concession.pdf ← Original source for adversarial PDF
│   │       └── pune_metro_adversarial_15_changes.pdf   ← PDF with injected bad clauses
│   └── raw/
│       └── open-india-law-readme.md        ← Description of 32.5M judgment dataset for future fine-tuning
│
├── scripts/
│   ├── run_custom_benchmark.py     ← Regression test: runs 3 contracts, checks expected vs detected
│   ├── pdf_to_markdown.py          ← Convert any PDF to Markdown using PyMuPDF
│   ├── create_indian_demo_pdf.py   ← Creates the labelled synthetic Indian MSA PDF
│   ├── inject_contract_irregularities.py    ← PDF adversarial injection tool
│   ├── inject_contract_irregularities_md.py ← Markdown adversarial injection tool
│   ├── download_models.py          ← Download/verify InLegal-SBERT and BGE models
│   └── check_gemini.py             ← Verify Gemini API key and model availability
│
├── tests/
│   └── test_pipeline.py            ← pytest unit tests for the core pipeline stages
│
├── runs/                           ← JSON output files from CLI analysis runs
│   ├── demo/                       ← Live demo output directory
│   └── indian/
│       ├── custom_benchmark.json   ← Most recent benchmark run results
│       ├── model_concession_4_laning.json ← CLI run on NHAI contract
│       └── pune_metro_sample.json  ← CLI run on Pune Metro sample
│
├── research/
│   ├── INDIAN_LAW_RESEARCH.md      ← Master research agenda on Indian law
│   ├── 01_LEGAL_STATUTORY_RESEARCH.md     ← ICA, BNS, DPDPA, Mediation Act deep dive
│   ├── 02_MODEL_SELECTION_AND_BENCHMARKING.md ← Model comparison and evaluation
│   ├── 03_CROSS_CLAUSE_GRAPH_AND_RISK_DETECTION.md ← Graph topology and detection design
│   ├── 04_ASSESSMENT_PROTOTYPE_SPEC.md    ← Panel demo specification
│   ├── 05_EXISTING_PROJECTS_AND_COMPETITIVE_ANALYSIS.md ← Competitor landscape
│   ├── 06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md ← LoRA fine-tuning roadmap
│   └── NEXT_STEPS.md               ← Near-term roadmap
│
└── docs/
    ├── API.md                      ← REST API reference
    ├── DATA_MODEL.md               ← SQLite schema documentation
    ├── CUAD.md                     ← Notes on CUAD dataset (not used — US law)
    └── V0_PLAN.md                  ← Original v0 design document
```

---

## File Details

### Root Documents

| File | Purpose |
|:-----|:--------|
| `DEMO_GUIDE.md` | Step-by-step panelist demo script with talking points, Q&A answers, fallback fixes |
| `CONTEXT.md` | System architecture, component roles, Indian statutes encoded |
| `HANDOFF.md` | Current git/branch state, how to run, immediate next steps |
| `ARCHITECTURE_FLOW.md` | Detailed data-flow diagram with SBERT embedding paths |
| `UPDATE.md` | Chronological session log of everything built |
| `README.md` | Project overview |

---

### `legalagent/` — Core Package

#### `legalagent/db.py`
SQLite database layer. Owns:
- Schema creation (`contracts`, `clauses`, `graph_edges`, `findings`, `clause_embeddings` tables)
- `seed_database()` — populates 6 seeded contracts:
  - `tech_msa` — Indian IT SaaS MSA (liability cap conflict + DPDPA)
  - `employment_nda` — Executive NDA (Section 27 void non-compete)
  - `vendor_supply` — Vendor supply agreement (Section 74 penalty)
  - `pune_metro_ppp` — Real Pune Metro PPP concession + adversarial clauses
  - `highway_concession` — Real NHAI BOT highway concession
  - `lorem_ipsum_demo` — Synthetic Latin instrument for UI testing
- `fetch_contract_graph_json()` — returns full graph JSON for a contract ID
- `fetch_all_contracts_summary()` — returns contract list with stats
- `store_clause_embeddings()` / `fetch_clause_embeddings()` — embedding persistence

#### `legalagent/core/types.py`
Three dataclasses that are the internal contracts between all pipeline stages:
- `Clause` — id, contract_id, number, heading, text, char offsets, labels, xrefs
- `Finding` — id, relation_type (conflict/dependency/overlap), severity, risk_score, rationale, evidence, surfaced_by
- `Run` — id, contract_id, config, stats

#### `legalagent/core/ingestion.py`
Loads files and produces normalised text:
- TXT, DOCX via `python-docx`, PDF via `fitz` (PyMuPDF)
- If native PDF text is too short (< 100 chars/page), falls back to Tesseract OCR page-by-page
- `normalize()` strips multiple blank lines, control characters, and returns canonical string

#### `legalagent/core/extraction.py`
Regex-based clause extraction:
- Detects decimal-numbered clauses: `1.`, `1.1`, `1.1.1`, `(a)`, `(i)` etc.
- Returns `Clause` objects with `char_start` / `char_end` offsets into normalised text
- Detects cross-references (`Section 8.2`, `Clause 14.1`) and resolves them to clause IDs
- Handles repeated section numbers by generating disambiguated stable IDs

#### `legalagent/core/classification.py`
Keyword-based clause labelling:
- Labels: `indemnification`, `liability_limitation`, `termination`, `survival`, `confidentiality`, `assignment`, `warranty`, `governing_law`, `non_compete`, `data_protection`, `dispute_resolution`, `payment`
- Returns `labels` list on each `Clause` as `[{"label": "...", "confidence": 0.9}]`

#### `legalagent/core/candidate_selection.py`
Builds the shortlist of clause pairs to analyse (avoids O(n²) brute force):
- **TYPE_MATRIX** — known risky label combinations: `{liability_limitation, indemnification}`, `{termination, survival}`, etc.
- **Cross-references** — if clause A mentions clause B, always pair them
- **BM25** — lexical similarity using `rank_bm25`
- **Dense retrieval** — optional InLegal-SBERT cosine similarity (adds pairs with score > 0.6)
- Cap: 30 pairs maximum

#### `legalagent/core/embeddings.py`
InLegal-SBERT embedding utilities:
- `load_model()` — lazy-loads `bhavyagiri/InLegal-Sbert` with `@lru_cache`; 768-dimensional vectors
- `embed_texts()` — returns L2-normalised float32 numpy arrays
- `related_pairs()` — dot-product cosine similarity on normalised vectors

#### `legalagent/core/analysis.py`
Deterministic finding generators (no LLM involved):
- `analyse_pair(clause_a, clause_b, surfaced_by)` — detects liability cap vs indemnity conflict; returns `Finding` or `None`
- `analyse_statutory(clauses, jurisdiction)` — detects Section 27 ICA non-compete; detects termination/survival dependency
- `validate_findings(findings, clauses)` — removes findings referencing non-existent clauses or empty evidence

#### `legalagent/core/gemini.py`
Gemini API client (available but not yet wired into main pipeline):
- Loads `.env` for `GEMINI_API_KEY`
- `list_models()` — discovers available generation models via REST
- `select_model()` — picks configured model or falls back to Flash
- `generate_json()` — sends prompt with JSON schema constraint, returns parsed dict
- Will be used for pair-level reasoning once schema and evidence validation are finalised

#### `legalagent/core/pipeline.py`
End-to-end orchestration:
```
ingest → extract → classify → select_candidates → analyse_pair (per pair) → analyse_statutory → validate_findings → Run
```
- Used by CLI (`python -m legalagent analyse FILE`) and now also by `POST /api/contracts/analyze`
- Returns `(Run, list[Clause], list[Finding])`

#### `legalagent/__main__.py`
CLI entry point. Usage:
```bash
venv/bin/python -m legalagent analyse INPUT.pdf --contract-id ID --output runs/out.json
```

---

### `web/` — Web Application

#### `web/server.py`
Uvicorn launcher. Runs `web.backend:app` on port 8080. Start with:
```bash
venv/bin/python web/server.py
```

#### `web/backend.py`
FastAPI REST API (328 lines). All endpoints:

| Endpoint | Method | Description |
|:---------|:-------|:------------|
| `/` | GET | Serves `landing.html` |
| `/app` | GET | Serves `index.html` |
| `/docs` | GET | Auto-generated Swagger UI |
| `/api/contracts` | GET | All contracts + stats (clause count, health score) |
| `/api/contracts/{id}` | GET | Full graph JSON for one contract |
| `/api/contracts/analyze` | POST | Analyse custom text via `core.pipeline` (with heuristic fallback) |
| `/api/contracts/{id}/embeddings` | GET | 2D PCA projection of InLegal-SBERT clause embeddings |
| `/api/export/{id}` | GET | Legal Risk Memorandum as Markdown |

#### `web/index.html`
Single-page 3-panel dashboard (~660 lines, vanilla HTML/CSS/JS + Vis.js):
- **Left panel**: Clause Explorer — expandable clause cards, search, "View Full" button
- **Centre panel**: Vis.js knowledge graph — nodes = clauses, typed edges = relationships. Physics: `gravitationalConstant: -8000`, `springLength: 250`, `avoidOverlap: 0.6`
- **Right panel**: Findings Dossier — per-finding cards with source clause, statutory citation, remedy
- **Edge click → finding highlight**: clicking a graph edge auto-scrolls and highlights the matching finding card with copper ring
- **Modals**: Upload/Analyze, Export Audit, Full Contract Viewer
- **Design**: Navy `#1a2332`, Ivory `#f5f3ef`, Copper `#9a7b4f`. No neon, no glow.

#### `web/landing.html`
Professional landing page introducing the product:
- Hero section with CTA to `/app`
- Feature grid (6 cards)
- 4-step pipeline explanation
- Indian Statutes section
- Tech stack pills
- Scroll-reveal animations

---

### `scripts/`

| Script | Purpose | Example command |
|:-------|:--------|:----------------|
| `run_custom_benchmark.py` | Regression test — runs 3 planted contracts and checks expected vs detected findings | `venv/bin/python scripts/run_custom_benchmark.py` |
| `pdf_to_markdown.py` | Convert any PDF to clean Markdown | `venv/bin/python scripts/pdf_to_markdown.py INPUT.pdf OUTPUT.md` |
| `create_indian_demo_pdf.py` | Generate the synthetic Indian MSA PDF with labelled clauses | `venv/bin/python scripts/create_indian_demo_pdf.py` |
| `inject_contract_irregularities.py` | Append adversarial clauses to a PDF for robustness testing | See script comments |
| `inject_contract_irregularities_md.py` | Markdown-first adversarial injection workflow | See script comments |
| `download_models.py` | Pull InLegal-SBERT and BGE models from HuggingFace | `venv/bin/python scripts/download_models.py` |
| `check_gemini.py` | Verify Gemini API key, list available models, run minimal request | `venv/bin/python scripts/check_gemini.py` |

---

### `tests/`

| File | Purpose |
|:-----|:--------|
| `tests/test_pipeline.py` | pytest unit tests covering ingestion, extraction, classification, candidate selection, and cross-clause analysis. Run: `venv/bin/python -m pytest -q` — currently 3 passed |

---

### `data/`

| Path | Contents |
|:-----|:---------|
| `data/demo/india/indian_tech_msa_demo.pdf` | Synthetic Indian IT MSA PDF used in CLI demos |
| `data/demo/india/official/pune_metro_signed_concession.pdf` | Real Pune Metro Line III concession (PMRDA, 2019) — source: PPP India portal |
| `data/demo/india/official/model_concession_4_laning.pdf` | Real NHAI 4-laning model BOT concession — source: Ministry of Road Transport |
| `data/demo/india/official/SOURCES.md` | Provenance and download metadata for both official PDFs |
| `data/demo/india/adversarial/INJECTIONS.json` | 15 adversarial clauses with expected detection flags |
| `data/demo/india/adversarial/pune_metro_adversarial_15_changes.pdf` | Pune Metro PDF with all 15 adversarial clauses appended |
| `data/demo/india/custom_benchmark/*.txt` | 3 synthetic contracts for regression benchmark |
| `data/raw/open-india-law-readme.md` | Description of the 32.5M judgment corpus for future fine-tuning |

---

### `research/`

| File | What it covers |
|:-----|:---------------|
| `INDIAN_LAW_RESEARCH.md` | Master research agenda |
| `01_LEGAL_STATUTORY_RESEARCH.md` | ICA 1872 (Sections 27, 73, 74, 124/125), BNS 2023, DPDPA 2023, Mediation Act 2023 |
| `02_MODEL_SELECTION_AND_BENCHMARKING.md` | InLegal-SBERT vs BGE vs InLegalBERT comparison |
| `03_CROSS_CLAUSE_GRAPH_AND_RISK_DETECTION.md` | Graph topology design and detection algorithm |
| `04_ASSESSMENT_PROTOTYPE_SPEC.md` | Panel demo functional specification |
| `05_EXISTING_PROJECTS_AND_COMPETITIVE_ANALYSIS.md` | Harvey AI, Spellbook, Robin AI, Indian competitors |
| `06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md` | LoRA/QLoRA fine-tuning on 32.5M Indian judgment corpus; temporal era models for BNS→IPC anachronism detection; 4-week training plan |
| `NEXT_STEPS.md` | Near-term prioritised task list |

---

### `docs/`

| File | What it covers |
|:-----|:---------------|
| `API.md` | REST API endpoint reference |
| `DATA_MODEL.md` | SQLite table schemas (`contracts`, `clauses`, `graph_edges`, `findings`, `clause_embeddings`) |
| `CUAD.md` | Notes on CUAD dataset — intentionally excluded because it contains US-law contracts |
| `V0_PLAN.md` | Original v0 planning document |

---

## SQLite Database Schema Summary

```
contracts        (id, title, category, jurisdiction, description, created_at)
clauses          (id, contract_id, clause_num, title, tag, text, ordinal)
graph_edges      (id, contract_id, source_clause_id, target_clause_id,
                  label, relation_type, severity, color, width, dashes)
findings         (id, contract_id, title, severity, relation_type,
                  source_clause_ref, target_clause_ref, description,
                  statute_citation, remedy_suggestion)
clause_embeddings (clause_id, contract_id, model_name, dimension, vector_json, created_at)
```

Edge `relation_type` values: `conflict` (red), `statutory` (purple), `xref` (blue), `semantic` (green).
Finding `severity` values: `high`, `statutory`, `medium`, `low`.

---

## Key Commands Reference

```bash
# Start server
venv/bin/python web/server.py

# Run tests
venv/bin/python -m pytest -q

# Run regression benchmark
venv/bin/python scripts/run_custom_benchmark.py

# Analyse a PDF from CLI
venv/bin/python -m legalagent analyse FILE.pdf --contract-id ID --output runs/out.json

# Convert PDF to Markdown
venv/bin/python scripts/pdf_to_markdown.py INPUT.pdf OUTPUT.md

# Re-seed database (resets all contracts to defaults)
venv/bin/python -c "from legalagent.db import init_db, seed_database; init_db(); seed_database()"

# Check Gemini API
venv/bin/python scripts/check_gemini.py
```
