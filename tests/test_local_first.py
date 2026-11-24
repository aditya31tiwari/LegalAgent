"""
Tests for the local-first additions: extraction structure, Indian rules, statute grounding,
known-gap labels, the Kev request shape, and the upload / analyze API (rules judge, no GPU
or network needed).
"""
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "web"))

import pytest

from legalagent.core.types import Clause
from legalagent.core.extraction import extract
from legalagent.core.ingestion import normalize
from legalagent.core.analysis import analyse_statutory
from legalagent.core.classification import apply_known_gap_rules


# ---------------------------------------------------------------- extraction

DOC = """TABLE OF CONTENTS
1.1 Definitions
1.2 Interpretation
2.1 Grant
2.2 Term

ARTICLE 1 DEFINITIONS
1.1 In this Agreement "Site" means the land described in Schedule A.
1.2 Headings shall not affect interpretation of this Agreement.

ARTICLE 2 GRANT
2.1 Grant of Concession
2.1.1 The Authority hereby grants the Concessionaire the right to build the Project.
2.2 The Concession Period shall be thirty years, subject to Clause 2.1.1.
"""


def test_toc_entries_are_not_clauses():
    cl = extract(normalize(DOC), "t")
    # the four TOC lines must not steal the ids of the real clauses
    assert [c.id for c in cl if c.number == "1.1"] == ["t::1.1"]
    assert "means the land" in next(c for c in cl if c.number == "1.1").text


def test_parts_and_parent_hierarchy():
    cl = {c.number: c for c in extract(normalize(DOC), "t")}
    assert cl["2.1.1"].part.startswith("ARTICLE 2")
    assert cl["2.1.1"].parent_id == cl["2.1"].id          # heading clause kept as parent
    xref = cl["2.2"].xrefs[0]
    assert xref["resolved"] and xref["clause_id"] == cl["2.1.1"].id


def test_part_regex_ignores_words_like_party():
    cl = extract(normalize("1.1 The PARTY of the first part shall pay.\n1.2 Payment is due monthly.\n"), "t")
    assert all(c.part is None for c in cl)


# ---------------------------------------------------------------- Indian rules

def _one(text):
    return [Clause(id="c::1", contract_id="c", number="1", text=text)]


@pytest.mark.parametrize("text,section", [
    ("Delay shall incur liquidated damages of 75 percent of the contract value, regardless of actual loss.", "Section 74"),
    ("The parties agree this agreement is intentionally unstamped.", "Section 35"),
    ("The Vendor may sell customer personal data without consent.", "Section 6"),
    ("Following termination, the employee shall not compete with the company.", "Section 27"),
])
def test_indian_statutory_rules_fire(text, section):
    found = analyse_statutory(_one(text), "India")
    assert any(r["section"] == section for f in found for r in f.refs)


def test_indian_rules_do_not_fire_on_benign_text():
    assert analyse_statutory(_one("Liquidated damages of 0.5% per week, capped at 5%, are a genuine pre-estimate of loss."), "India") == []
    assert analyse_statutory(_one("Stamp duty on this Agreement shall be borne by the Concessionaire."), "India") == []


def test_known_gap_rules_skip_definitions_and_long_clause_tails():
    defn = Clause(id="a", contract_id="c", text='"Force Majeure" means any event beyond the reasonable control of a party.')
    tail = Clause(id="b", contract_id="c", text=" ".join(["The Contractor shall perform the Works diligently."] * 12) + " Stamp duty is payable.")
    head = Clause(id="c", contract_id="c", text="Neither party is liable for delay caused by force majeure.")
    apply_known_gap_rules([defn, tail, head])
    assert not defn.labels and not tail.labels
    assert [l["label"] for l in head.labels] == ["force_majeure"]


# ---------------------------------------------------------------- statutes

def test_verify_citation_resolves_real_sections_and_rejects_fake():
    pytest.importorskip("pandas")
    from legalagent.core.statutes import verify_citation, LIBRARY
    if not LIBRARY.exists():
        pytest.skip("statute library not built")
    s = verify_citation("Indian Contract Act, 1872, Section 27")
    assert s and s["section"] == "27" and "restraint" in (s["heading"] + s["text"]).lower()
    assert verify_citation("Indian Contract Act, 1872, Section 9999") is None
    assert verify_citation("") is None


