# LegalAgent — Master Documentation Index

> **The Central Navigation Hub & Entry Point for the LegalAgent Repository.**  
> Use this document to navigate the architecture, research, API specifications, benchmark suites, and live demonstration guides.

---

## 🗺️ Documentation Map by Purpose

Depending on what you want to achieve, start with the recommended entry document:

```
                                  [ INDEX.md ] (You are here)
                                         │
    ┌───────────────────┬────────────────┼───────────────────┬───────────────────┐
    ▼                   ▼                ▼                   ▼                   ▼
[ DEMO_GUIDE.md ] [ ARCHITECTURE_   [ CONTEXT.md ]   [ research/INDIAN_  [ PROJECT_MAP.md ]
• Live Panel Script    FLOW.md ]    • Design Rationale    LAW_RESEARCH.md ] • Complete File
• 10-Min Walkthrough • Dataflow & SBERT • System State   • Statutory Engine   Index & Lineage
• Q&A & Fallbacks   • Stage Pipelines • Component Roles • Case Law Citations • Database Tables
```

| Your Goal | Recommended Starting Document | Follow-Up Documents |
|:---|:---|:---|
| **Preparing for Panel Q&A & Future Roadmap** | [`PANEL_DEFENSE_AND_FUTURE_ROADMAP.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/PANEL_DEFENSE_AND_FUTURE_ROADMAP.md) | [`DEMO_GUIDE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/DEMO_GUIDE.md), [`research/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md) |
| **Deep Dive into Every File & Feature** | [`CODEBASE_EXPLANATION.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/CODEBASE_EXPLANATION.md) | [`PROJECT_MAP.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/PROJECT_MAP.md), [`ARCHITECTURE_FLOW.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/ARCHITECTURE_FLOW.md) |
| **Presenting to an Evaluation Panel** | [`DEMO_GUIDE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/DEMO_GUIDE.md) | [`research/04_ASSESSMENT_PROTOTYPE_SPEC.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/04_ASSESSMENT_PROTOTYPE_SPEC.md) |
| **Understanding the Core Architecture** | [`ARCHITECTURE_FLOW.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/ARCHITECTURE_FLOW.md) | [`CONTEXT.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/CONTEXT.md), [`README.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/README.md) |
| **Exploring the Codebase & Modules** | [`PROJECT_MAP.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/PROJECT_MAP.md) | [`docs/DATA_MODEL.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/DATA_MODEL.md), [`docs/API.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/API.md) |
| **Studying Indian Legal Reasoning** | [`research/INDIAN_LAW_RESEARCH.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/INDIAN_LAW_RESEARCH.md) | [`research/01_LEGAL_STATUTORY_RESEARCH.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/01_LEGAL_STATUTORY_RESEARCH.md) |
| **Evaluating NLP Models & Fine-Tuning** | [`research/02_MODEL_SELECTION_AND_BENCHMARKING.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/02_MODEL_SELECTION_AND_BENCHMARKING.md) | [`research/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md) |
| **Benchmarking & Testing Robustness** | [`data/demo/india/custom_benchmark/README.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/README.md) | [`data/demo/india/official/SOURCES.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/official/SOURCES.md) |
| **Handoff & Development State** | [`HANDOFF.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/HANDOFF.md) | [`UPDATE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/UPDATE.md), [`research/NEXT_STEPS.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/NEXT_STEPS.md) |

---

## 📚 Complete Markdown Directory

### 1. Operations & Explanation Hubs (`explanation/`)

* [`PANEL_DEFENSE_AND_FUTURE_ROADMAP.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/PANEL_DEFENSE_AND_FUTURE_ROADMAP.md)  
  Exhaustive viva defense guide: answers to hard panel questions (LLM hallucination, Indian law nuances, SBERT vs BGE, OCR, $O(N^2)$ candidate reduction), and complete Phase 2–4 roadmap (LoRA on 32.5M corpus, temporal models, GNNs).
* [`CODEBASE_EXPLANATION.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/CODEBASE_EXPLANATION.md)  
  Exhaustive in-depth and general technical explanations for every single file, module, algorithm, class, regex, endpoint, and feature in the project.
* [`README.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/README.md) *(Repository Root)*  
  High-level product pitch, philosophy of cross-clause analysis over single-clause classification, pipeline stages, and setup instructions.
* [`DEMO_GUIDE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/DEMO_GUIDE.md)  
  Step-by-step panelist presentation script (10–15 min demo + 5 min Q&A). Covers Contract 1 (Tech MSA), Contract 2 (NDA Non-Compete), Contract 3 (Pune Metro PPP), and Contract 4 (NHAI Highway), plus fallback fixes.
* [`PROJECT_MAP.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/PROJECT_MAP.md)  
  Exhaustive structural index of every file in the project, module responsibilities, SQLite schema summary, and key CLI commands.
* [`CONTEXT.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/CONTEXT.md)  
  System design context, component responsibilities, error diagnosis protocol, and immediate engineering roadmap.
* [`ARCHITECTURE_FLOW.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/ARCHITECTURE_FLOW.md)  
  Detailed end-to-end dataflow diagrams, InLegal-SBERT embedding sequence charts, runtime caching flow, and pipeline reading order.
* [`HANDOFF.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/HANDOFF.md)  
  Developer session state, current git branch status, commands to verify system health, and upcoming tasks.
* [`UPDATE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/explanation/UPDATE.md)  
  Chronological log of features built, architectural milestones reached, and resolved issues.

---

### 2. Architecture & System Specifications (`docs/`)

