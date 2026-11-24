# LegalAgent Repository Map

This document explains where the project files live and what each area is responsible for.

## Start Here

Read these files first:

1. `README.md` - product purpose and high-level pipeline.
2. `CONTEXT.md` - current project context and known gaps.
3. `HANDOFF.md` - setup, commands, current status, and next work.
4. `UPDATE.md` - implementation history and prototype decisions.
5. `tests/old_examples/docs/INDEX.md` - older detailed research, viva, and architecture material.

## Top-Level Files

| Path | Purpose |
| --- | --- |
| `README.md` | Product overview, pipeline concept, retrieval strategy, and scope. |
| `CONTEXT.md` | Current architecture, responsibilities, data flow, and known issues. |
| `HANDOFF.md` | Operational handoff for another developer or session. |
| `UPDATE.md` | What has been built, how it was tested, and what remains. |
| `pyproject.toml` | Python package metadata, dependencies, and CLI entry point. |
| `requirements.txt` | Installable Python dependency list. |
| `contracts.db` | SQLite database containing seeded dashboard contracts and stored embeddings. |
| `.env.example` | Safe Gemini configuration template. |
| `.env` | Local Gemini key and configuration. Ignored by Git; never commit it. |
| `.gitignore` | Excludes secrets, virtual environments, PDFs, caches, and generated outputs. |

## Core Engine: `legalagent/`

### `legalagent/__main__.py`

CLI entry point.

```bash
venv/bin/python -m legalagent analyse INPUT_FILE --output runs/result.json
```

It calls the core pipeline and serializes the result.

### `legalagent/core/`

This is the main analysis engine.

| File | Responsibility |
| --- | --- |
| `types.py` | Defines `Clause`, `Finding`, and `Run` dataclasses shared between pipeline stages. |
| `ingestion.py` | Loads TXT, DOCX, and PDF; uses PyMuPDF and Tesseract OCR; normalizes text. |
| `extraction.py` | Finds numbered clauses, character offsets, headings, and cross-references. |
| `classification.py` | Adds keyword labels such as indemnity, liability, termination, survival, and confidentiality. |
| `candidate_selection.py` | Selects related clause pairs using xrefs, type matrix, BM25, and optional dense retrieval. |
| `embeddings.py` | Lazily loads InLegal-SBERT, creates normalized vectors, and computes cosine similarity. |
| `analysis.py` | Detects current deterministic risks and validates evidence references. |
| `gemini.py` | Discovers available Gemini models and sends structured JSON requests. |
| `gemini_analysis.py` | Gemini analysis adapter/work-in-progress; review before using in the main pipeline. |
| `pipeline.py` | Orchestrates ingestion, extraction, classification, candidate selection, analysis, validation, and run statistics. |
| `__init__.py` | Core package exports. |

### `legalagent/db.py`

SQLite storage layer.

It creates and queries:

- `contracts`
- `clauses`
- `graph_edges`
- `findings`
- `clause_embeddings`

It also seeds the dashboard’s demonstration contracts.

## Web Application: `web/`

### Server and API

| File | Responsibility |
| --- | --- |
| `server.py` | Starts Uvicorn on port 8080. |
| `backend.py` | FastAPI routes, SQLite access, custom analysis endpoint, embedding endpoint, and export endpoint. |

Start the application:

```bash
venv/bin/python web/server.py
```

Open:

- `http://localhost:8080/` - landing page
- `http://localhost:8080/app` - dashboard
- `http://localhost:8080/docs` - FastAPI documentation

### Pages

| File | Responsibility |
| --- | --- |
| `landing.html` | Product introduction and entry point. |
| `index.html` | Main three-panel dashboard: clauses, graph, findings, pipeline view, and embedding visualization. |
| `findings_review.html` | Findings-review interface. |
| `injections.html` | Adversarial injection/demo interface. |

The browser communicates with `backend.py`; it does not load Python models directly.

## Data: `data/`

### `data/demo/`

Demo contracts and extracted examples.

- `data/demo/india/`: Indian-law demo material.
- `data/demo/india/custom_benchmark/`: synthetic contracts with planted irregularities and a clean control.
- `data/demo/india/official/`: government-hosted Indian PPP agreement material and provenance.
- `data/demo/samples/`: readable Markdown demo samples, including the Pune Metro adversarial sample.

### `data/raw/`

- `open-india-law-readme.md`: metadata and source description for the Open India Law corpus.

