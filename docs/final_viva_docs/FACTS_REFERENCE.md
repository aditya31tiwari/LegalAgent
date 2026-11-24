# Facts reference — every exact detail in one place

LEARNING.md explains *why and how*. This file lists the exact facts: labels, pairs, datasets, models, settings,
files, pages. Checked against the code on 25 Nov 2026 (`clause20/labels.yaml`, `legalagent/core/*.py`).

---

## 1. Clause labels: CLAUSE-22 (not 20 any more)

**Short answer:** 22 trained clause types + `other` (a catch-all) = 23 classifier outputs, plus 7 rule-based
Indian labels = 30 labels a clause can carry.

### 1.1 Why it changed from CLAUSE-20 to CLAUSE-22
CLAUSE-20 was the mid-term taxonomy. A research pass (`research/clause_taxonomy/`) found two problems:
- `dispute_resolution` mixed three different things → split out **`arbitration`** (A&C Act 1996 clashes: seat,
  venue, court vs arbitration) and **`remedies`** (Specific Relief Act, ICA s.28/s.74 clashes).
- `limitation_of_liability` wrongly contained CUAD "Liquidated Damages" → moved to remedies/payment;
  `compliance_and_law` contained M&A boilerplate → moved to `other`; LEDGAR "Applicable Laws" → `governing_law`.

**Rule for a label to exist:** it must be able to clash with another label (it appears in a clash pair) **and**
have ≥ 300 training examples after de-duplication.

### 1.2 The 22 trained labels (InLegalBERT predicts these)
| # | Label | Clause about |
|---|---|---|
| 1 | indemnification | one party compensates the other's losses |
| 2 | limitation_of_liability | caps / exclusions of liability |
| 3 | warranty | promises about quality / facts, disclaimers |
| 4 | termination | how and when the contract can be ended |
| 5 | term_and_renewal | duration, lock-in, auto-renewal |
| 6 | survival | what continues after termination |
| 7 | confidentiality | NDA obligations |
| 8 | ip_ownership | who owns IP / assignment |
| 9 | license_grant | right to use IP |
| 10 | assignment_change_of_control | transfer of the contract, change of owner |
| 11 | exclusivity_and_restraint | exclusivity, non-compete, non-solicit |
| 12 | payment_and_fees | price, invoices, payment terms |
| 13 | tax | GST, TDS, withholding, gross-up |
| 14 | governing_law | which law applies |
| 15 | dispute_resolution | courts / jurisdiction / escalation |
| 16 | arbitration | arbitration agreement, seat, arbitrator |
| 17 | remedies | damages, specific performance, exclusive remedy |
| 18 | audit_and_records | audit rights, record keeping |
| 19 | insurance | required insurance |
| 20 | notices | how notices must be given |
| 21 | amendment_and_integration | amendments, entire agreement |
| 22 | compliance_and_law | compliance with laws / regulators |
| — | other | everything else (never a clash type) |

### 1.3 The 7 rule-based Indian labels (`known_gaps`; keyword rules, not trained)
They matter for Indian/PPP contracts but have < 300 examples in CUAD + LEDGAR, so they are detected by keyword
rules in `classification.py` and excluded from classifier F1.

| Label | Triggered by words like | Law |
|---|---|---|
| force_majeure | force majeure, act of God | ICA s.56 |
| liquidated_damages | liquidated / pre-estimated / delay damages, penalty for delay | ICA s.74 |
| data_protection | personal data, DPDP, data fiduciary, privacy policy | DPDP Act 2023 |
| stamp_duty | stamp duty, unstamped, e-stamp, impounding | Indian Stamp Act s.35 |
| performance_security | performance security, bank guarantee, encashment | PPP model concession agreements |
| change_in_law | change in law, economic equilibrium | PPP model concession agreements |
| step_in_rights | step-in, substitution agreement, senior lenders | PPP model concession agreements |

