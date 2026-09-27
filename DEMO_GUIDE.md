# LegalAgent — Panelist Demo Guide

> **Audience**: Assessment panel presentation.
> **Duration**: Aim for 10–15 minutes of live demo + 5 minutes Q&A.
> **Server must be running before you walk in.** See Step 0.

---

## Step 0 — Pre-Demo Setup (do this 5 minutes before)

Open a terminal:

```bash
cd /home/aryan/Projects/LegalAgent/LegalAgent
venv/bin/python web/server.py
```

You should see:

```
⚖️  LegalAgent Enterprise Intelligence Engine
🌐  Web Application  : http://localhost:8080
📚  Swagger REST API : http://localhost:8080/docs
🗄️  SQLite Database  : contracts.db
```

Open two browser tabs:
- `http://localhost:8080` — landing page
- `http://localhost:8080/app` — the main dashboard

---

## Step 1 — Open the Landing Page (`/`)

**What to say:**

> "This is LegalAgent — an AI-powered Indian contract review system. Unlike standard legaltech tools that check one clause at a time, our engine maps the *relationships between clauses* as a knowledge graph. It then detects cross-clause contradictions, statutory violations under Indian law, and risks that only emerge when two clauses are read together."

**Point out on the page:**

- The **three core differentiators** in the feature grid: Cross-Clause Graph, Indian Compliance Engine, Contradiction Detection.
- The **4-step pipeline diagram**: Upload → Extract & Classify → Graph Analysis → Findings & Audit.
- The **Indian Statutes** section listing ICA 1872, DPDPA 2023, BNS 2023, Mediation Act 2023, IBC 2016.
- Click **"Open Dashboard"** to move to the app.

---

## Step 2 — Dashboard & Contract Portfolio Overview (`/app`)

**What to say:**

> "The workspace gives lawyers and auditors an intuitive 3-panel command centre. In the header, clicking **'Contracts (6)'** opens our **Contract Portfolio Drawer**."

**Actions:**

1. Click **"Contracts (6)"** in the top navigation bar.
2. The slide-out portfolio drawer appears on the left, displaying all uploaded contracts:
   - **Health Score Badge** (green 88 for well-drafted NHAI, red 15 for high-risk Pune Metro, red 26 for Tech MSA).
   - Clause counts, jurisdiction tags, and critical risk counts.
   - Click any contract in the list to switch immediately into it.
3. Close the drawer (click ✕ or backdrop).
4. Point out the **three resizable panels**:
   - **Left Panel:** Clause Explorer (expandable clause cards, sequential full-text view).
   - **Centre Panel:** Vis.js Interdependent Knowledge Graph `G=(V,E)` with interactive physics.
   - **Right Panel:** Risk Findings & Statutory Audit Dossier.
5. Drag the **panel dividers** to demonstrate responsiveness.

---

## Step 3 — Demo Contract 1: Indian Tech MSA (IT/SaaS)

> *Best for showing the core cross-clause conflict detection.*

**Select**: "Indian Tech Services MSA (IT/SaaS)" in the dropdown (or from the Contracts Drawer).

**What to say:**

> "This is a Master Services Agreement drafted for an Indian SaaS vendor. It has a classic trap: Section 8.1 caps all liability at ₹15 Lakhs, but Section 12.1 mandates unlimited IP indemnification — with no exclusion carveout. These two clauses directly conflict."

**Actions:**

1. In the **left panel** click **Section 8.1 (Limitation of Liability)** — the graph highlights and focuses on that node.
2. Click the **red edge** between node 8.1 and 12.1 labelled "CONFLICT: Cap vs Indemnity" — the right panel **auto-scrolls** to the matching finding card with a copper ring highlight.
3. Read aloud the **Statutory Authority** box: *"Indian Contract Act, 1872 (Sections 124–125): Indemnity is a primary obligation..."*
4. Click **"Read more"** on any clause card to expand the full text.
5. Click **"View Full"** (top of left panel) to open the **Full Contract Viewer modal** — shows all clauses as a scrollable document.
6. Click **"Export Audit"** to generate the executive Legal Risk Memorandum — copy to clipboard.

**Key stat to mention**: Health Score = 26/100 (critically risky contract).

---

## Step 4 — Demo Contract 2: Executive Employment NDA

> *Best for showing Indian statutory law detection.*

**Select**: "Executive Employment (Non-Compete)" in the dropdown.

**What to say:**

> "This is an executive employment contract. It has a 24-month post-termination non-compete clause. Under Indian law, this is void *ab initio* — completely unenforceable from the moment it's signed — under Section 27 of the Indian Contract Act, 1872. This is fundamentally different from UK or US law, where reasonableness tests apply."

**Actions:**

