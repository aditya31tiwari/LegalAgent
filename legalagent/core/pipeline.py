"""
Orchestration: file/text -> clauses -> candidate pairs -> judged findings.

The pair judge is pluggable (config["judge"]):
  rules   deterministic pattern rules (analysis.analyse_pair) — no model, no network
  local   fine-tuned open-weight decision model on this machine (core.local_judge);
          contract text never leaves the machine
  gemini  Google Gemini via API (core.gemini_analysis)
Any judge that is unavailable degrades to the next one: gemini -> local -> rules.
Legacy config["use_gemini"]=True maps to judge="gemini".
"""
import logging
import time
import uuid

from legalagent.core.types import Run, Clause, Finding
from legalagent.core.ingestion import ingest
from legalagent.core.extraction import extract
from legalagent.core.classification import classify, available_backend
from legalagent.core.candidate_selection import select_candidates
from legalagent.core.analysis import analyse_pair, analyse_statutory, validate_findings

logger = logging.getLogger(__name__)

JUDGES = ("rules", "local", "gemini")
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _run_rules(pair_objects) -> tuple[list[Finding], int]:
    """Deterministic baseline: pattern-match rules, no API calls."""
    findings, no_issue = [], 0
    for clause_a, clause_b, surfaced_by in pair_objects:
        finding = analyse_pair(clause_a, clause_b, surfaced_by)
        if finding is None:
            no_issue += 1
        else:
            findings.append(finding)
    return findings, no_issue


def _run_local(pair_objects, config) -> tuple[list[Finding], int]:
    from legalagent.core.local_judge import judge_pairs
    results = judge_pairs(pair_objects, model_dir=config.get("local_judge_model"))
    return [f for f in results if f is not None], sum(1 for f in results if f is None)


def _run_gemini(pair_objects, config) -> tuple[list[Finding], int]:
    from legalagent.core.gemini_analysis import analyse_pairs_with_gemini
    results = analyse_pairs_with_gemini(pair_objects, model=config.get("gemini_model"))
    return [f for f in results if f is not None], sum(1 for f in results if f is None)


def judge_pairs(pair_objects, config: dict) -> tuple[list[Finding], int, str]:
    """Run the requested judge with graceful fallback. Returns (findings, no_issue, judge_used)."""
    judge = config.get("judge") or ("gemini" if config.get("use_gemini") else "rules")
    chain = {"gemini": ["gemini", "local", "rules"], "local": ["local", "rules"], "rules": ["rules"]}[judge]
    for name in chain:
        try:
            if name == "gemini":
                f, n = _run_gemini(pair_objects, config)
            elif name == "local":
                f, n = _run_local(pair_objects, config)
            else:
                f, n = _run_rules(pair_objects)
            return f, n, name
        except Exception as exc:  # unavailable model / API: degrade, never crash the demo
            logger.warning("judge %s unavailable (%s) — falling back", name, exc)
    raise RuntimeError("no judge available")


def analyse_clauses(clauses: list[Clause], config: dict, contract_id: str = "local"):
    """Pipeline from already-extracted clauses. Returns (run, clauses, findings)."""
    config = dict(config or {})
    timings = {}

    t = time.perf_counter()
    backend = available_backend(config.get("classifier", "auto"))
    clauses = classify(clauses, backend=backend)
    timings["classify_s"] = round(time.perf_counter() - t, 3)

    t = time.perf_counter()
    pairs = select_candidates(clauses, config)
    timings["candidates_s"] = round(time.perf_counter() - t, 3)

    by_id = {c.id: c for c in clauses}
    pair_objects = [(by_id[a], by_id[b], s) for a, b, s in pairs]

    t = time.perf_counter()
    pair_findings, no_issue, judge_used = judge_pairs(pair_objects, config)
    timings["judge_s"] = round(time.perf_counter() - t, 3)

    findings = list(pair_findings)
    # Clause vs Indian law: deterministic rules + Kev's single-clause check (shown with confidence
    # labels, never silently dropped) + grounded statute retrieval for every finding.
    rule_findings = analyse_statutory(clauses, config.get("jurisdiction", "India"))
    findings.extend(rule_findings)
    if config.get("kev_statutory", True) and judge_used == "local":
        t = time.perf_counter()
        try:
            from legalagent.core.statutory_kev import kev_statutory_findings
            kev_findings = kev_statutory_findings(clauses, rule_hits={f.target_clause_id for f in rule_findings})
            # One card per clause: when the rules confirm Kev's finding, fold the rule finding into it
            # (rule explanation + references) instead of showing the same clause twice.
            confirmed = {f.target_clause_id: f for f in kev_findings if f.scores.get("rule_confirmed")}
            for rf in rule_findings:
                kf = confirmed.get(rf.target_clause_id)
                if kf is None:
                    continue
                kf.rationale += f" Rule check: {rf.rationale}"
                kf.refs = kf.refs + [r for r in rf.refs if r not in kf.refs]
                kf.risk_score = max(kf.risk_score, rf.risk_score)
            findings = [f for f in findings if not (f in rule_findings and f.target_clause_id in confirmed)]
            findings.extend(kev_findings)
        except Exception as exc:
            logger.warning("Kev statutory check skipped: %s", exc)
        timings["kev_statutory_s"] = round(time.perf_counter() - t, 3)
    if config.get("ground_statutes", True):
        try:
            from legalagent.core.statutes import attach_statute_refs
            attach_statute_refs(findings, by_id)
        except Exception as exc:
            logger.info("statute grounding skipped: %s", exc)
    validate_findings(findings, clauses)

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 3), -f.risk_score))

    run = Run(
        id=f"run_{uuid.uuid4().hex[:8]}",
        contract_id=contract_id,
        config={"retrieval_method": "bm25", "top_k": 5, **config, "classifier": backend},
        stats={
            "clauses": len(clauses),
            "pairs": len(pairs),
            "findings": len(findings),
            "no_issue": no_issue,
            "judge": judge_used,
            "gemini_powered": judge_used == "gemini",
            **timings,
        },
    )
    return run, clauses, findings


def analyse_text(text: str, config: dict, contract_id: str = "local"):
    """Pipeline from raw contract text (already ingested/normalised or plain)."""
    return analyse_clauses(extract(text, contract_id), config, contract_id)


def analyse(file_path: str, config: dict, contract_id: str = "local") -> tuple[Run, list[Clause], list[Finding]]:
    """
    Full analysis pipeline:
        ingest -> extract -> classify -> select_candidates
        -> judge (rules | local | gemini) -> analyse_statutory -> statute grounding
        -> validate_findings -> rank
    """
    return analyse_text(ingest(file_path), config, contract_id)
