"""
CLAUSE-20 build: LEDGAR + CUAD -> one clause-level, multi-label corpus.

Reads the zips in dataset/ as downloaded -- nothing is unpacked to disk and
nothing is fetched at build time, so a build is reproducible from those four
files alone:

    dataset/data.zip                  CUAD v1 (github.com/TheAtticusProject/cuad)
    dataset/ledgar_train.csv.zip      LEDGAR via the Kaggle LexGLUE mirror
    dataset/ledgar_validation.csv.zip
    dataset/ledgar_test.csv.zip

Subcommands
  labels   check label_map.yaml against the labels the data really contains
  cuad     510 CUAD contracts -> clause-level CSV
  ledgar   LEDGAR provisions -> CSV
  merge    combine + apply label_map -> data/interim/clause20.csv
  dedup    drop fragments and duplicate provisions -> clause20_dedup.csv
  split    train/validation/test/test_ood, grouped -> clause20_final.csv

Every stage writes CSV, openable in Excel. A clause can carry several labels, so
list columns (labels, src_labels) are pipe-joined: "indemnification|warranty".

Why CUAD needs its own stage
----------------------------
CUAD ships lawyer-highlighted *spans* over raw contract text. This project's
classifier sees whole numbered clauses produced by legalagent.core.extract().
Training on spans would train on a text shape the model never meets at
inference, so each contract is re-cut with the project's own extractor and each
highlight is attached to the clause containing it. Labels become naturally
multi-label (one clause can hold several highlights), and the extractor gets a
free regression test over 510 real contracts -- see the miss rate printed at the
end of the cuad stage.
"""
import argparse
import csv
import io
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from legalagent.core.extraction import extract
from legalagent.core.ingestion import normalize
from legalagent.core.retrieval import _LEADING_NUMBER_RE

HERE = Path(__file__).parent
RAW = HERE.parent / "dataset"
INTERIM = HERE / "data" / "interim"

CUAD_ZIP = RAW / "data.zip"
CUAD_JSON = "CUADv1.json"        # the full 510, not the train/test split beside it
LEDGAR_ZIPS = {
    "train": RAW / "ledgar_train.csv.zip",
    "validation": RAW / "ledgar_validation.csv.zip",
    "test": RAW / "ledgar_test.csv.zip",
}
# The Kaggle CSV mirror stores LEDGAR labels as integers and drops the names.
# ledgar_labels.json holds the official ordered list; position == integer label.
LEDGAR_LABELS = HERE / "ledgar_labels.json"

# CUAD questions read: Highlight the parts (if any) of this contract related to
# "Governing Law" that should be reviewed by a lawyer. Details: ...
CUAD_CATEGORY_RE = re.compile(r'related to\s+"([^"]+)"')

# Only the head of a highlight is used to locate it. Spans run to hundreds of
# words; the first 200 characters are already unique within one contract, and a
# whole-span pattern would build a regex thousands of tokens long for no gain.
PROBE_CHARS = 200

# These four are document metadata, highlighted on the title page and preamble --
# before the first numbered clause exists. No clause can own them, and they are
# not clause types this project classifies. Counted apart so the miss rate keeps
# measuring what it is for: whether the extractor is losing real clause text.
CUAD_PREAMBLE = {"Document Name", "Parties", "Agreement Date", "Effective Date"}


def load_yaml(name):
    return yaml.safe_load((HERE / name).read_text(encoding="utf-8"))


def whitespace_pattern(probe):
    r"""
    Locate `probe` in normalized text.

    normalize() collapses whitespace runs and rewrites blank lines as "\n\n", so
    a highlight that crossed a line or paragraph break no longer matches
    character for character. Matching token-by-token with \s+ between survives
    both. Everything else is escaped, so punctuation still has to line up.
    """
    return re.compile(r"\s+".join(re.escape(t) for t in probe.split()))


def open_zip(path, member=None):
    """Read one member of a zip without unpacking it to disk."""
    if not path.exists():
        sys.exit("missing %s -- put the downloaded dataset there" % path)
    archive = zipfile.ZipFile(path)
    name = member or archive.namelist()[0]
    return archive.read(name)


