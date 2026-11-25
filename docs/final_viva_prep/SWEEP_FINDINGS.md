# Pre-viva sweep — what could hurt the presentation (25 Nov 2026, ~00:45; updated ~11:00)

## Update at ~11:00 (viva day) — what was fixed this morning
- ✅ Item 1: laptop is back (IP still 192.168.1.10 on this network); **backend started and checked**: all pages and APIs
  return 200, Kev on GPU (1.7 GB), `/scores` warmed up for Pune Metro.
- ✅ Item 2: **root README rewritten** for the final system (pipeline, results table, how to run, docs link).
- ✅ Workbench/playground: the :8008 judge was mislabelled "kev_finetuned" and showed "kev_base: server not running".
  Now it reads **"kev_base (served, zero-shot)"** and the missing :8009 row is hidden. Playground "Run every method"
  takes ~33 s (all methods incl. GNN and RAG).
- ✅ New: samples 03–06 (Tech MSA, Employment, Vendor Supply, NHAI excerpt) also contained "*(Contradiction: …)*"
  answer-key notes. They are now analysed from clean copies (`data/demo/generated/*_clean.md`), re-seeded with Kev.
  For the live upload, use `data/demo/generated/04_executive_employment_agreement_clean.md`.
- 🟠 New, know the answer: on the cap-vs-indemnity checklist twin Kev answers "ambiguity" for **both** the bad and the
  fixed version (P(no_issue) 0.20 vs 0.21); the teacher gets it right. See PANEL_VIVA.md §4 "Show me it distinguishing…".
- Still open (by choice): items 3–9 below are "know the answer" items, not bugs.

---

Read top to bottom; each item says **how serious**, **what to do** (mostly: nothing, just know the answer), and
**how long a fix would take** if you decide to fix it. Nothing here was changed in the project.

Legend: 🔴 deal with it before the panel · 🟠 know the answer, decide · 🟢 minor, ignore unless asked

---

## 🔴 1. Aryan's laptop: backend is stopped and the laptop went offline
- At ~00:40 Kev and the web server had shut down cleanly (someone ran `start_demo.sh stop` or similar). I restarted
  them, then the laptop stopped answering SSH entirely (sleep or Wi-Fi drop).
- **Do in the morning:** on Aryan's laptop:
  ```bash
  cd ~/Projects/LegalAgent/LegalAgent
  bash scripts/start_demo.sh            # or: bash scripts/start_demo.sh stop  first if anything half-runs
  hostname -I                           # NEW IP on the hotspot, NOT 192.168.1.10
  sudo ufw allow 8080/tcp               # once, so the other laptop can open the page
  ```
  Then do the warm-up from MORNING_RUNBOOK.md (open each contract once + one upload + `/scores` once).
- Disable sleep on Aryan's laptop during the viva (Settings → Power → Screen blank: Never / Automatic suspend: Off).

## 🟠 2. The GitHub README is still the mid-term proposal
- `README.md` at the repo root (first thing anyone sees on GitHub) says "Phase 1 target", "FAISS / ChromaDB",
  "LLM API for RAG generation", "login / delete account", "GNN can be added later", "fine-tuned LegalBERT".
  It does not mention Kev, InLegalBERT/CLAUSE-22, Indian law RAG, the results or the dashboard.
- **Risk:** only if a panel member opens GitHub. The project itself is fine.
- **Option A (0 min):** don't open GitHub; if asked, say "the README is the original proposal; the final docs are
  in `docs/final_viva_docs/`".
- **Option B (5 min, any laptop with the repo):** replace the README's top with a pointer:
  "Final system and results: see `docs/final_viva_docs/README.md` and `results/REPORT.html`", commit, push.

## 🟠 3. Kev flags a lot: even the clean contract gets many findings
| Contract | Clauses | Findings |
|---|---|---|
| Pune Metro excerpt **with** 15 planted faults | 28 | 74 |
| Pune Metro excerpt **baseline (clean)** | 13 | 44 |
| Executive Employment (sample) | 8 | 22 |
| Real CUAD contract | 73 | 70 |
- Base Kev zero-shot over-flags (vs teacher: 85 % recall, 32 % precision). A panel member may say "it flags everything".
- **Answer to prepare:** "It's a reviewer's assistant tuned for recall: missing a void clause costs more than a
  second look. Findings are ranked by severity, low-confidence ones are grouped separately, and on our checklist it
  still clears 75 % of the fixed (safe) clause pairs. A fine-tuned version flags less but misses much more (31 % vs 75 %
  lawyer-pair recall), so we chose recall." Use the **High severity** number and the **Clause ↔ Law** tab in the demo
  rather than the total.

## 🟠 4. Casebook headings contain the court's answer, and the pair judge can see headings
- The Supreme Court casebook's ARTICLE headings say "court held: VOID / UPHELD" (useful for the panel). The **pair
  judge** prompt includes each clause's part heading, so on the casebook *clause ↔ clause* cards Kev could read the
  outcome.
