# Using CUAD

How LegalAgent derives its clause taxonomy from CUAD, why that derivation is defensible, and
what to say when someone asks whether you invented your own labels.

---

## What CUAD actually is

<cite index="7-1">CUAD contains 510 contracts and 13,101 labeled clauses across 41 label categories, annotated by legal experts.</cite> <cite index="5-1">For each of the 41 labels, a model must learn to highlight the portions of a contract most salient to that label.</cite>

The critical point: **CUAD is span extraction, not clause classification.** An annotation
says *in contract X, characters 4,102 to 4,890 are a Cap On Liability*. Nobody labelled
"clause 5.2" as a unit. The categories were designed as a due-diligence checklist for M&A
review — *does this contract have an anti-assignment clause, and where?* — which is a
different question from *what type of clause is this?*

<cite index="7-1">Labeled clauses make up about 10% of each contract on average, meaning that with 41 categories, only a small fraction of any contract carries any given label.</cite> Most contract text is unannotated. That is by design, and it has consequences for how you
train.

---

## The conversion: spans → clause labels

Layer 2 gives every clause a `char_span`. The conversion is a spatial join:

```python
def assign_labels(clause, cuad_spans, threshold=0.5):
    labels = set()
    for span in cuad_spans:
        overlap = intersect_length(clause.char_span, span.char_span)
        if overlap / span_length(span) >= threshold:
            labels.add(CATEGORY_MAP[span.category])
    return labels
```

Roughly thirty lines. Note what it does **not** do: it makes no legal judgment. Every label
traces back to a decision made by an Atticus-supervised lawyer. Your code only moves those
labels from one coordinate system (character offsets) to another (clause boundaries).

The standard phrasing for your report:

> CUAD provides span-level annotations. We derive clause-level labels by spatial overlap
> between annotated spans and extracted clause boundaries.

That sentence appears in dozens of papers. It is preprocessing, not annotation.

### The overlap threshold

Pick one and state it. Options:

| Rule | Behaviour |
|---|---|
| Full containment | span must sit entirely inside the clause — strict, loses spans crossing boundaries |
| ≥50% of span inside clause | **recommended default** |
| Any overlap > 0 | permissive, over-assigns on extraction errors |

Then run the sensitivity check: report how many labels change if you move the threshold to
0.3 and 0.7. One table, one paragraph. That single check converts an arbitrary constant into
a justified design decision, and it is the kind of thing that reads well in a viva.

---

## Collapsing 41 categories → ~13 clause types

CUAD's 41 categories do not map cleanly to clause types, for three reasons:

1. **Several describe the same clause type.** Cap On Liability, Uncapped Liability, and
   Liability Cap Exceptions all annotate limitation-of-liability text with different answers.
2. **Several are metadata, not clauses.** Document Name, Parties, Agreement Date,
   Effective Date, Expiration Date. These are facts extracted from a contract, not clause
   types to reason about.
3. **Several are too rare to train on.** Third Party Beneficiary, Covenant Not To Sue,
   and similar appear in a handful of contracts across the whole corpus.

Merging them is a many-to-one mapping over an existing taxonomy. Nothing is invented and
nothing is lost: publish the mapping and any reviewer can expand your results back to CUAD's
original categories.

### How to choose the target types

**Derive them from the risk matrix, not from CUAD.** Ask: which clause types appear in
Layer 5's type-pair matrix? Those are your classes. If a type never pairs with anything, it
does not need to exist.

This is the argument that closes the question. The taxonomy is not a preference — it is
determined by the downstream task.

### Suggested mapping (verify against the actual label list)

| LegalAgent type | CUAD categories folded in |
|---|---|
| `limitation_of_liability` | Cap On Liability, Uncapped Liability, Liability Cap Exceptions |
| `indemnification` | Insurance, indemnity-related spans |
| `termination` | Termination For Convenience, Notice Period To Terminate Renewal |
| `renewal_term` | Renewal Term, Expiration Date, Agreement Date (term-related) |
| `confidentiality` | confidentiality / non-disclosure spans |
| `governing_law` | Governing Law |
| `dispute_resolution` | arbitration / venue spans |
| `assignment` | Anti-Assignment, Change Of Control |
| `exclusivity` | Exclusivity, No-Solicit Of Customers, Non-Compete |
| `ip_ownership` | IP Ownership Assignment, Joint IP Ownership, License Grant |
| `audit_rights` | Audit Rights |
| `warranty` | Warranty Duration |
| `payment_terms` | Revenue/Profit Sharing, Minimum Commitment, Price Restrictions |
| *(dropped)* | Document Name, Parties, Effective Date, Notice, Third Party Beneficiary, … |