def cuad(limit=None):
    # SQuAD-shaped: data -> contracts -> one paragraph -> 41 questions, where an
    # answer is a lawyer's highlight and an empty answers list means the category
    # is absent from that contract.
    payload = json.loads(open_zip(CUAD_ZIP, CUAD_JSON).decode("utf-8"))

    contracts, highlights = {}, {}
    for contract in payload["data"]:
        title = contract["title"]
        for paragraph in contract["paragraphs"]:
            contracts.setdefault(title, paragraph["context"])
            for qa in paragraph["qas"]:
                category = CUAD_CATEGORY_RE.search(qa["question"])
                if not category:
                    continue
                for answer in qa.get("answers", []):
                    highlights.setdefault(title, []).append(
                        (category.group(1), answer["text"])
                    )

    titles = sorted(contracts)
    if limit:
        titles = titles[:limit]

    out, stats = [], Counter()

    for doc_n, title in enumerate(titles):
        doc_id = "cuad:%04d" % doc_n
        text = normalize(contracts[title])
        clauses = extract(text, contract_id=doc_id)
        stats["contracts"] += 1
        if not clauses:
            # extract() reads decimal numbering only; contracts numbered
            # "ARTICLE V" or "(a)" yield nothing. Counted, not hidden.
            stats["contracts_no_clauses"] += 1
            continue
        stats["clauses"] += len(clauses)

        labels = {clause.id: set() for clause in clauses}
        for category, span in highlights.get(title, []):
            preamble = category in CUAD_PREAMBLE
            stats["preamble_highlights" if preamble else "highlights"] += 1
            probe = " ".join(span.split())[:PROBE_CHARS]
            if not probe:
                stats["highlight_empty"] += 1
                continue
            match = whitespace_pattern(probe).search(text)
            if not match:
                # Did not survive normalize()'s hyphen rejoin, or differs by OCR.
                stats["highlight_unlocatable"] += 1
                continue
            owner = next(
                (c for c in clauses if c.char_start <= match.start() < c.char_end),
                None,
            )
            if owner is None:
                stats["preamble_unowned" if preamble else "highlight_outside_clause"] += 1
                continue
            labels[owner.id].add(category)
            stats["highlight_attached"] += 1

        for clause in clauses:
            # Strip the leading clause number. Measured before this line: 100.0%
            # of CUAD rows began with a digit and 0.0% of LEDGAR rows did, which
            # made source perfectly separable -- and since limitation_of_liability
            # and license_grant are CUAD-only, "starts with a number" alone
            # scored 100% recall on both. The model would learn the formatting,
            # not the law, then collapse at inference where every clause is
            # numbered. The number carries no legal meaning; the heading does and
            # is kept, because extract() gives the classifier headings too.
            # Same regex, same reason, as legalagent.core.retrieval.
            text = _LEADING_NUMBER_RE.sub("", clause.text).strip()
            out.append({
                "uid": clause.id,
                "source": "cuad",
                "doc_id": doc_id,
                "text": text,
                "n_words": len(text.split()),
                "src_labels": sorted(labels[clause.id]),
            })

    write(out, "cuad.csv")
    for key, value in sorted(stats.items()):
        print("  %26s: %s" % (key, value))
    total = stats["highlights"] or 1
    missed = stats["highlight_unlocatable"] + stats["highlight_outside_clause"]
    print("\nhighlight miss rate: %.1f%%  (clause categories only; >5%% means investigate)"
          % (100 * missed / total))
    dropped = stats["contracts_no_clauses"]
    if dropped:
        print("contracts yielding no clauses: %d of %d (%.0f%%) -- extract() reads "
              "decimal numbering only, so ARTICLE V / (a) styles are lost"
              % (dropped, stats["contracts"], 100 * dropped / stats["contracts"]))
    return out


def ledgar_names():
    names = json.loads(LEDGAR_LABELS.read_text(encoding="utf-8"))["names"]
    if len(names) != 100:
        sys.exit("ledgar_labels.json holds %d names, expected 100" % len(names))
    return names


