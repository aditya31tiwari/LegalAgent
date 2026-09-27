# LegalAgent — Master Project Documentation Index

> **START HERE**: This is your central starting point for the LegalAgent project.  
> Follow the **Recommended 5-Step Reading Order** below. If you read these documents in sequence, you will achieve a 100% comprehensive understanding of the legal concepts, the contract structures, the code architecture, the demo workflow, and how to defend the system before an evaluation panel.

---

## The Master 5-Step Reading Curriculum

Follow this structured learning pathway to understand the entire project:

```
[Step 1: Legal Foundations]
CONTRACT_STRUCTURE_AND_LEGAL_GUIDE.md
  |  (Understand what contracts are, articles vs clauses,
  |   and Indian statutory rules: Sec 27 ICA, Sec 74 LD, DPDPA 2023, Stamp Act)
  v
[Step 2: Architecture & Codebase Deep-Dive]
ARCHITECTURE_FLOW.md -> CODEBASE_EXPLANATION.md
  |  (Understand the G=(V,E) graph, 8-stage pipeline, InLegal-SBERT,
  |   and exact file-by-file technical explanations)
  v
[Step 3: Live Panel Presentation & Walkthrough]
DEMO_GUIDE.md
  |  (Step-by-step presentation script, server commands,
  |   and actual paths to all 6 verified sample contracts)
  v
[Step 4: Panel Defense & Viva Q&A]
PANEL_DEFENSE_AND_FUTURE_ROADMAP.md
  |  (Hard questions: LLM hallucination, O(N^2) reduction, InLegal-SBERT vs BERT,
  |   and Phase 2–4 LoRA fine-tuning on 32.5M judgments)
  v
[Step 5: Structural Directory]
PROJECT_MAP.md
  |  (Every file, folder, SQLite table, and CLI command indexed)
```

---

## Summary Matrix: Which Document to Open

| Step | Your Objective | Primary Document | What You Will Learn |
|:---:|:---|:---|:---|
| **1** | **Understand Contracts & Indian Law** | [`CONTRACT_STRUCTURE_AND_LEGAL_GUIDE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/CONTRACT_STRUCTURE_AND_LEGAL_GUIDE.md) | What are articles, clauses, provisos, and recitals; Indian Contract Act (Sec 23, 27, 74, 124/125), DPDPA 2023, Mediation Act 2023, and Stamp Act rules. |
| **2** | **Understand the Core Architecture** | [`ARCHITECTURE_FLOW.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/ARCHITECTURE_FLOW.md) | End-to-end dataflow diagrams, graph building, candidate filtering, and InLegal-SBERT embedding pipeline. |
| **2b** | **Deep-Dive into Every Source File** | [`CODEBASE_EXPLANATION.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/CODEBASE_EXPLANATION.md) | Exhaustive, file-by-file, function-by-function technical breakdown of all 22 Python, JS, and HTML modules. |
| **3** | **Presenting Live to the Panel** | [`DEMO_GUIDE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/DEMO_GUIDE.md) | 10–15 min step-by-step script, server commands, live upload instructions, and actual paths to all 6 verified sample contracts. |
| **4** | **Defending Viva / Tough Questions** | [`PANEL_DEFENSE_AND_FUTURE_ROADMAP.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/PANEL_DEFENSE_AND_FUTURE_ROADMAP.md) | Concrete answers to challenging panel questions, benchmark metrics, and LoRA/temporal fine-tuning research roadmap. |
| **5** | **Looking up Any File or Module** | [`PROJECT_MAP.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/PROJECT_MAP.md) | Exhaustive repository directory, module duties, SQLite schema summary, and CLI commands. |

---

## Detailed Directory by Knowledge Domain

### 1. Master Explanation Hub (`tests/old_examples/docs/`)

