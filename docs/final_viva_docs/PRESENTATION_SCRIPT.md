# Presentation script: 3 speakers, about 15 minutes

Format: each block says **Explain: …** (the point to make), then a few plain lines on what it means. Say it in your
own words; the lines are prompts, not text to read. **Screen** says what is visible. Times are targets.

| Speaker | Part | Time | Screens |
|---|---|---|---|
| **A** | Problem, idea, the product (dashboard) | ~5 min | Frontend laptop: `/app` |
| **B** | How it works inside, stage by stage | ~5 min | Aryan's laptop: terminal `show_steps.py` |
| **C** | The models, Indian law, results, what failed, conclusion | ~5 min | Frontend laptop: `/report` (+ explainer if useful) |

Before starting: backend running, every contract opened once, one warm-up upload done (see MORNING_RUNBOOK.md).

---

## Speaker A: problem and product (~5 min)

### A1. Explain: the problem (no screen, 45 s)
- Contract review in India is slow and costly; big infrastructure contracts run to hundreds of pages, often only as scans.
- Existing tools look at one clause at a time. But risk often comes from **two clauses together**: a liability cap
  quietly undone by an indemnity "without limit, notwithstanding any other provision".
- And some clauses are simply **void under Indian law**, e.g. a non-compete after employment ends (Indian Contract Act
  s.27), even if it looks normal.

### A2. Explain: what LegalAgent does (45 s)
- It does two checks: **clause ↔ clause** inside the contract, and **clause ↔ Indian law**.
- It reads PDFs including scans, splits them into clauses, decides which clauses to compare, judges them with a small
  model, and attaches the real text of the Indian law.
- **Everything runs locally on one laptop GPU.** Contracts are confidential, so nothing is sent to the cloud.

### A3. Explain: the product, on a real Indian contract (2.5 min) · Screen: `/app`
- Open **Pune Metro Line-3 Concession, 15 planted irregularities**. "We planted 15 problems in a real concession
  agreement to test it."
- Top bar: number of clauses, clause↔clause issues, clause↔law issues, high-severity count. The grey line shows it came
  from a real run (`judge=local, classifier=inlegalbert`). Nothing here is typed in by hand.
- Graph: each box is a clause; red lines are clause pairs the judge flagged; dashed blue lines are cross-references
  ("subject to Clause X") our system found; purple borders are clauses with an Indian-law issue.
- Click **Clause ↔ Law** → **Clause 91.3** (36-month non-compete) → **Details**: the clause, the retrieved Indian
  Contract Act s.27 text, a Supreme Court precedent, and a confidence label.
- Click **Clause ↔ Clause** → open one pair (e.g. liability cap vs indemnity).
- Point at **Low-confidence signals**: "Weak signals are shown, labelled, not hidden."

### A4. Explain: real ground truth, the Supreme Court casebook (45 s)
- Open **Supreme Court casebook**: 18 real contract clauses from Supreme Court judgments; each heading says what the
  court decided (void or upheld).
- **Clause ↔ Law** tab: show a VOID non-compete that the system flags under s.27.
- Be upfront: "It also flags some clauses the court upheld. That's why it gives confidence levels and supports a
  reviewer instead of deciding."

### A5. Explain: it works live (30 s, optional if time)
- **Upload & analyse** → the clean employment agreement → stages stream live → findings open.
- "Any PDF, DOCX or text file works; scanned pages go through OCR."

**Handoff:** "That's what it does. B will show what happens inside, step by step."

---

## Speaker B: how it works inside (~5 min) · Screen: Aryan's terminal

Run: `venv/bin/python scripts/show_steps.py data/demo/generated/supreme_court_casebook.md --rows 12 --pairs 8`
Press Enter for each stage. One or two points per stage.

### B1. Explain: reading the document (ingestion)
- Digital PDF pages: PyMuPDF via **pymupdf4llm**, which keeps headings and tables.
- Scanned pages: **Tesseract OCR**, many pages in parallel, results cached so a file is never OCR'd twice.
- Example: the 305-page Pune Metro scan becomes text in about 2 minutes the first time.

### B2. Explain: splitting into clauses (extraction)
- Rules recognise numbering (14, 14.2, 14.2(a)), ARTICLE/SCHEDULE sections, and the table of contents (dropped).
- Cross-references like "subject to Clause 14.2" are linked to the actual clause, which is the strongest sign two
  clauses interact.
- Pune Metro: 580 clauses, 99 sections, 137 cross-references.

### B3. Explain: what type each clause is (classification)
- Our fine-tuned **InLegalBERT** (a BERT model pre-trained on Indian legal text) labels each clause with one or more
  of **22 clause types** (CLAUSE-22): indemnification, limitation of liability, termination, arbitration…
- Plus 7 keyword rules for Indian clause types (stamp duty, data protection, step-in rights…).
- 0.93 F1; the older MiniLM model we had at mid-term got 0.83.

