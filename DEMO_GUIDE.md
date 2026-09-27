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

## Step 2 — Dashboard Overview (`/app`)

**What to say:**

> "The workspace has three resizable panels. On the left: the Clause Explorer. In the centre: the live knowledge graph. On the right: the Risk Findings and Statutory Audit panel."

**Quick orientation:**

- Drag the **dividers** between panels to resize — show this is interactive.
- Point to the **metrics bar** at the top: Clauses, Contradictions, Statutory Flags, Graph Edges.
- Note the **jurisdiction badge** next to the contract title.

---

## Step 3 — Demo Contract 1: Indian Tech MSA (IT/SaaS)

> *Best for showing the core cross-clause conflict detection.*

**Select**: "Indian Tech Services MSA (IT/SaaS)" in the dropdown (it loads by default).

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

## Step 5 — Demo Contract 3: Pune Metro PPP Concession (Real Indian Contract)

> *Best for showing that the system works on real Government of India contracts, not just synthetic data.*

**Select**: "Pune Metro Line III — PPP Concession (2019)" in the dropdown.

**What to say:**

> "This is a real signed concession agreement between the Pune Metropolitan Region Development Authority and Pune IT City Metro Rail Limited, sourced from the Government of India's PPP India portal. We have injected adversarial clauses — clauses that should not exist in a proper concession agreement — to test and demonstrate the detection engine."

**Actions:**

1. Point to the **graph**: three critical edges visible — a conflict (red), two statutory violations (purple).
2. Note **health score of 15/100** — lowest of all contracts.
3. Click the red edge between Clause 91.1 and 91.2: **"INR 1,000 Cap vs Unlimited Indemnity"**.
4. Right panel shows the finding: *"The aggregate liability of the Authority shall not exceed INR 1,000 — even for fraud, death, personal injury..."* — read this aloud.
5. Click the purple edge between 91.3 and 91.4: Section 27 ICA violation on the non-compete.
6. Click the third statutory finding: **DPDPA 2023** — the INR 10,000 cap on Data Protection Board penalties (actual penalties up to ₹250 Crore).

**Key talking point**: *"The system flagged three critical violations in a real signed government contract — two contractual conflicts and one DPDPA statutory violation — all from automatically reading the clause graph."*

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

## Step 7 — Live Custom Contract Analysis (Optional — impressive if it works)

> *Only do this if you have 3+ minutes remaining and confidence.*

Click **"New Contract"** in the header.

Paste this into the text box:

```
1.1 Limitation of Liability
The aggregate liability of the Company shall not exceed Rs. 10,000 (ten thousand rupees only) for any claim.

1.2 Indemnification
The Company shall indemnify and hold harmless the Client against all losses, fines, and penalties without any financial limitation whatsoever.

1.3 Post-Termination Restriction
For a period of 36 months after termination, the Contractor shall not engage in any competing business anywhere in India.

1.4 Governing Law
This Agreement is governed by the laws of India.
```

Set title: `"Live Demo Contract"`, jurisdiction: `"India"`.

Click **"Run Graph Analysis"**.

**What to say:**

> "The system is now running our full pipeline — clause extraction, BM25 retrieval, cross-clause pair analysis, and Indian statutory checks — in real time."

The new contract appears in the selector. Switch to it. Two findings appear automatically: liability cap vs uncapped indemnity, and the Section 27 non-compete violation.

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
