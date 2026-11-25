# Learn everything — exact facts + every concept from zero

One file to open and learn the whole project.
- **Part 1 (§1–8): exact facts.** Labels, clash pairs, datasets, models, Kev's questions, settings, pages, numbers.
  Checked against the code on 25 Nov 2026.
- **Part 2 (§9–30): every concept explained from zero.** For each idea: what it is in plain words, how it works,
  a tiny example, where we use it, and a one-line viva answer. Start with Part 2 if a word in Part 1 is unfamiliar.

| Part 2 contents | |
|---|---|
| 9 PDFs, text layers, PyMuPDF, OCR | 20 GNN / GraphSAGE (in detail) |
| 10 Regex, clause extraction, cross-references | 21 LLMs vs decision models: Kev, pointer head |
| 11 Tokens | 22 Zero-shot, fine-tuning, LoRA |
| 12 How a neural network learns | 23 GPU memory: bf16, checkpointing, OOM, CUDA graphs |
| 13 Transformers, attention, BERT, InLegalBERT | 24 Class imbalance, focal loss, thresholds |
| 14 Multi-label classification | 25 Teacher–student distillation, silver/gold, κ |
| 15 Embeddings, cosine similarity, SBERT | 26 Metrics (precision … ROC-AUC) |
| 16 Contrastive fine-tuning (MNRL) | 27 Evaluation design: held-out, OOD, ablation, leakage |
| 17 BM25 | 28 The Indian law we use |
| 18 Hybrid search, RRF, rerankers | 29 Web side: API, FastAPI, SSE, SQLite, LAN, firewall |
| 19 RAG | 30 Putting it together: one clause's journey |

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

---
---

# PART 2 — Every concept from zero

Format for each: **What** (plain words) · **How** (mechanism) · **Example** · **In our project** · **Viva line**.

## 9. PDFs, text layers, PyMuPDF, OCR
**What.** A PDF page is either *digital* (it contains the actual characters, a "text layer") or *scanned* (it is
only a photo of paper, with no characters inside).
**How.** For digital pages we read the text layer with **PyMuPDF** (a fast PDF library; Python name `fitz`/`pymupdf`).
**pymupdf4llm** is an add-on that outputs **Markdown** (headings `#`, lists, tables) instead of a flat string, so
structure such as "ARTICLE 12 TERMINATION" survives. For scanned pages there is no text to read, so we render the
page to an image and run **OCR** (Optical Character Recognition) with **Tesseract**, an open-source engine (originally
HP, then Google) that uses an LSTM neural network to read lines of text from images.
**Example.** Pune Metro PDF: 305 pages, 300 have no text layer → 300 pages OCR'd.
**In our project.** `ingestion.py`: per page, "is there enough text?" → PyMuPDF/pymupdf4llm, else Tesseract. OCR runs
in parallel (one process per page) and the result is **cached by the file's hash** (a fingerprint of the bytes), so
the same file is never OCR'd twice.
**Viva line.** "Digital pages: PyMuPDF via pymupdf4llm to keep structure; scanned pages: Tesseract OCR, parallel and cached."

## 10. Regex, clause extraction, cross-references
**What.** A **regular expression (regex)** is a pattern for matching text, e.g. `^\d+(\.\d+)*\s` matches "14.2 " at
the start of a line.
**How.** The extractor walks the text line by line: numbered lines start new clauses (`14`, `14.2`, `14.2(a)`); lines
like "ARTICLE 12" or "SCHEDULE B" start a **part**; `14.2` gets **parent** `14`. A table of contents looks like many short
numbered lines with page numbers, so such a run is dropped. **Cross-references** are phrases like "subject to Clause
14.2" or "notwithstanding Article 9"; we find them with patterns and link them to the actual clause id ("resolved").
**Example.** "18.3 Notwithstanding Clause 12.1, …" → clause 18.3, parent 18, cross-reference → 12.1.
**In our project.** `extraction.py`. Pune Metro → 580 clauses, 99 parts, 137 resolved cross-references.
**Viva line.** "Rules, not ML, because numbering is regular, and cross-references are the strongest signal that two clauses interact."

