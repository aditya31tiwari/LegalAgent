# Clause taxonomy research — requirements

**Goal:** decide the final set of clause labels LegalAgent assigns to every clause (currently
"CLAUSE-20"), so that the labels (a) are learnable from data we can actually get, (b) drive
cross-clause risk detection, and (c) make sense for **Indian** commercial contracts.

The output of this research feeds directly into code: `clause20/labels.yaml` (taxonomy +
clash pairs), `clause20/label_map.yaml` (source-label → our label), and the training scripts.
So every recommendation must be concrete enough to edit those files.

## Hard constraints

1. **Deadline.** Project viva in ~18 h. Research output is needed within ~3 h so a retrain
   (~45 min InLegalBERT fine-tune on an RTX 4050, 6 GB) still fits. Prefer changes that
   only need `label_map.yaml` / `labels.yaml` edits + a rebuild, over new annotation work.
2. **Trainability.** A label is only worth adding if there are ≥ ~300 training examples after
   de-duplication (current `min_support`), from a source we can download today without
   gated access or paid licences — or if it can be reliably detected by a documented rule
   (like `force_majeure` today) or silver-labelled by Gemini with spot checks.
3. **Compatibility with the pipeline.**
   - Multi-label classification, one clause can carry 1–3 labels; `other` is a sink.
   - Every label must take part in at least one entry of `conflict_pairs` (a pair of labels
     that can clash or depend on each other, with a weight 0–1). Labels with no clash role
     are useless to cross-clause detection and should be `other`.
   - Labels are consumed by: candidate selection (`TYPE_MATRIX` from `conflict_pairs`), the
     rule judge (`legalagent/core/analysis.py`), the local Kev judge (labels go into its input
     text), the GNN (one-hot node features), and the UI.
   - Renaming/merging labels is fine; the code reads names from `labels.yaml`.
4. **Indian relevance.** Contracts we demo on are Indian (PPP/concession agreements — NHAI,
   Pune Metro — IT/SaaS MSAs, employment, vendor supply). Labels should cover what an Indian
   reviewer checks: e.g. stamp duty, Section 27 restraint of trade, liquidated damages vs
   penalty (ICA s.74), arbitration seat/venue (A&C Act 1996), DPDP Act 2023 data protection,
   force majeure / change in law, performance security / bank guarantee, termination
   payments / compensation, step-in / substitution rights in concessions.
5. **Honesty.** No public Indian contract-clause dataset is known to us. If you find one,
   that is the single most valuable result. Otherwise say so plainly and propose the least
   costly route (silver labels, mapping, rules).

## Questions to answer

1. **Taxonomy:** Is the current 20-label set right? What should be split, merged, added or
   demoted? Specifically consider:
   - `limitation_of_liability` currently absorbs CUAD "Uncapped Liability" **and**
     "Liquidated Damages" — semantically opposite/different. Split?
   - `compliance_and_law` and `amendment_and_integration` are large catch-alls (7k rows each).
     Useful for clash detection or noise?
   - `dispute_resolution` mixes jurisdiction, jury waiver, arbitration, remedies, releases.
     Split arbitration out (very relevant for India)?
   - Candidates to add: `force_majeure`, `liquidated_damages`, `data_protection`,
     `non_compete`/`non_solicit` (split from `exclusivity_and_restraint`), `performance_security`,
     `change_in_law`, `step_in_rights`, `stamp_duty`, `representations` vs `warranty`,
     `definitions` (needed to resolve defined-term conflicts?), `payment_terms` vs `pricing`.
2. **Data:** For each proposed label, which source provides examples and how many?
   Check at least: CUAD (41 cats), LEDGAR (100 labels), **ContractNLI**, **MAUD** (merger
   agreements, 92 questions), **ACORD** (2025 clause retrieval benchmark), **LEDGAR full
   (non-LexGLUE, ~12.6k labels)**, **CLAUSEEDGE / ToS datasets (unfair ToS, CLAUDETTE)**,
   **LegalBench** clause tasks, **Atticus "MAUD"/"CUAD-QA"**, Indian sources: **IL-TUR**,
   **InLegalNER**, **Open India Law** (statutes only), OpenNyAI, any Indian contract corpora
   (e.g. model concession agreements from NITI Aayog / DEA PPP cell / MoRTH — public PDFs we
   could silver-label). Give HF ids / URLs, licence, size, gated or not.
3. **Compatibility matrix:** Propose the final `conflict_pairs` (label A + label B → weight,
   one-line legal reason each, Indian statute where relevant). Mark which pairs are
   *conflict* vs *dependency* vs *overlap*.
4. **Hierarchy?** Would a two-level taxonomy (coarse 8–10 families → fine labels) help
   training (hierarchical loss) or the UI? Cost/benefit given the deadline.
5. **Evaluation:** How should the new labels be evaluated on Indian text? (We have ~220
   Gemini-silver-labelled Indian clauses in `data/derived/india_clause_eval.jsonl`.)

## Deliverables (write into this folder)

- `04_FINDINGS.md` — answers to the questions above, with sources (URLs).
- `05_PROPOSED_labels.yaml` — drop-in replacement for `clause20/labels.yaml`
  (same schema: `labels`, `min_support`, `known_gaps`, `conflict_pairs`).
- `06_PROPOSED_label_map.yaml` — drop-in for `clause20/label_map.yaml`
  (every CUAD and LEDGAR label must still map; `unmapped_policy: fail`).
- `07_DATASETS.md` — table: dataset, URL/HF id, licence, gated?, size, which labels it feeds,
  effort to integrate (S/M/L).
- `08_MIGRATION.md` — exact steps + expected retrain time, and what changes in code
  (classification keywords, `analysis.py` rules, UI colours).