* [`CONTRACT_STRUCTURE_AND_LEGAL_GUIDE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/CONTRACT_STRUCTURE_AND_LEGAL_GUIDE.md)  
  **The legal foundation**: Explains contract anatomy (preamble, recitals, articles, clauses, provisos, boilerplate, execution), the 4 project contract archetypes (PPP DBFOT, Tech MSA, Executive NDA, Vendor Supply), and the 7 key Indian legal doctrines (Sec 27 void non-competes, Sec 74 penalties vs liquidated damages, liability cap vs indemnity clashes, DPDPA 2023 ₹250 Cr penalties, Mediation Act 2023, BNS 2023 vs IPC 420, and the SC 7-Judge stamp duty bench).
* [`DEMO_GUIDE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/DEMO_GUIDE.md)  
  **The presentation manual**: Step-by-step panelist presentation script (10–15 min demo + 5 min Q&A). Includes server commands, live manual upload workflow, side-by-side comparator instructions, and actual absolute file paths to all verified contract samples.
* [`PANEL_DEFENSE_AND_FUTURE_ROADMAP.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/PANEL_DEFENSE_AND_FUTURE_ROADMAP.md)  
  **The viva defense guide**: Defends against tough panel critiques (why not standard GPT-4, why InLegal-SBERT, how $O(N^2)$ candidate pairs are pruned by 85–92%, how OCR noise is handled, and the multi-phase roadmap for LoRA fine-tuning on 32.5M Indian judgment chunks).
* [`CODEBASE_EXPLANATION.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/CODEBASE_EXPLANATION.md)  
  **The technical reference**: Exhaustive, file-by-file technical explanations for every single Python module, REST endpoint, regex pattern, database query, and UI component in the repository.
* [`ARCHITECTURE_FLOW.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/ARCHITECTURE_FLOW.md)  
  **The system diagrams**: ASCII and conceptual flowcharts showing the 8-stage ingestion-to-graph pipeline, embedding sequence charts, and runtime caching mechanism.
* [`PROJECT_MAP.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/PROJECT_MAP.md)  
  **The structural index**: Complete directory of every file in the project, database schemas, and CLI operations.
* [`CONTEXT.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/CONTEXT.md)  
  High-level system design philosophy and historical design decisions.
* [`HANDOFF.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/HANDOFF.md)  
  Session state, git branch tracking (`aryan-sethi`), and verification commands.
* [`UPDATE.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/UPDATE.md)  
  Chronological log of milestones achieved and bugs resolved.

---

### 2. Verified Sample Contracts for Manual Review (`data/demo/samples/`)

All broken/garbled OCR conversions from scanned PDFs have been permanently removed. Use these 6 pristine, human-verified, clean contract instruments for manual review, panel inspection, or live upload testing:

1. **Pune Metro PPP (Clean Baseline Concession)**:  
   [`data/demo/samples/01_pune_metro_concession_baseline.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/01_pune_metro_concession_baseline.md)  
   *Authentic 2019 concession agreement baseline across 13 core DBFOT articles without adversarial additions.*
2. **Pune Metro PPP (15 Adversarial Injections)**:  
   [`data/demo/samples/02_pune_metro_adversarial_15_injections.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/02_pune_metro_adversarial_15_injections.md)  
   *The complete concession agreement with Article 91 (all 15 synthetic adversarial test clauses) appended.*
3. **Indian Tech Services Master Services Agreement (IT/SaaS)**:  
   [`data/demo/samples/03_indian_tech_services_msa.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/03_indian_tech_services_msa.md)  
   *Complete SaaS agreement featuring liability cap vs uncapped IP indemnity, DPDPA 2023 statutory cap, and Mediation Act exclusion.*
4. **Executive Employment & Restrictive Covenants Agreement**:  
   [`data/demo/samples/04_executive_employment_agreement.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/04_executive_employment_agreement.md)  
   *Executive contract featuring a void 24-month post-termination non-compete under Section 27 ICA.*
5. **Commercial Vendor Supply & Procurement Agreement**:  
   [`data/demo/samples/05_commercial_vendor_supply_agreement.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/05_commercial_vendor_supply_agreement.md)  
   *Commercial procurement agreement featuring Section 74 punitive liquidated delay damages and Maharashtra Stamp Act impounding validity.*
