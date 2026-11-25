# Review of LegalAgent_Final_Report_final.docx (25 Nov 2026, viva day)

**Verdict:** the report matches the built system. The earlier change list was largely applied: CLAUSE-22, 4,408
sections, base Kev served, statute 0.32, no ContractNLI/FAISS/login claims, no placeholders. About a dozen fixes
remain. **#1 and #3 are the ones a panel can catch.**

## NEW (viva day): clause-vs-law check upgraded. Update §3.2.6, §5.1.4, Table 5.4
The law check now combines four measured signals, and the dashboard shows the result:
1. **Type gate:** InLegalBERT; only clauses whose type can carry a legal risk are checked.
2. **Kev risk type:** 7 categories, each mapped to its section.
3. **RAG corroboration:** the India Code search independently retrieves the same section → *law-confirmed*, +1 confidence level.
4. **Rule corroboration:** the regex rules fire too → *rule-confirmed*, +1 level; merged into one card.

Suggested text for §5.1.4: "As deployed, the check surfaced 13 of 15 real violations (7/9 Supreme Court struck-down,
6/6 planted) and flagged 1 of 30 ordinary clauses; keyword rules alone caught 4 of 15. Findings confirmed by an
independent India Code search were correct 4 times out of 5. Having Kev judge directly from retrieved statute text was
tested and was weaker (AUC 0.64 vs 0.74), so retrieval corroborates rather than decides. The 4 clauses the court upheld
are still flagged, because legal exceptions are not modelled." The full table is `/report` 4b
(`results/eval_lawcheck_pipeline.json`, `scripts/eval_rag_check.py`). This replaces the "nine false alarms" / 11/30 wording.

## Required changes (most serious first)

| # | Where | Now says | Change to | Why |
|---|---|---|---|---|
| 1 | §5.1.4 text + Table 5.4 | "nine false alarms, including all four [upheld]…"; column "False alarms: 9" | "It also wrongly flagged all 4 clauses the court upheld and 11 of 30 ordinary CUAD clauses." Split the column into "Upheld SC flagged 4/4" and "Ordinary clauses flagged 11/30" (regex: 0/4 and 0/30) | Re-measured this morning on the **served base Kev** (the old figure was from the fine-tuned v2) |
| 2 | Table 4.2 (test sets) | no false-alarm set | Add row "Ordinary CUAD clauses, 30, false-alarm check" | Backs the 11/30 |
| 3 | Table 4.1 (models) | "Kev-0.8B (bf16, about 3.8 GB peak GPU memory)" | "Kev-0.8B base, zero-shot (bf16, ~1.8 GB GPU, CUDA graphs disabled)" | Current serving setup |
| 4 | §3.2.7, §4.1.6, Table 5.8 O4 | "4,408 sections from 37 central Acts" | "4,408 sections from 37 sources (central Acts, the Constitution and 7 key Supreme Court precedents), from India Code and the Nyaya datasets" | Exact composition |
| 5 | Abstract | "Training labels for the judge were produced by a large teacher model" | "Teacher labels (Gemini 4: 1,740 pairs; Claude: 620) were used to fine-tune Kev; the fine-tuned versions lost on independent tests, so the base Kev-0.8B is served zero-shot." | The current text implies the served judge was trained on those labels |
| 6 | §3.2.8 | "Kev was then fine-tuned on the labels." | Add: "The untouched base model won and is the one the system serves." | Same as #5 |
| 7 | §3.2.2 vs §3.2.5, §3.1, §4.4 | "Gemini is used only for the optional 'Expand' explanation" | "Gemini is used only when the user opts in: as a judge chosen in the upload dialog, or for the Expand explanation." In Table 3.1, add "opt-in judge" to Gemini's role | The upload dialog offers Gemini as a judge, so the current text contradicts itself |
| 8 | Table 5.1 | InLegalBERT Indian silver "0.417" | "0.411" | Final results |
| 9 | Abstract, Table 5.1, Table 5.8 O1 | MiniLM out-of-domain "0.591" | "0.590" | Final results |
| 10 | Table 5.8 O2 | "six retrieval methods compared" | "five" (or add the sixth row to Table 5.2) | Table 5.2 lists five |
| 11 | §4.3 | "pytest suite of 28 tests" | "32 tests" | Current count |
| 12 | Table 1.2 | "Main contributions" column | Fill in each member's contributions (Annexure 3 points here) | Looks empty in the extracted text; check in Word |
| 13 | §5.1.4 vs Appendix F | "nine clauses the Supreme Court struck down … four … upheld" | Add a column in Table A.6 marking which cases are in the 9 / 4 clause-vs-law test, and what the other cases are used for | Appendix F lists 5 void, 2 penalty, 5 upheld and 6 others; a panel member counting may find a mismatch |
| 14 | §6.3 Limitations | "The clause-vs-law check flags too often" | Give the numbers: 4/4 upheld and 11/30 ordinary clauses flagged; exact section in the top 5 only 32 %; InLegalBERT ≈ MiniLM on Indian text (0.411 vs 0.418); teacher cited sections from memory (85.7 % exist); Kev cannot separate the cap-vs-indemnity bad/fixed twin | The panel will probe these |
| 15 | §4.1.7 / Fig 4.3 caption | "All screenshots show real pipeline output…" | Add: "Planted-fault contracts were analysed from a clean copy with the answer-key notes removed." | Pre-empts a "leakage" question |
| 16 | §3.2.7 vs TC11 | "never shows a citation that does not exist" vs "Citation marked as unverified" | Make both describe the same behaviour: citations are checked; unverifiable ones are labelled "unverified" | The two statements contradict each other |

