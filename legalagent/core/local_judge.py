"""
Local pair judge: a fine-tuned Kev decision model served on this machine.

Kev (github.com/jaredpalmer/kev, Apache-2.0) is an open reconstruction of TypeSafe's
"Jev" System One decision model: a frozen Qwen3.5 backbone + LoRA + pointer head that
reads a document ("state") and returns a calibrated probability distribution over the
options of typed questions in one forward pass, without generating text. That is
exactly the shape of our pair-judging task, and it fits a 6 GB laptop GPU.

We fine-tune Kev-0.8B on clause pairs labelled by Gemini (distillation, see
scripts/build_judge_set.py + train/finetune_kev.py) and serve it locally:

    ~/Projects/kev/.venv/bin/python -m kev.serve --run models/kev_judge --port 8008

Each clause pair becomes one request with three questions:
  relation  choice   conflict | dependency | overlap | ambiguity | no_issue
  severity  score    low < medium < high
  statute   choice   one of the 4 Indian statute sections retrieved for this pair, or none
So citations are always picked from real section text (core.statutes), never invented.
Contract text only ever goes to 127.0.0.1.
"""
import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request, urlopen

from legalagent.core.types import Clause, Finding

KEV_URL = os.environ.get("KEV_URL", "http://127.0.0.1:8008/v1/systemone")
TIMEOUT = float(os.environ.get("KEV_TIMEOUT", "30"))
MAX_CLAUSE_CHARS = 1200
N_STATUTE_OPTIONS = 4

RELATIONS = {
    "conflict": "the two clauses make demands that cannot both be satisfied, or one silently undoes the other (e.g. an indemnity not subject to a liability cap)",
    "dependency": "one clause only works, or changes meaning, through the other (e.g. what survives termination, a cross-referenced procedure)",
    "overlap": "both clauses govern the same matter with different or duplicated terms, inviting inconsistency",
    "ambiguity": "read together the clauses leave a gap or an unclear outcome a court would have to resolve",
    "no_issue": "the clauses are independent or consistent; nothing a reviewer needs to flag",
}
SEVERITIES = ["low", "medium", "high"]
RELATION_TEXT = {
    "conflict": "Conflict",
    "dependency": "Dependency",
    "overlap": "Overlap",
    "ambiguity": "Ambiguity",
}


def _clause_block(tag: str, c: Clause) -> str:
    labels = ", ".join(l["label"] for l in c.labels) or "unlabelled"
    part = f" [{c.part}]" if getattr(c, "part", None) else ""
    return f"Clause {tag} — {c.number}{part} — types: {labels}\n{c.text[:MAX_CLAUSE_CHARS]}"


def statute_options(a: Clause, b: Clause) -> list[dict]:
    try:
        from legalagent.core.statutes import retrieve_sections
        query = f"{a.text[:600]} {b.text[:600]}"
        return [s for s, _ in retrieve_sections(query, k=N_STATUTE_OPTIONS)]
    except Exception:
        return []


def _statute_key(s: dict) -> str:
    return f"{s['act'].replace('The ', '', 1)} s.{s['section']}"


def pair_request(a: Clause, b: Clause, surfaced_by: list[str], sections: list[dict] | None = None) -> dict:
    """System One request for one clause pair (no labels). Shared by training and inference."""
    if sections is None:
        sections = statute_options(a, b)
    state = (
        "Two clauses from the same commercial contract (Indian law applies).\n"
        f"Why they were paired: {', '.join(surfaced_by) or 'retrieval'}\n\n"
        f"{_clause_block('A', a)}\n\n{_clause_block('B', b)}"
    )
    statute_criteria = {_statute_key(s): f"{s['heading']}: {s['text'][:240]}" for s in sections}
    statute_criteria["none"] = "none of these sections bears on the issue between the two clauses"
    return {
        "state": state,
        "questions": {
            "relation": {
                "type": "choice",
                "instructions": "How do clause A and clause B relate, from a contract reviewer's point of view?",
                "criteria": RELATIONS,
            },
            "severity": {
                "type": "score",
                "instructions": "How serious is the risk this pair creates for the party relying on the contract?",
                "criteria": SEVERITIES,
            },
            "statute": {
                "type": "choice",
                "instructions": "Which Indian statute section is most relevant to the issue between these clauses?",
                "criteria": statute_criteria,
            },
        },
    }