Plus two helpers on top of the model: a **keyword backstop** (adds a label when the model misses an obvious one)
and a **heading prior** (a heading such as "ARBITRATION" adds that label).

### 1.4 The 40 clash pairs (type matrix used for shortlisting)
27 pairs of trained labels from `labels.yaml` + 13 pairs involving the rule labels (`KNOWN_GAP_PAIRS`).
The weight (0–1) is how risky the combination usually is; it is used to rank pairs.

| Pair | Weight | Typical problem |
|---|---|---|
| limitation_of_liability + indemnification | 0.90 | uncapped indemnity vs liability cap |
| limitation_of_liability + remedies | 0.85 | exclusive remedy / LD vs cap |
| arbitration + dispute_resolution | 0.85 | arbitration vs exclusive court jurisdiction |
| liquidated_damages + limitation_of_liability | 0.85 | LD vs cap |
| data_protection + limitation_of_liability | 0.85 | data breach liability vs cap |
| ip_ownership + license_grant | 0.80 | assignment vs licence of the same IP |
| governing_law + arbitration | 0.80 | substantive law vs seat |
| stamp_duty + arbitration | 0.80 | unstamped arbitration agreement |
| warranty + remedies | 0.75 | disclaimer + waiver of remedies |
| exclusivity_and_restraint + survival | 0.75 | non-compete surviving termination (ICA s.27) |
| step_in_rights + termination | 0.75 | lender step-in vs termination |
| limitation_of_liability + warranty, termination + term_and_renewal, exclusivity + license_grant, governing_law + dispute_resolution, confidentiality + compliance_and_law, LD + payment, data_protection + confidentiality, performance_security + termination, change_in_law + payment, step_in + assignment | 0.70 | … |
| indemnification + remedies, performance_security + LD, change_in_law + tax | 0.65 | … |
| termination + survival, survival + confidentiality, assignment + license, exclusivity + assignment, payment + tax, payment + remedies, amendment + payment, force_majeure + termination | 0.60 | … |
| force_majeure + payment | 0.55 | … |
| liability + insurance, termination + payment, assignment + confidentiality, payment + audit, compliance + warranty, amendment + warranty | 0.50 | … |
| amendment_and_integration + notices | 0.45 | written-notice formalities |

---

## 2. Datasets

| Dataset | What | Size | Used for |
|---|---|---|---|
| CUAD v1 | 510 US commercial contracts, 41 lawyer-labelled categories | 510 contracts | classifier training (mapped), CUAD interaction pairs, demo contract |
| LEDGAR (LexGLUE) | SEC contract provisions, 100 labels | ~80k provisions | classifier training (mapped) |
| CLAUSE-22 (ours, built from both) | de-duplicated, mapped to 22 labels | 74,374 clauses; split 55,915 / 9,341 / 8,415 + 703 out-of-domain | InLegalBERT training and test |
| Indian contracts | Pune Metro Line-3 concession (305-page scan), NHAI model concession (276-page scan), our 6 samples | 2 full PDFs + 6 MD | silver set (220 clauses), demo, end-to-end |
| Pune Metro injections | 15 irregularities we planted | 15 | end-to-end + clause-vs-law test |
| Teacher pairs | clause pairs labelled by Gemini 4 (1,740) and Claude Sonnet (620) via the Antigravity CLI | 2,360 | Kev training (silver), 172 held-out |
| Checklist | 28 bad/fixed clause-pair twins we wrote | 28 | judge test (catches + false alarms) |
| CUAD interaction pairs | pairs whose lawyer categories interact by definition (7 kinds × 40) | 280 | judge recall test |
| Supreme Court casebook | real clauses quoted in 18 SC judgments (13 struck down / 5 upheld) | 18 cases | clause-vs-law + statute retrieval test, demo |
| India Code (Open India Law mirror) + Nyaya datasets | central Acts, section text | 4,408 sections / 37 sources | statute RAG library |
| Retriever training pairs | clause↔clause 2,821 and clause↔section 2,967 | 5,788 | InLegal-SBERT fine-tuning |

