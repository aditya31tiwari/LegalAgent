# API Specification

Backend HTTP API for the product layer. Response shapes map 1:1 onto the five tables in
`DATA_MODEL.md`.

Not needed for v0 — the v0 deliverable is a CLI that writes JSON. Build this alongside the
frontend.

## Conventions

- Base path `/api/v1`. Versioned so the later MCP interface can sit beside it.
- JSON in, JSON out, except upload.
- **Every identifier in a request or response is `public_id`.** Internal numeric IDs never
  appear in a payload, URL, or log line.
- Auth is a bearer token. The user is derived from the token, **never** from the request
  body. A `user_id` in a body is ignored.
- Analysis is asynchronous: starting a run returns a run ID, the client polls it.
- JSONB columns (`labels`, `xrefs`, `evidence`, `refs`, `scores`, `config`, `stats`) are
  returned verbatim as nested JSON. No reshaping between database and API.

### Error shape

```json
{ "error": { "code": "CONTRACT_NOT_FOUND", "message": "No contract with that id." } }
```

| Status | When |
|---|---|
| 400 | malformed request |
| 401 | missing or invalid token |
| 404 | no such resource, **or it belongs to another user** |
| 409 | conflicting state, e.g. run already in progress |
| 413 / 415 | file too large / unsupported type |
| 422 | valid JSON, invalid values |
| 429 | rate limited |

Return 404 rather than 403 for another user's resource. A 403 confirms it exists, which
leaks information about other users' documents.

---

## Auth → `users`

### `POST /api/v1/auth/register`
```json
{ "email": "a@example.com", "password": "...", "display_name": "Aryan" }
```
→ `201` `{ "user": { "id": "usr_...", "email": "...", "display_name": "..." }, "access_token": "...", "expires_in": 3600 }`

### `POST /api/v1/auth/login`
Same response shape. Identical error **and identical response timing** for unknown email and
wrong password — a faster 401 for unknown emails is a user-enumeration oracle.

### `POST /api/v1/auth/logout` → `204`

### `GET /api/v1/auth/me`
→ `200` `{ "id": "usr_...", "email": "...", "display_name": "...", "created_at": "..." }`

### `DELETE /api/v1/auth/me`
```json
{ "confirm": "DELETE" }
```
→ `202` `{ "status": "deletion_scheduled" }`

Cascades users → contracts → clauses → runs → findings. Then, explicitly, because the
cascade does not reach them: the object-store file and any cached LLM responses.

---

## Contracts → `contracts`

### `POST /api/v1/contracts`
`multipart/form-data`, one `file` part. PDF / DOCX / TXT, validated on magic bytes not
extension. 20 MB cap. → `201`

```json
{
  "id": "ctr_...",
  "filename": "acme_msa.pdf",
  "status": "processing",
  "created_at": "2026-09-13T10:04:00Z"
}
```

Ingestion and extraction run async. `status` moves `processing` → `ready` | `failed`.

### `GET /api/v1/contracts`
Query: `limit` (default 20), `cursor`, `status`
→ `200` `{ "items": [ …contract summaries… ], "next_cursor": "..." }`

The History screen.

### `GET /api/v1/contracts/{id}`
→ `200` the contract row plus `clause_count` and a summary of the latest run.

### `GET /api/v1/contracts/{id}/text`
→ `200` `{ "text": "...", "length": 48213 }`

This is `contracts.normalized_text`. The frontend needs it because every evidence offset
indexes into this exact string. Never render highlights against the original file — its
offsets will not match.

### `GET /api/v1/contracts/{id}/clauses`
Query: `label`, `limit`, `cursor` → `200`

```json
{
  "items": [
    {
      "id": "cls_...",
      "parent_id": "cls_...",
      "number": "5.2",
      "heading": "Limitation of Liability",
      "text": "...",
      "char_start": 12044,
      "char_end": 12890,
      "labels": [ { "label": "limitation_of_liability", "confidence": 0.91 } ],
      "xrefs": [ { "raw": "Section 9.1", "clause_id": "cls_...", "resolved": true } ]
    }
  ],
  "next_cursor": null
}
```

`labels` and `xrefs` are the JSONB columns passed straight through.

### `DELETE /api/v1/contracts/{id}` → `204`
Sets `deleted_at`, removes the object-store file.

---

## Runs → `analysis_runs`