**Check visually in Word:** in the extracted text, the Contents entries and References entries start with leftover
`<w:tab…>` markup. This is probably only an extraction artefact, but look at those two pages before printing.

## Recommended (not required)
- §3.2.4: state the cap ("all cross-reference pairs + 60 best others, ranked") and the 14,025 → 173 example.
- §3.2.5 and the abstract: write "base model, zero-shot" explicitly.
- Tables 3.1 and 4.1: add Claude Sonnet as the second teacher, with the counts 1,740 / 620.
- §5.1.8:
  - Add 1.8 GB GPU and ~4 decisions/s inside the full pipeline.
  - The NHAI timing (276 pages, 632 clauses, 279 pairs, ≈4.7 min) is in `/report` table 10, taken from the seeding log.
- Table 5.5:
  - Add the base dense row (0.053).
  - Say "three times better" applies to the exact-section metric only.
- §5.1.2:
  - Change "hybrid strongest overall" to "strongest on Indian text; bge-small best on CUAD".
  - Name the shortlist's dense model (MiniLM).
  - The fine-tuned clause↔clause retriever has no reported result: report it or say it wasn't evaluated.
- §5.1.7 GNN: change "kept as an optional component" to "off by default".
- Software: Python "3.11+" → "3.12 (project) / 3.13 (Kev server)"; Ubuntu 26.04.
- Table 5.10: change "Yes, pair by pair" to "Yes, for shortlisted pairs".
- Cite references [19]–[21] somewhere in the text, and add a reference for the Nyaya datasets.

## Correct, keep as is
- Classifier 0.931 / 0.750, the CLAUSE-22 splits and hyperparameters.
- Appendix A: 22 + other + 7 labels, 40 clash pairs.
- Judge numbers: 71 % / 75 % vs rules 46 % / 7.5 %; v1 43 %; v2 54 % / 21 % / 31 %.
- Statute retrieval 0.316 / 0.53, BM25 0.105, reranker 0.263.
- Clause-vs-law 6/9 vs regex 0/9; planted faults 5/6 vs 4/6.
- Teacher validation; GNN 0.742 vs 0.748.
- Kev 11 decisions/s, ~3,500 tokens/s, 82 ms.
- Pune Metro: 580 / 99 / 137, 173 pairs, 4.4 min.
- Appendix E failure log, the "chosen by independent tests" lesson, the economics section.
- ContractNLI only in related work and future work.