## 11. Tokens
**What.** Models don't read letters or words, they read **tokens**: pieces of words from a fixed vocabulary.
**How.** "indemnification" might become `indemn` + `ification`. A model has a maximum input length in tokens
(InLegalBERT 512; we use 256 for speed).
**Example.** A typical clause ≈ 60–200 tokens; a Kev request (clause + question + options) ≈ 300 tokens.
**Viva line.** "Tokens are sub-word pieces; speeds and limits are measured in tokens."

## 12. How a neural network learns (the basics)
**What.** A neural network is a big function with millions of adjustable numbers (**weights/parameters**) that maps
input numbers to output numbers.
**How (training).**
1. Feed an example, get a prediction.
2. A **loss** function measures how wrong it is (e.g. **cross-entropy**: large when the model gave low probability to the right answer).
3. **Backpropagation** computes, for every weight, which direction reduces the loss (the **gradient**).
4. The **optimizer** (AdamW) nudges every weight a little in that direction; the size of the nudge is the **learning rate** (lr).
5. Examples are processed in **batches** (e.g. 16 at once); one pass over all training data = one **epoch**.

**Overfitting** = memorising the training data instead of learning the pattern; we detect it with data the model
never saw (validation/test).
**In our project.** InLegalBERT: 3 epochs, lr 3e-5, batch 16. Kev v2: 2 epochs, lr 2e-4. GNN: 60 epochs, lr 2e-3.
**Viva line.** "Loss tells how wrong, gradients tell which way, the optimizer takes small steps; epochs are passes over the data."

## 13. Transformers, attention, BERT, InLegalBERT
**What.** A **transformer** is the neural network architecture behind modern language models. Its key part is
**attention**: every token looks at every other token and decides how much each one matters for its meaning.
**How.** In "the Supplier shall indemnify the Customer… *it* shall…", attention lets "it" draw information from
"Supplier". Many attention layers are stacked. **BERT** is a transformer *encoder* pre-trained on huge text by hiding
15 % of words and predicting them (**masked language modelling**); this teaches it general language.
**Pre-training vs fine-tuning.** Pre-training = general knowledge from lots of unlabelled text (done by others).
Fine-tuning = a short extra training on *our* labelled task.
**InLegalBERT** (law-ai, IIT Kharagpur) is BERT further pre-trained on Indian legal text (court judgments), so it
already "knows" legal Indian English.
**In our project.** We fine-tuned InLegalBERT on 55,915 labelled clauses for the 22 clause types → 0.931 F1.
**Viva line.** "A transformer with attention, pre-trained on Indian legal text, fine-tuned by us for clause types."

## 14. Multi-label classification, sigmoid, threshold
**What.** *Multi-class* = exactly one answer (cat or dog). *Multi-label* = any number of answers: a clause can be both
`termination` and `payment_and_fees`.
**How.** The model outputs one score per label; the **sigmoid** function turns each into a probability 0–1
independently; every label above the **threshold** (0.5) is assigned.
**Example.** termination 0.92, payment 0.61, notices 0.08 → labels: termination, payment_and_fees.
**Viva line.** "One sigmoid per label, threshold 0.5, so a clause can have several types."

## 15. Embeddings, cosine similarity, Sentence-BERT
**What.** An **embedding** is a list of numbers (a vector, e.g. 384 or 768 numbers) representing the meaning of a
text. Similar meanings → vectors pointing in similar directions.
**How.** **Cosine similarity** = the cosine of the angle between two vectors: 1 = same direction (same meaning),
0 = unrelated. **Sentence-BERT (SBERT)** is BERT trained so that one vector per sentence works well for this.
**Bi-encoder:** each text is encoded separately, so vectors can be pre-computed and compared fast. **Cross-encoder:**
both texts go through the model together (more accurate, much slower; see rerankers, §18).
**Example.** "The Supplier's total liability shall not exceed fees paid" and "aggregate liability is capped at the
contract price" → high cosine, even with few shared words.
**In our project.** MiniLM (384-dim) and InLegal-SBERT (768-dim) for clause↔clause and clause→law search.
**Viva line.** "Embeddings turn meaning into vectors; cosine similarity finds clauses that mean the same thing in different words."

