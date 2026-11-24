# Teacher labelling job for the Antigravity CLI

Run from the repo root on the laptop (`/home/aryan/Projects/LegalAgent/LegalAgent`). Paste
everything below the line as the task. It is safe to split across several parallel agents:
give each one a different `CHUNK` range (see step 2).

---

You are labelling clause pairs from commercial contracts as a **teacher** for a small
on-device model in the LegalAgent project (Indian contract review). Your labels become the
training data, so be careful and consistent. Work **only** inside `research/teacher_labels/`:
do not modify any other file, do not run git, do not use the GPU, do not install anything.

## Input

`research/teacher_labels/pairs_to_label.jsonl`, one JSON object per line:

```
{"pair_id": "p00042", "contract": "...", "a_id": "...", "b_id": "...",
 "a_text": "<clause A>", "b_text": "<clause B>",
 "a_labels": ["limitation_of_liability"], "b_labels": ["indemnification"],
 "surfaced_by": ["type_matrix", "hybrid"]}
```

`a_labels`/`b_labels` are predicted clause types (may be wrong). `surfaced_by` says why the
pair was shortlisted (xref = one clause cites the other; type_matrix = their types often
clash; bm25/dense/hybrid = textual similarity). Most shortlisted pairs are **not** problems;
`no_issue` is expected to be the most common answer.

## Task

1. Read `research/teacher_labels/PROMPT.md` (this file) fully.
2. Process the pairs whose line numbers fall in your CHUNK (1-based, inclusive). If no CHUNK is
   given, do all lines. Work in batches of ~25 pairs. Before each batch, read your output
   file and skip pair_ids already labelled, so you can resume after an interruption.
3. For each pair, decide, as a senior Indian contract lawyer reading both clauses together:

   - `relation`, exactly one of:
     - `conflict`: the clauses make demands that cannot both be satisfied, or one silently
       undoes the other (e.g. an indemnity not made subject to a liability cap; a cap that
       excludes the very losses an indemnity promises to cover; two different notice periods
       for the same right).
     - `dependency`: one clause only works, or changes meaning, through the other (e.g. which
       obligations survive termination; a procedure defined elsewhere and cross-referenced;
       a payment triggered by a milestone in another clause).
     - `overlap`: both govern the same matter with duplicated or differing terms that invite
       inconsistency, without being a direct contradiction.
     - `ambiguity`: read together they leave a gap or an unclear outcome a court would resolve.
     - `no_issue`: independent or consistent; nothing a reviewer needs to flag. **Use this
       whenever you would not actually raise it with a client.**
   - `severity`: `low` | `medium` | `high` (use `low` for `no_issue`).
   - `risk`: number 0.0–1.0 (0.0 for `no_issue`).
   - `rationale`: one precise sentence naming the specific interaction (cite clause wording,
     not generalities). Empty string allowed for `no_issue`.
   - `citation`: the single most relevant **Indian** statute section, written exactly as
     `"<Act name with year>, Section <n>"` (e.g. `"Indian Contract Act, 1872, Section 74"`,
     `"Arbitration and Conciliation Act, 1996, Section 34"`, `"Specific Relief Act, 1963,
     Section 14"`, `"Digital Personal Data Protection Act, 2023, Section 8"`). For every pair
     that is NOT `no_issue`, give the closest Indian section that a reviewer would cite for
     the issue if the contract were governed by Indian law (e.g. survival/continuing
     obligations → ICA s.37 or s.62; uncapped indemnity → ICA s.124; penalty-like damages →
     ICA s.74; forum/arbitration → A&C Act s.7 or s.8; restraint → ICA s.27). Use `""` only
     for `no_issue` pairs or when no section genuinely bears on it. Never invent a section
     number you are not sure exists.

   Apply Indian law even when the contract is American (most pairs come from US SEC filings):
   e.g. ICA s.23 (unlawful object), s.27 (restraint of trade, post-termination non-competes
   void), s.28 (restraint of legal proceedings / limitation shortening), s.73-74 (damages,
   liquidated damages vs penalty), s.124-125 (indemnity), SRA 1963, A&C Act 1996.

4. Append one JSON object per line to your output file
   `research/teacher_labels/labels/<your-agent-name-or-chunk>.jsonl` (create `labels/` if
   needed), e.g. `labels/chunk_0001_0800.jsonl`:

```
{"pair_id": "p00042", "relation": "conflict", "severity": "high", "risk": 0.85,
 "rationale": "Clause A caps aggregate liability at fees paid while clause B requires uncapped indemnity for third-party IP claims, without stating which prevails.",
 "citation": "Indian Contract Act, 1872, Section 124"}
```

   One line per pair, valid JSON, no comments, no markdown fences, `pair_id` copied exactly.

5. When your chunk is finished, check that every pair_id in your range appears exactly once
   in your output file (write a tiny script in `research/teacher_labels/` if helpful) and
   report counts per relation.

## Quality bar

- Decide from the clause text, not from `a_labels`/`b_labels` or `surfaced_by`.
- Do not label everything as a conflict: a realistic share of `no_issue` is 50–75%.
- Be consistent: similar pairs get similar labels.
- If a clause is OCR garbage or truncated to meaninglessness, use `no_issue`, `low`, 0.0, and
  rationale `"unreadable"`.