* [`docs/API.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/API.md)  
  REST and Server-Sent Events (SSE) API specification for the backend service (`web/backend.py`), including endpoint contracts, status codes, and JSON schemas.
* [`docs/DATA_MODEL.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/DATA_MODEL.md)  
  Relational SQLite data model (`contracts.db`) defining schemas for `contracts`, `clauses`, `graph_edges`, `findings`, and `clause_embeddings`.
* [`docs/CUAD.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/CUAD.md)  
  Evaluation notes on the Contract Understanding Atticus Dataset (CUAD) and the design decision to adapt beyond US-only contracts.
* [`docs/V0_PLAN.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/V0_PLAN.md)  
  Original foundation plan outlining the layered contract review architecture.

---

### 3. Legal Research & Machine Learning Strategy (`research/`)

* [`research/INDIAN_LAW_RESEARCH.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/INDIAN_LAW_RESEARCH.md)  
  Master research agenda covering the Indian Contract Act 1872, the 2023–2024 criminal/evidence reforms (BNS, BSA), DPDPA 2023, and the Mediation Act 2023.
* [`research/01_LEGAL_STATUTORY_RESEARCH.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/01_LEGAL_STATUTORY_RESEARCH.md)  
  Exhaustive legal analysis on Section 27 ICA (void non-competes), Sections 73–74 (liquidated damages vs. penalties), Sections 124–125 (indemnities), and the landmark 7-Judge Constitution Bench ruling on stamp duty.
* [`research/02_MODEL_SELECTION_AND_BENCHMARKING.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/02_MODEL_SELECTION_AND_BENCHMARKING.md)  
  Evaluation of embedding models (`InLegal-Sbert`, `bge-small`, `InLegalBERT`) and why Hierarchical Agglomerative Clustering replaces K-Means for contracts.
* [`research/03_CROSS_CLAUSE_GRAPH_AND_RISK_DETECTION.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/03_CROSS_CLAUSE_GRAPH_AND_RISK_DETECTION.md)  
  Mathematical formulation of contracts as directed attributed graphs $G=(V,E)$ and the 4-tier candidate reduction algorithm.
* [`research/04_ASSESSMENT_PROTOTYPE_SPEC.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/04_ASSESSMENT_PROTOTYPE_SPEC.md)  
  Panel presentation prototype specification, detailing interactive graph synchronization, color-coded relationships, and UI layout.
* [`research/05_EXISTING_PROJECTS_AND_COMPETITIVE_ANALYSIS.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/05_EXISTING_PROJECTS_AND_COMPETITIVE_ANALYSIS.md)  
  Competitive landscape analysis contrasting LegalAgent against Spellbook, Robin AI, Kira Systems, and academic datasets.
* [`research/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md)  
  Phase 2 training roadmap using LoRA/QLoRA on 32.5M Indian judgment chunks, including temporal era classifiers to detect anachronistic statutory references.
* [`research/NEXT_STEPS.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/research/NEXT_STEPS.md)  
  Prioritized roadmap covering pipeline unification, quantitative benchmark targets, and research deliverables.

---

### 4. Data Assets, Benchmarks & Contract Texts (`data/`)

* [`data/README.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/README.md)  
  Overview of contract data formats, OCR pipeline handling, and provenance of test fixtures.
* [`data/demo/india/custom_benchmark/README.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/README.md)  
  Description of the 3-contract regression test suite (liability conflict, void non-compete, and clean control).
* [`data/demo/india/official/SOURCES.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/official/SOURCES.md)  
  Official provenance and download metadata for Government of India PPP contracts (PMRDA Pune Metro Line III and NHAI BOT-Toll).
* [`data/raw/open-india-law-readme.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/raw/open-india-law-readme.md)  
  Documentation of the 32.5M open Indian court judgment corpus (`open-india-law`) earmarked for future domain adaptation.

#### Contract Markdown Extracts
* [`data/demo/india/indian_tech_msa_demo.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/indian_tech_msa_demo.md) — Synthetic Indian SaaS MSA.
* [`data/demo/india/official/pune_metro_signed_concession.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/official/pune_metro_signed_concession.md) — Official 2019 Pune Metro PPP Concession.
* [`data/demo/india/official/model_concession_4_laning.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/official/model_concession_4_laning.md) — Official NHAI BOT 4-laning model concession.
* [`data/demo/india/official/samples/pune_metro_first_20_pages.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/official/samples/pune_metro_first_20_pages.md) — 20-page test slice for OCR verification.

---

### 5. Agent Instructions & Knowledge Graph Rules (`.agents/`)

* [`.agents/rules/graphify.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/.agents/rules/graphify.md)  
  Operational instructions for navigating the local codebase knowledge graph (`graphify-out/`).

---

## ⚡ Quick Start Command Cheat-Sheet

```bash
# 1. Start Web Dashboard (port 8080)
venv/bin/python web/server.py

# 2. Run Automated Regression Benchmark Suite (3/3 contracts)
venv/bin/python scripts/run_custom_benchmark.py

# 3. Run Pytest Suite
venv/bin/python -m pytest -q

# 4. CLI Contract Analysis
venv/bin/python -m legalagent analyse data/demo/india/custom_benchmark/01_msa_cap_indemnity.txt --top-k 5

# 5. Convert Any PDF to Structured Markdown
venv/bin/python scripts/pdf_to_markdown.py input.pdf output.md

# 6. Re-seed SQLite Database to Factory Defaults
venv/bin/python -c "from legalagent.db import init_db, seed_database; init_db(); seed_database()"
```

