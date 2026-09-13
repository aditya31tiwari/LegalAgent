================================================================================
LegalAgent v0 — Contract Analysis Pipeline Architecture
================================================================================

GOAL: One thing only: a contract file goes in one end, a list of flagged
clause pairs with reasons comes out the other. Nothing in v0 needs to be good.
Everything in v0 needs to be connected.

PRINCIPLE: If a stage can be faked in under fifty lines, fake it. The purpose
is to surface integration problems while they cost an afternoon instead of
a fortnight.

================================================================================
DIRECTORY STRUCTURE
================================================================================

LegalAgent/
  ├── core/                        # Pipeline implementation
  │   ├── __init__.py              # Package export
  │   ├── types.py                 # Data shapes (final from day one)
  │   ├── ingestion.py             # PDF/DOCX/TXT → normalized_text
  │   ├── extraction.py            # Regex-based clause extraction
  │   ├── classification.py        # Keyword-based clause labeling
  │   ├── candidate_selection.py   # BM25 + xref + type_matrix
  │   └── pipeline.py              # Orchestration
  ├── tests/
  │   ├── fixtures/                # Test contracts (CUAD subset)
  │   └── test_pipeline.py         # Smoke test: end-to-end
  ├── README_ARCHITECTURE.txt      # This file
  ├── DATA_MODEL.md                # DB schema (to be implemented)
  ├── API.md                        # API spec (to be implemented)
  └── V0_PLAN.md                    # Original 12-day plan

================================================================================
DATA SHAPES (Core)
================================================================================

All three classes are FINAL. Field names match DB columns exactly and will
become database columns directly. No renaming anywhere in the v0→product path.

class Clause:
  ├── id: str                      # Public identifier (e.g., "acme_msa::5.2")
  ├── contract_id: str
  ├── number: str                  # "5.2", "(a)" — document numbering
  ├── heading: str                 # Section title
  ├── text: str                    # Full clause text
  ├── char_start: int              # Offset into normalized_text
  ├── char_end: int                # Offset into normalized_text
  ├── ordinal: int                 # Document order
  ├── labels: [{"label": "...", "confidence": 0.9, "source": "keyword"}]
  └── xrefs: [{"raw": "Section 8.2", "clause_id": "...", "resolved": true}]

class Finding:
  ├── id: str                      # Unique finding ID
  ├── target_clause_id: str        # Primary clause in conflict
  ├── related_clause_ids: [str]    # Supporting clauses
  ├── relation_type: str           # conflict | dependency | overlap | ambiguity | no_issue
  ├── severity: str                # low | medium | high
  ├── risk_score: float            # 0.0 — 1.0
  ├── rationale: str               # Why these clauses interact
  ├── surfaced_by: ["bm25", "type_matrix", ...]  # Detection method
  ├── evidence: [{"clause_id": "...", "start": 0, "end": 0}]  # Offsets only
  ├── refs: []                     # RAG sources (empty in v0)
  └── scores: {"retrieval": 0.62, "analysis_confidence": 0.88}

class Run:
  ├── id: str                      # Run identifier
  ├── contract_id: str
  ├── config: {"retrieval_method": "bm25", "top_k": 5}
  └── stats: {"clauses": 47, "pairs": 28, "findings": 6, "no_issue": 22}

================================================================================
PIPELINE STAGES (Current: Days 1–8)
================================================================================

1. INGESTION (Days 3–4)
   Input: File path (PDF, DOCX, TXT)
   Output: normalized_text (canonical document)
   Method: pdfplumber / python-docx / text read
   Processing:
     - Strip repeating headers/footers
     - Drop standalone page numbers
     - Rejoin hyphenated line breaks
     - Collapse whitespace, preserve paragraphs
   Guarantee: Same file → byte-identical output
   Location: core/ingestion.py

2. EXTRACTION (Days 5–6)
   Input: normalized_text
   Output: List[Clause] (flat, decimal numbering only)
   Method: Regex (^\s*(\d+(?:\.\d+)*)\s*\.?\s+)
   Features:
     - Decimal numbering: "5.2", "1.2.3" (not Roman or lettered)
     - Cross-reference detection: Section/Clause N.M
     - xref resolution: checked against extracted clauses
   Location: core/extraction.py