def ledgar():
    names = ledgar_names()
    out = []
    for split_name, path in LEDGAR_ZIPS.items():
        text = open_zip(path).decode("utf-8", "replace")
        reader = csv.DictReader(io.StringIO(text))
        for i, row in enumerate(reader):
            index = int(row["label"])
            if not 0 <= index < len(names):
                sys.exit("%s row %d: label %d outside 0-99" % (split_name, i, index))
            out.append({
                # LexGLUE's LEDGAR drops the source filing id, so there is no
                # real document to group by. Each provision is its own doc_id and
                # near-duplicate removal is the ONLY leakage guard on this half
                # of the corpus. A stated limitation, not a solved one.
                "uid": "ledgar:%s:%d" % (split_name, i),
                "source": "ledgar",
                "doc_id": "ledgar:%s:%d" % (split_name, i),
                "split_hint": split_name,   # keep LexGLUE's official split
                "text": row["text"],
                "n_words": len(row["text"].split()),
                "src_labels": [names[index]],
            })
    write(out, "ledgar.csv")
    return out


def labels():
    """Check label_map.yaml against the labels the downloaded data contains."""
    mapping = load_yaml("label_map.yaml")
    gaps = 0

    shipped = ledgar_names()
    missing = [name for name in shipped if name not in mapping["ledgar"]]
    print("LEDGAR: %d labels, %d unmapped" % (len(shipped), len(missing)))
    for name in missing:
        print('  "%s": [other]' % name)
    gaps += len(missing)

    payload = json.loads(open_zip(CUAD_ZIP, CUAD_JSON).decode("utf-8"))
    categories = {
        match.group(1)
        for contract in payload["data"]
        for paragraph in contract["paragraphs"]
        for qa in paragraph["qas"]
        for match in [CUAD_CATEGORY_RE.search(qa["question"])]
        if match
    }
    missing = sorted(name for name in categories if name not in mapping["cuad"])
    print("CUAD:   %d categories, %d unmapped" % (len(categories), len(missing)))
    for name in missing:
        print('  "%s": [other]' % name)
    gaps += len(missing)

    unused = sorted(set(mapping["cuad"]) - categories)
    if unused:
        print("\nin label_map.yaml but absent from CUAD (likely a spelling drift):")
        for name in unused:
            print("  %s" % name)

    print("\n%s" % ("all labels mapped" if not gaps else "%d label(s) to add" % gaps))


def merge():
    mapping = load_yaml("label_map.yaml")
    spec = load_yaml("labels.yaml")
    taxonomy = set(spec["labels"])
    rows, unmapped = [], Counter()

    for name in ("cuad.csv", "ledgar.csv"):
        for row in read(name):
            table = mapping[row["source"]]
            targets = set()
            for src in row["src_labels"]:
                if src not in table:
                    unmapped["%s:%s" % (row["source"], src)] += 1
                    continue
                targets.update(table[src])
            unknown = targets - taxonomy
            if unknown:
                sys.exit("label_map.yaml targets %s, absent from labels.yaml"
                         % sorted(unknown))
            row["labels"] = sorted(targets) or ["other"]
            rows.append(row)

    if unmapped and mapping.get("unmapped_policy") == "fail":
        print("unmapped source labels (build stopped):", file=sys.stderr)
        for name, count in unmapped.most_common():
            print("  %6d  %s" % (count, name), file=sys.stderr)
        sys.exit("add them to label_map.yaml, or run `build.py labels`")

    write(rows, "clause20.csv")
    counts = Counter(label for row in rows for label in row["labels"])
    floor = spec["min_support"]
    print("\nmerged rows: %d" % len(rows))
    for label, count in counts.most_common():
        thin = count < floor and label != "other"
        print("  %7d  %s%s" % (count, label, "   <- below min_support" if thin else ""))


MIN_WORDS = 10