6. **NHAI Model Concession Agreement (4-Laning Highway BOT-Toll)**:  
   [`data/demo/samples/06_nhai_highway_concession_agreement.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/samples/06_nhai_highway_concession_agreement.md)  
   *Model BOT highway concession demonstrating well-drafted liquidated damages and asymmetric termination compensation ratios.*

#### Regression Benchmarks
* [`data/demo/india/custom_benchmark/01_msa_cap_indemnity.txt`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/01_msa_cap_indemnity.txt)
* [`data/demo/india/custom_benchmark/02_employment_non_compete.txt`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/02_employment_non_compete.txt)
* [`data/demo/india/custom_benchmark/03_clean_services_control.txt`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/03_clean_services_control.txt)
* [`data/demo/india/custom_benchmark/MANIFEST.json`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/custom_benchmark/MANIFEST.json)
* [`data/demo/india/adversarial/INJECTIONS.json`](file:///home/aryan/Projects/LegalAgent/LegalAgent/data/demo/india/adversarial/INJECTIONS.json)

---

### 3. Architecture & System Specifications (`docs/`)

* [`docs/API.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/API.md) — REST and Server-Sent Events (SSE) API specification (`web/backend.py`).
* [`docs/DATA_MODEL.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/DATA_MODEL.md) — SQLite schema documentation (`contracts.db`).
* [`docs/CUAD.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/CUAD.md) — Evaluation of the CUAD dataset and why Indian law adaptation is necessary.
* [`docs/V0_PLAN.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/docs/V0_PLAN.md) — Initial project milestone blueprint.

---

### 4. Legal Research & Machine Learning Strategy (`tests/old_examples/docs/`)

* [`INDIAN_LAW_RESEARCH.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/INDIAN_LAW_RESEARCH.md) — Master statutory research foundation.
* [`01_LEGAL_STATUTORY_RESEARCH.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/01_LEGAL_STATUTORY_RESEARCH.md) — Deep legal analysis of ICA 1872, DPDPA 2023, and landmark case law.
* [`02_MODEL_SELECTION_AND_BENCHMARKING.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/02_MODEL_SELECTION_AND_BENCHMARKING.md) — Benchmark comparison of InLegal-SBERT vs general-domain embedding models.
* [`03_CROSS_CLAUSE_GRAPH_AND_RISK_DETECTION.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/03_CROSS_CLAUSE_GRAPH_AND_RISK_DETECTION.md) — Graph formulation $G=(V,E)$ and candidate reduction mathematics.
* [`04_ASSESSMENT_PROTOTYPE_SPEC.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/04_ASSESSMENT_PROTOTYPE_SPEC.md) — Original prototype specification for panel assessment.
* [`05_EXISTING_PROJECTS_AND_COMPETITIVE_ANALYSIS.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/05_EXISTING_PROJECTS_AND_COMPETITIVE_ANALYSIS.md) — Competitive analysis contrasting LegalAgent with US/UK legaltech tools.
* [`06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md`](file:///home/aryan/Projects/LegalAgent/LegalAgent/tests/old_examples/docs/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md) — Future training plan for LoRA fine-tuning on 32.5M Indian judgment chunks.

---

## Quick Start Command Reference

```bash
# Start Web Server (Dashboard at :8080/app, Injections at :8080/injections)
venv/bin/python web/server.py

# Run Automated Regression Benchmark Suite (3/3 contracts pass)
venv/bin/python scripts/run_custom_benchmark.py

# Run Pytest Suite
venv/bin/python -m pytest -q

# CLI Pipeline Analysis on Any Contract File
venv/bin/python -m legalagent analyse data/demo/samples/03_indian_tech_services_msa.md --output runs/demo.json
```
