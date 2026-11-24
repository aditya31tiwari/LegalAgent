# START HERE — one page: understand it, check it, show it

Follow the steps in order. Each step says **what to open**, **what to look at**, and **what you should be able
to say afterwards**. Deeper detail lives in the other files of this folder; you only open them when a step says so.

Time needed: tonight ≈ 60–75 min · morning ≈ 30 min · panel ≈ 12 min.

---

## PART A — Tonight: understand it by looking at it (≈ 60 min)

Open pages on your laptop: `http://localhost:8080/...` (through the SSH tunnel) or `http://192.168.1.10:8080/...`
once `sudo ufw allow 8080/tcp` has been run on Aryan's laptop.

### A1. The idea in one minute (read, 2 min)
Contracts are risky in two ways: (1) two clauses that clash or depend on each other (**clause ↔ clause**), and
(2) a clause that Indian law makes void or risky (**clause ↔ law**). LegalAgent reads a contract (even a scan),
splits it into clauses, labels them, picks the pairs worth checking, asks a small local model (**Kev**) about each
pair and each risky clause, and attaches the real India Code section, all on one laptop GPU.
**Say afterwards:** the two kinds of checks and "nothing leaves the laptop".

### A2. Watch the pipeline run, stage by stage (10 min) — Aryan's laptop terminal
```bash
cd ~/Projects/LegalAgent/LegalAgent
venv/bin/python scripts/show_steps.py data/demo/generated/supreme_court_casebook.md --rows 12 --pairs 8
```
Press Enter after each stage and match it to this list:

| Stage | What you see | What it means |
|---|---|---|
| 1 Ingestion | pages, OCR pages, characters | PDF → text. pymupdf4llm for digital pages, Tesseract OCR for scans |
| 2 Extraction | clause numbers, parts, parents, cross-refs | text → numbered clauses + "subject to Clause X" links |
| 3 Classification | labels with scores | our fine-tuned InLegalBERT says what type each clause is (22 types) |
| 4 Shortlisting | 253 possible pairs → 60 | which pairs are worth asking Kev about (cross-refs, clashing types, similar text) |
| 5 Kev judge | P(no_issue), P(conflict)… per pair | Kev's probabilities; the highest one is the decision |
| 6 Clause vs law | P(none), top risk, Act + section | Kev's single-clause legal-risk check vs the regex column |
| 7 Statute RAG | top India Code sections + score | real law text retrieved for a finding |
| 8 Result | counts | what goes to the database / dashboard |

**Say afterwards:** the 8 stages in one breath.

### A3. The product (15 min) — `/app`
1. Pick **Pune Metro Line-3 Concession — 15 planted irregularities**. Read the top bar: clauses, clause↔clause,
   clause↔law, high severity, and the run line `judge=local, classifier=inlegalbert`.
2. Click **Clause ↔ Law** → first card **Clause 91.3** → open *Details*: clause text, retrieved **ICA s.27** with a
   confidence chip, Supreme Court precedent.