1. Point to the **purple statutory edge** between Section 8.1 and Section 11.1.
2. Click the edge — right panel highlights the **"Post-Termination Non-Compete is Void Ab Initio"** finding.
3. Read the **Statutory Authority**: *"Percept D'Mark (India) Pvt. Ltd. v. Zaheer Khan (2006) 4 SCC 227 — Supreme Court confirmed all post-employment non-competes are void under Indian law."*
4. Read the **Recommended Amendment**: *"Delete the post-termination non-compete restriction. Rely instead on non-disclosure of trade secrets and non-solicitation..."*

---

## Step 5 — Demo Contract 3: Pune Metro PPP Concession & Adversarial Injections

> *Best for showing that the system works on real Government of India contracts, not just synthetic data.*

**What to say:**

> "This is a real signed concession agreement between the Pune Metropolitan Region Development Authority and Pune IT City Metro Rail Limited, sourced from the Government of India's PPP India portal. We have injected 15 adversarial clauses to test our detection engine against classical single-clause LLMs."

**Actions:**

1. Select **"Pune Metro Line III — PPP Concession (2019)"** in the dropdown.
2. Point to the **graph**: three critical edges visible — a conflict (red), two statutory violations (purple).
3. Note **health score of 15/100** — lowest of all contracts.
4. Click the red edge between Clause 91.1 and 91.2: **"INR 1,000 Cap vs Unlimited Indemnity"**.
5. Click the purple edge between 91.3 and 91.4: Section 27 ICA violation on the non-compete.
6. Click the third statutory finding: **DPDPA 2023** — the INR 10,000 cap on Data Protection Board penalties (actual penalties up to ₹250 Crore).
7. Now click **"⚡ Injections"** in the top navigation bar (or open `http://localhost:8080/injections`).
8. Walk through the **Adversarial Injections Dossier**:
   - Show the **official provenance card** (PMRDA signed 2019 concession agreement, Government of India PPP portal).
   - Point out the **Methodology Comparison**: why isolated single-clause LLMs miss the trap vs how LegalAgent's GraphRAG captures it.
   - Show the **15 Injected Clauses cards** and use the filter buttons (`All`, `Detected in Demo`, `Statutory Violations`, `Roadmap Expansion`).
   - Highlight the **Master Adversarial Matrix table** at the bottom.

---

## Step 6 — Demo Contract 4: NHAI Highway Concession (Well-Drafted Contrast)

> *Best for showing nuanced analysis — not everything is "bad".*

**Select**: "NHAI 4-Laning Highway Concession (BOT-Toll)" in the dropdown.

**What to say:**

> "For contrast, this is the Government of India's model BOT highway concession — a well-drafted agreement. Watch how the findings change."

**Actions:**

1. Note the **health score is 88/100** — the highest after the clean control.
2. Show the **green semantic edges** (well-structured indemnity carveout from the cap).
3. The two findings are **medium severity** — no critical red flags. Findings focus on asymmetric termination payment terms and LD rate evidence.
4. Contrast with the Pune Metro findings — shows the system can distinguish genuinely risky contracts from well-drafted ones.

---

## Step 7 — LIVE MANUAL UPLOAD: Real-Time Pipeline Streaming (The Showstopper!)

> *Show this to the panel to prove live, working end-to-end functionality.*

**What to say:**

> "Now let me demonstrate uploading a contract live in front of you. Watch our pipeline process the document in real time across all seven stages — from text normalization, clause extraction, BM25 candidate selection, cross-clause reasoning, to Indian statutory compliance auditing."

**Actions:**

1. Click **"Upload / Analyze"** in the top navigation bar.
2. The **Live Contract Analysis Modal** opens.
3. Show the options:
   - **Option A (Instant Demo):** Click the button: **`⚡ Insert Sample Contract with Planted Traps`**. It instantly pre-populates a realistic Indian Cloud & IT MSA with:
     - 7.1 Illegal DPDPA ₹25,000 Penalty Cap
     - 8.1 Aggregate Liability Cap (₹5 Lakhs)
     - 12.1 Uncapped IP Indemnity (direct clash with 8.1)
     - 15.3 24-Month Non-Compete Restraint (void under Sec 27 ICA)
     - 18.2 Dispute Resolution excluding Mediation Act 2023
   - **Option B (File Upload):** Drag-and-drop any `.txt` or `.md` contract file into the dropzone.
