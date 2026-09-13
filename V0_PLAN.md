# V0 Implementation Plan

One thing only: a contract file goes in one end, a list of flagged clause pairs with reasons
comes out the other. Nothing in v0 needs to be good. Everything in v0 needs to be connected.

Target: running by end of week 2.

## The rule for v0

If a stage can be faked in under fifty lines, fake it. The purpose is to surface integration
problems — mismatched field names, clause IDs that don't resolve, findings pointing at
clauses that no longer exist — while they cost an afternoon instead of a fortnight.

Two things v0 does **not** cut corners on:

1. **Ingestion**, built to v1 immediately. Every `char_start` in the system is an offset into
   whatever text this stage emits. Getting it wrong twice means re-deriving every offset.
2. **The data shapes**, which are final from day one. They mirror the columns in
   `DATA_MODEL.md` and the response bodies in `API.md`, so the later database and API are
   persistence and transport over structures that already exist — not a redesign.

---

## Day 1–2: Fix the shapes

`core/types.py`. Field names match the table columns exactly, because they will later *be*
the table columns.

```python
@dataclass
class Clause:
    id: str                    # "acme_msa::5.2" in v0, becomes public_id
    contract_id: str
    parent_id: str | None
    number: str | None         # "5.2", "(a)"
    heading: str | None
    text: str
    char_start: int            # offset into normalized_text
    char_end: int
    ordinal: int               # document order
    labels: list[dict]         # [{"label": "...", "confidence": 0.9}]  -> JSONB
    xrefs: list[dict]          # [{"raw": "Section 8.2", "clause_id": "...",
                               #   "resolved": True}]                   -> JSONB

@dataclass
class Finding:
    id: str
    target_clause_id: str
    related_clause_ids: list[str]
    relation_type: str         # conflict | dependency | overlap | ambiguity
    severity: str              # low | medium | high
    risk_score: float
    rationale: str
    surfaced_by: list[str]     # ["bm25", "type_matrix"]
    evidence: list[dict]       # [{"clause_id": "...", "start": 0, "end": 0}]  -> JSONB
    refs: list[dict]           # RAG sources, empty in v0                      -> JSONB
    scores: dict               # {"retrieval": 0.62, "analysis_confidence": 0.88}

@dataclass
class Run:
    id: str
    contract_id: str
    config: dict               # {"retrieval_method": "bm25", "top_k": 5}
    stats: dict                # {"clauses": 47, "pairs": 28, "findings": 6,
                               #  "no_issue": 22}
```

Three notes on why these look the way they do:

- `labels` and `xrefs` are lists of dicts rather than typed objects because they become JSONB
  columns and pass through the API untouched. Keeping them as plain dicts end to end means
  zero serialization glue later.
- `evidence` holds **offsets, not text**. The renderer slices `normalized_text`. A
  hallucinated quote then cannot be persisted or displayed — it fails validation first.
- `Run` exists in v0 even though there is no database. It is where `stats.no_issue` lives,
  and that number is the denominator of your false-positive rate.

All three of you review this file together. After it merges, changes need everyone's
agreement.

### The pipeline skeleton

`core/pipeline.py`, every stage stubbed to return empty:

```python
def analyse(file_path: str, config: dict) -> tuple[Run, list[Clause], list[Finding]]:
    text     = ingest(file_path)
    clauses  = extract(text)
    clauses  = classify(clauses)
    pairs    = select_candidates(clauses, config)
    findings = analyse_pairs(pairs)
    findings = score_risk(findings)
    findings = explain(findings)
    return build_run(config, clauses, pairs, findings), clauses, rank(findings)
```

This file should not change again for the rest of the project. Every later week replaces the
body of one of these seven functions.

### The test that carries the project

```python
def test_smoke():
    run, clauses, findings = analyse("tests/fixtures/acme_msa.pdf", {})
    ids = {c.id for c in clauses}
    text = load_normalized_text()

    assert findings
    for f in findings:
        assert f.target_clause_id in ids
        assert all(r in ids for r in f.related_clause_ids)
        for e in f.evidence:
            assert text[e["start"]:e["end"]].strip()      # offsets resolve
```