The full legal corpus is not stored locally. The prototype should use a targeted statute/judgment subset rather than downloading everything.

### PDF policy

Large PDFs are ignored by Git. Markdown extractions and source metadata are kept where useful.

## Scripts: `scripts/`

| File | Purpose |
| --- | --- |
| `run_custom_benchmark.py` | Runs the planted-irregularity benchmark and compares expected/detected categories. |
| `pdf_to_markdown.py` | Converts a PDF to Markdown using PyMuPDF and OCR fallback. |
| `create_indian_demo_pdf.py` | Generates the labelled synthetic Indian MSA PDF. |
| `inject_contract_irregularities.py` | Injects adversarial clauses into a PDF copy. |
| `inject_contract_irregularities_md.py` | Injects adversarial clauses into a Markdown/text copy. |
| `download_models.py` | Loads and verifies candidate embedding/legal models. |
| `check_gemini.py` | Lists Gemini models available to the local API key and selects one. |
| `setup_openssh_lan.sh` | Installs/enables OpenSSH server and allows private-LAN access; requires sudo. |

## Tests: `tests/`

### `tests/test_pipeline.py`

Core regression tests for:

- Clause extraction.
- Candidate generation.
- No self-pairs.
- Finding clause IDs.
- Evidence validity.
- Section 27 non-compete detection.

### `tests/old_examples/docs/`

Older project documentation and research examples. Important files include:

- `INDEX.md` - index and recommended reading order.
- `ALGORITHMS_AND_MATHEMATICAL_FOUNDATIONS.md` - BM25, SBERT, cosine similarity, candidate pruning, and Gemini design.
- `CODEBASE_EXPLANATION.md` - detailed file-by-file explanation.
- `DEMO_GUIDE.md` - presentation walkthrough.
- `PANEL_DEFENSE_AND_FUTURE_ROADMAP.md` - viva questions and future work.
- `DATABASE_SCHEMA.md` - database documentation.
- `HANDOFF.md` and `CONTEXT.md` - historical project notes.

Treat this directory as historical/reference documentation and compare it with the current source before relying on claims about implementation.

## Documentation: `docs/`

| File | Purpose |
| --- | --- |
| `API.md` | Planned/current API contract. |
| `DATA_MODEL.md` | Data model and persistence design. |
| `V0_PLAN.md` | Original staged implementation plan. |
| `CUAD.md` | CUAD analysis; CUAD is not used as the Indian-law demo corpus. |
| `OPENSSH_LAN.md` | Linux LAN SSH setup and Windows passwordless-login instructions. |

## Research: `research/`

Contains Indian legal research, model selection, graph-risk design, benchmarking, competitive analysis, fine-tuning plans, and the project roadmap.

Use this for rationale and future research, not as the source of truth for current runtime behavior. The current code and `UPDATE.md` take priority.

## Generated and Local-Only Areas

These are normally not uploaded:

- `venv/` - Python virtual environment.
- `.env` - local secret configuration.
- `graphify-out/` - generated code knowledge graph.
- `runs/` - generated analysis reports.
- `.pytest_cache/` and `__pycache__/` - Python/test caches.
- Large `.pdf` and `.docx` files.
- Model caches.

## Common Commands

```bash
# Activate/use the project environment
source venv/bin/activate

# Run tests
venv/bin/python -m pytest -q

# Run benchmark
venv/bin/python scripts/run_custom_benchmark.py

# Analyze a contract
venv/bin/python -m legalagent analyse data/demo/samples/03_indian_tech_services_msa.md --output runs/demo.json

# Convert a PDF to Markdown
venv/bin/python scripts/pdf_to_markdown.py input.pdf output.md

# Check Gemini
venv/bin/python scripts/check_gemini.py

# Start dashboard
venv/bin/python web/server.py
```

## Recommended Review Path

```text
README.md
  -> CONTEXT.md
  -> legalagent/core/types.py
  -> legalagent/core/pipeline.py
  -> legalagent/core/ingestion.py
  -> legalagent/core/extraction.py
  -> legalagent/core/classification.py
  -> legalagent/core/candidate_selection.py
  -> legalagent/core/embeddings.py
  -> legalagent/core/analysis.py
  -> legalagent/core/gemini.py
  -> legalagent/db.py
  -> web/backend.py
  -> web/index.html
  -> tests/test_pipeline.py
  -> scripts/run_custom_benchmark.py
```
