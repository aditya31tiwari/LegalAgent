# Litigated clauses: Indian court ground-truth set

`cases.jsonl` holds 18 real contract clauses (or clause pairs) that the Supreme Court of India ruled on. Each clause text is copied verbatim from the clause as the judgment quotes it on Indian Kanoon, and the court's decision is the label.

| # | Case | Year | Kind | Outcome | Statute | Verified |
|---|------|------|------|---------|---------|----------|
| 1 | Percept D'Mark v. Zaheer Khan | 2006 | single_clause | void | ICA s.27 | yes |
| 2 | Superintendence Co. v. Krishan Murgai | 1980 | single_clause | void | ICA s.27 | yes |
| 3 | Niranjan Shankar Golikari v. Century Spinning | 1967 | single_clause | upheld | ICA s.27 | yes |
| 4 | Gujarat Bottling v. Coca Cola | 1995 | single_clause | upheld | ICA s.27 | yes |
| 5 | Kailash Nath Associates v. DDA | 2015 | single_clause | penalty | ICA s.74 | yes |
| 6 | Maula Bux v. Union of India | 1969 | single_clause | penalty | ICA s.74 | yes |
| 7 | ONGC v. Saw Pipes | 2003 | single_clause | upheld | ICA ss.73-74 | yes |
| 8 | Central Inland Water Transport v. Brojo Nath Ganguly | 1986 | single_clause | void | ICA s.23; Art.14 | yes |
| 9 | Union of India v. IndusInd Bank | 2016 | single_clause | upheld* | ICA s.28 | yes |
| 10 | Jagdish Chander v. Ramesh Chander | 2007 | single_clause | other | A&C Act s.7 | yes |
| 11 | N.N. Global Mercantile v. Indo Unique Flame | 2021/2023 | single_clause | other | Stamp Act; A&C Act | yes |
| 12 | Perkins Eastman v. HSCC | 2019 | single_clause | void | A&C Act s.12(5) | yes |
| 13 | TRF Ltd v. Energo Engineering | 2017 | cross_clause | void | A&C Act s.12(5) | yes |
| 14 | Enercon (India) v. Enercon GmbH | 2014 | cross_clause | other | A&C Act Part I | yes |
| 15 | Union of India v. Hardy Exploration | 2018 | cross_clause | other | A&C Act ss.20, 34 | yes |
| 16 | BGS SGS Soma JV v. NHPC | 2019 | single_clause | other | A&C Act ss.20, 42 | yes |
| 17 | Mankastu Impex v. Airvisual | 2020 | cross_clause | other | A&C Act ss.2(2), 11 | yes |
| 18 | Swastik Gases v. Indian Oil | 2013 | cross_clause | upheld | ICA s.28 | yes |

\* IndusInd: the court upheld the clause only because the pre-1997 Section 28 applied. Under the current Section 28 the same wording would be void, so read its `notes` field before using `expected_flag`.

## How to use it, and its limits

Use this as a case-study and sanity-check set. Run LegalAgent on each `clause_a` (and `clause_b` for cross-clause rows), then compare its flag and reasoning with `expected_flag` and `court_held`. The five `upheld` rows are negatives that test whether the agent over-flags valid clauses. With 18 hand-picked, mostly Supreme Court cases, it is far too small and too skewed (toward restraint-of-trade, penalty and arbitration seat/appointment clauses) to support precision/recall figures or any statistical claim; report the results as per-case findings.

Some labels depend on law that has since changed (IndusInd, N.N. Global, Hardy) or on interim rulings (Percept), and some risks sit at document level (stamping) rather than in the clause text, so check `notes` for each row. Clause text was copied from Indian Kanoon's rendering of each judgment; printed typos are kept, and the only edits are joined line-break hyphens, as stated in the notes.