### 2.1 Statute library: what is inside (sections per Act)
BNSS 2023 531 · Constitution 498 · Companies Act 2013 453 · BNS 2023 358 · IBC 2016 268 · **Indian Contract Act
1872 201** · CPC 1908 171 · BSA 2023 170 · Trade Marks 161 · Negotiable Instruments 156 · Patents 147 · Transfer of
Property 136 · IT Act 125 · Consumer Protection 2019 107 · **Arbitration & Conciliation 1996 102** · Copyright 87 ·
Industrial Disputes 79 · **Stamp Act 77** · Partnership 75 · Code on Wages 69 · Sale of Goods 67 · Mediation 2023 66 ·
Competition 56 · Limitation 53 · **DPDP 2023 45** · **Specific Relief 44** · FEMA 31 · POSH 30 · Commercial Courts 22 ·
MSMED 16 · plus 7 key court precedents stored as entries (on ICA s.27 restraint of trade, e.g. Percept D'Mark v.
Zaheer Khan; ICA s.74 penalties; ICA ss.124-125 indemnity; Stamp Act + arbitration (7-judge bench); A&C Act s.12(5)
arbitrator independence (5-judge bench); A&C Act s.20 seat; foreign seat for Indian parties, PASL Wind v. GE).
**Act prior:** contract-relevant Acts (ICA 1.0; Specific Relief, A&C, Sale of Goods 0.6; …) get a small boost
(0.004 in rank-fusion units), so a contract clause doesn't retrieve criminal-law sections.

---

## 3. Models

| Model | Base | Size | Trained by us? | Job | Where |
|---|---|---|---|---|---|
| InLegalBERT classifier | law-ai/InLegalBERT | 110 M params | yes: 3 epochs, lr 3e-5, batch 16, max 256 tokens, 48 min | clause → 22 labels | `models/clause20_inlegalbert` |
| MiniLM + logistic regression | all-MiniLM-L6-v2 | 22 M | yes (mid-term model) | baseline classifier | `models/clause20_labeller.joblib` |
| InLegal-SBERT (clauses) | bhavyagiri/InLegal-Sbert | 110 M | yes: 1 epoch, 2 min | clause↔clause search | `models/inlegal_sbert_clauses` |
| InLegal-SBERT (statutes) | bhavyagiri/InLegal-Sbert | 110 M | yes: 1 epoch, 1.3 min | clause→law search | `models/inlegal_sbert_statutes` |
| **Kev-0.8B** (judge in demo) | jaredpalmer/kev-0.8b (Qwen3.5-0.8B + pointer head) | 0.8 B | **no, base model zero-shot** (won on independent tests) | pair judge + clause-vs-law | Hugging Face cache |
| Kev v1 / v2 (fine-tuned) | Kev-0.8B + LoRA r=16 | +LoRA | yes: v1 43 min, v2 58 min | experiments (lost to base) | `models/kev_judge*` |
| GraphSAGE GNN | — | small | yes: 19 min | optional pair ranking | `models/clause_gnn.pt` |
| Teacher: Gemini 4 / Claude Sonnet | cloud | — | no | labelled training pairs (offline only) | — |
| Gemini Flash (Expand) | cloud | — | no | opt-in explanation button | — |
| Tesseract | OCR engine | — | no | scanned pages | system package |

---

## 4. What Kev is asked (exact questions)

**Pair judge** (`local_judge.py`): the state is both clauses (each cut to 1,200 characters, with their labels) and why they were paired.
1. **relation** (choice): conflict · dependency · overlap · ambiguity · no_issue (each with a one-line definition)
2. **severity** (score): low · medium · high
3. **statute** (choice): 4 retrieved India Code sections or "none"