3. Click **Clause ↔ Clause** → open a card → both clauses + retrieved law.
4. Scroll to the bottom: **Low-confidence signals**, shown, not hidden.
5. Pick **Supreme Court casebook**: each heading says what the court held (VOID / UPHELD). Find a VOID clause that
   is flagged, and an UPHELD clause that is also flagged (Kev's false alarm; be ready to admit it).
6. Pick **Pune Metro … full scanned PDF (305 pp)**: 580 clauses from a scan.

**How the card text is made (likely question).** No model writes the sentences. They are fixed templates filled
by Kev's probabilities:

| Card | Text comes from |
|---|---|
| Clause ↔ law, "Kev reads this clause as one that …" | Kev picks the most likely of 7 risk categories; the sentence is that category's fixed description + its Act/section (`legalagent/core/statutory_kev.py`, `CATEGORIES`) |
| Clause ↔ law, "This clause appears to restrain trade …" | hand-written sentence of a regex rule (`analysis.py`) |
| Clause ↔ clause, "Overlap between clause X (types) and clause Y (types): …" | Kev's relation + that relation's fixed definition; types from InLegalBERT; "Relevant law" only if Kev picked one of the 4 retrieved sections (`local_judge.py`, `_to_finding`) |
| "Retrieved Indian law" box | real India Code text from retrieval, with a confidence chip |
| "Explain with Gemini" | the only generated text: opt-in, cloud, cites only retrieved sections |

**Say afterwards:** "templates filled by probabilities, so it cannot invent a law."

### A4. The numbers (15 min) — `/report`
Every table has a "Tests: …" line. Focus on these five and learn one sentence each:

| Table | The sentence |
|---|---|
| 1 Classification | "Our fine-tuned InLegalBERT gets 0.93 F1, 0.75 on unseen contract types; the old MiniLM got 0.83 / 0.59." |
| 3 Judge | "Kev gets 71 % on our bad/fixed checklist and finds 75 % of lawyer-annotated interactions; rules get 46 % / 7.5 %." |
| 4 Clause vs law | "On clauses the Supreme Court struck down, Kev caught 6 of 9, regex 0 of 9, but Kev also flags upheld ones, hence confidence labels." |
| 5 Statute RAG | "The exact section is in the top 5 for 32 % of cases (BM25 alone 11 %); the right Act is in the top 3 for 53 %." |
| 9 + 10 Speed | "Kev makes 11 decisions a second, reading ~3,500 tokens/s on a 6 GB laptop GPU; a 305-page scan takes ~4.5 min end to end." |

Then skim tables 6 (GNN: no gain, an honest ablation) and 7 (teacher checked against independent truth).

### A5. Why, why-not, and what failed (15 min) — read
- `LEARNING.md`: sections 1–9, the **why / why not** lines only, and the **Likely viva questions**.
- `PROCESS.md` §4: the failed-attempts table. Learn three stories:
  1. **Kev fine-tuning made it worse** than the base model, so we chose by independent tests, not by the teacher.
  2. **Regex caught 0/9** real void clauses, so we added Kev + RAG.
  3. **14,025 pairs → 173**: the pair cap made a 305-page scan go from about an hour to 4.4 minutes.
- Glossary at the end of `LEARNING.md`: make sure you can define PyMuPDF, OCR, BM25, embeddings, RRF, RAG, LoRA,
  focal loss, F1, recall@k, κ.

### A6. Exact facts (10 min) — read `LEARN_EVERYTHING.md`
The 22 + 7 labels (and why CLAUSE-20 became CLAUSE-22), the 40 clash pairs, datasets and sizes, the models, and
Kev's exact questions. Panels ask "how many labels / what data / which model / what threshold": the answers are there.

**You are done tonight when** you can explain the 8 stages, the card text, the five sentences, and the three stories.

---

## PART B — Morning (≈ 30 min) — `MORNING_RUNBOOK.md`
Nothing is changed or retrained: the project is shown exactly as committed. Only start, check, rehearse.
1. Both laptops on one hotspot. On Aryan's laptop: `bash scripts/start_demo.sh`, then `hostname -I` → IP.
2. If the other laptop can't open the page: `sudo ufw allow 8080/tcp` (once).
3. Warm up: open every contract once; **do one upload** (first one ≈ 50 s, later ≈ 15 s); open `/scores` once.
4. Rehearse Part C twice with a timer.

---

## PART C — In front of the panel (≈ 12 min) — full script in `PANEL_DEMO.md`

| Min | Screen | Show | Say |
|---|---|---|---|
| 1 | none | — | the problem + two kinds of checks + local-only |
| 3 | frontend `/app` | Pune Metro → Clause ↔ Law → 91.3 Details → Clause ↔ Clause card → low-confidence group | "from the pipeline, nothing typed in"; "law is retrieved, not written" |
| 2 | frontend `/app` | Supreme Court casebook: VOID caught, UPHELD also flagged | 6/9 vs 0/9 and why confidence labels |
| 2 | frontend `/app` | **Upload & analyse** a short contract live | stages streaming; OCR for scans |
| 3 | Aryan's terminal | `show_steps.py` stages 1→8 | one line per stage (A2 table) |
| 1 | frontend `/report` | tables 3, 4, 9, 10 | the five sentences (A4) |

Close with: "It is a complete local system: any contract in, grounded findings out, every stage measured. What it
still needs is lawyer-verified Indian training data."

---

## Which other file for what (only if needed)
| Need | File |
|---|---|
| Exact demo script + fallbacks | `PANEL_DEMO.md` |
| Deep explanation of any part, Q&A, glossary | `LEARNING.md` |
| Full history, schema, every failed attempt | `PROCESS.md` |
| Report wording | `FINAL_REPORT.md` |
| Editing the .docx | `REPORT_CHANGES.md` |
| Morning checks and fixes | `MORNING_RUNBOOK.md` |