4. Click **"Run Live Analysis"**.
5. **Watch the live streaming feed:**
   - Real-time elapsed timer counts up in seconds (`0.24s`, `0.65s`, `1.12s`...).
   - The progress bar smoothly fills from 0% to 100%.
   - Each pipeline stage activates with a pulsing indicator, updates its detail message with exact counts, and turns into a green checkmark `✓`:
     1. `📄 Contract Ingestion` (character count)
     2. `⚙️ Text Normalization` (canonical formatting)
     3. `📑 Clause & Offset Extraction` (found 7 numbered clauses)
     4. `🏷️ Classification & Tagging` (Indemnity, Liability, High Risk, DPDPA)
     5. `🔍 Candidate Pair Shortlisting` (BM25 + TYPE_MATRIX pairs)
     6. `⚡ Cross-Clause Conflict Analysis` (detected cap vs indemnity conflict)
     7. `⚖️ Indian Statutory Compliance Audit` (Sec 27 ICA void non-compete)
     8. `🗄️ Knowledge Graph Storage` (saved to SQLite)
6. The green **"Analysis Complete — Contract Graph Ready"** card appears with live metrics:
   - Clauses: 7
   - Critical Flags: 2
   - Total Findings: 2
   - Pairs Examined: 4
7. Click **"View Contract Graph →"** (or let it auto-transition after 2 seconds).
8. The modal closes, the newly analyzed contract is automatically loaded, and the interactive knowledge graph is rendered live in the center panel!
9. Open the **"Contracts (6+)"** drawer to show the new contract has been persisted into the SQLite database.

---

## Step 8 — Show the Technical Pipeline (if asked)

Run in a second terminal while keeping the browser open:

```bash
cd /home/aryan/Projects/LegalAgent/LegalAgent
venv/bin/python -m legalagent analyse data/demo/india/custom_benchmark/01_msa_cap_indemnity.txt --contract-id demo-live --output runs/demo/live.json
cat runs/demo/live.json
```

**What to say:**

> "Under the hood, the CLI runs the same seven-stage pipeline: ingestion, extraction, classification, candidate selection using BM25 and InLegal-SBERT embeddings, cross-clause analysis, statutory checking, and validated output. The web dashboard and the CLI share exactly the same core engine."

---

## Step 9 — Run the Regression Benchmark (if asked about reliability)

```bash
venv/bin/python scripts/run_custom_benchmark.py
```

Expected output:

```
[PASS] 01_msa_cap_indemnity.txt:       expected=['cross_clause_conflict'] detected=['cross_clause_conflict']
[PASS] 02_employment_non_compete.txt:  expected=['section_27_statutory_violation', 'termination_survival_dependency'] ...
[PASS] 03_clean_services_control.txt:  expected=[] detected=[]
```

**What to say:**

> "We have a regression benchmark with three planted contracts — a liability conflict, a non-compete violation, and a clean control with no issues. The system passes 3/3 with zero false positives on the clean contract."

---

## Likely Panelist Questions & Answers

| Question | Answer |
|:---------|:-------|
| "Is this legal advice?" | No — explicitly a research prototype. All findings are clearly labelled as AI-generated risk flags for lawyer review. |
| "What model does it use?" | InLegal-SBERT (`bhavyagiri/InLegal-Sbert`) — 768-dim embeddings trained on Indian court judgments. Candidate pair retrieval uses BM25 + dense embedding similarity. Analysis is deterministic rule-based (not LLM hallucination). |
| "Can it handle PDF contracts?" | Yes — PyMuPDF extracts text; Tesseract OCR handles scanned PDFs. Try: `venv/bin/python scripts/pdf_to_markdown.py data/demo/india/official/pune_metro_signed_concession.pdf /tmp/out.md` |
| "How does the graph work?" | Clause nodes are connected by typed edges: `conflict` (red), `statutory` (purple), `xref` (blue), `semantic` (green). The graph topology reveals which clauses interact. |
| "What Indian laws are encoded?" | ICA 1872 (Sections 27, 73, 74, 124/125), DPDPA 2023, BNS 2023 (replaces IPC), Mediation Act 2023, IBC 2016. |
| "What's next / future work?" | Fine-tune InLegal-SBERT with LoRA adapters on open-india-law dataset (32.5M judgment chunks). Build temporal era models to detect IPC→BNS anachronisms in older contracts. See `research/06_FINE_TUNING_AND_TEMPORAL_MODEL_PLAN.md`. |
| "Why not use GPT-4/Claude?" | Deterministic rules give explainable, auditable evidence trails — critical for legal contexts. Gemini is integrated and available for pair analysis (see `legalagent/core/gemini.py`) as the next planned step. |

---

## Fallback If Something Breaks

| Problem | Fix |
|:--------|:----|
| Server not running | `venv/bin/python web/server.py` from project root |
| Port 8080 in use | `pkill -9 -f uvicorn` then restart |
| DB is empty / contracts not loading | `venv/bin/python -c "from legalagent.db import init_db, seed_database; init_db(); seed_database()"` then restart server |
| Graph not rendering | Refresh browser; check browser console for Vis.js errors |
| Custom analysis fails | Pipeline falls back to heuristic automatically — you will still get results |

