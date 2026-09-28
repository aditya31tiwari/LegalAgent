# LegalAgent — Complete Code Dossier

> **Purpose:** Read this before any viva, demo, or code review. After reading it, you should be able to open any file, point to any line, and explain exactly what it does, why it exists, and how it connects to everything else.

---

## Table of Contents

1. [The Big Picture — One Paragraph](#1-the-big-picture--one-paragraph)
2. [Repository Layout](#2-repository-layout)
3. [Data Structures — types.py](#3-data-structures--typespy)
4. [Stage 1 — Ingestion (ingestion.py)](#4-stage-1--ingestion-ingestionpy)
5. [Stage 2 — Extraction (extraction.py)](#5-stage-2--extraction-extractionpy)
6. [Stage 3 — Classification (classification.py)](#6-stage-3--classification-classificationpy)
7. [Stage 4 — Candidate Selection (candidate_selection.py)](#7-stage-4--candidate-selection-candidate_selectionpy)
8. [Stage 5a — Embeddings (embeddings.py)](#8-stage-5a--embeddings-embeddingspy)
9. [Stage 5b — Gemini Analysis (gemini_analysis.py)](#9-stage-5b--gemini-analysis-gemini_analysispy)
10. [Stage 5c — Deterministic Analysis (analysis.py)](#10-stage-5c--deterministic-analysis-analysispy)
11. [The Gemini Client (gemini.py)](#11-the-gemini-client-geminipy)
12. [The Pipeline Orchestrator (pipeline.py)](#12-the-pipeline-orchestrator-pipelinepy)
13. [The Database Layer (db.py)](#13-the-database-layer-dbpy)
14. [The Web Backend (web/backend.py)](#14-the-web-backend-webbackendpy)
15. [The Web Server (web/server.py)](#15-the-web-server-webserverpy)
16. [End-to-End Data Flow — Trace a Request](#16-end-to-end-data-flow--trace-a-request)
17. [How the Graph is Built](#17-how-the-graph-is-built)
18. [Config Dictionary — What Every Key Does](#18-config-dictionary--what-every-key-does)
19. [The Two Analysis Modes — Side by Side](#19-the-two-analysis-modes--side-by-side)
20. [Why Things are Done This Way — Design Decisions](#20-why-things-are-done-this-way--design-decisions)
21. [Common Panel Questions on the Code](#21-common-panel-questions-on-the-code)

---

## 1. The Big Picture — One Paragraph

LegalAgent takes a raw contract PDF/DOCX/TXT, breaks it into numbered clauses, gives each clause a label (e.g., "indemnification"), uses **BM25 + cross-references + a label conflict matrix** to shortlist ~30 pairs of clauses that might conflict, then sends those pairs either to **Gemini** (for natural-language legal reasoning) or runs **deterministic rules** (for guaranteed offline operation). The result — a list of `Finding` objects — is stored in SQLite and rendered as an interactive graph in the browser using Vis.js. The whole system runs locally with zero cloud dependencies except the optional Gemini API call.

---

## 2. Repository Layout

```
LegalAgent/
├── legalagent/                  ← Core Python package (the brain)
│   ├── __init__.py
│   ├── __main__.py              ← CLI entry point (`python -m legalagent`)
│   ├── db.py                    ← Database init, seed, and helper queries
│   └── core/
│       ├── types.py             ← Clause, Finding, Run dataclasses
│       ├── ingestion.py         ← PDF/DOCX/TXT → normalized text
│       ├── extraction.py        ← Text → list[Clause] (regex)
│       ├── classification.py    ← Clause → labels (keyword dict)
│       ├── embeddings.py        ← InLegal-SBERT dense vectors
│       ├── candidate_selection.py ← BM25 + xrefs + type matrix → pairs
│       ├── analysis.py          ← Deterministic rule-based pair analysis
│       ├── gemini_analysis.py   ← NEW: Gemini-powered pair analysis
│       ├── gemini.py            ← Gemini API client (generate_json)
│       └── pipeline.py          ← Orchestrator: calls all stages in order
│
├── web/
│   ├── server.py               ← Uvicorn launcher (just sets port/host)
│   ├── backend.py              ← FastAPI app, all REST endpoints
│   └── index.html              ← Single-page dashboard (Vis.js graph)
│   └── injections.html         ← Adversarial injection explainer page
│
├── data/demo/india/             ← Sample contracts (PDF + TXT)
├── scripts/                     ← Utility scripts (check Gemini, benchmark)
├── tests/                       ← pytest tests + old examples + docs
│   └── old_examples/docs/       ← All AI-generated reference docs (HERE)
│
├── contracts.db                 ← SQLite database (auto-created)
├── .env                         ← GEMINI_API_KEY=... (never commit)
└── requirements.txt
```

> **Rule:** The `legalagent/` package is the brain. The `web/` folder is the eyes (UI). The `db.py` is the memory. `pipeline.py` is the nervous system connecting them.

---

## 3. Data Structures — types.py

**File:** [`legalagent/core/types.py`](../../../legalagent/core/types.py)

This file defines the three core dataclasses. Everything in the project is built around these types.

### `Clause` — One numbered clause from a contract

```python
@dataclass
class Clause:
    id: str              # e.g. "acme_msa::5.2" — contract_id + clause_number
    contract_id: str     # e.g. "acme_msa"
    parent_id: str | None    # for sub-clauses (not used in v0)
    number: str | None       # "5.2", "1.2.3"
    heading: str | None      # First line if short, e.g. "Limitation of Liability"
    text: str            # Full clause text, verbatim from document
    char_start: int      # Byte offset in normalized_text where clause starts
    char_end: int        # Byte offset where clause ends
    ordinal: int         # 0-indexed document order
    labels: list[dict]   # [{"label": "indemnification", "confidence": 0.9}]
    xrefs: list[dict]    # [{"raw": "Section 8.2", "clause_id": "...", "resolved": True}]
```

**Why `char_start` / `char_end`?** The UI needs to highlight the exact text span. These offsets let us jump to the right position in the original document.

**Why `labels` as a list of dicts?** A clause can have multiple labels (e.g., a clause can be both "termination" AND "survival"). Each label has a confidence score so future ML models can plug in without changing the schema.

---

### `Finding` — One detected legal issue between clauses

```python
@dataclass
class Finding:
    id: str                        # "finding_a3f9b2c1" (UUID hex)
    target_clause_id: str          # The "primary" clause with the problem
    related_clause_ids: list[str]  # The other clause(s) involved
    relation_type: str             # "conflict" | "dependency" | "overlap" | "ambiguity" | "no_issue"
    severity: str                  # "high" | "medium" | "low"
    risk_score: float              # 0.0–1.0
    rationale: str                 # Plain English explanation
    surfaced_by: list[str]         # ["bm25", "type_matrix", "gemini"]
    evidence: list[dict]           # [{"clause_id": "...", "start": 0, "end": 245}]
    refs: list[dict]               # [{"source": "ICA 1872", "section": "S.27", "snippet": "..."}]
    scores: dict                   # {"analysis_confidence": 0.88, "gemini_powered": 1.0}
```

**Why `surfaced_by`?** Tells you what retrieval method found this pair. Useful for evaluating which methods catch what. Also shown in the UI.

**Why `evidence`?** Allows the UI to highlight the exact text span that caused the finding.

---

### `Run` — Metadata about one analysis run

```python
@dataclass
class Run:
    id: str             # "run_079c284e"
    contract_id: str
    config: dict        # {"retrieval_method": "bm25", "top_k": 5, "use_gemini": True}
    stats: dict         # {"clauses": 12, "pairs": 28, "findings": 4, "no_issue": 24}
```

---

## 4. Stage 1 — Ingestion (ingestion.py)

**File:** [`legalagent/core/ingestion.py`](../../../legalagent/core/ingestion.py)

**Job:** Convert a raw file (PDF, DOCX, TXT) into a single clean string called `normalized_text`.

### Function: `ingest(file_path) → str`

This is the entry point. It looks at the file extension and routes:

| Extension | Library Used | Method |
|-----------|-------------|--------|
| `.pdf` | `pymupdf` | `pdf_to_markdown()` then strip markdown tags |
| `.docx` | `python-docx` | Extract all paragraph text |
| `.txt` | built-in | `path.read_text()` |

Then calls `normalize(text)` on the result.

---

### Function: `pdf_to_markdown(file_path) → str`

Iterates over every PDF page. For each page:
1. Extracts text blocks using `pymupdf`'s `get_text("dict")` — gives you font size, boldness, position
2. **OCR fallback:** If a page has fewer than 80 characters of native text, it's probably a scanned image → runs `tesseract` OCR at 150 DPI automatically
3. Detects headings: if a span is **bold** OR font size ≥ 14 AND text ≤ 100 chars → wraps it in `## heading`
4. Joins pages with `<!-- Page N -->` markers (later stripped)

---

### Function: `normalize(text) → str`

Four cleanup steps **in exact order** (order matters!):

```
Step 1: Remove repeating headers/footers
        → Count how often each line appears; if > 80% of pages, it's a header/footer
        → Only runs on multi-page documents (single-page: nothing "repeats across pages")

Step 2: Drop standalone page numbers
        → Lines matching r'^\s*\[?\s*\d+\s*\]?\s*$' are page numbers → delete

Step 3: Rejoin hyphenated line breaks
        → "cross-\ncourt" → "crosscourt" (regex: r'([a-z])-\n\s*([a-z])')

Step 4: Collapse whitespace
        → Split on blank lines (paragraph breaks), strip each paragraph,
          collapse internal whitespace, rejoin with '\n\n'
```

**Why normalize?** The regex clause extractor needs consistent whitespace. Hyphenated breaks would cause "limita-\ntion" to look like two words. Repeated headers would create ghost clauses.

---

## 5. Stage 2 — Extraction (extraction.py)

**File:** [`legalagent/core/extraction.py`](../../../legalagent/core/extraction.py)

**Job:** Find all numbered clauses in the normalized text → return `list[Clause]`.

### The Main Regex

```python
CLAUSE_RE = re.compile(r'^\s*(\d+(?:\.\d+)*)\.?\s+', re.MULTILINE)
```

This matches clause numbers like: `1`, `1.1`, `1.1.2`, `91.3`

- `^\s*` — start of line, optional leading spaces
- `(\d+(?:\.\d+)*)` — capture group: one or more number segments separated by dots
- `\.?\s+` — optional trailing dot, then whitespace

**Important:** This only matches **decimal numbering** (1.1, 1.2.3). It does NOT match `(a)`, `(i)`, lettered clauses. That's intentional — it keeps the extraction flat and simple.

### How Clause Boundaries Work

```
match[0].start ─────────────────── match[1].start
      ↓                                   ↓
 "1.1 The Supplier shall..."   "1.2 Payment is due..."
 ←──── clause 1.1 span ──────→←──── clause 1.2 span ──→
```

Each clause runs from its own match start to the next match start (or end of document for the last clause). This means clauses tile the entire document perfectly.

### Cross-Reference Detection

```python
XREF_RE = re.compile(r'(?:Section|Clause|Article|clause|§)\s+(\d+(?:\.\d+)*)', re.I)
```

For every clause, scans its text for references like "Section 8.2" or "Clause 5.1". Stores them as:
```python
{"raw": "Section 8.2", "clause_id": "contract::8.2", "resolved": False}
```

After all clauses are extracted, resolves each xref: checks if `contract::8.2` exists in the extracted clause IDs. If yes → `resolved: True`. This is how the graph knows to draw a "real" cross-reference edge.

### Clause ID Format

```
{contract_id}::{clause_number}
e.g. "acme_msa::5.2"
```

If the same number appears twice (deduplication):
```
"acme_msa::5.2::2"  ← second occurrence
```

---

## 6. Stage 3 — Classification (classification.py)

**File:** [`legalagent/core/classification.py`](../../../legalagent/core/classification.py)

**Job:** Give each clause one or more **labels** by scanning its text for keywords.

### The Keyword Dictionary

```python
KEYWORDS = {
    "indemnification":        ["indemnif", "hold harmless", "defend"],
    "limitation_of_liability": ["limitation of liability", "in no event shall",
                                 "aggregate liability", "consequential damages"],
    "termination":            ["terminate", "termination", "following termination",
                                "post-termination"],
    "confidentiality":        ["confidential information", "non-disclosure", "nda"],
    "governing_law":          ["governed by the laws", "governing law", "jurisdiction"],
    "assignment":             ["assign", "successors and assigns"],
    "survival":               ["survive", "shall survive termination"],
    "exclusivity":            ["exclusive", "sole and exclusive"],
    "warranty":               ["warranty", "represent and warrant"],
    "force_majeure":          ["force majeure", "act of god"],
    "payment":                ["payment", "invoice", "compensation", "fee"],
    "intellectual_property":  ["intellectual property", "patent", "trademark"],
}
```

### How It Works

For each clause:
1. Lowercase the full clause text
2. For each label → loop its keyword list → if any keyword appears in text → add label, BREAK (don't double-add)
3. A clause can get multiple labels (e.g., a clause with "terminate" AND "survive" gets both `termination` and `survival`)

Stored as:
```python
clause.labels = [
    {"label": "limitation_of_liability", "confidence": 1.0, "source": "keyword"},
    {"label": "termination",             "confidence": 1.0, "source": "keyword"},
]
```

**Confidence is always 1.0 in v0** — it's a boolean keyword match. Future ML models would put real confidence here.

**Why keyword-based?** Fast, offline, reproducible, and good enough for the prototype. For real production you'd use a fine-tuned BERT classifier.

---

## 7. Stage 4 — Candidate Selection (candidate_selection.py)

**File:** [`legalagent/core/candidate_selection.py`](../../../legalagent/core/candidate_selection.py)

**Job:** From N clauses (potentially hundreds), find the ~30 pairs most worth analysing. Returns: `list[tuple[str, str, list[str]]]` → each tuple is `(clause_a_id, clause_b_id, methods_that_surfaced_it)`.

This is the **most important stage** for your panel. It's the "retrieval" step before the "reasoning" step.

### Why Candidate Selection?

You can't compare every pair: with 100 clauses that's 4,950 pairs. Sending all 4,950 to Gemini would cost \$\$\$ and take minutes. The retrieval stage is a cheap filter that reduces to ≤ 30 high-signal pairs.

### Three Retrieval Methods

#### Method 1: Cross-Reference Graph (`xref`)

```python
for clause in clauses:
    for xref in clause.xrefs:
        if xref["resolved"]:
            add_pair(clause.id, xref["clause_id"], "xref")
```

If Clause 5 says "see Section 8.2", they're connected by definition. These pairs are **always kept** (not capped by `MAX_CANDIDATES`).

#### Method 2: Type Matrix (`type_matrix`)

```python
TYPE_MATRIX = {
    ("limitation_of_liability", "indemnification"): 0.9,  # Classic conflict
    ("termination", "survival"):                    0.6,  # Dependency
    ("assignment", "confidentiality"):              0.5,
    ("exclusivity", "assignment"):                  0.6,
    ("warranty", "limitation_of_liability"):        0.7,
}
```

If Clause A has label `limitation_of_liability` AND Clause B has label `indemnification` → they conflict according to legal domain knowledge → surface the pair. These pairs are also **always kept**.

The numbers (0.9, 0.6...) are the weights — not used in sorting currently, but planned for future ranking.

#### Method 3: BM25 (`bm25`)

```python
tokenized = [c.text.lower().split() for c in clauses]
bm25 = BM25Okapi(tokenized)
for i, clause_a in enumerate(clauses):
    scores = bm25.get_scores(tokenized[i])
    # ranked: sorted by BM25 score descending
    for score, clause_b_id in ranked[:k]:
        add_pair(clause_a.id, clause_b_id, "bm25")
```

BM25 finds clauses that use **similar vocabulary**. "Liability" + "indemnify" in the same clause → high BM25 score for the liability clause against the indemnity clause. BM25 pairs fill remaining slots up to `MAX_CANDIDATES = 30`.

#### Method 4: Dense (optional, `config["retrieval_method"] == "dense"`)

Calls `embeddings.related_pairs()` using InLegal-SBERT to find semantically similar pairs. Only activated when explicitly configured. Much slower (requires GPU or several seconds on CPU) but catches paraphrases that BM25 misses.

### Priority System

```
xref pairs → ALWAYS kept  (priority 1)
type_matrix → ALWAYS kept  (priority 2)
bm25-only → fill remaining slots up to MAX_CANDIDATES=30
```

This means if you have 5 xref pairs + 3 type_matrix pairs, BM25 can add up to 22 more pairs.

### Deduplication

```python
key = tuple(sorted((a_id, b_id)))
pairs.setdefault(key, set()).add(method)
```

If BM25 and type_matrix both surface the same pair, the pair appears once with `methods = ["bm25", "type_matrix"]`. The `sorted()` ensures `(A, B)` and `(B, A)` are treated as the same pair.

---

## 8. Stage 5a — Embeddings (embeddings.py)

**File:** [`legalagent/core/embeddings.py`](../../../legalagent/core/embeddings.py)

**Job:** Convert clause text into dense vectors using **InLegal-SBERT** (a BERT model fine-tuned on Indian legal documents).

### Functions

#### `load_model(model_name)` — `@lru_cache`

```python
@lru_cache(maxsize=2)
def load_model(model_name):
    return SentenceTransformer(model_name)
```

`@lru_cache` means the model is loaded only **once** per Python process, then cached in RAM. Loading a SentenceTransformer takes 3–10 seconds — you don't want to do that on every request.

#### `embed_texts(texts) → np.ndarray`

Encodes a list of strings into a `(N, 768)` float32 matrix. `normalize_embeddings=True` means each vector has L2 norm = 1 (required for cosine similarity via dot product).

#### `related_pairs(clauses, top_k=5) → list[(id_a, id_b, score)]`

```python
vectors = model.encode([clause.text for clause in clauses], normalize_embeddings=True)
scores = np.asarray(vectors) @ np.asarray(vectors).T  # Full cosine similarity matrix
```

`vectors @ vectors.T` computes all pairwise cosine similarities in one BLAS call. For each clause, sorts results descending and keeps top_k. Returns `(id_a, id_b, cosine_score)` tuples.

**Where used:** In `candidate_selection.py` when `config["retrieval_method"] == "dense"` or `"hybrid"`. Also used in `web/backend.py` to compute 2D SVD projections for the visual graph layout.

---

## 9. Stage 5b — Gemini Analysis (gemini_analysis.py)

**File:** [`legalagent/core/gemini_analysis.py`](../../../legalagent/core/gemini_analysis.py)

**Job:** Take the shortlisted pairs from candidate selection → send them ALL in one batched Gemini prompt → parse the response into `Finding` objects.

This is the **new module** that replaces the deterministic rule engine.

### Constants

```python
VALID_RELATION_TYPES = {"conflict", "dependency", "overlap", "ambiguity", "no_issue"}
VALID_SEVERITIES = {"high", "medium", "low"}
```

These are the only values Gemini is allowed to return. Anything else gets normalised to `no_issue` / `low` with a warning.

### `_build_prompt(pairs) → str`

Builds a single large prompt containing ALL shortlisted pairs. Example structure:

```
--- PAIR 1 ---
Clause A  id=acme::8.1  labels=['limitation_of_liability']
"""The aggregate liability shall not exceed INR 15,00,000..."""

Clause B  id=acme::12.1  labels=['indemnification']
"""Vendor shall indemnify... without any financial limitation..."""

Retrieval signals: ['bm25', 'type_matrix']
```

Then instructs Gemini to return exactly N findings in JSON format.

**Why batch all pairs?** Reduces API calls from N (one per pair) to 1. Cheaper and faster.

**Why include retrieval signals?** Tells Gemini which methods flagged the pair, giving it context about why this pair was surfaced.

### `analyse_pairs_with_gemini(pairs, model) → list[Finding | None]`

1. Calls `_build_prompt(pairs)` to build the prompt
2. Calls `generate_json(prompt, model)` from `gemini.py` → gets back a JSON dict
3. Extracts `response["findings"]` — expects exactly `len(pairs)` items
4. If Gemini returns fewer items (truncated response) → pads with `no_issue` dicts
5. Calls `_parse_finding()` for each item to convert to a `Finding` object

### `_parse_finding(clause_a, clause_b, surfaced_by, item) → Finding | None`

Validates Gemini's output item:
- Normalises `relation_type` (if invalid → `no_issue`)
- Clamps `risk_score` to `[0.0, 1.0]`
- If `relation_type == "no_issue"` → returns `None` (no finding)
- Otherwise builds a proper `Finding` with `scores["gemini_powered"] = 1.0`

Any exception during parsing → logs warning → returns `None` (safe degradation).

### Fallback Behavior

If `GeminiConfigurationError` is raised (no API key, network error, 503) → `pipeline.py` catches it and falls back to `_run_deterministic_analysis()`. **The pipeline never crashes due to Gemini being unavailable.**

---

## 10. Stage 5c — Deterministic Analysis (analysis.py)

**File:** [`legalagent/core/analysis.py`](../../../legalagent/core/analysis.py)

**Job:** Rule-based analysis of clause pairs. Used as the baseline when Gemini is off, and as the fallback when Gemini fails.

### Helper: `_evidence(clause) → dict`

```python
return {"clause_id": clause.id, "start": 0, "end": len(clause.text)}
```

Creates an evidence record pointing to the entire clause text. (In a real system you'd point to the specific sentence.)

### Helper: `_finding(target, related, ...) → Finding`

Central factory for all deterministic findings. Builds the `Finding` object with:
- `id` = random UUID hex (e.g., `finding_a3f9b2c1`)
- `evidence` = list of `_evidence()` dicts for target + all related clauses
- `scores["analysis_confidence"] = 0.82` (hardcoded for deterministic rules)

### `analyse_pair(clause_a, clause_b, surfaced_by) → Finding | None`

Two hard-coded rules:

**Rule 1: Liability Cap vs. Uncapped Indemnity**
```
IF clause_a has label "limitation_of_liability"
AND clause_b has label "indemnification" (or vice versa)
→ HIGH CONFLICT — "The liability clause sets an aggregate ceiling, while the
  indemnity clause does not clearly state whether indemnity obligations are
  subject to that ceiling."
→ Cites ICA 1872 Sections 124-125
```

**Rule 2: Termination vs. Survival**
```
IF one clause has label "termination" (but NOT "survival")
AND another clause has label "survival"
→ MEDIUM DEPENDENCY — "The termination clause depends on the survival clause
  to determine which obligations continue after termination."
```

Returns `None` if no rule fires.

### `analyse_statutory(clauses, jurisdiction) → list[Finding]`

Runs on the **full clause list** (not pairs). Applies jurisdiction-specific statutory rules.

**Currently one rule: Section 27 ICA (post-termination non-compete)**

```python
if (re.search(r"post[- ]termination|following termination", text)
    and re.search(r"non[- ]compete|shall not\s+compete", text)):
    → HIGH STATUTORY_VIOLATION — "void under Section 27 ICA, 1872"
```

This is checked on EVERY clause individually (not pairs), because it's a standalone statutory violation that appears in one clause, not between two clauses.

### `validate_findings(findings, clauses)`

Final sanity check. For every finding:
1. All clause IDs referenced must exist in the contract
2. All evidence spans must point to non-empty text

Raises `ValueError` immediately if anything is wrong (fail-fast).

---

## 11. The Gemini Client (gemini.py)

**File:** [`legalagent/core/gemini.py`](../../../legalagent/core/gemini.py)

**Job:** Minimal, dependency-free HTTP client for the Gemini REST API. No Google SDK needed.

### Why No SDK?

The Google Generative AI Python SDK is heavy. This file uses only `urllib` (Python stdlib) so the project has minimal dependencies.

### Constants

```python
API_ROOT = "https://generativelanguage.googleapis.com/v1beta"
PREFERRED_MODELS = (
    "gemini-3-flash-preview",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.5-flash-lite",
)
```

`PREFERRED_MODELS` is tried in order — first one available wins.

### `list_models() → list[str]`

Calls `GET /v1beta/models` with the API key. Returns model names that support `"generateContent"`. This is how we discover which models are available for your specific API key.

### `choose_model(available) → str`

Priority:
1. If `GEMINI_MODEL` env variable is set AND is in available → use it
2. Else try each `PREFERRED_MODELS` in order
3. Else pick any Flash model alphabetically
4. Else pick the first available model
5. If nothing → raise `GeminiConfigurationError`

### `generate_json(prompt, model) → dict`

```python
body = {
    "contents": [{"parts": [{"text": prompt}]}],
    "generationConfig": {
        "responseMimeType": "application/json",  # Forces JSON output
        "temperature": 0.1,                       # Low temp = deterministic
    },
}
```

`responseMimeType: "application/json"` is the key — Gemini guarantees valid JSON output, so we can directly `json.loads()` the response text.

`temperature: 0.1` → very low randomness → consistent, reproducible results.

### `GeminiConfigurationError`

A custom exception raised for any config problem (missing key, no models, network error). Pipeline catches this and falls back to deterministic analysis.

---

## 12. The Pipeline Orchestrator (pipeline.py)

**File:** [`legalagent/core/pipeline.py`](../../../legalagent/core/pipeline.py)

**Job:** Call all stages in the right order. The only file that knows about all other files.

### `analyse(file_path, config, contract_id) → tuple[Run, list[Clause], list[Finding]]`

The pipeline in pseudocode:

```
text = ingest(file_path)                     # Stage 1
clauses = extract(text, contract_id)         # Stage 2
clauses = classify(clauses)                  # Stage 3
pairs = select_candidates(clauses, config)   # Stage 4

if config["use_gemini"]:                     # Stage 5a (Gemini)
    try:
        findings = analyse_pairs_with_gemini(pairs)
    except GeminiConfigurationError:
        findings = deterministic_fallback(pairs)  # auto-fallback
else:                                        # Stage 5b (deterministic)
    findings = deterministic_analysis(pairs)

findings += analyse_statutory(clauses)       # Always runs (Stage 6)
validate_findings(findings, clauses)         # Sanity check (Stage 7)
```

### Helper: `_run_gemini_analysis(pairs_data, clauses, config)`

Converts `(id_a, id_b, methods)` tuples into `(Clause, Clause, methods)` objects, then calls `analyse_pairs_with_gemini()`. Catches `GeminiConfigurationError` and falls back to `_run_deterministic_analysis()`.

### Helper: `_run_deterministic_analysis(pair_objects)`

Simple loop: call `analyse_pair()` for each pair, collect findings and no-issue count.

### Run Stats

```python
run.stats = {
    "clauses": len(clauses),
    "pairs": len(pairs),
    "findings": len(findings),
    "no_issue": no_issue_count,
    "gemini_powered": True/False,  # Was Gemini actually used?
}
```

### Final Sort

```python
findings.sort(
    key=lambda f: ({"high": 0, "medium": 1, "low": 2}.get(f.severity, 3), -f.risk_score)
)
```

Sort by severity first (high first), then by risk_score descending within same severity.

---

## 13. The Database Layer (db.py)

**File:** [`legalagent/db.py`](../../../legalagent/db.py)

**Job:** SQLite schema, seed data, and helper queries.

### Schema (5 Tables)

```sql
contracts         ← One row per uploaded/seeded contract
clauses           ← Many rows per contract (one per clause)
graph_edges       ← Connections between clauses (for Vis.js)
findings          ← Legal issues found (displayed in sidebar)
clause_embeddings ← InLegal-SBERT vectors stored as JSON (for 2D projection)
```

### `init_db()`

Creates all tables with `CREATE TABLE IF NOT EXISTS` — safe to call multiple times. Called automatically when the server starts.

### `seed_database()`

Inserts 4 pre-built demo contracts:
1. **Indian Tech Services MSA** — cap vs. uncapped indemnity + DPDPA issues
2. **Executive Employment NDA** — Section 27 void non-compete
3. **Vendor Supply Agreement** — Section 74 punitive penalty
4. **Pune Metro PPP Concession** — adversarial test clauses

Each demo contract includes pre-built `edges` (graph connections) and `findings` (legal issues) so the demo works instantly without running the pipeline.

### `conn.row_factory = sqlite3.Row`

This makes SQLite return rows as dict-like objects (you can do `row["column_name"]`), not plain tuples. Makes the backend code cleaner.

### Foreign Keys

```sql
FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
```

If you delete a contract, all its clauses, edges, and findings are automatically deleted. This prevents orphaned data.

---

## 14. The Web Backend (web/backend.py)

**File:** [`web/backend.py`](../../../web/backend.py)

**Job:** FastAPI REST API. Receives HTTP requests from the browser, runs the pipeline, reads/writes SQLite, returns JSON.

### Key Endpoints

| Method | Path | What it does |
|--------|------|-------------|
| `GET` | `/api/contracts` | List all contracts in DB |
| `GET` | `/api/contracts/{id}` | Get clauses, edges, findings for one contract |
| `POST` | `/api/contracts/analyze` | Upload contract text → run pipeline → store → return analysis |
| `GET` | `/api/contracts/{id}/embeddings` | Get 2D positions for all clauses (SVD projection) |
| `DELETE` | `/api/contracts/{id}` | Delete contract and all its data |
| `POST` | `/api/seed` | Re-seed demo contracts |
| `GET` | `/injections` | Serve the adversarial injection explainer HTML page |

### The Analyze Endpoint — Step by Step

When you upload a contract (`POST /api/contracts/analyze`):

1. **Generate contract ID:** `uuid4().hex[:8]`
2. **Write to temp file:** Because `pipeline.ingest()` needs a file path
3. **Run pipeline:**
   ```python
   config = {
       "retrieval_method": "bm25", "top_k": 10,
       "jurisdiction": jurisdiction,
       "use_gemini": True      ← Gemini enabled in web backend
   }
   run, pipeline_clauses, pipeline_findings = pipeline_analyse(tmp_path, config, contract_id)
   ```
4. **Delete temp file**
5. **Insert to DB:**
   - `contracts` table: title, category, jurisdiction
   - `clauses` table: every extracted clause with tag (mapped from label)
   - `graph_edges`: one edge per finding (connecting target ↔ related clauses)
   - `findings`: every finding with title, severity, rationale, statute citation

6. **If pipeline failed** (e.g., no numbered clauses found): falls back to simple heuristic (split on blank lines)

### The Embeddings Endpoint — SVD Projection

```python
GET /api/contracts/{id}/embeddings
```

1. Load all clauses for the contract from DB
2. Call `embed_texts([clause.text for clause in clauses])` → `(N, 768)` matrix
3. Run `TruncatedSVD(n_components=2)` to project to 2D
4. Normalise to `[-200, 200]` range (Vis.js coordinate space)
5. Return `{"clause_id": str, "x": float, "y": float}` for each clause

**Why SVD and not UMAP/t-SNE?** SVD is deterministic, fast, and has no hyperparameters to tune. Same input always gives same 2D layout — important for reproducibility.

### Label to Tag Mapping

```python
LABEL_TO_TAG = {
    "indemnification":          "Indemnity",
    "liability_limitation":     "Liability",
    "termination":              "Term",
    "survival":                 "Survival",
    "confidentiality":          "IP",
    "data_protection":          "Compliance",
    ...
}
```

Converts internal ML labels to human-readable tags shown in the UI.

---

## 15. The Web Server (web/server.py)

**File:** [`web/server.py`](../../../web/server.py)

**Job:** Just launches Uvicorn. 25 lines total.

```python
uvicorn.run("web.backend:app", host="0.0.0.0", port=8080, reload=False)
```

- `host="0.0.0.0"` → accessible from any network interface (not just localhost)
- `port=8080` → you access it at `http://localhost:8080`
- `reload=False` → no file-watching in production (use `reload=True` in dev)

**To start:** `venv/bin/python web/server.py`

---

## 16. End-to-End Data Flow — Trace a Request

Here is what happens when you upload a contract through the browser:

```
Browser (user clicks "Analyze")
  │
  │ POST /api/contracts/analyze
  │ Body: {text: "1.1 Definitions...\n\n1.2 Payment..."}
  ▼
web/backend.py — analyze endpoint
  │
  ├─► ingestion.py:normalize(text)
  │       → strips headers, collapses whitespace
  │
  ├─► [write to /tmp/tmpXXXXX.txt]
  │
  ├─► pipeline.py:analyse(tmp_path, config, contract_id)
  │   │
  │   ├─► ingestion.py:ingest() → normalized_text
  │   ├─► extraction.py:extract() → [Clause(id="c::1.1"), Clause(id="c::1.2"), ...]
  │   ├─► classification.py:classify() → clauses with labels attached
  │   ├─► candidate_selection.py:select_candidates()
  │   │       → BM25 scores + xref graph + type_matrix
  │   │       → 30 candidate pairs [(id_a, id_b, ["bm25", "type_matrix"]), ...]
  │   │
  │   ├─► [use_gemini=True branch]
  │   │   ├─► gemini_analysis.py:_build_prompt(pairs) → single big prompt
  │   │   ├─► gemini.py:generate_json(prompt) → HTTP POST to Gemini API
  │   │   │       → {"findings": [{relation_type, severity, risk_score, rationale}, ...]}
  │   │   └─► _parse_finding() × 30 → [Finding(...), None, Finding(...), ...]
  │   │
  │   ├─► analysis.py:analyse_statutory() → statutory findings (Section 27 etc.)
  │   ├─► analysis.py:validate_findings() → sanity check
  │   └─► sort by severity → return (Run, clauses, findings)
  │
  ├─► [DELETE /tmp/tmpXXXXX.txt]
  │
  ├─► db: INSERT contracts, clauses, graph_edges, findings
  │
  └─► return JSON response to browser
          {contract_id, clauses, graph_edges, findings, stats}

Browser (receives response)
  ├─► Vis.js renders graph: nodes=clauses, edges=graph_edges
  ├─► Sidebar renders: findings list with severity badges
  └─► GET /api/contracts/{id}/embeddings → update node positions with SVD layout
```

---

## 17. How the Graph is Built

The Vis.js graph in the browser has:

**Nodes** = clauses. Color = tag type. Size = importance.

**Edges** = relationships. Each `Finding` creates at least one edge:
- `target_clause_id → related_clause_ids[0]`
- Edge color: `#ef4444` (red) for conflict, `#ec4899` (pink) for statutory, `#38bdf8` (blue) for xref, `#10b981` (green) for semantic

**Seeded contracts** have pre-built edges in `db.py:seed_database()` — these are hardcoded so the demo works without running the pipeline.

**Uploaded contracts** get edges built dynamically from `Finding.target_clause_id` and `Finding.related_clause_ids` in the backend's analyze endpoint.

---

## 18. Config Dictionary — What Every Key Does

The `config` dict is passed through `pipeline.analyse()` all the way to candidate selection and analysis.

| Key | Type | Default | Purpose |
|-----|------|---------|---------|
| `retrieval_method` | `str` | `"bm25"` | `"bm25"` / `"dense"` / `"hybrid"` |
| `top_k` | `int` | `5` | How many BM25 results per clause |
| `jurisdiction` | `str` | `"India"` | Passed to `analyse_statutory()` |
| `use_gemini` | `bool` | `False` | Route pairs to Gemini or deterministic rules |
| `gemini_model` | `str` | `None` | Force a specific model (else auto-select) |
| `embedding_model` | `str` | `"bhavyagiri/InLegal-Sbert"` | HuggingFace model for dense retrieval |

**Web backend always sets:** `{"use_gemini": True, "top_k": 10, "jurisdiction": "India"}`

**Tests always use:** `{"retrieval_method": "bm25", "top_k": 5}` — no Gemini → deterministic → always pass

---

## 19. The Two Analysis Modes — Side by Side

| Aspect | Deterministic (analysis.py) | Gemini (gemini_analysis.py) |
|--------|----------------------------|----------------------------|
| **Speed** | < 1ms per pair | 5–15 sec total (one API call) |
| **Cost** | Free | ~\$0.001–0.01 per request |
| **Offline** | ✅ Always | ❌ Needs internet + API key |
| **Rules** | 2 hardcoded patterns | Full legal reasoning |
| **Rationale** | Hardcoded string | Gemini writes it |
| **Citations** | Hardcoded | Gemini provides |
| **New clause types** | Need new code | Just works |
| **Tests** | Always pass | Can't test without key |
| **`Finding.scores`** | `{"analysis_confidence": 0.82}` | `{"gemini_powered": 1.0, "analysis_confidence": 0.88}` |

**The pattern:** Deterministic = reliable baseline. Gemini = rich reasoning. Fallback = if Gemini fails, deterministic kicks in automatically.

---

## 20. Why Things are Done This Way — Design Decisions

### Why SQLite instead of PostgreSQL?

Zero config. Runs as a file. Perfect for a prototype/demo. Can be swapped for PostgreSQL later by changing `DB_PATH` to a connection string.

### Why one Gemini call for all pairs (batching)?

Reduces API calls from 30 to 1. Reduces latency. The Gemini API has a large context window — 30 short clause pairs fit easily in one prompt.

### Why not use LangChain/LlamaIndex?

Adds heavy dependencies, makes the code harder to read and debug, and is overkill for one API call. The entire Gemini integration is 89 lines of stdlib Python.

### Why `@lru_cache` on `load_model()`?

SentenceTransformer models are large (~400MB). Without caching, every request would reload the model from disk, taking 5+ seconds. With `lru_cache`, it loads once.

### Why keyword classification instead of ML?

1. **Interpretable** — you can see exactly why a clause got a label
2. **Fast** — microseconds, not seconds
3. **No GPU needed** — runs anywhere
4. **Accurate enough** — legal clauses use consistent vocabulary

### Why `MAX_CANDIDATES = 30`?

Trade-off between coverage and cost. 30 pairs is enough to catch the major conflicts in a typical 10-50 clause contract. Sending 500 pairs to Gemini would be expensive and the extra pairs would mostly be irrelevant.

### Why `temperature: 0.1` for Gemini?

Legal analysis should be deterministic and consistent. Low temperature means Gemini picks the highest-probability tokens, reducing hallucinations and making results reproducible.

---

## 21. Common Panel Questions on the Code

**Q: "Walk me through what happens when I click Analyze."**
> Answer: See [Section 16](#16-end-to-end-data-flow--trace-a-request) — the full 15-step trace.

**Q: "How does BM25 work?"**
> BM25 is a probabilistic ranking function. It scores Clause B against Clause A's vocabulary. If Clause A talks about "liability cap" and Clause B also mentions "liability" frequently (but not all contracts do), B gets a high BM25 score against A. The key difference from TF-IDF is the saturation term: after a certain frequency, more occurrences of a word stop increasing the score.

**Q: "Why isn't Gemini used for detection (finding pairs)? Why only for classification?"**
> Detection (finding which pairs exist) needs to be fast and cheap — you can't send every possible pair combination to Gemini. So we use BM25/embeddings/type-matrix for detection. Classification (what TYPE of problem is it — conflict, dependency, etc.) only needs to run on 30 pre-selected pairs, so that's where Gemini adds value.

**Q: "What happens if the Gemini API is down?"**
> `GeminiConfigurationError` is caught in `pipeline.py:_run_gemini_analysis()`, which calls `_run_deterministic_analysis()` instead. The user still gets results — they just come from the rule engine instead of Gemini. The `gemini_powered: True` flag in `run.stats` still shows `True` because Gemini was attempted.

**Q: "How do you know the extraction is correct?"**
> `validate_findings()` checks that every Finding's clause IDs exist in the extracted clause list. If extraction went wrong (e.g., clause IDs don't match), this raises a `ValueError` before anything is stored.

**Q: "What is `char_start` / `char_end` used for?"**
> They mark the byte offsets of each clause in `normalized_text`. The UI uses these to highlight the exact text span in the contract viewer. The evidence dicts in `Finding` also reference these spans.

**Q: "Could this scale to a 500-page contract?"**
> Extraction and classification would handle it fine (both are linear time). Candidate selection caps at 30 pairs regardless of N clauses. The bottleneck would be embedding (one GPU forward pass per clause), which could take ~30 seconds for 500 clauses. For the prototype, `top_k=10` and `MAX_CANDIDATES=30` keep it fast.

**Q: "Why is `analyse_statutory()` always deterministic even in Gemini mode?"**
> Statutory rules like Section 27 ICA (non-compete void) are absolutely clear — there's no ambiguity. A regex check is faster, cheaper, and 100% reliable. Gemini would agree with the regex 100% of the time, so there's nothing to gain.

**Q: "What does `surfaced_by` tell you?"**
> It tells you which retrieval method found this pair. If a pair shows `["bm25", "type_matrix"]`, both BM25 (vocabulary overlap) and the conflict matrix (label pair) flagged it — that's a stronger signal than just one method. After Gemini analysis, the finding also gets `"gemini"` added to `surfaced_by`.

---

*Generated for panel preparation. All code references point to the live project at `legalagent/core/`.*