3. CLASSIFICATION (Day 7)
   Input: List[Clause]
   Output: List[Clause] with labels populated
   Method: Keyword dictionary (substring match, case-insensitive)
   Keywords: indemnification, limitation_of_liability, termination, etc.
   Confidence: 1.0 (keyword), will upgrade to LegalBERT in week 5
   Location: core/classification.py

4. CANDIDATE SELECTION (Day 8)
   Input: List[Clause], config
   Output: List[(clause_a_id, clause_b_id, ["bm25", "type_matrix", ...])]
   Methods (in order of contribution):
     a) BM25 scoring: top-k similar clauses per clause
     b) Cross-reference: if clause_a xrefs clause_b
     c) Type matrix: label pairs that commonly conflict
   Cap: ~30 pairs per contract (keep runs cheap)
   Location: core/candidate_selection.py

5. ANALYSIS (Day 9 — STUB)
   Input: Pair of clauses
   Output: Finding or None (no_issue)
   Status: Stubbed to return None
   Next: Replace with LLM call + validation
   Location: core/pipeline.py (analyse_pair_stub)

6. RISK SCORING (Day 10 — STUB)
   Input: Finding with relation_type
   Output: Finding with severity + risk_score
   Status: Lookup table (conflict → high/0.9, dependency → medium/0.6, etc.)
   Location: core/pipeline.py (stub)

7. EXPLANATION (Day 10 — STUB)
   Input: Finding
   Output: Finding.rationale populated
   Status: Template strings + model reason
   Next: Upgrade to retrieval-grounded explanations in week 10
   Location: core/pipeline.py (stub)

8. OUTPUT (Days 11–12)
   Input: Run, List[Clause], List[Finding]
   Output: JSON (GET /runs/{id}/findings response body, exactly)
   Ranking: severity then risk_score
   Format: Same field names and nesting as final API
   Location: (to be added: core/output.py)

================================================================================
KEY CONSTRAINTS (V0 Only)
================================================================================

✓ INGESTION: Built correctly from day one. Every char_start is precious.
✓ DATA SHAPES: Final from day one. No renaming in v0→product path.
✓ EVIDENCE: Offsets only, never text. Hallucinates fail validation.

✗ EXTRACTION: Decimal numbering only. Roman numerals / lettered sub-clauses
  are week 3.
✗ CLASSIFICATION: Keyword dictionary. Real model (LegalBERT) is week 5.
✗ RETRIEVAL: BM25 only. Dense / hybrid retrieval is week 6–7.
✗ LLM ANALYSIS: Stubbed. Real analysis + fact-checking is day 9.
✗ FRONTEND / API / DATABASE: Omitted. Add after v0 validates shapes.

================================================================================
RUNNING V0
================================================================================

1. Install dependencies:
   pip install pdfplumber python-docx

2. Run smoke test (validates all layers):
   python test_pipeline.py

3. Analyze a contract (command-line, no API yet):
   python -m core.pipeline <contract.pdf>  [--top-k 5] [--output run.json]

4. Expected output (end of week 2):
   Extracted  47 clauses
   Classified 31 (16 unlabelled)
   Candidates 28 pairs
   Analysed   28 → 6 findings, 22 no_issue

================================================================================
TESTING STRATEGY
================================================================================

Fixture: CUAD subset (acme_msa.pdf, sample_nda.txt, etc.)
Test: Smoke test validates all layers work end-to-end
  - Clauses extracted
  - Labels classified
  - Candidates selected
  - Evidence offsets resolve to text (no hallucination)
  - Run stats are consistent

No per-function unit tests in v0. One runnable check: test_smoke().

================================================================================
NEXT STEPS (After v0)
================================================================================

Week 3: Extraction v1 (Roman numerals, lettered sub-clauses, hierarchies)
Week 5: Classification v1 (LegalBERT fine-tuned on CUAD)
Week 6: Candidate selection v2 (Dense + hybrid retrieval)
Day 9: Analysis v1 (Claude API + structured JSON extraction + validation)
Week 10: Risk and explanation v2 (Retrieval-grounded rationale)
Weeks 11+: Database, API, frontend, evaluation

================================================================================