## 16. Contrastive fine-tuning (MNRL)
**What.** Teaching an embedding model which texts *should* be close.
**How.** **Multiple-Negatives Ranking Loss**: take a batch of matching pairs (clause, its correct statute section).
For each clause, its own section is the positive and the *other* sections in the batch are negatives; the loss pulls
the positive closer and pushes negatives away. "Cached" MNRL lets us use a big batch (64) on a small GPU.
**In our project.** InLegal-SBERT fine-tuned on 2,967 clause→section pairs (1.3 min) → exact-section top-5 from 0.21 to 0.32.
**Viva line.** "Contrastive learning: pull the right section closer, push the others in the batch away."

## 17. BM25
**What.** The classic keyword search ranking (used by search engines for decades).
**How.** A document scores high when it contains the query's words (**term frequency**, with diminishing returns),
especially *rare* words (**inverse document frequency**: "earnest money" matters more than "shall"), adjusted for
document length (long clauses don't win just by being long).
**Example.** Query "forfeiture of earnest money" → sections containing "forfeit" and "earnest" rank top.
**In our project.** Clause↔clause and clause→law search. It is the strongest single method on OCR'd Indian text
(exact legal words survive OCR; paraphrase models get confused by noise).
**Viva line.** "Keyword ranking weighted by word rarity and length; robust on OCR'd legal text."

## 18. Hybrid search, RRF, rerankers
**What.** Combine keyword search (BM25) and meaning search (embeddings) to get the best of both.
**How. Reciprocal Rank Fusion:** score(d) = Σ over methods of 1 / (60 + rank of d in that method). Only ranks matter,
so scores on different scales combine fairly.
**Example.** Section X is rank 1 in BM25 and rank 3 in dense → 1/61 + 1/63 = 0.0323. Section Y is rank 2 in BM25 only →
1/62 = 0.0161. X wins.
**Act prior:** we add a small bonus (0.004) to contract-related Acts so contract clauses don't retrieve criminal-law sections.
**Reranker:** a cross-encoder that re-reads the top results together with the query and re-scores them. We tried
bge-reranker-v2-m3: it scored *worse* (0.26 vs 0.32) and needs GPU memory, so it is off.
**Viva line.** "RRF merges rankings by summing 1/(60+rank); hybrid beats either alone; the reranker didn't help on Indian statutes."

## 19. RAG (Retrieval-Augmented Generation)
**What.** Instead of trusting a model's memory, **retrieve** real documents first and give them to the model as evidence.
**How.** 1) Search a library (our 4,408 India Code sections) for the passages relevant to the question. 2) Give those
passages to the model. 3) The model may only use or choose from them. 4) Show the passages to the user.
**In our project.** For every finding we retrieve the top sections; Kev *chooses* among 4 retrieved sections (it
cannot invent one); Gemini Expand may cite only retrieved sections, and every citation is checked to exist.
**Viva line.** "The law shown is retrieved from India Code text, never written from a model's memory: no hallucinated sections."

## 20. GNN / GraphSAGE (in detail)
**What is a graph?** **Nodes** (things) connected by **edges** (relations). Our graph: each **clause is a node**;
edges connect clauses that cite each other, a clause and its parent, neighbouring clauses in the document, and each
clause with its 5 most similar clauses.
**What is a GNN?** A **Graph Neural Network** learns a vector for each node using not only the node's own features but
also its neighbours'. Intuition: "you are partly defined by who you are connected to." A survival clause that is
connected to a non-compete clause should look different from one connected to a confidentiality clause.
**How: message passing (one layer).**
1. Each node starts with a feature vector (ours: 384-number MiniLM embedding + 30 label flags (22 + other + 7 rule
   labels, 1 if the clause has that label) + its relative position in the document).