# SEC filing furniture that normalize() cannot catch: it strips lines recurring
# on most PAGES, and these appear once or twice per document. Found while
# sampling recovered rows -- one "clause" was nothing but a redaction notice --
# so it is cleaned corpus-wide, not just on recovered rows.
SEC_NOISE_RE = re.compile(
    r"(Source:\s*[A-Z][^,]{2,60},\s*(?:10-[QK]|8-K|S-\d|EX-[\d.]+)[^\n]{0,40})"
    r"|(CONFIDENTIAL TREATMENT (?:HAS BEEN )?REQUESTED[^\n]{0,80})"
    r"|(\[\*{1,3}\]\s*CONFIDENTIAL[^\n]{0,60})",
    re.I,
)

# Table-of-contents rows: "Indemnification of Customer 58 10.2 Indemnification
# of Manufacturer 59". extract() sees the leading number and emits them as
# clauses. They are page references, not text, and they carry the heading words
# of every section they list -- so they poison whichever label they mention.
_TOC_NUM_RE = re.compile(r"\b\d+(?:\.\d+)*\b")


def looks_like_toc(text):
    tokens = text.split()
    if len(tokens) < 12:
        return False
    numbers = len(_TOC_NUM_RE.findall(text))
    return numbers / len(tokens) > 0.18

# Heading-anchored recovery of CUAD clauses no lawyer highlighted. Restricted to
# the four labels CUAD's 41 categories cannot express at all -- without these,
# five of the seventeen conflict pairs in labels.yaml fire in zero contracts and
# cannot be evaluated end to end, including the 0.9-weighted flagship pair.
# The anchor is the clause HEADING, not the body: matching anywhere in the body
# pulls in warranty clauses that merely mention indemnity, which is the exact
# mislabelling that made dropping these rows correct in the first place.
RECOVERY_ANCHORS = {
    "indemnification": r"indemnif|hold harmless",
    "confidentiality": r"confidential|non-?disclosure",
    "tax": r"\btax(es|ation)?\b|withholding",
    "amendment_and_integration": r"entire agreement|amendment|no waiver",
}
RECOVERY_HEAD_WORDS = 12

# Near-duplicate test: same first 200 characters once punctuation and case are
# stripped. ~35 words of identical wording is not a coincidence in contract text,
# and the pairs it finds are the same provision with different bracket styles or
# a changed date. Cheap enough to run over 100k rows without MinHash, which the
# measured duplication rate (2.3% exact) does not justify bringing in.
NEAR_DUP_CHARS = 200

_JUNK_RE = re.compile(r"[^a-z0-9 ]+")


def fingerprint(text, chars=None):
    flat = _JUNK_RE.sub(" ", re.sub(r"\s+", " ", text.lower())).strip()
    return (flat[:chars] if chars else flat)