That last assertion catches hallucinated evidence automatically for the next ten weeks.
Write it before there is a model capable of hallucinating.

---

## Day 3–4: Ingestion, built properly

Skips v0 entirely — build it once, correctly.

- `pdfplumber` for PDF, `python-docx` for DOCX, plain read for TXT
- Normalization, in a fixed order, applied exactly once:
  1. strip repeating headers/footers (lines recurring on most pages)
  2. drop standalone page numbers
  3. rejoin hyphenated line breaks
  4. collapse whitespace runs, preserve paragraph breaks
- Emit `normalized_text`. This is the canonical document; the original file is kept for
  download only. It becomes `contracts.normalized_text` and is served by
  `GET /contracts/{id}/text`.

Test: the same file ingested twice produces byte-identical output. Make it an assertion.

---

## Day 5–6: Extraction v0

One regex, decimal numbering only:

```python
CLAUSE_RE = re.compile(r'^\s*(\d+(?:\.\d+)*)\.?\s+(.{0,80}?)\n', re.M)
```

Split on matches, text runs to the next match, `char_start`/`char_end` from match offsets,
`ordinal` from enumeration. Flat list — no `parent_id`, no heading detection, no `(a)/(b)`.

Pick three CUAD contracts with plain decimal numbering as fixtures. Contracts with Roman
numerals or lettered sub-clauses are week 3.

**Do the cross-reference regex properly now:**

```python
XREF_RE = re.compile(r'(?:Section|Clause|Article|clause)\s+(\d+(?:\.\d+)*)')
```

Populate `xrefs` with `{"raw": ..., "clause_id": ..., "resolved": bool}`. Keep unresolved
ones — a high unresolved rate is your signal that extraction is missing clauses. Twenty
minutes of work, and it produces the gold pairs for your retrieval evaluation.

---

## Day 7: Classification v0

A dictionary, not a model. See `CUAD.md` for the real taxonomy work.

```python
KEYWORDS = {
  "indemnification":         ["indemnif", "hold harmless", "defend"],
  "limitation_of_liability": ["limitation of liability", "in no event shall",
                              "aggregate liability", "consequential damages"],
  "termination":             ["terminate", "termination for cause"],
  "confidentiality":         ["confidential information", "non-disclosure"],
  "governing_law":           ["governed by the laws", "governing law"],
  "assignment":              ["assign", "successors and assigns"],
  "survival":                ["survive", "shall survive termination"],
  "exclusivity":             ["exclusive", "sole and exclusive"],
}
```

Substring match, lowercase, append every hit to `labels` with `confidence: 1.0` and a
`"source": "keyword"` field.

It will be wrong often. Its only job is to make the type matrix fire so the downstream stages
have something to work on. Real classification is week 5, and it writes to the same `labels`
field with `"source": "legalbert"`.

---

## Day 8: Candidate selection v0

BM25 only, plus cross-references, plus the type matrix.

```python
def select_candidates(clauses, config):
    k = config.get("top_k", 5)
    pairs = {}
    def add(a, b, how):
        key = tuple(sorted((a, b)))
        pairs.setdefault(key, set()).add(how)

    for c in clauses:
        for hit in bm25_top_k(c, clauses, k):
            add(c.id, hit.id, "bm25")
        for x in c.xrefs:
            if x["resolved"]:
                add(c.id, x["clause_id"], "xref")
    for a, b in type_matrix_pairs(clauses):
        add(a, b, "type_matrix")

    return [(a, b, sorted(hows)) for (a, b), hows in pairs.items()]
```

The `hows` set becomes `Finding.surfaced_by`. Dedupe by sorted pair so the same pair found by
two methods is one candidate carrying both attributions — that is exactly the field the
retrieval comparison is built on.

Write the type matrix YAML now. Twenty lines, ships in v0, survives untouched to the final
system.

Cap candidates at ~30 per contract so a run is cheap.

---

## Day 9: Analysis v0

One LLM call per pair, prompt demanding JSON that matches the `Finding` fields.

Two guardrails from the start:

