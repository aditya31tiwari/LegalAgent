# Data Model

Five tables. Anything that is a list belonging to exactly one row is JSONB on that row, not
a join table — this is a single-tenant-per-user app with no queries that filter by label or
join across findings, so normalising those out buys nothing and costs five migrations.

Not needed for v0. The v0 pipeline writes JSON to disk. Introduce this when the frontend
and login arrive.

## Conventions

- `id` is `BIGSERIAL` and never leaves the backend. APIs expose `public_id` only.
- `public_id` is a ULID/UUID text column, unique, generated on insert.
- Timestamps are `TIMESTAMPTZ`, UTC.
- Every content table carries `user_id`. Every query filters on it.

---

## `users`

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `public_id` | TEXT UNIQUE NOT NULL | |
| `email` | CITEXT UNIQUE NOT NULL | |
| `password_hash` | TEXT NOT NULL | argon2id |
| `display_name` | TEXT | |
| `created_at` | TIMESTAMPTZ NOT NULL | |

---

## `contracts`

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `public_id` | TEXT UNIQUE NOT NULL | |
| `user_id` | BIGINT FK → users | indexed, ON DELETE CASCADE |
| `filename` | TEXT NOT NULL | |
| `sha256` | TEXT NOT NULL | dedupe |
| `storage_key` | TEXT NOT NULL | original file in object store |
| `normalized_text` | TEXT | **canonical**; all char offsets index into this |
| `status` | TEXT NOT NULL | `processing` / `ready` / `failed` |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `deleted_at` | TIMESTAMPTZ | |

Index `(user_id, created_at DESC)` for the history list.

`normalized_text` is immutable after ingestion. Regenerating it with different normalization
logic silently invalidates every stored offset in the system.

---

## `clauses`

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `public_id` | TEXT UNIQUE NOT NULL | |
| `contract_id` | BIGINT FK → contracts | indexed, ON DELETE CASCADE |
| `parent_id` | BIGINT FK → clauses | nullable self-reference |
| `number` | TEXT | `"5.2"`, `"(a)"` |
| `heading` | TEXT | |
| `text` | TEXT NOT NULL | |
| `char_start` | INTEGER NOT NULL | offset into `contracts.normalized_text` |
| `char_end` | INTEGER NOT NULL | |
| `ordinal` | INTEGER NOT NULL | document order |
| `labels` | JSONB NOT NULL DEFAULT `'[]'` | `[{"label":"indemnification","confidence":0.91}]` |
| `xrefs` | JSONB NOT NULL DEFAULT `'[]'` | `[{"raw":"Section 8.2","clause_id":"cls_...","resolved":true}]` |

Index `(contract_id, ordinal)`.

**Labels are multi-label** — a clause can be both a liability cap and an indemnity. A JSONB
array handles that without a second table. Add a GIN index only if you ever filter by label.

**Embeddings do not live here.** Keep them in FAISS or ChromaDB keyed by `clauses.public_id`.
Putting vectors in Postgres means pgvector setup you don't need for a project this size.

---

## `analysis_runs`

One pipeline execution over one contract. Worth keeping as its own table because you will run
the same contract under BM25, dense, and hybrid and need to compare the outputs.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `public_id` | TEXT UNIQUE NOT NULL | |
| `contract_id` | BIGINT FK → contracts | indexed, ON DELETE CASCADE |
| `user_id` | BIGINT FK → users | for access checks without a join |
| `config` | JSONB NOT NULL | retrieval method, k, thresholds, model names |
| `stats` | JSONB NOT NULL | `{"clauses":47,"pairs":28,"findings":6,"no_issue":22}` |
| `status` | TEXT NOT NULL | `queued` / `running` / `complete` / `failed` |
| `error` | TEXT | |
| `created_at` | TIMESTAMPTZ NOT NULL | |
| `finished_at` | TIMESTAMPTZ | |

`config` as JSONB means new knobs need no migration, and every result stays traceable to the
settings that produced it. `stats.no_issue` is the denominator of your false-positive rate.

---

## `findings`

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL PK | |
| `public_id` | TEXT UNIQUE NOT NULL | |
| `run_id` | BIGINT FK → analysis_runs | indexed, ON DELETE CASCADE |
| `target_clause_id` | BIGINT FK → clauses | indexed |
| `related_clause_ids` | BIGINT[] NOT NULL | usually one |
| `relation_type` | TEXT NOT NULL | `conflict` / `dependency` / `overlap` / `ambiguity` |
| `severity` | TEXT NOT NULL | `low` / `medium` / `high` |
| `risk_score` | REAL NOT NULL | pre-threshold value |
| `rationale` | TEXT NOT NULL | |
| `surfaced_by` | TEXT[] NOT NULL | `{bm25,type_matrix}` |
| `evidence` | JSONB NOT NULL | `[{"clause_id":"cls_...","start":12210,"end":12288}]` |
| `refs` | JSONB NOT NULL DEFAULT `'[]'` | RAG sources: `[{"source":"CUAD::0142","snippet":"...","score":0.78}]` |
| `scores` | JSONB NOT NULL | retrieval score, analysis confidence |
| `feedback` | TEXT | `agree` / `disagree` / `unsure`, nullable |
| `created_at` | TIMESTAMPTZ NOT NULL | |

`no_issue` results are not stored — count them in `analysis_runs.stats`.

**Evidence is offsets, not copied text.** The frontend slices `normalized_text` to render a
highlight, so a highlight is always real document text and a hallucinated quote is
structurally impossible to persist.

**`feedback` is a column, not a table.** One verdict per finding is all you need, and joining
it against `surfaced_by` answers *which retrieval method produced findings a human agreed
with* — a stronger result than precision@k alone.

---

## What is deliberately not a table

**Evaluation data.** Gold pairs and precision/recall results live in CSV under `eval/`,
produced by scripts and read by your report. They are research artifacts, not application
state. Putting them in Postgres adds migrations and gives you nothing a dataframe doesn't.

**The CUAD reference corpus** for Layer 7 RAG grounding. That is a vector index in ChromaDB,
not an application table. Built once offline, read-only at runtime.

**Clause labels, xrefs, evidence, refs.** JSONB columns above. Each belongs to exactly one
parent row and is never queried independently.

---

## Deletion

`DELETE FROM users WHERE id = ?` cascades through contracts → clauses → runs → findings.
Verify every FK declares `ON DELETE CASCADE` or the cascade stops partway.

Two things the cascade does not reach, so do them explicitly:
- the original file in the object store
- cached LLM responses keyed to that user's clause text

Uploaded contracts are private documents. Not training data, and never in a log line.
