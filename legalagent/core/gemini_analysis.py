"""Gemini-powered cross-clause analysis adapter.

Replaces the deterministic ``analyse_pair`` rule engine with a structured
Gemini prompt that classifies the relationship between a pair of clauses and
explains its legal significance under Indian law.

Pipeline integration
--------------------
Called from ``pipeline.py`` when ``config["use_gemini"]`` is truthy.
Falls back gracefully to the deterministic baseline when:
  - ``GEMINI_API_KEY`` is absent / invalid
  - Gemini returns a response that cannot be parsed or validated
  - A network error occurs

The function signature is intentionally identical to ``analyse_pair`` so it
can be used as a drop-in replacement.
"""

import json
import logging
import uuid

from legalagent.core.types import Clause, Finding
from legalagent.core.gemini import GeminiConfigurationError, generate_json

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Response schema that Gemini must fill in
# ---------------------------------------------------------------------------

RESPONSE_SCHEMA = {
    "findings": [
        {
            "relation_type": "<conflict | dependency | overlap | ambiguity | no_issue>",
            "severity": "<high | medium | low>",
            "risk_score": "<float 0.0-1.0>",
            "rationale": "<one-sentence plain-English explanation>",
            "statute_citation": "<Indian-law citation or empty string>",
        }
    ]
}

VALID_RELATION_TYPES = {"conflict", "dependency", "overlap", "ambiguity", "no_issue"}
VALID_SEVERITIES = {"high", "medium", "low"}

# Maximum number of clause pairs sent in a single Gemini call.
# Keeping this at 10 avoids context-window bloat and makes retries cheaper.
MAX_PAIRS_PER_PROMPT = 10

# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(pairs: list[tuple[Clause, Clause, list[str]]]) -> str:
    """Build a single Gemini prompt for a batch of clause pairs.

    Batching reduces API round-trips: one call for up to ~30 pairs.
    """
    pair_blocks = []
    for idx, (clause_a, clause_b, surfaced_by) in enumerate(pairs, start=1):
        labels_a = [lbl["label"] for lbl in clause_a.labels]
        labels_b = [lbl["label"] for lbl in clause_b.labels]

        pair_blocks.append(
            f"""--- PAIR {idx} ---
Clause A  id={clause_a.id}  labels={labels_a}
\"\"\"{clause_a.text[:1200]}\"\"\"

Clause B  id={clause_b.id}  labels={labels_b}
\"\"\"{clause_b.text[:1200]}\"\"\"

Retrieval signals: {surfaced_by}"""
        )

    pairs_text = "\n\n".join(pair_blocks)

    return f"""You are a senior Indian contract-law analyst reviewing pairs of clauses extracted from a commercial contract.

For each pair below, decide:
1. relation_type — one of: conflict | dependency | overlap | ambiguity | no_issue
   - conflict    : the clauses make contradictory demands that cannot both be satisfied
   - dependency  : one clause only makes sense or is legally effective in the context of the other
   - overlap     : both clauses address the same subject; possible redundancy or inconsistency
   - ambiguity   : individually unclear or together create interpretive uncertainty
   - no_issue    : clauses are independent and raise no concern as a pair
2. severity — one of: high | medium | low
3. risk_score — a float from 0.0 (no risk) to 1.0 (critical)
4. rationale — one precise sentence explaining the legal issue
5. statute_citation — the most relevant Indian statute + section (e.g. "Indian Contract Act 1872, Section 27"), or an empty string

Rules:
- Apply Indian contract law (ICA 1872, DPDPA 2023, Mediation Act 2023, BNS 2023, etc.)
- If a clause contains a post-termination non-compete, that is a statutory_violation → use relation_type "conflict" and cite Section 27 ICA
- If an indemnity is not clearly subordinated to a liability cap, classify as "conflict"
- If clauses are completely unrelated, return relation_type "no_issue", severity "low", risk_score 0.0
- Return exactly {len(pairs)} findings in the same order as the pairs

Respond with valid JSON matching this schema exactly:
{json.dumps(RESPONSE_SCHEMA, indent=2)}

CLAUSE PAIRS:
{pairs_text}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_pairs_with_gemini(
    pairs: list[tuple[Clause, Clause, list[str]]],
    model: str | None = None,
) -> list[Finding | None]:
    """Analyse a list of clause pairs via Gemini.

    Pairs are split into chunks of at most ``MAX_PAIRS_PER_PROMPT`` (default 10)
    so each prompt stays within a comfortable token budget.  Results from all
    chunks are flattened back into the original order before returning.

    Returns a list of ``Finding | None`` in the same order as *pairs*.
    ``None`` means no issue was found for that pair.

    Raises ``GeminiConfigurationError`` only if Gemini is completely
    unavailable; individual malformed results are logged and treated as
    ``None``.
    """
    if not pairs:
        return []

    results: list[Finding | None] = []

    # Chunk the pairs so no single prompt exceeds MAX_PAIRS_PER_PROMPT
    for chunk_start in range(0, len(pairs), MAX_PAIRS_PER_PROMPT):
        chunk = pairs[chunk_start : chunk_start + MAX_PAIRS_PER_PROMPT]
        logger.info(
            "Sending chunk %d–%d (%d pairs) to Gemini",
            chunk_start + 1,
            chunk_start + len(chunk),
            len(chunk),
        )

        prompt = _build_prompt(chunk)

        try:
            raw = generate_json(prompt, model=model)
        except GeminiConfigurationError:
            raise
        except Exception as exc:
            raise GeminiConfigurationError(f"Unexpected Gemini error: {exc}") from exc

        raw_findings = raw.get("findings", [])
        if len(raw_findings) != len(chunk):
            logger.warning(
                "Gemini returned %d findings for %d pairs in chunk — padding/truncating",
                len(raw_findings),
                len(chunk),
            )
            while len(raw_findings) < len(chunk):
                raw_findings.append(
                    {"relation_type": "no_issue", "severity": "low", "risk_score": 0.0,
                     "rationale": "Gemini did not return a result for this pair.",
                     "statute_citation": ""}
                )
            raw_findings = raw_findings[: len(chunk)]

        for (clause_a, clause_b, surfaced_by), item in zip(chunk, raw_findings):
            results.append(_parse_finding(clause_a, clause_b, surfaced_by, item))

    return results


def _parse_finding(
    clause_a: Clause,
    clause_b: Clause,
    surfaced_by: list[str],
    item: dict,
) -> Finding | None:
    """Parse and validate a single Gemini finding dict into a ``Finding``."""
    try:
        relation_type = str(item.get("relation_type", "no_issue")).strip().lower()
        severity = str(item.get("severity", "low")).strip().lower()
        risk_score = float(item.get("risk_score", 0.0))
        rationale = str(item.get("rationale", "")).strip()
        statute_citation = str(item.get("statute_citation", "")).strip()

        # Normalise
        if relation_type not in VALID_RELATION_TYPES:
            logger.warning("Unexpected relation_type %r — treating as no_issue", relation_type)
            relation_type = "no_issue"
        if severity not in VALID_SEVERITIES:
            severity = "low"
        risk_score = max(0.0, min(1.0, risk_score))

        if relation_type == "no_issue":
            return None

        refs = []
        if statute_citation:
            refs = [{"source": statute_citation, "section": "", "snippet": rationale}]

        return Finding(
            id=f"finding_{uuid.uuid4().hex[:8]}",
            target_clause_id=clause_a.id,
            related_clause_ids=[clause_b.id],
            relation_type=relation_type,
            severity=severity,
            risk_score=risk_score,
            rationale=rationale,
            surfaced_by=[*surfaced_by, "gemini"],
            evidence=[
                {"clause_id": clause_a.id, "start": 0, "end": len(clause_a.text)},
                {"clause_id": clause_b.id, "start": 0, "end": len(clause_b.text)},
            ],
            refs=refs,
            scores={"analysis_confidence": risk_score, "gemini_powered": 1.0},
        )

    except Exception as exc:
        logger.warning("Could not parse Gemini finding for pair (%s, %s): %s", clause_a.id, clause_b.id, exc)
        return None