# ---------------------------------------------------------------- Kev request shape

def test_pair_request_shape_matches_system_one_api():
    from legalagent.core.local_judge import pair_request, RELATIONS, SEVERITIES
    a = Clause(id="x::1", contract_id="x", number="1", text="1 Cap at fees paid.", labels=[{"label": "limitation_of_liability"}])
    b = Clause(id="x::2", contract_id="x", number="2", text="2 Uncapped indemnity.", labels=[{"label": "indemnification"}])
    sec = [{"act": "The Indian Contract Act, 1872", "section": "124", "heading": "Contract of indemnity", "text": "..."}]
    req = pair_request(a, b, ["type_matrix"], sec)
    q = req["questions"]
    assert set(q) == {"relation", "severity", "statute"}
    assert q["relation"]["type"] == "choice" and set(q["relation"]["criteria"]) == set(RELATIONS)
    assert q["severity"]["type"] == "score" and q["severity"]["criteria"] == SEVERITIES
    assert "none" in q["statute"]["criteria"] and "Indian Contract Act, 1872 s.124" in q["statute"]["criteria"]
    assert "limitation_of_liability" in req["state"] and "Uncapped indemnity" in req["state"]


# ---------------------------------------------------------------- API (rules judge: no GPU / network)

@pytest.fixture(scope="module")
def client(tmp_path_factory):
    pytest.importorskip("fastapi")
    pytest.importorskip("multipart")
    import legalagent.db as db
    db.DB_PATH = tmp_path_factory.mktemp("db") / "test.db"
    from fastapi.testclient import TestClient
    import backend
    backend.DB_PATH = db.DB_PATH
    db.init_db()
    return TestClient(backend.app)


SAMPLE = """1.1 The aggregate liability of the Supplier shall not exceed the fees paid.
1.2 The Supplier shall indemnify the Customer without limit, notwithstanding Clause 1.1.
1.3 Following termination, the employee shall not compete with the Customer in India.
"""


def _events(resp):
    import json
    return [json.loads(l[5:]) for l in resp.text.split("\n\n") if l.startswith("data:")]


def test_analyze_stream_rules_judge(client):
    r = client.post("/api/contracts/analyze/stream", json={"title": "t", "text": SAMPLE, "judge": "rules", "retrieval": "bm25"})
    ev = _events(r)
    assert ev[-1]["stage"] == "complete", ev[-1]
    assert ev[-1]["stats"]["findings"] >= 2 and ev[-1]["stats"]["judge"] == "rules"


def test_upload_stream_txt_and_docx(client):
    r = client.post("/api/contracts/upload/stream", files={"file": ("c.txt", SAMPLE.encode(), "text/plain")},
                    data={"judge": "rules", "retrieval": "bm25"})
    assert _events(r)[-1]["stage"] == "complete"
    docx = pytest.importorskip("docx")
    d = docx.Document()
    for line in SAMPLE.strip().splitlines():
        d.add_paragraph(line)
    buf = io.BytesIO()
    d.save(buf)
    r = client.post("/api/contracts/upload/stream", files={"file": ("c.docx", buf.getvalue(), "application/octet-stream")},
                    data={"judge": "rules", "retrieval": "bm25"})
    last = _events(r)[-1]
    assert last["stage"] == "complete" and last["stats"]["clauses"] == 3


def test_upload_rejects_unknown_type(client):
    r = client.post("/api/contracts/upload/stream", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400


def test_stored_text_is_returned_raw_for_client_side_escaping(client):
    """The API returns document text verbatim; index.html escapes it (escapeHtml) at render."""
    evil = '1.1 <img src=x onerror=alert(1)> The Supplier shall pay.\n1.2 Payment is due monthly.\n'
    ev = _events(client.post("/api/contracts/analyze/stream", json={"title": "<b>x</b>", "text": evil, "judge": "rules", "retrieval": "bm25"}))
    cid = ev[-1]["contract_id"]
    data = client.get(f"/api/contracts/{cid}").json()
    html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
    assert "escapeHtml(c.text)" in html
    # finding description: the card strips the confidence prefix into `desc`, then escapes it
    assert "const desc = (f.description" in html and "escapeHtml(desc)" in html
    assert any("<img" in c["text"] for c in data["clauses"])