- **Not affected:** the clause ↔ law check (reads only the clause text), and every number in the report (evaluated
  separately on clause text only, `results/eval_statutory.json`).
- **Do:** on the casebook, show the **Clause ↔ Law** tab, not Clause ↔ Clause. If asked, the 6/9 vs 0/9 numbers are clean.
- Fix (10 min): move the outcome out of the heading in `scripts/seed_demo.py make_casebook()` and re-seed only
  `--only demo_02`. Not worth it the night before.

## 🟠 5. Gemini "Explain" is slow or unavailable tonight
- Google's Flash models were returning 503 (overloaded). It now falls back across models, but took 25–57 s and once
  failed outright. When it fails, the card says "Cloud assist unavailable … the local finding stands on its own".
- **Do:** don't click it in front of the panel unless it worked in the morning. It's opt-in and not part of the
  local pipeline, which is the point of the project.

## 🟠 6. Two statute-retrieval result sets exist with different numbers
- `results/eval_statutes.json` (older, 10 Supreme Court queries: fine-tuned R@5 0.50) and
  `results/eval_statutes_independent.json` (final, 19 queries = SC + Pune injections: R@5 0.316).
- `/report` table 5 and all final docs use **0.316 / Act@3 0.53**. If `results/REPORT_TABLES.md` is shown, it may
  show the older 10-query table. **Always quote 0.32.**

## 🟢 7. Old docs in `docs/` contradict the final ones
- `docs/VIVA_NOTES.md`, `DEMO_GUIDE.md`, `EVALUATION.md`, `ARCHITECTURE.md`, `MODELS_AND_TRAINING.md`, `DATASETS.md`,
  `PLAN.md`, `V0_PLAN.md`, `PUNE_METRO_…GUIDE.md` were written before tonight (CLAUSE-20, 3,142 sections / 33 Acts,
  old judge numbers). **Use only `docs/final_viva_docs/`.** Don't open the others in front of the panel.

## 🟢 8. Leftover UI bits
- **Export** button memo says "Engine: LegalAgent Cross-Clause GraphRAG" (inaccurate buzzword) → don't click Export.
- Old routes `/findings` and `/injections` still exist (pre-final pages; removed from the header) → don't open them.
- The clause panel shows a small "InLegal-SBERT" label (fine; it's the search model).

## 🟢 9. First-time slowness (all normal, already in the runbook)
- First upload after a restart ≈ 50 s (models load), then ≈ 15 s for a short contract.
- `/scores` → Clause-pair scores: first time per contract 10–40 s (encoders on CPU).
- Kev speed table (11 decisions/s) is a benchmark with ~311-token requests; real pipeline requests also carry 4
  statute sections, so in a full run it's ~4 decisions/s with 2 in parallel. If asked: "benchmark vs in-pipeline".

## 🟢 10. Things checked and fine
- No API keys or `.env` in git; no large model weights in git (only the small MiniLM baseline .joblib).
- GitHub `final` = latest commit (806f354); 32 tests passed.
- Database: 10 contracts, all judged by local Kev (2 + 1 + 1 + 1 single pairs skipped after retries, logged).
- `contracts.db` shows "modified" in `git status` because the web server touched it: harmless, don't commit it.

---

## Is the Workbench GUI worth showing?

**What it is:** a desktop window (Tkinter) on Aryan's laptop with 3 tabs:
1. **Playground:** two clauses in (examples such as "cap"), **Run every method**, and you see every method's raw
   output side by side: classifier probabilities, BM25 / MiniLM / InLegal-SBERT similarity, type-matrix weight,
   the rules judge, Kev's probability bars, GNN risk, and retrieved India Code sections.
2. **Document → clauses → findings:** open a PDF, see the page image, OCR vs native per page, the clause tree, then Analyse.
3. **Console:** every stage's log line with timings + the raw JSON.

**Verdict: optional, show only the Playground for ~1 minute, and only if a panel member asks "how do the methods
compare on one example?" or "show me the GNN / BM25 actually running".** It's the only place where every technique
(including the GNN) runs live on the same input, which answers "did you really use X?" in one click.

**Cautions (couldn't verify live: laptop went offline):**
- Its label still says "Kev fine-tuned :8008 · Kev base :8009". Now :8008 serves the **base** Kev and nothing runs on
  :8009, so one Kev row will show an error or "unavailable". Say: "port 8009 was the fine-tuned comparison server,
  not running in the demo."
- Keep **"also ask Gemini" unchecked** (Gemini is slow tonight).
- It's dark-themed (the web pages are light).
- **Test it once in the morning** (`Run every method` on example "cap", note how long it takes). If it takes more than
  ~20 s or shows errors, skip it. `show_steps.py` and `/scores` already cover the same ground.