2. Each node collects its neighbours' vectors (the "messages").
3. It **aggregates** them (GraphSAGE uses the **mean**).
4. It combines its own vector with the aggregated one through a small learned layer → new vector.
With **2 layers**, information travels 2 hops (a clause learns about its neighbours' neighbours).
**GraphSAGE** ("SAmple and aggreGatE", Hamilton et al. 2017) is a GNN that learns the aggregation function, so it
works on new, unseen graphs (each contract is a new graph). That is why we chose it.
**Link prediction.** Our task is "is this *pair* of clauses risky?": take the two node vectors h_a, h_b, build
[h_a, h_b, |h_a − h_b|, h_a × h_b, clash-matrix weight] and a small network outputs P(risky). Trained with
binary cross-entropy on teacher-labelled pairs (risky = any relation except no_issue), split by contract, 60 epochs.
**The ablation.** The *same* scorer is trained on the raw node features **without message passing**. If the GNN is
better, the graph helped. Result: GNN ROC-AUC 0.742, no-graph 0.748, cosine alone 0.738 → **the graph did not help**.
**Why (likely).** Contracts have few cross-references per clause, so the graph is sparse; only 172 labelled test pairs;
the embedding already carries most of the signal.
**In our project.** Optional extra shortlisting signal (`use_gnn`), off by default; reported as an honest negative result.
**Viva line.** "GraphSAGE averages neighbours' vectors over 2 hops to score clause pairs; our ablation showed no gain over the same features without the graph, so it's off by default."

## 21. LLMs vs decision models: Kev, pointer head
**What.** A normal **LLM** (ChatGPT, Gemini) *generates* text token by token. A **decision model** reads a situation
and a question with fixed options, and outputs a **probability for each option**: no free text.
**How.** **Kev** = a small language model (Qwen3.5-0.8B, 0.8 billion parameters) that reads the "state" (clauses) and
the question, plus a **pointer head**: an output layer that, instead of predicting the next word, *points* at one
of the given options and gives each a probability. Kev is an open re-implementation of the "Jev"/System One
decision-model idea.
**Example.** Options conflict/dependency/overlap/ambiguity/no_issue → 0.06 / 0.14 / 0.43 / 0.22 / 0.16 → "overlap".
**Why we use it.** Small enough for a 6 GB laptop GPU, fast (~0.1 s per decision), outputs probabilities (we can show
confidence and set thresholds), and cannot write a fake explanation.
**Speed.** Since it doesn't generate, we measure **input tokens read per second** (~3,500) and **decisions per second** (~11).
**Viva line.** "Kev reads and points at an answer with probabilities: fast, local, and it can't hallucinate prose."

## 22. Zero-shot, fine-tuning, LoRA
**Zero-shot** = using a model on a task with no task-specific training (just the question). Our demo uses Kev
zero-shot because it won on the independent tests.
**Fine-tuning** = extra training on our labelled examples. We fine-tuned Kev twice; it agreed more with the teacher
but did worse on independent tests (see PROCESS.md §4).
**LoRA (Low-Rank Adaptation)** = instead of changing all 0.8 B weights, freeze them and train two small matrices
per layer whose product is added to the frozen weights. "Rank 16" = the small matrices have width 16. Result: about 1 %
of the parameters are trained, so it fits a 6 GB GPU.
**Viva line.** "LoRA trains tiny add-on matrices instead of the whole model; our fine-tunes lost to zero-shot on independent tests, so we kept zero-shot."

## 23. GPU memory: bf16, gradient checkpointing, OOM, CUDA graphs
**GPU** = the graphics card that does the matrix maths fast; ours has **6 GB** of memory (**VRAM**).
**bf16** = storing numbers in 16 bits instead of 32 → half the memory, nearly the same accuracy.
**Gradient checkpointing** = during training, don't keep every intermediate result; recompute when needed → less
memory, a bit slower.
**OOM (out of memory)** = the model asked for more VRAM than is free → crash/HTTP 500.
**CUDA graphs** = recording a sequence of GPU operations once and replaying it (faster), but each recorded input
shape keeps memory. On our 6 GB card they filled memory, so we turned them off: Kev uses 1.8 GB and is still ~11 decisions/s.
**Viva line.** "bf16 and checkpointing to train on 6 GB; in serving we disabled CUDA graphs because they filled VRAM."

## 24. Class imbalance, focal loss, thresholds, calibration
**Class imbalance** = one answer is much more common (73 % of teacher pairs were no_issue). A lazy model learns to
always say the common answer and still looks "73 % accurate": that is what **Kev v1** did (it **collapsed**).
**Fixes we used.** (1) **Balanced data**: equal-ish numbers of each answer (440 pairs). (2) **Focal loss**: a loss that
down-weights easy, already-correct examples (factor (1 − p)^γ, γ = 2) so the model focuses on hard ones.
(3) **Decision threshold τ**: instead of taking the most likely answer, flag "risky" when P(no_issue) < τ; τ is
chosen on training contracts only. This is **calibration**.
**Viva line.** "Imbalance made v1 always say no_issue; balancing, focal loss and a tuned threshold fixed the collapse."

## 25. Teacher–student distillation, silver/gold labels, Cohen's κ
**Distillation** = a big, expensive model (**teacher**: Gemini 4) labels examples; a small model (**student**: Kev)
learns from those labels.
**Gold labels** = from experts or reality (lawyers, court outcomes). **Silver labels** = from a model (the teacher).
Silver is cheap and large but can be wrong.
**Validating the teacher:** compare it with things it did not produce: checklist 92.9 %, lawyer clause types 75 %,
real citations 85.7 %.
**Cohen's κ (kappa)** = agreement between two labellers corrected for agreement by chance. 0 = chance, 1 = perfect;
0.41–0.60 = "moderate". Gemini vs Claude: κ = 0.57.
**Viva line.** "Gemini labelled pairs to train Kev; we checked Gemini against gold it didn't create; κ 0.57 with Claude shows the task is genuinely hard."

## 26. Metrics
Imagine the model flags 10 pairs as risky; 6 really are; there were 12 risky pairs in total.
- **Precision** = correct flags / all flags = 6/10 = 60 % ("when it says risky, how often is it right?").
- **Recall** = found / all real = 6/12 = 50 % ("how many real ones did it find?").
- **F1** = harmonic mean of precision and recall = 2·0.6·0.5/(0.6+0.5) = 0.545 (high only if both are high).
- **Accuracy** = correct decisions / all decisions (misleading when classes are imbalanced, see §24).
- **Micro-F1** = pool all labels' counts then compute F1 (dominated by common labels). **Macro-F1** = F1 per label,
  then average (every label counts equally, punishes rare-label mistakes).
- **Recall@k (R@k)** = is the right answer in the top k results? **Precision@k (P@k)** = share of the top k that are right.
- **ROC-AUC** = probability that a random risky pair is scored higher than a random safe pair (0.5 = coin flip, 1 = perfect).
- **Average precision** = area under the precision–recall curve; rewards ranking true items at the top.
- **Checklist binary accuracy** = (bad twins flagged + fixed twins cleared) / 28: counts both catches and false alarms.
**Viva line.** "Precision = how often a flag is right, recall = how much we find, F1 balances them; R@5 for search; ROC-AUC for ranking."

## 27. Evaluation design: train/validation/test, held-out, OOD, ablation, leakage
- **Train / validation / test**: learn on train; tune settings (threshold, epochs) on validation; report on test once.
- **Held-out** = data kept aside and never trained on (our 172 teacher pairs, split by contract).
- **OOD (out-of-distribution)** = test data deliberately different from training (other contract types): tests generalisation.
- **Ablation** = remove one part and measure again, to prove that part matters (GNN vs no-graph; with/without Act prior).
- **Leakage** = test information sneaking into training → inflated scores. We split by contract and chose the judge on
  tests the teacher never saw (choosing by teacher agreement would be circular).
- **Baseline** = a simple method to beat (rules, keyword, BM25, "always say Indian Contract Act").
**Viva line.** "We report on held-out and independent gold, include baselines and ablations, and never select on data we trained on."

## 28. The Indian law we use (plain words)
| Law | Plain meaning | Typical clause it hits |
|---|---|---|
| Indian Contract Act 1872 **s.27** | agreements restraining a lawful profession/trade are **void** (except sale of goodwill) | post-employment non-compete |
| ICA **s.74** | on breach you get *reasonable* compensation up to the stated sum, not a penalty | huge fixed penalties, forfeiture |
| ICA **s.28** | agreements barring or time-limiting going to court are void (with exceptions) | "claims must be filed within 30 days or are extinguished" |
| ICA **s.23** | agreements against public policy are void | one-sided termination at will (argued) |
| ICA **ss.124–125** | indemnity: what an indemnity holder can recover | indemnity vs liability cap |
| Arbitration & Conciliation Act 1996 **s.12(5)** | an interested person can't be the arbitrator or appoint one unilaterally | "the MD shall appoint the sole arbitrator" |
| A&C Act **s.20 / s.28** | seat (place) of arbitration and applicable law | seat vs governing-law clashes |
| Indian Stamp Act 1899 **s.35** | an unstamped document isn't admissible in evidence until stamped | "this agreement is executed on plain paper" |
| DPDP Act 2023 **s.6** | personal data needs free, specific, informed consent | "may share customer data with any third party" |
| Specific Relief Act 1963 | when courts order performance / injunctions | waiver of remedies |
**Void** = no legal effect from the start. **Voidable** = valid until a party cancels it.
**PPP / concession agreement** = a government grants a private company the right to build and operate infrastructure
(metro, highway) for years; long contracts with lenders' step-in rights, performance security, change-in-law clauses.

## 29. Web side: API, FastAPI, SSE, SQLite, LAN, firewall
- **Backend** = the program doing the work (Python on Aryan's laptop). **Frontend** = the web page in a browser.
- **API** = URLs the frontend calls to get data, e.g. `GET /api/contracts/demo_01` returns JSON.
- **FastAPI** = the Python web framework serving those URLs.
- **SSE (Server-Sent Events)** = the server keeps the connection open and pushes progress messages ("ingestion done,
  extraction done…"): that is how upload shows live stages.
- **SQLite** = a database stored in one file (`contracts.db`); no separate server needed.
- **Port** = a numbered door on a computer (8080 dashboard, 8008 Kev). **LAN / hotspot** = laptops on the same local
  network can reach each other by IP. **Firewall (ufw)** = blocks ports unless allowed → `sudo ufw allow 8080/tcp`.
- **localhost / 127.0.0.1** = "this same computer". Kev listens only on localhost, so only our backend can use it.
**Viva line.** "FastAPI backend with SSE progress and SQLite; the model server is localhost-only, so contract text never leaves the machine."

## 30. Putting it together: one clause's journey
Clause 91.3 of the Pune Metro scan: *"For 36 months following termination, the Concessionaire shall not compete…"*
1. **Ingestion:** page is a scan → Tesseract OCR → text (cached).
2. **Extraction:** regex sees "91.3" → clause `91.3`, parent `91`, part "ARTICLE 91 …".
3. **Classification:** InLegalBERT → `exclusivity_and_restraint` (≈0.9); rules add nothing.
4. **Shortlisting:** clause 91.4 says "Clauses 91.2 and 91.3 shall survive…" → cross-reference pair (91.4, 91.3);
   the type matrix also pairs `exclusivity_and_restraint` + `survival` (weight 0.75); BM25/dense find similar clauses.
5. **Kev pair judge:** (91.3, 91.4) → probabilities → e.g. dependency/conflict, severity high, statute option "ICA s.27".
6. **Kev clause-vs-law:** 91.3 alone → `restraint_of_trade` with P ≥ 0.7 → "high confidence" → ICA s.27.
7. **Statute RAG:** BM25 + fine-tuned InLegal-SBERT + Act prior → ICA s.27 text + Percept D'Mark precedent, confidence chips.
8. **Validation & ranking:** evidence spans checked; sorted by severity and risk.
9. **Storage & display:** SQLite → dashboard card "Clause 91.3 — Clause ↔ Indian law — HIGH", graph node with a purple border.
10. **Optional:** "Explain with Gemini" writes a plain-English explanation citing only the retrieved sections.