1. `no_issue` is an allowed `relation_type`, stated explicitly in the prompt. These are
   dropped from the findings list and counted into `Run.stats["no_issue"]` — matching how
   `analysis_runs.stats` works later.
2. `evidence` spans are validated as verbatim substrings of the clause text, then converted
   to absolute offsets against `normalized_text`. Reject and log the finding if validation
   fails.

Cache responses keyed by a hash of the two clause texts. You will run this pipeline hundreds
of times and should not pay for every run.

---

## Day 10: Risk and explanation v0

**Risk** — a lookup, plus a score so `risk_score` is populated from the start:

```python
SEVERITY = {"conflict": ("high", 0.9), "dependency": ("medium", 0.6),
            "overlap": ("low", 0.3), "ambiguity": ("medium", 0.5)}
```

**Explanation** — a template, no retrieval. `refs` stays `[]`.

```python
rationale = f"Clause {a.number} and clause {b.number} appear to {relation}. {model_reason}"
```

Both are replaced in week 10 and both take fifteen minutes now.

---

## Day 11–12: Output

Rank by severity then retrieval score, group by target clause, dump JSON.

**The JSON is the `GET /runs/{id}/findings` response body, exactly.** Same field names, same
nesting. When the API arrives it serializes these dataclasses directly, and the evaluation
scripts you write against v0 JSON keep working against API exports unchanged.

```json
{
  "run": {
    "id": "run_local_001",
    "contract_id": "ctr_local_001",
    "config": { "retrieval_method": "bm25", "top_k": 5 },
    "stats": { "clauses": 47, "pairs": 28, "findings": 6, "no_issue": 22 }
  },
  "items": [
    {
      "id": "fnd_...",
      "relation_type": "conflict",
      "severity": "high",
      "risk_score": 0.9,
      "rationale": "...",
      "surfaced_by": ["type_matrix", "bm25"],
      "target_clause": { "id": "...", "number": "5.2", "heading": "Limitation of Liability" },
      "related_clauses": [ { "id": "...", "number": "9.1", "heading": "Indemnification" } ],
      "evidence": [ { "clause_id": "...", "start": 12210, "end": 12288 } ],
      "refs": [],
      "scores": { "retrieval": 0.62, "analysis_confidence": 0.88 }
    }
  ]
}
```

CLI is sufficient:

```
python -m legalagent analyse contracts/acme.pdf --method bm25 -o out/run_001.json
```

No frontend in v0. A JSON file your mentor can open is a complete deliverable.

---

## What "done" looks like

```
$ python -m legalagent analyse tests/fixtures/acme_msa.pdf

  Extracted  47 clauses
  Classified 31  (16 unlabelled)
  Candidates 28 pairs
  Analysed   28  ->  6 findings, 22 no_issue

  HIGH   5.2 (Limitation of Liability) <-> 9.1 (Indemnification)   [type_matrix, bm25]
         The liability cap in 5.2 is not carved out of the indemnity
         obligation in 9.1, so 9.1 may operate without limit.

  MEDIUM 12.3 (Termination) <-> 14.1 (Survival)                    [xref]
         ...
```

Six findings, some wrong, with every stage boundary proven. That is the goal.

---

## What v0 deliberately omits

No LegalBERT. No dense or hybrid retrieval. No RAG grounding. No database, API, login, or
frontend. No LangGraph, MCP, or GNN. No evaluation numbers.

Each is a replacement for a function that already exists and already has a caller, writing
into a field that already exists. That is what the two weeks bought.

## The path from v0 to the product layer

| v0 | Later |
|---|---|
| `Clause` dataclass | `clauses` row; `labels`/`xrefs` become JSONB |
| `Finding` dataclass | `findings` row; `evidence`/`refs`/`scores` become JSONB |
| `Run` dataclass | `analysis_runs` row; `config`/`stats` become JSONB |
| JSON file on disk | `GET /runs/{id}/findings` response body |
| `id` string | `public_id`; an internal `BIGSERIAL` appears alongside it |
| CLI flags | `POST /contracts/{id}/runs` request body |

No field is renamed anywhere in that table. That is the point of fixing the shapes on day one.
