# V0 Implementation Plan

The goal of v0 is **one thing only**: a contract file goes in one end, a list of flagged
clause pairs with reasons comes out the other. Nothing in v0 needs to be good. Everything
in v0 needs to be *connected*.

Target: running by end of week 2.

---

## The rule for v0

If a stage can be faked in under fifty lines, fake it. The purpose is to discover integration
problems — mismatched field names, clause IDs that don't resolve, findings that reference
clauses that no longer exist — while they cost an afternoon instead of a fortnight.

The one thing v0 does **not** cut corners on is the data structures. Those are v1 quality
from day one, because every later upgrade is defined as "replace the body of this function,
keep the signature." If the signatures churn, the plan fails.

---

## Day 1–2: Fix the contracts

Write `core/types.py` containing `Clause`, `Finding`, `Span`, and `Ref` exactly as specified
in `LAYERS.md` Section 0. All three of you review it together. After this file is merged,
changes to it need everyone's agreement.

Write `core/pipeline.py` with the full call chain, every stage stubbed to return an empty
list:

```python
def analyse(file_path: str) -> list[Finding]:
    text     = ingest(file_path)
    clauses  = extract(text)
    clauses  = classify(clauses)
    pairs    = select_candidates(clauses)
    findings = analyse_pairs(pairs)
    findings = score_risk(findings)
    findings = explain(findings)
    return rank(findings)
```

This file should not change again for the rest of the project. Every subsequent week is
filling in or replacing one of these seven functions.

Alongside it, write the test that will carry the whole project:

```python
def test_smoke():
    findings = analyse("tests/fixtures/sample_contract.pdf")
    assert len(findings) > 0
    for f in findings:
        assert f.target_clause_id in clause_ids
        assert all(s.text in clause_text[s.clause_id] for s in f.evidence_spans)
```

That second assertion — evidence spans must be verbatim substrings — catches model
hallucination automatically for the rest of the project. Write it now, before there is a
model to hallucinate.

---

## Day 3–4: Ingestion, built properly

**This layer skips v0 entirely.** Every downstream `char_span` is an offset into whatever
text this stage emits, so getting it wrong twice means re-deriving every offset in the
system. Build it once, correctly.

- `pdfplumber` for PDF, `python-docx` for DOCX, plain read for TXT
- Normalization pass, in a fixed order, applied exactly once:
  1. strip repeating headers and footers (detect by finding lines that recur on most pages)
  2. drop standalone page numbers
  3. rejoin words broken by hyphenated line breaks
  4. collapse runs of whitespace to single spaces, preserve paragraph breaks
- Persist the **normalized** text as canonical. The original file is kept for download only.

Verify with: same file ingested twice produces byte-identical output. Make it a test.

---

## Day 5–6: Extraction v0

One regex, decimal numbering only:

```python
CLAUSE_RE = re.compile(r'^\s*(\d+(?:\.\d+)*)\.?\s+(.{0,80}?)\n', re.M)
```

Split on matches, take text up to the next match, record `char_span` from the match offsets.
Flat list — no `parent_id`, no heading detection, no `(a)/(b)` handling.

Pick three CUAD contracts that use plain decimal numbering as your fixtures. Do not fight
contracts with Roman numerals or lettered sub-clauses in v0; that is week 3 work.

**One thing to do properly here:** the cross-reference regex.

```python
XREF_RE = re.compile(r'(?:Section|Clause|Article|clause)\s+(\d+(?:\.\d+)*)')
```

It takes twenty minutes and it produces your gold-standard retrieval evaluation set. There is
no reason to defer it.

---

## Day 7: Classification v0

A dictionary. Not a model.

```python
KEYWORDS = {
  "indemnification":        ["indemnif", "hold harmless", "defend"],
  "limitation_of_liability":["limitation of liability", "in no event shall",
                             "aggregate liability", "consequential damages"],
  "termination":            ["terminate", "termination for cause", "notice period"],
  "confidentiality":        ["confidential information", "non-disclosure"],
  "governing_law":          ["governed by the laws", "governing law"],
  "assignment":             ["assign", "successors and assigns"],
  "survival":               ["survive", "shall survive termination"],
  "exclusivity":            ["exclusive", "sole and exclusive"],
}
```

Substring match, lowercase, assign every matching label. That is the whole implementation.

It will be wrong often. It does not matter. Its only job is to make the type matrix in the
next stage fire so you can see the downstream stages work. Real classification is week 5.

---

## Day 8: Candidate selection v0

BM25 only, via `rank-bm25`, plus explicit cross-references, plus the type matrix.

```python
def select_candidates(clauses):
    pairs = set()
    for c in clauses:
        for hit in bm25_top_k(c, clauses, k=5):
            pairs.add((c.id, hit.id, "bm25"))
        for ref in c.xrefs:
            if ref in by_number:
                pairs.add((c.id, by_number[ref].id, "xref"))
    for a, b in type_matrix_pairs(clauses):
        pairs.add((a.id, b.id, "type_matrix"))
    return dedupe(pairs)
```

Write the type matrix YAML now — it is twenty lines and it never needs upgrading. It is the
one component that ships in v0 and survives untouched to the final system.

No dense retrieval, no hybrid, no reranking. Those are weeks 6–7.

---

## Day 9: Analysis v0

One LLM call per candidate pair, with a prompt that demands JSON matching the `Finding`
schema. Crude prompt, no few-shot examples, no tuned instructions.

Two guardrails that go in from the start:

1. `no_issue` is an allowed `relation_type`, stated explicitly in the prompt
2. `evidence_spans` are validated as verbatim substrings after parsing — reject and log the
   finding if validation fails

Cache responses keyed by a hash of the two clause texts. You will re-run this pipeline
hundreds of times over the next ten weeks and you do not want to pay for every run.

Cap candidate pairs at something small — 30 per contract — so a v0 run is cheap and fast.

---

## Day 10: Risk and explanation v0

**Risk:** a lookup table, four lines.

```python
SEVERITY = {"conflict": "high", "dependency": "medium",
            "overlap": "low", "ambiguity": "medium", "no_issue": None}
```

**Explanation:** a template string, no retrieval.

```python
rationale = (f"Clause {a.number} and clause {b.number} appear to "
             f"{relation}. {model_reason}")
```

Both get replaced in week 10. Both take fifteen minutes now.

---

## Day 11–12: Output and wiring

Rank by severity then BM25 score, group by target clause, dump to JSON. A CLI is sufficient:

```
python -m legalagent analyse contracts/acme.pdf -o findings.json
```

The frontend is not part of v0. A JSON file your mentor can open is a complete v0 deliverable.

---

## What "done" looks like

```
$ python -m legalagent analyse tests/fixtures/acme_msa.pdf

  Extracted 47 clauses
  Classified 31 (16 unlabelled)
  Generated 28 candidate pairs
  Analysed  28 pairs -> 6 findings

  HIGH   5.2 (Limitation of Liability) <-> 9.1 (Indemnification)   [type_matrix]
         The liability cap in 5.2 is not carved out of the indemnity
         obligation in 9.1, so 9.1 may operate without limit.

  MEDIUM 12.3 (Termination) <-> 14.1 (Survival)   [xref]
         ...
```

Six findings on one contract, some of them wrong, with the plumbing between every stage
proven to work. That is the entire goal.

---

## What v0 deliberately does not have

No LegalBERT. No dense or hybrid retrieval. No RAG grounding. No frontend, login, storage,
or database. No LangGraph, MCP, or GNN. No evaluation numbers.

Every one of those is a replacement for a function that already exists and already has a
caller. That is what the two weeks bought you.
