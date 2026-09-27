# LegalAgent Prototype Update

Date: 2026-09-20
Branch: `aryan-sethi`

## Current Objective

Build a working Indian contract review prototype that reads a contract, compares clauses against one another, checks selected Indian-law rules, and presents evidence-backed findings in the web dashboard.

This is an assistive research prototype. It is not legal advice and does not replace review by a qualified lawyer.

## What We Built

### Core pipeline

The pipeline now runs:

```text
PDF/DOCX/TXT
  -> canonical text normalization
  -> clause extraction with offsets and cross-references
  -> keyword clause classification
  -> BM25, cross-reference, type-matrix, and optional dense retrieval
  -> cross-clause analysis
  -> deterministic Indian-law checks
  -> validated Finding objects
  -> JSON/SQLite/web presentation
```

Implemented components:

- PyMuPDF PDF extraction with Markdown conversion.
- Tesseract OCR fallback for scanned PDFs when native PDF text is unavailable.
- Clause extraction with unique IDs for repeated section numbers.
- InLegal-SBERT local embeddings using `bhavyagiri/InLegal-Sbert`.
- SQLite persistence for clause embeddings, including model name, dimension, and vector data.
- Embedding-space visualization and pipeline-step graph in the dashboard.
- Evidence validation: every finding must reference an existing clause and non-empty source text.
- Order-independent termination/survival dependency detection.
- Gemini model discovery using the configured API key.
- Automatic Flash-model selection when `GEMINI_MODEL` is missing or unavailable.
- Gemini structured JSON generation helper in `legalagent/core/gemini.py`.

### Web application

The dashboard now includes:

- Three-panel clause, graph, and findings workspace.
- Pipeline explainer modal showing all seven analysis stages.
- Clause embedding graph projected to two dimensions.
- SQLite-backed embedding endpoint:
  `GET /api/contracts/{contract_id}/embeddings`.
- Existing contract graph, findings, full-contract viewer, custom analysis, and audit export.

### Indian contract inputs

CUAD was removed because it contains US-law contracts and is not appropriate as an Indian-law demo corpus.

The current official Indian contract sources are hosted by the Government of India's PPP India portal:

- Model Concession Agreement for four-laning of National Highways.
- Signed Pune Metro concession agreement.

Source records and URLs are documented in `data/demo/india/official/SOURCES.md`.

Because these documents are scanned or partially scanned, PyMuPDF plus Tesseract OCR is used. A 20-page Pune Metro sample produced:

```text
182 clauses extracted
45 candidate pairs
45 no-issue pairs
```

### Custom irregularity benchmark

Synthetic Indian-law contracts were created for controlled testing:

- Liability cap versus uncapped indemnity.
- Post-termination non-compete under Section 27.
- Termination/survival dependency.
- Clean control contract with no planted risk.

The benchmark runner is:

```bash
venv/bin/python scripts/run_custom_benchmark.py
```

Current result:

```text
3/3 benchmark contracts passed
0 false positives on the clean control
```

Report: `runs/indian/custom_benchmark.json`.

## Specific Procedures Used

1. Keep the normalized contract text canonical. Evidence offsets always refer to this text.
2. Extract clause numbers and cross-references before classification.
3. Use xrefs and the type matrix as high-priority candidates.
4. Use BM25 for lexical retrieval and InLegal-SBERT for semantic retrieval.
5. Cap the candidate shortlist so the analysis remains practical for a demo.
6. Apply deterministic high-confidence rules for known Indian-law risks.
7. Validate all clause IDs and evidence spans before returning findings.
8. Store embeddings lazily in SQLite rather than loading every model at startup.
9. Use Gemini only after retrieval, with JSON output requested and model availability checked first.
10. Keep synthetic benchmark expectations separate from analysis output to measure detection honestly.
11. Attribute government contract documents and keep their source URLs in a manifest.
12. Keep `.env` ignored; only `.env.example` is committed.

## Gemini Configuration

Put the key in the ignored `.env` file:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=auto
```

Check available models:

```bash
venv/bin/python scripts/check_gemini.py
```

The current key was verified successfully. `gemini-3-flash-preview` was selected automatically and returned valid JSON.

## Indian-Law Data Strategy

We should **not** download every Indian law document for the prototype.

The full Open India Law corpus is very large and contains judgments, legislation, and other legal material. Downloading and indexing everything would increase storage, processing time, retrieval noise, and legal-version management complexity without improving the midterm demonstration proportionally.

Use a targeted legal reference index instead:

1. Indian Contract Act, 1872: Sections 27, 73, 74, 124, and 125.
2. Digital Personal Data Protection Act, 2023: relevant consent, processing, and penalty provisions.
3. Arbitration and Conciliation Act, 1996 and Mediation Act, 2023: provisions relevant to dispute clauses.
4. BNS/IPC transition mappings only when the contract contains criminal-law references.
5. A small set of authoritative Supreme Court judgments for each rule, with citation, date, court, and source URL.
6. Later, add KanoonGPT or Open India Law judgment chunks filtered by statute, court, date, and legal topic.

The retrieval index should store source metadata and version/date information. It should not treat every judgment as a rule, and it should never present an unverified retrieved passage as conclusive legal advice.

## What Is Left

### Required for the midterm prototype

- Connect the web custom-upload endpoint to the shared core pipeline instead of its duplicated heuristic path.
- Add the targeted Indian statutory corpus and retrieval endpoint.
- Add the Gemini pair-analysis adapter using the existing `Finding` schema.
- Persist live pipeline clauses, findings, references, and run statistics consistently in SQLite.
- Render evidence excerpts and legal references from the shared pipeline in the dashboard.
- Add API integration tests for upload, analysis, persistence, and reload.
- Add a presentation script and latency/findings summary for the Pune Metro and custom benchmark demos.

### Later research work

- Full legal corpus ingestion with filters and versioned indexes.
- BM25 versus dense versus hybrid retrieval evaluation on manually labelled Indian contracts.
- Annotation of Indian commercial contract clause pairs.
- InLegal-SBERT fine-tuning or LoRA adapters.
- BNS/IPC temporal conflict detection.
- Larger Indian commercial contract collection with explicit licensing.
- Authentication, asynchronous jobs, multi-user storage, and production deployment.

## Verification Commands

```bash
venv/bin/python -m pytest -q
venv/bin/python scripts/run_custom_benchmark.py
venv/bin/python scripts/check_gemini.py
venv/bin/python scripts/pdf_to_markdown.py INPUT.pdf OUTPUT.md
venv/bin/python web/server.py
```

The latest core and benchmark validation result is:

```text
3 passed
3/3 custom benchmark contracts passed
```