def dedup():
    """
    Drop fragments and duplicate provisions. Reports every decision rather than
    quietly shrinking the file.
    """
    from hashlib import blake2b

    rows = list(read("clause20.csv"))
    start = len(rows)
    stats = Counter()

    # -1. Strip SEC filing furniture, then drop rows that were nothing else.
    for row in rows:
        cleaned = SEC_NOISE_RE.sub(" ", row["text"])
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned != row["text"]:
            stats["sec_noise_cleaned"] += 1
            row["text"] = cleaned
            row["n_words"] = len(cleaned.split())

    kept = [r for r in rows if not looks_like_toc(r["text"])]
    stats["toc_rows_dropped"] = len(rows) - len(kept)

    # 0a. Recover the four labels CUAD cannot express, from its unhighlighted
    #     clauses, anchored on the heading. Tagged `silver`: derived by rule, not
    #     by a lawyer, so it can be ablated out to prove it helped.
    for row in kept:
        row.setdefault("provenance", "gold")
        if row["source"] != "cuad" or row["labels"] != "other":
            continue
        head = " ".join(row["text"].split()[:RECOVERY_HEAD_WORDS]).lower()
        for label, pattern in RECOVERY_ANCHORS.items():
            if re.search(pattern, head):
                row["labels"] = label
                row["provenance"] = "silver"
                stats["recovered_" + label] += 1
                break

    # 0b. CUAD clauses still unhighlighted. They are NOT `other` -- CUAD has no
    #    category for indemnification, confidentiality, amendment_and_integration
    #    or tax, so an unhighlighted clause may well be one of those, and calling
    #    it `other` teaches the model the opposite of the truth. Worst for
    #    indemnification, this corpus's thinnest important class and half of its
    #    highest-weighted conflict pair. LEDGAR rows labelled `other` are kept:
    #    there the label is a real one (Headings, Counterparts) deliberately
    #    binned, so it carries genuine negative signal.
    before_drop = len(kept)
    kept = [r for r in kept if not (r["source"] == "cuad" and r["labels"] == "other")]
    unlabelled_cuad = before_drop - len(kept)

    # 1. Fragments. extract() emits a span per numbered marker, so a heading on
    #    its own line and a table cell both become "clauses". They carry no
    #    classifiable text, and when a CUAD highlight lands on one the label it
    #    picks up is usually wrong -- noise twice over.
    before_fragments = len(kept)
    kept = [row for row in kept if int(row["n_words"]) >= MIN_WORDS]
    fragments = before_fragments - len(kept)

    # 2. Duplicates, exact then near, both on the normalised text. Within a group
    #    the longest row survives and the group's labels are unioned: copies that
    #    disagree are the same provision annotated twice, so keeping one copy's
    #    labels would throw away a real annotation.
    def collapse(rows, chars):
        groups = {}
        for row in rows:
            key = blake2b(fingerprint(row["text"], chars).encode(), digest_size=16).digest()
            groups.setdefault(key, []).append(row)
        out, merged = [], 0
        for group in groups.values():
            winner = max(group, key=lambda r: int(r["n_words"]))
            if len(group) > 1:
                labels = sorted({l for r in group for l in r["labels"].split("|")})
                if len(labels) > 1 and "other" in labels:
                    labels.remove("other")   # a real label beats the sink
                if labels != winner["labels"].split("|"):
                    merged += 1
                winner["labels"] = "|".join(labels)
            out.append(winner)
        return out, len(rows) - len(out), merged

    kept, exact, relabelled_exact = collapse(kept, None)
    kept, near, relabelled_near = collapse(kept, NEAR_DUP_CHARS)

    write(kept, "clause20_dedup.csv")
    print("\n  %6d  rows in" % start)
    print("   %5d  rows had SEC filing furniture stripped" % stats["sec_noise_cleaned"])
    print("  -%5d  table-of-contents rows" % stats["toc_rows_dropped"])
    for label in RECOVERY_ANCHORS:
        print("  +%5d  recovered as %s (silver)" % (stats["recovered_" + label], label))
    print("  -%5d  CUAD clauses with no highlight (not genuinely `other`)"
          % unlabelled_cuad)
    print("  -%5d  fragments under %d words" % (fragments, MIN_WORDS))
    print("  -%5d  exact duplicates" % exact)
    print("  -%5d  near duplicates (first %d chars)" % (near, NEAR_DUP_CHARS))
    print("  %6d  rows out  (%.1f%% removed)"
          % (len(kept), 100 * (start - len(kept)) / start))
    print("  %6d  rows gained a label by merging duplicate annotations"
          % (relabelled_exact + relabelled_near))

    counts = Counter(l for row in kept for l in row["labels"].split("|"))
    floor = load_yaml("labels.yaml")["min_support"]
    print()
    for label, count in counts.most_common():
        thin = count < floor and label != "other"
        print("  %7d  %s%s" % (count, label, "   <- below min_support" if thin else ""))


CUAD_HOLDOUT = 0.15   # share of CUAD *contracts* held out, not clauses
CUAD_VAL = 0.15
SPLIT_SEED = 20200