### B4. Explain: choosing which pairs to check (shortlisting)
- Comparing every pair is too slow (580 clauses = 167,000 pairs).
- Three signals: cross-references, a table of 40 clause-type combinations that commonly clash (cap × indemnity), and
  search for similar clauses (BM25 keywords + meaning-based search, merged).
- Pune Metro: from 14,025 candidates to 173 pairs, so the whole 305-page scan runs in 4.4 minutes.

### B5. Explain: the judge's answer (Kev)
- For each pair a small local model (**Kev**) answers three questions: how the clauses relate (conflict, dependency,
  overlap, ambiguity, no issue), how serious, and which Indian law section applies.
- Point at the probability columns: "It gives a probability for every option; the highest wins."
- Point at the milliseconds: it runs on the laptop GPU in a fraction of a second.

### B6–B8. Explain: law check, law text, result (quickly)
- Stage 6: the same model checks single clauses against 7 Indian-law risks (restraint of trade, penalties, one-sided
  arbitrator…).
- Stage 7: the real India Code sections are searched and attached.
- Stage 8: everything is stored and shown in the dashboard.

**Handoff:** "C will explain the models, how we know they work, and what didn't work."

---

## Speaker C: models, Indian law, results, conclusion (~5 min) · Screen: `/report`

### C1. Explain: what Kev is, and why a small local model
- Kev is a **decision model**: it reads the clauses and a question with fixed options and returns probabilities. It
  doesn't write free text, so it can't make up a reason or a law.
- 0.8 billion parameters, runs on a 6 GB laptop GPU, about 11 decisions per second.
- Why not GPT/Gemini for everything: confidentiality, cost per contract, and availability (Gemini was often overloaded
  while we built this).

### C2. Explain: where the training data came from (teacher–student)
- No dataset of labelled Indian clause *pairs* exists, so a large model (**Gemini 4**, the "teacher") labelled 2,360
  pairs; Claude gave a second opinion.
- We checked the teacher against things it didn't create: 93 % on our known-answer checklist, 86 % of its law
  citations exist.
- Important finding: we fine-tuned Kev on these labels twice, and it got *worse* on independent tests. So we serve the
  original model, chosen by tests the teacher never saw.

### C3. Explain: Indian law without making things up (RAG)
- A library of 4,408 real India Code sections. For each finding we **search** it and attach the actual text; every
  cited section is checked to exist.
- Our fine-tuned search model finds the exact right section in the top 5 for 32 % of cases, up from 11 % with plain
  keyword search, and the right Act in the top 3 for 53 %.

### C4. Explain: results on ground truth we didn't create (`/report` tables 3, 4, 9, 10)
- Pair judge: Kev 71 % on our bad/fixed checklist vs 46 % for rules; finds 75 % of lawyer-annotated interactions vs 7.5 %.
- Law check: catches 6 of 9 clauses the Supreme Court struck down; keyword rules caught 0.
- Speed: 305-page scan end to end in 4.4 minutes on one laptop.

### C5. Explain: what didn't work (shows we tested properly)
- Fine-tuning the judge: first version always said "no issue"; second agreed with the teacher but did worse on real tests.
- Graph neural network: no gain over the same features without the graph, so it's off by default.
- Keyword rules for law: 0 of 9 real void clauses.
- Uncapped shortlisting: an hour per big contract, fixed by ranking and capping.

### C6. Explain: limitations and future work
- It favours finding problems over avoiding false alarms; it supports a reviewer, it doesn't replace a lawyer.
- Next: lawyer-verified Indian training data, a larger model, giving the teacher the retrieved law when labelling.

### C7. Conclusion (20 s)
"LegalAgent is a complete, local system: any contract in, ranked findings grounded in real Indian law out, with every
stage measured against independent ground truth."

---

## Q&A: who answers what

| Topic | Answers | Backup file |
|---|---|---|
| Product, demo, use case, dashboard, upload | **A** | PANEL_DEMO.md |
| PDF/OCR, clause splitting, 22 labels, InLegalBERT, shortlisting, BM25/RRF, GNN | **B** | LEARN_EVERYTHING.md §9–20 |
| Kev, fine-tuning, teacher, RAG, Indian law, results, failures, future work | **C** | PANEL_VIVA.md, DECISIONS.md |
| "Why X and not Y?" | whoever owns the topic | DECISIONS.md |

Rules for Q&A: if unsure, say what you measured and what you didn't; never claim ContractNLI is used; quote statute
retrieval as 0.32; on the cap/indemnity bad-vs-fixed example, admit Kev can't tell them apart (the teacher can).

## If something breaks mid-presentation
- Page won't load → switch to Aryan's laptop browser (`http://localhost:8080/app`).
- Kev down → `bash scripts/start_demo.sh stop && bash scripts/start_demo.sh`; stored results still show meanwhile.
- Terminal step viewer slow → open `logs/steps_supreme_court_casebook.html` (saved earlier run) or skip to `/report`.