Decision: highest probability (argmax). A calibrated threshold τ was tried (base 0.271, v2 0.378); the selected judge uses argmax.

**Clause vs law** (`statutory_kev.py`): one clause (2,000 chars), one question **risk** (choice) over 8 options →

| Option | Law it maps to |
|---|---|
| restraint_of_trade | ICA s.27 |
| penalty_or_forfeiture | ICA s.74 |
| restricts_legal_remedies | ICA s.28 |
| one_sided_arbitrator | A&C Act s.12 |
| termination_at_will | ICA s.23 |
| unstamped_or_invalid_form | Stamp Act s.35 |
| personal_data_without_consent | DPDP Act s.6 |
| none | — |

Shown if P(risk) = 1 − P(none) ≥ 0.30; label **high ≥ 0.70**, **medium ≥ 0.45**, else **low**. Checked for at most 150
clauses per contract, only clauses whose type can carry such a risk.

---

## 5. Settings (all defaults)

| Setting | Value | Where |
|---|---|---|
| Classifier threshold | 0.5 per label (ensemble 0.35) | classification.py |
| Retrieval neighbours per clause | top_k = 5 | pipeline config |
| Pair cap | all cross-reference pairs + 60 best others (ranked: signals agreeing → clash weight → retrieval rank) | candidate_selection.py |
| Rank fusion | RRF, k = 60 | retrieval.py / statutes.py |
| Statute options given to Kev | 4 | local_judge.py |
| Statute refs attached per finding | 2, confidence "medium" for rank 1, "low" after | statutes.py |
| Kev parallel requests | 2 (KEV_WORKERS), 3 tries per pair, a failing pair is skipped | local_judge.py |
| Kev server memory settings | no CUDA graphs, prefix cache 2 states / 6,000 tokens, expandable segments | start_demo.sh |
| Encoders' device in the demo | CPU (GPU kept for Kev) | start_demo.sh, LEGALAGENT_DEVICE |
| Gemini Expand | `.env` model first, then other Flash models; 1 try each, 15 s timeout; busy models skipped 10 min | gemini.py |

---

## 6. Pages, ports, commands

| Thing | Value |
|---|---|
| Dashboard | `http://<ip>:8080/app` |
| Under the hood | `/scores` (Document → clauses, Clause-pair scores, Finding explained, Results) |
| All comparisons + timings | `/report` (= `results/REPORT.html`) |
| Kev server | `127.0.0.1:8008` (local only) |
| Start / stop | `bash scripts/start_demo.sh` · `bash scripts/start_demo.sh stop` |
| Backend stage tables | `venv/bin/python scripts/show_steps.py <file>` |
| Rebuild results page | `venv/bin/python scripts/build_report.py` |
| Kev speed benchmark | `venv/bin/python scripts/bench_kev.py` |
| Tests | `venv/bin/python -m pytest -q tests clause20` (32 pass) |
| Database | SQLite `contracts.db`: contracts, clauses, findings, finding_details, graph_edges, clause_embeddings |
| Firewall for the other laptop | `sudo ufw allow 8080/tcp` |

## 7. Hardware / software
RTX 4050 Laptop GPU 6 GB · Ubuntu 26.04 · NVIDIA driver 595 · Python 3.12 (project) / 3.13 (Kev) · PyTorch with
CUDA · uv for environments · FastAPI + SQLite · vis-network (graph) + Chart.js (charts).

## 8. Key numbers (one line each)
Classifier 0.931 / 0.750 F1 · judge 71 % checklist, 75 % CUAD recall (rules 46 % / 7.5 %) · law check 6/9 SC
struck-down (regex 0/9) · statute R@5 0.32 (BM25 0.11) · teacher 92.9 % checklist, 85.7 % real citations, κ 0.57 ·
Kev 11.3 decisions/s, ~3,500 tokens read/s, 82 ms p50, 1.8 GB GPU · 305-page scan 4.4 min end to end.
