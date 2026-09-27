"""
The one thing in the CUAD stage that can break silently: attaching a
lawyer-highlighted span to the clause that contains it.

It is the only non-obvious step -- the span is written against the raw contract
while the clauses are cut from normalize()d text, so the two no longer share
character offsets and the match has to survive line and paragraph breaks. If
this regresses, every CUAD label lands on the wrong clause and the dataset looks
fine while being wrong. Everything else here is file plumbing and needs no test.

    python clause20/test_build.py      (or: pytest clause20)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from build import HERE, whitespace_pattern
from legalagent.core.extraction import extract
from legalagent.core.ingestion import normalize

RAW = """1. Definitions
In this Agreement, "Services" means the work described in Schedule A.

2. Payment
Customer shall pay all
invoices within thirty days of receipt.

3. Liability
In no event shall Supplier's aggregate liability exceed the fees paid.
"""


def owner_of(span, text, clauses):
    """The cuad() attachment step, isolated."""
    probe = " ".join(span.split())
    match = whitespace_pattern(probe).search(text)
    assert match, "span not locatable in normalized text: %r" % probe[:60]
    return next(c for c in clauses if c.char_start <= match.start() < c.char_end)


def test_span_crossing_a_line_break_lands_on_its_clause():
    text = normalize(RAW)
    clauses = extract(text, contract_id="t")
    # As CUAD stores it: raw, with the newline the drafter's layout put there.
    assert owner_of("pay all\ninvoices within thirty days", text, clauses).number == "2"


def test_each_clause_gets_its_own_span():
    text = normalize(RAW)
    clauses = extract(text, contract_id="t")
    assert owner_of('"Services" means the work', text, clauses).number == "1"
    assert owner_of("aggregate liability exceed", text, clauses).number == "3"


def test_label_map_targets_exist_in_taxonomy():
    """A typo'd target would bin real data into a label nothing trains on."""
    mapping = yaml.safe_load((HERE / "label_map.yaml").read_text(encoding="utf-8"))
    taxonomy = set(yaml.safe_load((HERE / "labels.yaml").read_text(encoding="utf-8"))["labels"])
    for source in ("cuad", "ledgar"):
        for src_label, targets in mapping[source].items():
            unknown = set(targets) - taxonomy
            assert not unknown, "%s:%s -> %s not in labels.yaml" % (source, src_label, sorted(unknown))


def test_conflict_pairs_reference_real_labels():
    """Criterion 1 is only meaningful if every pair names labels that exist."""
    spec = yaml.safe_load((HERE / "labels.yaml").read_text(encoding="utf-8"))
    taxonomy = set(spec["labels"])
    for key in spec["conflict_pairs"]:
        unknown = set(key.split("+")) - taxonomy
        assert not unknown, "conflict_pairs %s names %s, absent from labels" % (key, sorted(unknown))
    covered = {label for key in spec["conflict_pairs"] for label in key.split("+")}
    orphans = taxonomy - covered - {"other"}
    assert not orphans, "labels failing criterion 1 (no conflict role): %s" % sorted(orphans)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok  %s" % name)
