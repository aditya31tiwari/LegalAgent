# Next Steps & Project Execution Roadmap

## Phase 1: Prototype & Assessment Demonstration (Completed)
- [x] **Legal Framework Research:** Compiled statutory analysis on ICA 1872, DPDPA 2023, BSA 2023, BNS 2023, and the 7-Judge Stamp Ruling (`01_LEGAL_STATUTORY_RESEARCH.md`).
- [x] **Model Benchmarking & Strategy:** Documented pre-trained vs. fine-tuning strategy and density clustering (`02_MODEL_SELECTION_AND_BENCHMARKING.md`).
- [x] **Local Model Weights Cached & Verified:** Tested local CPU inference for `bhavyagiri/InLegal-Sbert` (768-dim) and `BAAI/bge-small-en-v1.5` (384-dim).
- [x] **Competitor & Academic Landscape:** Exhaustive competitive matrix comparing LegalAgent to Robin AI, Spellbook, Kira, and CUAD (`05_EXISTING_PROJECTS_AND_COMPETITIVE_ANALYSIS.md`).
- [x] **SQLite3 Storage Engine:** Created `contracts.db` with relational schema storing contracts, clauses, graph edges, and risk findings (`legalagent/db.py`).
- [x] **Lorem Ipsum Synthetic Test Case:** Added synthetic Latin legal instrument to test graph layout and stress-test conflict detection.
- [x] **Interactive Web Prototype:** Built visually appealing 3-panel UI with Vis.js force-directed graph, bidirectional node/clause highlighting, and live REST API (`web/index.html` & `web/server.py`).

---

## Phase 2: Immediate Next Steps for Assessment Presentation

### 1. Rehearse Assessment Panel Walkthrough (10-Minute Script)
* **Minute 0–2: Problem Statement**
  * Demonstrate why single-clause tools fail (show Clause 8 Liability Cap).
* **Minute 2–5: The Cross-Clause Graph Innovation**
  * Show the interactive network graph. Highlight how Section 8 is linked to Section 12 (Indemnity) and turns red (**High Severity Conflict**).
* **Minute 5–7: Indian Law Specificity**
  * Switch to Contract 2 (Employment Agreement) and Contract 1 (IT MSA).
  * Show the pink statutory red flag: **Post-termination non-compete void under Section 27 ICA 1872** and **DPDPA ₹250 Cr fine cap attempt**.
* **Minute 7–8: Synthetic Stress Testing (Lorem Ipsum)**
  * Switch to Contract 4 (Lorem Ipsum) to prove the graph and candidate selection architecture functions structurally even on novel/unseen formats.
* **Minute 8–10: Architectural Defense & Q&A**
  * Explain the $0 local CPU stack (`InLegal-Sbert` + SQLite + Density Clustering) and zero reliance on expensive third-party APIs.

---

## Phase 3: Core Pipeline Refactor & Pipeline Unification

- [ ] **Connect Live Pipeline to SQLite:**
  * Connect `legalagent/core/pipeline.py` to write its output directly to `contracts.db` when a user uploads a new raw PDF/DOCX file.
- [ ] **Integrate `InLegal-Sbert` in Candidate Selection:**
  * Replace the BM25-only stub in `legalagent/core/candidate_selection.py` with hybrid dense retrieval (`InLegal-Sbert` + BM25Okapi).
- [ ] **Statutory Deterministic Rule Engine:**
  * Implement `legalagent/rules/indian_statutes.py` containing deterministic regex & semantic filters for Sections 27, 74, and DPDPA violations.

---

## Phase 4: Quantitative Evaluation & Research Paper Deliverables

- [ ] **Indian Commercial Contract Benchmark (ICCB):**
  * Curate 30–50 open Indian commercial agreements.
- [ ] **Precision@K & Recall@K Benchmarks:**
  * Compare BM25 vs. Dense (`InLegal-Sbert`) vs. Dense (`bge-small`) vs. Hybrid on gold-standard cross-reference retrieval.
- [ ] **Panel Viva Defense Guide:**
  * Compile FAQ on computational complexity, false positive rates, and why K-Means was rejected.