**Verify every row against the real label list** in the CUAD repository before you commit —
the exact category names matter and this table is reconstructed, not copied. Publish the
final version as an appendix in your report.

---

## Three consequences for training

**Multi-label, not single-label.** A clause saying *"Liability is capped at fees paid, except
for indemnity obligations under Section 9"* legitimately carries both
`limitation_of_liability` and `indemnification`. Use sigmoid outputs with per-class
thresholds, not softmax. Accuracy is the wrong metric because a prediction can be partly
right.

**Most clauses have no label.** Definitions, notices, severability, counterparts — CUAD does
not annotate them and they are the majority of any contract. That is not missing data. Your
model needs a valid "none of the above" outcome, and your report should state how the system
behaves on unlabelled clauses rather than quietly excluding them.

**Severe class imbalance.** Governing Law appears in nearly every contract; Audit Rights in
a fraction. A model that predicts only the five common classes scores well on micro-averaged
metrics while being useless. Report **macro-F1 and a per-class F1 table**, not accuracy, not
micro-F1 alone.

---

## The TF-IDF baseline is not optional

Run TF-IDF + one-vs-rest logistic regression before LegalBERT.

Contract language is formulaic — *"shall indemnify, defend and hold harmless"* recurs near
verbatim across hundreds of contracts — so the baseline will score better than you expect.
That is the point:

- LegalBERT beats it by 15 macro-F1 points → evidence that legal-domain pretraining matters
- LegalBERT beats it by 2 points → a more interesting and more honest finding

Either outcome gives you a number to defend. Fine-tuning a transformer and reporting its
score alone gives you nothing to compare against, and it is the first thing an examiner will
probe.

---

## Answering "did you make up your own dataset?"

**No.** Three separate things, and only one of them involves your judgment:

**1. Span→clause conversion.** Deterministic function over CUAD's expert annotations. Fully
reproducible, no human decision.

**2. 41→13 category mapping.** A documented many-to-one mapping over an existing taxonomy,
justified by which types the risk matrix consumes. Reversible — publish the table and results
expand back to CUAD categories.

**3. The loophole contract set.** This one *is* yours, and the synopsis already handles it
correctly: small, curated, explicitly described as illustrative case studies rather than a
statistically rigorous benchmark. Keep that wording exactly. A team that overclaims a
15-contract set as a benchmark gets taken apart in questioning; a team that calls it case
studies gets credit for calibration.

**The one-line answer:** *Every label our models train on traces back to a decision made by
an Atticus-supervised lawyer. Our code moves labels between coordinate systems — it never
creates one.*

---

## Where the real ground truth lives

Worth remembering that classification is Layer 3 infrastructure. It exists to make the type
matrix fire. It is not the project's contribution.

Your actual research claim is the retrieval comparison in Layer 4, and its ground truth does
not come from CUAD's annotations at all. It comes from **cross-references written into the
contracts themselves** — *subject to Section 8.2*, *notwithstanding Clause 11*. Those are
statements by the drafting lawyer that two clauses must be read together.

That is arguably a cleaner ground truth than any annotation you could commission, it exists
in every contract for free, and it scales across all 510 CUAD contracts at zero annotation
cost. It is also entirely defensible: you did not decide those clauses were related. The
people who wrote the contract did.

---

## Checklist

- [ ] Pull the real 41-category list from the CUAD repository
- [ ] Write the risk matrix first, derive target types from it
- [ ] Finalise and publish the 41→N mapping table
- [ ] Fix the overlap threshold; run and report the sensitivity check
- [ ] Verify label distribution; confirm imbalance before choosing metrics
- [ ] TF-IDF baseline, per-class macro-F1
- [ ] LegalBERT, same metrics, same splits
- [ ] Report behaviour on unlabelled clauses explicitly
