# LegalAgent Handoff

Date: 2026-09-27
Branch: `aryan-sethi`

## Current Status

LegalAgent is a working Indian-law contract-analysis prototype. It can:

- Read TXT, DOCX, and PDF contracts.
- Convert PDFs to Markdown using PyMuPDF.
- OCR scanned PDF pages through Tesseract when native text is unavailable.
- Extract numbered clauses and cross-references.
- Classify clauses with a transparent keyword baseline.
- Retrieve related clauses using BM25, cross-references, a type matrix, and optional InLegal-SBERT embeddings.
- Detect a small set of deterministic risks (liability cap vs uncapped indemnity, Section 27 void non-compete, DPDPA penalty caps, Section 74 LD penalties).
- Store clause embeddings in SQLite.
- Stream 9 pipeline analysis stages in real time via Server-Sent Events (`/api/contracts/analyze/stream`).
- Display clauses, graph relationships, findings, pipeline stages, and embedding projections in the dashboard.
- Display a dedicated Contract Portfolio Drawer (`Contracts (6+)`) with health score rings.
- Present a dedicated Adversarial Injections Dossier at `/injections` explaining 15 synthetic clauses planted in the official Pune Metro PPP Concession (2019).
- Run a synthetic benchmark with planted irregularities (100% pass, 0 FP).

## Architecture Integration Complete

- `web/backend.py` upload analysis is unified with the shared core pipeline in `legalagent/core/pipeline.py`.
- Both synchronous analysis (`POST /api/contracts/analyze`) and real-time SSE streaming analysis (`POST /api/contracts/analyze/stream`) run through `core.pipeline` with heuristic fallback.
- Injected real-world Indian PPP contracts: Pune Metro Line III (PMRDA, 2019) and NHAI 4-Laning Model Concession.
- Gemini model discovery and structured JSON request helper are in `legalagent/core/gemini.py` (optional enrichment path). Current findings remain deterministic and verifiable.

## Run Environment

Always use the project interpreter:

```bash
/home/aryan/Projects/LegalAgent/LegalAgent/venv/bin/python
```

Do not use system Python.

## Core Commands

```bash
venv/bin/python -m pytest -q
venv/bin/python scripts/run_custom_benchmark.py
venv/bin/python scripts/pdf_to_markdown.py INPUT.pdf OUTPUT.md
venv/bin/python -m legalagent analyse INPUT.pdf --contract-id demo --output runs/demo.json
venv/bin/python scripts/check_gemini.py
venv/bin/python web/server.py
```

URLs:

- `http://localhost:8080/` landing page
- `http://localhost:8080/app` dashboard
- `http://localhost:8080/docs` FastAPI documentation

## Configuration

The real `.env` file is ignored by Git:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=auto
```

`.env.example` is safe to commit. Never print or commit the real key.

## File Responsibilities

### Core

- `legalagent/core/ingestion.py`: PyMuPDF extraction, OCR fallback, normalization.
- `legalagent/core/extraction.py`: numbered clauses, offsets, cross-reference resolution.
- `legalagent/core/types.py`: `Clause`, `Finding`, and `Run` dataclasses.
- `legalagent/core/classification.py`: keyword clause labels.
- `legalagent/core/candidate_selection.py`: BM25, dense, xref, and type-matrix candidate pairs.
- `legalagent/core/embeddings.py`: lazy cached InLegal-SBERT loading and cosine retrieval.
- `legalagent/core/analysis.py`: deterministic cross-clause and Section 27 checks plus evidence validation.
- `legalagent/core/gemini.py`: Gemini model discovery and structured JSON client.
- `legalagent/core/pipeline.py`: end-to-end CLI orchestration.

### Web and storage

- `web/server.py`: Uvicorn launcher.
- `web/backend.py`: FastAPI routes, environment loading, embedding API, and current web persistence.
- `web/index.html`: dashboard, clause graph, findings panel, pipeline graph, embedding graph.
- `web/landing.html`: landing page.
- `legalagent/db.py`: SQLite schema, seed data, contract queries, embedding persistence.
- `contracts.db`: local seeded prototype database.

### Data and verification

- `data/demo/india/custom_benchmark/`: synthetic contracts with planted issues and clean control.
- `data/demo/india/official/SOURCES.md`: official Indian PPP contract provenance.
- `scripts/run_custom_benchmark.py`: expected-versus-detected benchmark.
- `scripts/inject_contract_irregularities.py`: PDF adversarial injection workflow, if present.
- `scripts/inject_contract_irregularities_md.py`: Markdown-first adversarial injection workflow, if present.
- `scripts/pdf_to_markdown.py`: PDF-to-Markdown utility.
- `scripts/create_indian_demo_pdf.py`: creates the labelled synthetic Indian MSA PDF.
- `tests/test_pipeline.py`: focused automated tests.
- `ARCHITECTURE_FLOW.md`: detailed file and SBERT flow guide.
- `UPDATE.md`: project status, procedure record, and remaining work.

## Current Detection Benchmark

The custom benchmark contains:

1. Liability cap versus uncapped indemnity.
2. Post-termination non-compete under Section 27.
3. Termination/survival dependency.
4. Clean control contract.

Expected current result:

```text
3/3 contracts passed
0 false positives on the clean control
```

This is a prototype regression check, not a statistical accuracy claim.

## Indian Contract Data

CUAD is intentionally not used because it contains primarily US-law contracts.

The current official Indian inputs are Government of India PPP concession agreements listed in `data/demo/india/official/SOURCES.md`. Full PDFs are ignored because they are large; their Markdown extractions and source metadata are retained. Scanned documents require OCR and may contain extraction errors.

The Open India Law material currently stored in `data/raw/open-india-law-readme.md` is a source description, not the entire corpus. For the prototype, build a targeted legal index of relevant statutes and selected authoritative judgments rather than downloading every Indian legal document.

## Next Work

1. Route `POST /api/contracts/analyze` through `core.pipeline.analyse()`.
2. Add a targeted Indian statute/reference index with source URLs and version metadata.
3. Wire Gemini into shortlisted pair analysis with strict JSON and evidence validation.
4. Persist shared `Run`, `Finding`, evidence, and references from the core pipeline.
5. Add API integration tests for upload, analysis, persistence, and reload.
6. Improve OCR and unnumbered-clause extraction.
7. Evaluate BM25 versus dense versus hybrid retrieval on manually labelled Indian contracts.
8. Consider SBERT fine-tuning only after collecting labelled Indian clause pairs.

## Git Safety

Before committing:

```bash
git status --short
git diff --check
git diff --cached --name-only
```

Confirm `.env`, large PDFs, model caches, and generated temporary output are not staged.