def split():
    """
    train / validation / test / test_ood, grouped so no contract straddles a
    boundary.

    LEDGAR keeps LexGLUE's official split, which makes any number reported here
    comparable to published LEDGAR results. Its rows cannot be grouped by
    document -- the mirror drops the source filing id -- so near-duplicate
    removal in the dedup stage is the only leakage guard on that half, and that
    is a limitation rather than a solution.

    CUAD is split by whole contract with a fixed seed. Its held-out contracts
    become test_ood: unseen documents, real PDF-shaped clauses, the closest
    thing here to what the deployed pipeline meets. The gap between test and
    test_ood is the honest measure of how far the model travels.
    """
    import random

    rows = list(read("clause20_dedup.csv"))
    contracts = sorted({r["doc_id"] for r in rows if r["source"] == "cuad"})
    random.Random(SPLIT_SEED).shuffle(contracts)

    n_ood = int(len(contracts) * CUAD_HOLDOUT)
    n_val = int(len(contracts) * CUAD_VAL)
    assignment = {}
    for i, doc in enumerate(contracts):
        assignment[doc] = "test_ood" if i < n_ood else "validation" if i < n_ood + n_val else "train"

    counts = Counter()
    for row in rows:
        if row["source"] == "ledgar":
            row["split"] = row["split_hint"] or "train"
        else:
            row["split"] = assignment[row["doc_id"]]
        counts[(row["source"], row["split"])] += 1

    write(rows, "../CLAUSE20.csv")
    print()
    for (source, name), count in sorted(counts.items()):
        print("  %-7s %-11s %6d" % (source, name, count))

    prov = Counter(r.get("provenance", "gold") for r in rows)
    print("\n  provenance: %d gold, %d silver (rule-derived, ablate to verify)"
          % (prov["gold"], prov["silver"]))

    # The confound check. Before the fix this printed 100.0 / 0.0.
    digit = Counter()
    for row in rows:
        digit[(row["source"], bool(re.match(r"^\s*\d", row["text"])))] += 1
    print()
    for source in ("cuad", "ledgar"):
        total = digit[(source, True)] + digit[(source, False)]
        print("  %-7s rows starting with a digit: %.1f%%"
              % (source, 100 * digit[(source, True)] / total))

    print()
    for name in ("train", "validation", "test", "test_ood"):
        subset = [r for r in rows if r["split"] == name]
        if not subset:
            continue
        labelled = Counter(l for r in subset for l in r["labels"].split("|"))
        thin = [l for l in load_yaml("labels.yaml")["labels"]
                if l != "other" and labelled[l] == 0]
        print("  %-11s %6d rows, %2d labels present%s"
              % (name, len(subset), len(labelled),
                 "  MISSING: " + ", ".join(thin) if thin else ""))


def write(rows, name):
    """
    CSV, so the dataset is readable in Excel at every stage rather than only
    after training. List columns are pipe-joined -- a clause really can be both
    indemnification and limitation_of_liability, and splitting that into two
    rows would make one clause look like two.
    """
    INTERIM.mkdir(parents=True, exist_ok=True)
    path = INTERIM / name
    # Union, not rows[0]'s keys: the merged file mixes CUAD rows and LEDGAR rows,
    # and only LEDGAR carries split_hint. Taking the first row's columns would
    # drop it for every row, silently.
    columns = list(dict.fromkeys(name for row in rows for name in row))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([
                "|".join(row[name]) if isinstance(row.get(name), list) else row.get(name, "")
                for name in columns
            ])
    print("wrote %d rows -> %s" % (len(rows), path))


def read(name):
    path = INTERIM / name
    if not path.exists():
        sys.exit("missing %s -- run the cuad and ledgar stages first" % path)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            # "" means no labels at all, which must not become [""].
            row["src_labels"] = [s for s in row["src_labels"].split("|") if s]
            yield row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["labels", "cuad", "ledgar", "merge", "dedup", "split"])
    parser.add_argument("--limit", type=int, help="cuad: only the first N contracts")
    args = parser.parse_args()
    if args.stage == "cuad":
        cuad(args.limit)
    else:
        {"labels": labels, "ledgar": ledgar, "merge": merge,
         "dedup": dedup, "split": split}[args.stage]()


if __name__ == "__main__":
    main()