def _post(body: dict) -> dict:
    req = Request(KEV_URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    key = os.environ.get("KEV_API_KEY")
    if key:
        req.add_header("Authorization", f"Bearer {key}")
    with urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read())


def available() -> bool:
    try:
        with urlopen(KEV_URL.rsplit("/v1/", 1)[0] + "/v1/models", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def threshold() -> float | None:
    """
    Decision threshold τ for the served Kev model: a pair is flagged when P(no_issue) < τ.
    Kev's training data is ~73 % no_issue, so its probabilities lean that way and argmax
    under-flags; τ is tuned on TRAINING contracts only (train/calibrate_kev.py).
    Source: env KEV_THRESHOLD, else results/judge_selection.json, else None (= argmax).
    """
    env = os.environ.get("KEV_THRESHOLD")
    if env:
        return float(env)
    from pathlib import Path
    sel = Path(__file__).resolve().parents[2] / "results" / "judge_selection.json"
    try:
        t = json.loads(sel.read_text()).get("threshold")
        return float(t) if t is not None else None
    except Exception:
        return None


def decide(rel_probs: dict, tau: float | None) -> str:
    """argmax, or threshold rule: risky iff P(no_issue) < τ, then the most likely risky relation."""
    if tau is None:
        return max(rel_probs, key=lambda k: float(rel_probs[k]))
    if float(rel_probs.get("no_issue", 0.0)) >= tau:
        return "no_issue"
    return max((k for k in rel_probs if k != "no_issue"), key=lambda k: float(rel_probs[k]))


def _to_finding(a: Clause, b: Clause, surfaced_by: list[str], sections: list[dict], resp: dict) -> Finding | None:
    ans = resp["answers"]
    rel_probs = ans["relation"]["probabilities"]
    relation = decide(rel_probs, threshold())
    if relation == "no_issue":
        return None
    sev_probs = [float(ans["severity"]["probabilities"][str(i)]) for i in range(len(SEVERITIES))]
    severity = SEVERITIES[max(range(len(sev_probs)), key=sev_probs.__getitem__)]
    risk = round(1.0 - float(rel_probs.get("no_issue", 0.0)), 3)

    refs = []
    by_key = {_statute_key(s): s for s in sections}
    pick = ans.get("statute", {}).get("choice")
    if pick in by_key:
        s = by_key[pick]
        refs.append({"source": s["act"], "section": f"Section {s['section']}", "heading": s["heading"],
                     "snippet": s["text"][:300], "url": s.get("url", ""), "grounding": "kev_choice", "verified": True,
                     "p": ans["statute"]["probabilities"].get(pick)})
    statute_note = f" Relevant law: {refs[0]['source']}, {refs[0]['section']} ({refs[0]['heading']})." if refs else ""
    rationale = (
        f"{RELATION_TEXT.get(relation, relation.title())} between clause {a.number} "
        f"({', '.join(l['label'] for l in a.labels) or 'unlabelled'}) and clause {b.number} "
        f"({', '.join(l['label'] for l in b.labels) or 'unlabelled'}): {RELATIONS[relation]}.{statute_note}"
    )
    return Finding(
        id=f"finding_{uuid.uuid4().hex[:8]}",
        target_clause_id=a.id,
        related_clause_ids=[b.id],
        relation_type=relation,
        severity=severity,
        risk_score=risk,
        rationale=rationale,
        surfaced_by=[*surfaced_by, "kev"],
        evidence=[{"clause_id": a.id, "start": 0, "end": len(a.text)},
                  {"clause_id": b.id, "start": 0, "end": len(b.text)}],
        refs=refs,
        scores={"analysis_confidence": float(ans["relation"]["confidence"]),
                "relation_probs": rel_probs, "severity_probs": sev_probs,
                "kev_latency_ms": resp.get("latency_ms")},
    )


def judge_pairs(pairs: list[tuple[Clause, Clause, list[str]]], model_dir: str | None = None, workers: int = 4) -> list[Finding | None]:
    """Judge every pair with the local Kev server. Raises if the server is not running."""
    if not pairs:
        return []
    if not available():
        raise RuntimeError(f"Kev server not reachable at {KEV_URL}")

    def one(pair):
        a, b, surfaced_by = pair
        sections = statute_options(a, b)
        return _to_finding(a, b, surfaced_by, sections, _post(pair_request(a, b, surfaced_by, sections)))

    with ThreadPoolExecutor(workers) as pool:
        return list(pool.map(one, pairs))