### `POST /api/v1/contracts/{id}/runs`
```json
{ "retrieval_method": "hybrid", "top_k": 5, "include_type_matrix": true, "include_xrefs": true }
```
All optional, server defaults apply. The body becomes `analysis_runs.config` as-is.
→ `202` `{ "id": "run_...", "status": "queued", "contract_id": "ctr_..." }`
→ `409` if a run for that contract is already queued or running.

Exposing `retrieval_method` is deliberate: it lets you switch BM25 / dense / hybrid on the
same contract live in a viva, which lands better than a table of numbers on a slide.

### `GET /api/v1/runs/{id}`
→ `200`

```json
{
  "id": "run_...",
  "contract_id": "ctr_...",
  "status": "complete",
  "config": { "retrieval_method": "hybrid", "top_k": 5 },
  "stats": { "clauses": 47, "clauses_labelled": 31, "pairs": 28, "findings": 6, "no_issue": 22 },
  "created_at": "...",
  "finished_at": "..."
}
```

`config` and `stats` are the JSONB columns verbatim. `stats.no_issue` is the denominator of
your false-positive rate — it is evidence the analysis layer can say "nothing wrong here."

Poll this every two seconds while `status` is `queued` or `running`. Skip SSE unless the
demo feels sluggish without it.

---

## Findings → `findings`

### `GET /api/v1/runs/{id}/findings`
Query: `severity`, `relation_type`, `group_by=target_clause`, `limit`, `cursor` → `200`

```json
{
  "items": [
    {
      "id": "fnd_...",
      "relation_type": "conflict",
      "severity": "high",
      "risk_score": 0.86,
      "rationale": "The liability cap in 5.2 is not carved out of the indemnity obligation in 9.1, so 9.1 may operate without limit.",
      "surfaced_by": ["type_matrix", "bm25"],
      "target_clause": { "id": "cls_...", "number": "5.2", "heading": "Limitation of Liability" },
      "related_clauses": [ { "id": "cls_...", "number": "9.1", "heading": "Indemnification" } ],
      "evidence": [
        { "clause_id": "cls_...", "start": 12210, "end": 12288 },
        { "clause_id": "cls_...", "start": 19004, "end": 19102 }
      ],
      "refs": [ { "source": "CUAD::0142::Cap On Liability", "snippet": "...", "score": 0.78 } ],
      "scores": { "retrieval": 0.62, "analysis_confidence": 0.88 },
      "feedback": null
    }
  ],
  "next_cursor": null
}
```

`related_clauses` is `findings.related_clause_ids` resolved to number and heading for
display. `evidence`, `refs`, and `scores` are JSONB passed through unchanged.

Evidence is offsets, not text. The frontend already holds `normalized_text` from
`/contracts/{id}/text` and slices it, which guarantees a highlight is real document text and
makes a fabricated quote impossible to display.

### `GET /api/v1/findings/{id}`
→ `200` one finding with full clause bodies inlined, for the detail view.

### `PATCH /api/v1/findings/{id}/feedback`
```json
{ "verdict": "agree", "note": "optional" }
```
`verdict` ∈ `agree` / `disagree` / `unsure`. Writes the `findings.feedback` column. → `204`

A `PATCH` on the finding rather than a `POST` to a sub-collection, because it is one column
on one row. Joining it against `surfaced_by` tells you which retrieval method produced
findings a human actually agreed with.

### `GET /api/v1/runs/{id}/export`
Query: `format=json|csv` → `200` file download.

Same structure the v0 CLI emits, so evaluation scripts work unchanged regardless of whether
results came from the CLI or the API.

---

## Dashboard

### `GET /api/v1/dashboard`
→ `200`

```json
{
  "contracts_total": 12,
  "runs_total": 31,
  "findings_by_severity": { "high": 14, "medium": 39, "low": 52 },
  "recent_contracts": [ … ]
}
```

Aggregated server-side in one query. Do not fetch all findings and total them in the browser.

---

## Non-negotiables

- Identity comes from the token. `user_id`, `email`, or `role` in a body is ignored, always.
- Every contract, clause, run, and finding query filters on the authenticated user. No query
  in this system legitimately reads across users.
- Internal numeric IDs never appear in a response, URL, or log.
- Never log tokens, passwords, clause text, or uploaded filenames.
- Uploaded contracts are private documents, not training data.
- No endpoint lets a client set `severity` or `risk_score`. The rubric decides; the API
  reports.
