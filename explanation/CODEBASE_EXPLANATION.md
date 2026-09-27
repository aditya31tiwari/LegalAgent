# LegalAgent: Comprehensive Codebase & Feature Guide

> **Exhaustive In-Depth and General Explanations for Every File, Module, Algorithm, and Feature in the LegalAgent Platform.**

---

## Table of Contents

1. [High-Level Architectural Paradigm](#1-high-level-architectural-paradigm)
2. [Core Engine Package (`legalagent/core/`)](#2-core-engine-package-legalagentcore)
   - [types.py](#legalagentcoretypespy)
   - [ingestion.py](#legalagentcoreingestionpy)
   - [extraction.py](#legalagentcoreextractionpy)
   - [classification.py](#legalagentcoreclassificationpy)
   - [candidate_selection.py](#legalagentcorecandidate_selectionpy)
   - [embeddings.py](#legalagentcoreembeddingspy)
   - [analysis.py](#legalagentcoreanalysispy)
   - [gemini.py](#legalagentcoregeminipy)
   - [pipeline.py](#legalagentcorepipelinepy)
3. [CLI & Persistence Layer (`legalagent/`)](#3-cli--persistence-layer-legalagent)
   - [__main__.py](#legalagent__main__py)
   - [db.py](#legalagentdbpy)
4. [Web Application Layer (`web/`)](#4-web-application-layer-web)
   - [server.py](#webserverpy)
   - [backend.py](#webbackendpy)
   - [index.html](#webindexhtml)
   - [landing.html](#weblandinghtml)
5. [Scripts & Tooling Suite (`scripts/`)](#5-scripts--tooling-suite-scripts)
   - [run_custom_benchmark.py](#scriptsrun_custom_benchmarkpy)
   - [pdf_to_markdown.py](#scriptspdf_to_markdownpy)
   - [create_indian_demo_pdf.py](#scriptscreate_indian_demo_pdfpy)
   - [inject_contract_irregularities.py & _md.py](#scriptsinject_contract_irregularitiespy--inject_contract_irregularities_mdpy)
   - [download_models.py](#scriptsdownload_modelspy)
   - [check_gemini.py](#scriptscheck_geminipy)
6. [Data Assets, Official PPP Contracts & Benchmarks (`data/`)](#6-data-assets-official-ppp-contracts--benchmarks-data)
7. [Research Foundation & Indian Statutory Framework (`research/`)](#7-research-foundation--indian-statutory-framework-research)
8. [Automated Test Suite (`tests/`)](#8-automated-test-suite-tests)

---

## 1. High-Level Architectural Paradigm

### Why Traditional LegalTech Fails on Complex Contracts
Mainstream commercial contract review tools (such as Spellbook, Robin AI, and Kira Systems) evaluate agreements **linearly, clause-by-clause**. They classify Clause $N$ as a *"Limitation of Liability"*, check if its threshold meets standard playbook rules, and move forward.

This single-pass paradigm is fundamentally blind to two critical classes of legal vulnerabilities:
1. **Cross-Clause Contradictions:** A clause capping liability at ₹15 Lakhs is quietly nullified four pages later by an uncapped indemnity clause lacking an exclusion carveout. Neither clause is invalid in isolation; the risk emerges exclusively from their **interplay**.
2. **Indian Statutory Invalidity:** In US common law, restrictive covenants undergo a "reasonableness" balancing test. Under Indian law (**Section 27 of the Indian Contract Act, 1872**), post-termination non-compete covenants are **void *ab initio*** (*Percept D'Mark v. Zaheer Khan (2006)*). Similarly, under the **Digital Personal Data Protection Act (DPDPA), 2023**, statutory penalties reach up to **₹250 Crore** and cannot be waived or capped contractually.

### LegalAgent's Solution: Attributed Knowledge Graph $G = (V, E)$
LegalAgent converts the contract into an attributed knowledge graph:
* **Vertices ($V$):** Clauses ($v_i \in V$), each tagged with section numbers, titles, character span offsets into canonical normalized text, multi-label categories, and dense semantic embeddings.
* **Edges ($E$):** Explicit cross-clause relationship types:
  - `conflict` (Red): Substantive legal contradictions (e.g., Liability Cap vs. Uncapped Indemnity).
  - `statutory` (Purple): Direct violations of Indian statutory law (e.g., Section 27 ICA, DPDPA 2023).
  - `xref` (Blue): Explicit textual cross-references (*"Notwithstanding Section 8.1..."*).
  - `semantic` (Green): Uncited clauses with high dense embedding cosine similarity ($\ge 0.60$).

```
                      Raw Contract (PDF / DOCX / TXT)
                                     │
                                     ▼
                ┌─────────────────────────────────────────┐
                │ 1. INGESTION (ingestion.py)             │
                │    - PyMuPDF OCR & heading detection    │
                │    - 4-step canonical normalization     │
                └────────────────────┬────────────────────┘
                                     │ canonical normalized_text
                                     ▼
                ┌─────────────────────────────────────────┐
                │ 2. EXTRACTION (extraction.py)           │
                │    - Decimal numbering regex            │
                │    - Document tiling (char offsets)     │
                │    - Two-pass xref extraction & resolve │
                └────────────────────┬────────────────────┘
                                     │ list[Clause]
                                     ▼
                ┌─────────────────────────────────────────┐
                │ 3. CLASSIFICATION (classification.py)   │
                │    - 12-category keyword taxonomy       │
                │    - In-place clause labeling           │
                └────────────────────┬────────────────────┘
                                     │ labeled Clause objects
                                     ▼
                ┌─────────────────────────────────────────┐
                │ 4. CANDIDATE SELECTION                  │
                │    (candidate_selection.py)             │
                │    - Priority: xrefs & Type Matrix      │
                │    - Lexical BM25 (rank_bm25)           │
                │    - Optional Dense (embeddings.py)     │
                │    - Budget cap (MAX_CANDIDATES = 30)   │
                └────────────────────┬────────────────────┘
                                     │ candidate pairs (clause_a, clause_b)
                                     ▼
                ┌─────────────────────────────────────────┐
                │ 5. ANALYSIS ENGINE (analysis.py)        │
                │    - Pairwise rules (Cap vs Indemnity,  │
                │      Termination vs Survival)           │
                │    - Statutory Indian law (Sec 27 ICA)  │
                │    - Evidence span validation           │
                └────────────────────┬────────────────────┘
                                     │ tuple[Run, list[Clause], list[Finding]]
                                     ▼
              ┌─────────────────────────────────────────────┐
              │ 6. CONSUMERS & STORAGE                      │
              │    - pipeline.py (Orchestrator)             │
              │    - __main__.py (CLI & JSON serializer)    │
              │    - db.py (SQLite Graph & Vectors)         │
              │    - web/backend.py & web/index.html        │
              └─────────────────────────────────────────────┘
```

---

## 2. Core Engine Package (`legalagent/core/`)

### `legalagent/core/types.py`
* **General Overview:** The domain model and type schema. Uses standard library `@dataclass` without third-party ORMs, establishing strict contracts between pipeline stages and persistence layers.
* **In-Depth Technical Breakdown:**
  - `Clause`:
    - `id: str`: Unique identifier formatted as `"{contract_id}::{number}"` (e.g., `"tech_msa::8.1"`). Duplicate numbers receive a collision suffix `"::{occurrence}"`.
    - `contract_id: str`: Foreign document namespace.
    - `parent_id: str | None`: Reserved for hierarchical clauses (e.g., subclauses `(a)`, `(i)`).
    - `number: str | None`: Extracted decimal numbering string (`"8.1"`, `"12.1.3"`).
    - `heading: str | None`: Section title if present and $\le 80$ characters.
    - `text: str`: Verbatim textual content from `normalized_text`.
    - `char_start: int`, `char_end: int`: Character slice offsets into `normalized_text`, providing document tiling without gaps.
    - `ordinal: int`: 0-indexed document sequence order.
    - `labels: list[dict]`: Array of classification objects, e.g. `[{"label": "limitation_of_liability", "confidence": 1.0, "source": "keyword"}]`.
    - `xrefs: list[dict]`: Extracted cross-references, e.g. `[{"raw": "Section 8.2", "clause_id": "contract::8.2", "resolved": True}]`.
  - `Finding`:
    - `id: str`: Hex identifier formatted as `f"finding_{uuid.uuid4().hex[:8]}"`.
    - `target_clause_id: str`: Primary clause exhibiting the risk or conflict.
    - `related_clause_ids: list[str]`: Correlated clauses in conflict or dependency.
    - `relation_type: str`: Categorical relation: `"conflict"`, `"dependency"`, `"overlap"`, `"ambiguity"`, `"statutory_violation"`, `"no_issue"`.
    - `severity: str`: Risk classification level: `"high"`, `"medium"`, `"low"`, `"statutory"`.
    - `risk_score: float`: Calibrated float score between `0.0` and `1.0`.
    - `rationale: str`: Legal explanation of the issue.
    - `surfaced_by: list[str]`: Discovery provenance: `["bm25"]`, `["type_matrix"]`, `["xref"]`, `["dense"]`, or `["statutory_rule"]`.
    - `evidence: list[dict]`: Character span pointers into the clause text: `[{"clause_id": str, "start": int, "end": int}]`.
    - `refs: list[dict]`: Legal/statutory grounding sources (e.g., Indian Contract Act sections and statutory snippets).
    - `scores: dict`: Subsystem confidence and retrieval scores (e.g., `{"retrieval": 0.62, "analysis_confidence": 0.82}`).
  - `Run`:
    - Metadata and runtime audit telemetry: `id`, `contract_id`, `config` dict, and `stats` (`clauses`, `pairs`, `findings`, `no_issue`).

---

### `legalagent/core/ingestion.py`
* **General Overview:** Document loader and text standardizer. Converts raw TXT, DOCX, or PDF files into canonical `normalized_text`. Every character offset produced in later stages indexes into this exact string.
* **In-Depth Technical Breakdown:**
  - `pdf_to_markdown(file_path: str, use_ocr: bool = True) -> str`: Uses `pymupdf` (Fitz). Reads layout blocks (`page.get_text("dict")`).
    - **OCR Fallback Heuristic:** If native text on a page is $< 80$ characters (indicating a scanned or image-based PDF, common with Indian government concessions), it triggers `page.get_textpage_ocr(language="eng", dpi=150, full=True)` via Tesseract OCR.
    - Heading Detection: Inspects font spans (`is_bold` or `size >= 14` and length $\le 100$) to format lines as Markdown headings (`## `).
    - Separates pages with the form-feed sentinel `PAGE_BREAK = "\f"`.
  - `ingest(file_path: str) -> str`: Inspects file extension (`.pdf`, `.docx`, `.txt`) and delegates to PyMuPDF, `python-docx`, or UTF-8 decoding (with `errors="replace"`), then passes raw text to `normalize()`.
  - `normalize(text: str) -> str`: Applies a fixed 4-step canonical transformation:
    1. *Header/Footer Elimination:* Computes line frequencies across pages (`\f`). Stripped lines (length $5 < \text{len} < 100$) appearing on $> 80\%$ of pages are stripped as recurring headers/footers.
    2. *Standalone Page Numbers:* Regex drops standalone page counters: `r'^\s*\[?\s*\d+\s*\]?\s*$'`.
    3. *Hyphenated Line Breaks:* Rebinds broken words: `re.sub(r'([a-z])-\n\s*([a-z])', r'\1\2', text, flags=re.I)`.
    4. *Whitespace Collapse:* Normalizes inline whitespace runs to single spaces while strictly preserving double newlines (`\n\n`) as paragraph boundaries.

---

### `legalagent/core/extraction.py`
* **General Overview:** Deterministic clause boundary parser. Segments canonical text into numbered legal provisions and resolves internal cross-references.
* **In-Depth Technical Breakdown:**
  - **Regex Engine:**
    - `CLAUSE_RE = re.compile(r'^\s*(\d+(?:\.\d+)*)\.?\s+', re.M)`: Matches decimal-style numbering (`1.`, `1.1`, `8.2.1`) whether standalone or inline.
    - `XREF_RE = re.compile(r'(?:Section|Clause|Article|clause|§)\s+(\d+(?:\.\d+)*)', re.I)`: Extracts citations to other sections.
  - **Span Tiling:** Clause spans start at the clause number match and extend to the start of the next match (`char_end = matches[i + 1].start()`), ensuring contiguous, gapless coverage across the document.
  - **Collision Handling:** If duplicate clause numbers appear, an occurrence counter appends a suffix (e.g., `contract::8.1::2`), maintaining unique IDs.
  - **Two-Pass Cross-Reference Resolution:**
    - Pass 1 builds a directory of all `clause_ids` and records the first occurrence of each section number in `first_clause_by_number`.
    - Pass 2 iterates through `xrefs` on each clause. If `ref_id` exists in the document, it flags `resolved = True`; otherwise, it falls back to matching by section number.

---

### `legalagent/core/classification.py`
* **General Overview:** Multi-label keyword classification engine. Applies legal taxonomy labels to extracted clauses to guide candidate retrieval.
* **In-Depth Technical Breakdown:**
  - Uses an explicit `KEYWORDS` mapping covering 12 standard legal categories:
    - `indemnification`: `["indemnif", "hold harmless", "defend"]`
    - `limitation_of_liability`: `["limitation of liability", "in no event shall", "aggregate liability", "consequential damages"]`
    - `termination`: `["terminate", "termination", "following termination", "post-termination"]`
    - `confidentiality`, `governing_law`, `assignment`, `survival`, `exclusivity`, `warranty`, `force_majeure`, `payment`, `intellectual_property`.
  - Scans lowercased clause text; upon keyword match, appends a label dictionary `{"label": label_name, "confidence": 1.0, "source": "keyword"}`.
  - Multi-label architecture allows a single clause to carry both `limitation_of_liability` and `indemnification` tags.

---

### `legalagent/core/candidate_selection.py`
* **General Overview:** Complexity-reduction filter. For a contract with $N$ clauses, brute-force pair analysis requires $O(N^2)$ checks ($\approx 1,800$ pairs for $N=60$). This module filters and prioritizes clause pairs down to a cap of $\le 30$ candidates.
* **In-Depth Technical Breakdown:**
  - **4-Tier Retrieval Pipeline:**
    1. *Tier 1 — Explicit Cross-References (Xref):* Any clause explicitly citing another (e.g., *"notwithstanding Section 8.2"*) is added to `priority_pairs`.
    2. *Tier 2 — Risky Type Matrix (`TYPE_MATRIX`):* Known dangerous label combinations are matched automatically:
       - `("limitation_of_liability", "indemnification")`: weight `0.9`
       - `("termination", "survival")`: weight `0.6`
       - `("warranty", "limitation_of_liability")`: weight `0.7`
       - `("assignment", "confidentiality")`: weight `0.5`
       - `("exclusivity", "assignment")`: weight `0.6`
    3. *Tier 3 — BM25 Lexical Retrieval:* Uses `rank_bm25.BM25Okapi`. Tokenizes clause texts and computes BM25 relevance scores between all clause pairs, selecting top-$k$ related clauses.
    4. *Tier 4 — Dense Semantic Retrieval:* When `retrieval_method` is set to `"dense"` or `"hybrid"`, queries `embeddings.py` to retrieve nearest neighbors using InLegal-SBERT embeddings.
  - **Priority Cap Logic:** `MAX_CANDIDATES = 30`. Tier 1 (xrefs) and Tier 2 (`TYPE_MATRIX`) are **never dropped**. BM25 and dense pairs fill whatever candidate slots remain (`remaining_slots = max(0, MAX_CANDIDATES - len(priority_pairs))`).

---

### `legalagent/core/embeddings.py`
* **General Overview:** Local embedding pipeline using Indian legal NLP models. Provides domain-adapted vector representations without external cloud APIs.
* **In-Depth Technical Breakdown:**
  - **Model:** Default is `bhavyagiri/InLegal-Sbert` (110M parameter transformer trained on Indian Supreme Court and High Court judgments; outputs 768-dimensional vectors).
  - `load_model(model_name)`: Decorated with `@lru_cache(maxsize=2)`. Imports `sentence_transformers.SentenceTransformer` lazily so importing LegalAgent does not incur model loading overhead.
  - `embed_texts(texts, model_name)`: Calls `model.encode(texts, normalize_embeddings=True)`. Returns normalized float32 NumPy arrays of shape $(N, 768)$.
  - `related_pairs(clauses, top_k=5, model_name)`: Encodes all clause texts with L2 normalization. Computes the full pairwise similarity matrix via dot product:
    $$\text{Scores} = \mathbf{V} \cdot \mathbf{V}^T$$
    Since $\mathbf{V}$ is L2-normalized, this directly equals cosine similarity. Extracts top-$k$ nearest neighbors per clause (excluding self-comparisons).

---

### `legalagent/core/analysis.py`
* **General Overview:** Deterministic risk detection engine and evidence validator. Evaluates clause pairs and individual provisions against Indian statutory mandates.
* **In-Depth Technical Breakdown:**
  - `analyse_pair(clause_a, clause_b, surfaced_by)`:
    - **Liability Cap vs. Indemnity Conflict:** Checks if one clause is `limitation_of_liability` and the other is `indemnification`. Inspects indemnity text for uncapped formulations (*"all losses"*, *"every claim"*, *"without limitation"*). Checks liability clause to verify if indemnification is carved out. If uncapped indemnity is not carved out, flags as **High Severity Conflict** (`risk_score = 0.90`).
    - **Termination & Survival Dependency:** Checks if `termination` references `survival`.
  - `analyse_statutory(clauses, jurisdiction="India")`:
    - **Section 27 Indian Contract Act (ICA) Violation:** Identifies post-termination non-compete clauses. Uses regex targeting `r"post[- ]termination|following termination|after termination"` combined with `r"non[- ]compete|competing business|restraint of trade|shall not\s+compete"`. Emits a **High Severity Statutory Violation** (`risk_score = 0.94`) citing Section 27 and case law (*Percept D'Mark v. Zaheer Khan*).
  - `validate_findings(findings, clauses)`: Structural anti-hallucination safeguard. Validates that every `target_clause_id` and `related_clause_id` exists in `clauses`. Ensures all character spans in `evidence` resolve to non-empty text strings in the normalized document.

---

### `legalagent/core/gemini.py`
* **General Overview:** Standalone, dependency-free Google Gemini API client built using Python standard library `urllib`. Designed to provide generative explanations for shortlisted clause pairs.
* **In-Depth Technical Breakdown:**
  - Operates directly against `https://generativelanguage.googleapis.com/v1beta` without third-party dependencies.
  - Loads `GEMINI_API_KEY` from `.env`.
  - `list_models()`: Queries available models supporting `generateContent`.
  - `choose_model()`: Prioritizes models in order: `gemini-3-flash-preview`, `gemini-3.5-flash`, `gemini-2.5-flash`, `gemini-flash-latest`, `gemini-2.5-flash-lite`.
  - `generate_json(prompt, model)`: Executes a POST request with `generationConfig: {"responseMimeType": "application/json", "temperature": 0.1}` and parses the response into a Python dictionary.

---

### `legalagent/core/pipeline.py`
* **General Overview:** The master orchestrator. Chains ingestion, extraction, classification, candidate selection, analysis, and validation into a unified execution flow.
* **In-Depth Technical Breakdown:**
  - `analyse(file_path: str, config: dict, contract_id: str = "local") -> tuple[Run, list[Clause], list[Finding]]`:
    1. Ingests raw document via `ingest()`.
    2. Extracts clauses with offsets via `extract()`.
    3. Categorizes clauses via `classify()`.
    4. Selects high-risk candidate pairs via `select_candidates()`.
    5. Iterates through candidate pairs with `analyse_pair()`, tracking `no_issue_count` for false-positive denominator tracking.
    6. Runs statutory checks via `analyse_statutory()`.
    7. Validates findings against clause text offsets via `validate_findings()`.
    8. Generates a `Run` object with execution statistics.
    9. Ranks findings by severity (`high` $\to$ `medium` $\to$ `low`) and descending `risk_score`.
    10. Returns `(Run, list[Clause], list[Finding])`.

---

## 3. CLI & Persistence Layer (`legalagent/`)

### `legalagent/__main__.py`
* **General Overview:** Command-line interface (CLI) entry point (`python -m legalagent`).
* **In-Depth Technical Breakdown:**
  - Uses `argparse` to parse arguments: `analyse <file>`, `--top-k <int>`, `--contract-id <id>`, `--output <json-path>`.
  - Executes `pipeline.analyse()` and serializes findings, clauses, and run stats to stdout or a designated JSON file.
  - Prints a console summary to `stderr`: extracted clause count, labeled count, candidate pair count, and top flagged findings.

---

### `legalagent/db.py`
* **General Overview:** SQLite3 persistence and graph database layer managing `contracts.db`. Implements schema generation, pre-seeded demonstration contracts, graph retrieval, and embedding storage.
* **In-Depth Technical Breakdown:**
  - **Relational Schema:**
    - `contracts`: `(id TEXT PRIMARY KEY, title, category, jurisdiction, description, created_at)`.
    - `clauses`: `(id TEXT PRIMARY KEY, contract_id REFERENCES contracts ON DELETE CASCADE, clause_num, title, tag, text, ordinal)`.
    - `graph_edges`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id, source_clause_id, target_clause_id, label, relation_type, severity, color, width, dashes)`.
    - `findings`: `(id INTEGER PRIMARY KEY AUTOINCREMENT, contract_id, title, severity, relation_type, source_clause_ref, target_clause_ref, description, statute_citation, remedy_suggestion)`.
    - `clause_embeddings`: `(clause_id TEXT, contract_id TEXT, model_name TEXT, dimension INTEGER, vector_json TEXT, created_at TIMESTAMP, PRIMARY KEY(clause_id, model_name))`.
  - **Six Seeded Contracts (`seed_database()`):**
    1. `tech_msa`: Indian Tech Services MSA (IT/SaaS). Planted liability cap (₹15L) vs. uncapped IP indemnity; DPDPA penalty limit conflict. (Health Score: 26/100).
    2. `employment_nda`: Executive Employment Agreement. Planted 24-month post-termination non-compete void under Section 27 ICA. (Health Score: 42/100).
    3. `vendor_supply`: Industrial Vendor Supply Contract. Planted liquidated damages clause violating Section 74 ICA penalty doctrine. (Health Score: 58/100).
    4. `pune_metro_ppp`: Real Pune Metro Line III Concession Agreement (2019) with 3 injected adversarial clauses (₹1,000 liability cap vs. unlimited indemnity; Section 27 non-compete; DPDPA ₹10,000 cap). (Health Score: 15/100).
    5. `highway_concession`: Real NHAI 4-Laning Model BOT Concession. Well-drafted agreement with proper carveouts and balanced terms. (Health Score: 88/100).
    6. `lorem_ipsum_demo`: Synthetic Latin contract for UI stress testing and layout verification.
  - **Query Methods:**
    - `fetch_contract_graph_json(contract_id)`: Assembles full contract payload (contract metadata, clauses list, graph edges list, findings list) formatted for Vis.js.
    - `store_clause_embeddings(contract_id, model_name, embeddings)`: Persists vectors as JSON strings in `clause_embeddings`.
    - `fetch_clause_embeddings(contract_id, model_name)`: Retrieves stored embeddings for dimensional projection.

---

## 4. Web Application Layer (`web/`)

### `web/server.py`
* **General Overview:** Web server entry point. Launches Uvicorn hosting the FastAPI application on `http://0.0.0.0:8080`.
* **In-Depth Technical Breakdown:** Sets up `sys.path` injection for root module resolution, displays an ASCII banner with Swagger REST docs (`/docs`) and database links, and launches `uvicorn.run("web.backend:app", host="0.0.0.0", port=8080)`.

---

### `web/backend.py`
* **General Overview:** FastAPI application providing REST endpoints, Server-Sent Events (SSE) streaming, embedding dimensional reduction, and export generation.
* **In-Depth Technical Breakdown:**
  - `GET /`: Serves marketing landing page (`landing.html`).
  - `GET /app`: Serves 3-panel dashboard (`index.html`).
  - `GET /api/contracts`: Returns all contracts with aggregated metrics (clause count, finding count, computed health score: `max(15, 100 - (critical * 28) - (total * 6))`).
  - `GET /api/contracts/{id}`: Returns complete graph JSON for the contract.
  - `POST /api/contracts/analyze`: Analyzes custom text input via `core.pipeline` (with heuristic fallback).
  - `POST /api/contracts/analyze/stream`: Server-Sent Events (SSE) endpoint providing real-time streaming progress across 7 pipeline stages (`received` $\to$ `ingestion` $\to$ `extraction` $\to$ `classification` $\to$ `candidates` $\to$ `analysis` $\to$ `persisting` $\to$ `complete`).
  - `GET /api/contracts/{id}/embeddings`: Retrieves 768-dim embeddings from SQLite (or generates them on the fly). Uses Truncated Singular Value Decomposition (SVD / PCA) to project high-dimensional vectors to 2D coordinates $(x, y)$ for visualization.
  - `GET /api/export/{id}`: Compiles an executive **Legal Risk Audit Memorandum** in Markdown format.

---

### `web/index.html`
* **General Overview:** Single-page dashboard application built with vanilla HTML5, CSS3, and JavaScript, powered by Vis.js for interactive network visualization.
* **In-Depth Technical Breakdown:**
  - **Layout:** Three resizable panels:
    - *Left Panel (Clause Explorer):* Searchable, expandable clause cards with category badges and a "View Full" document modal.
    - *Center Panel (Network Canvas):* Interactive Vis.js network graph. Nodes represent clauses, colored by tag (Risk = Burgundy, Statutory = Purple, Commercial = Navy, Default = Slate). Edges represent relationships (Red = Conflict, Purple = Statutory, Blue = Xref, Green = Semantic).
    - *Right Panel (Findings Dossier):* Detailed risk cards showing severity badge, relationship type, source/target provisions, legal description, statutory citations, and suggested redlines.
  - **Vis.js Physics Configuration:**
    ```javascript
    physics: {
      solver: 'forceAtlas2Based',
      forceAtlas2Based: {
        gravitationalConstant: -8000,
        centralGravity: 0.005,
        springLength: 250,
        springConstant: 0.04,
        damping: 0.4,
        avoidOverlap: 0.6
      }
    }
    ```
  - **Bidirectional Cross-Linking:**
    - Clicking a clause in the left panel centers the graph camera on that node.
    - Clicking an edge in the graph identifies the corresponding finding and auto-scrolls the right-hand panel, applying a copper ring highlight animation (`ring-copper`).
  - **Modals:**
    - *Upload / Analyze Modal:* Supports drag-and-drop file upload (`.txt`, `.pdf`, `.docx`) or direct text pasting, with real-time SSE progress indicators.
    - *Full Contract Viewer:* Renders all clauses sequentially in a clean reading view.
    - *Legal Memorandum Export:* Renders an executive Markdown audit memo with one-click clipboard copy.

---

### `web/landing.html`
* **General Overview:** Product landing page introducing LegalAgent to prospective users and panel reviewers.
* **In-Depth Technical Breakdown:**
  - Styled with classic typography (`Playfair Display` serif headings paired with `Inter` sans-serif body text).
  - Design tokens: Navy (`#1a2332`), Warm Ivory (`#f5f3ef`), and Burnished Copper (`#9a7b4f`).
  - Sections: Hero Section with direct CTA button to `/app`, Core Value Grid (Cross-Clause Graph, Indian Compliance Engine, Deterministic Audit Trail), 4-step Pipeline walkthrough, and Statutory Overview.

---

## 5. Scripts & Tooling Suite (`scripts/`)

| Script | Purpose & Operational Mechanics |
|:---|:---|
| `scripts/run_custom_benchmark.py` | **Regression Benchmark Suite.** Reads `MANIFEST.json`, executes `pipeline.analyse()` over 3 benchmark contracts, compares detected finding categories against expected flags, and writes results to `runs/indian/custom_benchmark.json`. Exits with code 0 on pass, 1 on regression. |
| `scripts/pdf_to_markdown.py` | **Document Conversion Utility.** CLI wrapper around `ingestion.pdf_to_markdown()`. Converts any input PDF to clean Markdown via PyMuPDF + Tesseract OCR. |
| `scripts/create_indian_demo_pdf.py` | **Synthetic Data Generator.** Fetches clauses from `tech_msa` in SQLite and formats them into a clean, multi-page PDF (`indian_tech_msa_demo.pdf`) with running headers and clause numbers using PyMuPDF. |
| `scripts/inject_contract_irregularities.py` | **PDF Adversarial Injection Harness.** Takes the official Pune Metro concession PDF and appends 15 adversarial clauses (91.1 to 91.15) to evaluate detector robustness on real scanned government contracts. |
| `scripts/inject_contract_irregularities_md.py` | **Markdown Adversarial Injection Harness.** Markdown-native version of the adversarial injection pipeline for text-based analysis. |
| `scripts/download_models.py` | **Model Caching Script.** Pre-downloads and validates weights for `bhavyagiri/InLegal-Sbert` (768-dim) and `BAAI/bge-small-en-v1.5` (384-dim) into the local HuggingFace cache. |
| `scripts/check_gemini.py` | **Gemini Diagnostics.** Validates `GEMINI_API_KEY`, queries available models via Google REST API, and prints the selected model. |

---

## 6. Data Assets, Official PPP Contracts & Benchmarks (`data/`)

```
data/
├── demo/india/
│   ├── indian_tech_msa_demo.pdf / .md   ← Synthetic Indian SaaS MSA used in CLI demos
│   ├── official/
│   │   ├── SOURCES.md                  ← Provenance of official Government of India PPP contracts
│   │   ├── pune_metro_signed_concession.pdf ← Real 2019 Pune Metro PPP concession agreement
│   │   ├── model_concession_4_laning.pdf    ← Real NHAI BOT 4-laning model concession
│   │   └── samples/pune_metro_first_20_pages.pdf ← 20-page sample for OCR testing
│   ├── custom_benchmark/
│   │   ├── MANIFEST.json               ← Expected findings specification for regression tests
│   │   ├── 01_msa_cap_indemnity.txt    ← Planted: Liability cap vs. unlimited indemnity conflict
│   │   ├── 02_employment_non_compete.txt ← Planted: Section 27 ICA void non-compete
│   │   └── 03_clean_services_control.txt ← Clean control: Expects 0 findings (evaluates false positives)
│   └── adversarial/
│       ├── INJECTIONS.json             ← 15 adversarial injected clauses and expected flags
│       └── pune_metro_adversarial_15_changes.pdf ← Pune Metro PDF with injected clauses
└── raw/open-india-law-readme.md        ← Metadata for the 32.5M Indian court judgment corpus
```

### Benchmark Results
Running `python scripts/run_custom_benchmark.py`:
- `01_msa_cap_indemnity.txt`: Expected `['cross_clause_conflict']` $\to$ **PASS**
- `02_employment_non_compete.txt`: Expected `['section_27_statutory_violation', 'termination_survival_dependency']` $\to$ **PASS**
- `03_clean_services_control.txt`: Expected `[]` $\to$ **PASS** (Zero false positives)

---

## 7. Research Foundation & Indian Statutory Framework (`research/`)

* **Section 27, Indian Contract Act 1872 (`01_LEGAL_STATUTORY_RESEARCH.md`):** Negative covenants post-termination are void *ab initio*. Cites *Percept D'Mark v. Zaheer Khan* (2006) and *Niranjan Shankar Golikari* (1967).
* **Sections 73 & 74 ICA 1872:** Distinction between liquidated damages and penalties. Cites *Kailash Nath Associates v. DDA* (2015) — liquidated damages represent a ceiling, not an automatic entitlement; proof of reasonable loss is mandatory.
* **Sections 124 & 125 ICA 1872:** Indemnity obligations become actionable upon liability being determined, even prior to out-of-pocket payment (*Gajanan Moreshwar v. Moreshwar Madan*, 1942).
* **The 2023–2024 Statutory Overhaul:**
  - *Bharatiya Sakshya Adhiniyam (BSA), 2023:* Replaced Evidence Act; governs electronic contracts, digital signatures, and hash verification (§§61–63).
  - *Digital Personal Data Protection Act (DPDPA), 2023:* Non-waivable statutory duties; penalties up to ₹250 Crore.
  - *The Mediation Act, 2023:* Mandatory pre-litigation commercial mediation; mediated settlement agreements carry the force of a court decree.
* **Landmark Stamp Duty Ruling (7-Judge Bench, Dec 2023):** Overruled *NN Global*. Non-stamping is a curable defect for arbitral tribunals; it does not render the arbitration clause void *ab initio*.
* **Model Selection & Clustering Strategy (`02_MODEL_SELECTION_AND_BENCHMARKING.md`):** Why K-Means fails on legal contracts (unknown $k$, forced assignment of preamble/signature noise) and why **Agglomerative Hierarchical Clustering with Cosine Distance Threshold** is superior.
* **LoRA Fine-Tuning & Temporal Era Classifiers (`06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md`):** 4-adapter training roadmap on 32.5M open-india-law corpus to detect anachronistic statutory references.

---

## 8. Automated Test Suite (`tests/`)

### `tests/test_pipeline.py`
* **General Overview:** End-to-end integration and smoke test suite verifying pipeline integrity.
* **In-Depth Technical Breakdown:**
  - `test_extraction_and_candidates()`: Validates that inline clause numbering (`1.1 The Supplier shall...`) is extracted accurately into `Clause` objects with valid start/end offsets, and verifies that candidate pairs contain no self-comparisons.
  - `test_smoke_findings_and_evidence()`: Verifies that every `Finding` produced by `analyse()` resolves to real clause IDs and that character offsets match non-empty strings in the document text (structural anti-hallucination test).
  - `test_statutory_non_compete_finding()`: Ingests a synthetic non-compete clause and asserts that a `statutory_violation` finding referencing Section 27 of the Indian Contract Act is produced.
