"""
Live analysis API (local-first).

  POST /api/contracts/analyze/stream   JSON {title, text, ...}          -> SSE progress
  POST /api/contracts/upload/stream    multipart file (PDF/DOCX/img/TXT) -> SSE progress
  POST /api/contracts/analyze          JSON, non-streaming
  POST /api/findings/{id}/expand       opt-in Gemini explanation grounded in retrieved statutes
  GET  /api/system/status              which models are loaded / reachable

Every stage runs the same functions as the CLI (legalagent.core.*), so what the demo
shows is what the evaluation measured. The default judge is the local Kev model; the
chain degrades local -> rules. Gemini is never called unless the request asks for it
(judge="gemini" or the Expand button).
"""
import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from legalagent.db import get_db_connection

router = APIRouter()

SEVERITY_COLOUR = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}
EDGE_TYPE = {"conflict": "conflict", "dependency": "xref", "overlap": "semantic",
             "ambiguity": "semantic", "statutory_violation": "statutory"}
# CLAUSE-22 labels + known_gaps -> existing UI tag colours in web/index.html.
LABEL_TO_TAG = {
    "limitation_of_liability": "Liability", "exclusivity_and_restraint": "High Risk",
    "liquidated_damages": "High Risk", "warranty": "Risk", "remedies": "Risk",
    "indemnification": "Indemnity", "compliance_and_law": "Compliance", "data_protection": "DPDPA",
    "stamp_duty": "Statutory", "change_in_law": "Statutory",
    "termination": "Term", "term_and_renewal": "Term", "survival": "Survival", "force_majeure": "Term",
    "confidentiality": "IP", "ip_ownership": "IP", "license_grant": "IP",
    "governing_law": "Governing Law", "dispute_resolution": "Dispute", "arbitration": "Dispute",
    "payment_and_fees": "Payment", "tax": "Payment", "performance_security": "Payment",
    "audit_and_records": "General", "insurance": "General", "assignment_change_of_control": "General",
    "step_in_rights": "General", "notices": "General", "amendment_and_integration": "General",
}
ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}
MAX_UPLOAD_BYTES = 40 * 1024 * 1024


class AnalyzeRequest(BaseModel):
    title: str
    text: str
    jurisdiction: Optional[str] = "India"
    max_candidates: Optional[int] = 30
    judge: Optional[str] = "local"          # local | rules | gemini
    retrieval: Optional[str] = "hybrid"     # bm25 | dense | hybrid
    use_gnn: Optional[bool] = False


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


def _config(judge, retrieval, max_candidates, jurisdiction, use_gnn) -> dict:
    return {
        "judge": judge if judge in ("local", "rules", "gemini") else "local",
        "retrieval_method": retrieval if retrieval in ("bm25", "dense", "hybrid") else "hybrid",
        "top_k": 5,
        "max_candidates": max_candidates,
        "jurisdiction": jurisdiction or "India",
        "use_gnn": bool(use_gnn),
        "classifier": "auto",
    }


def _refs_text(refs: list[dict]) -> str:
    parts = []
    for r in refs:
        mark = "" if r.get("verified", True) else " [unverified]"
        parts.append(f"{r.get('source', '')}, {r.get('section', '')}{(' — ' + r['heading']) if r.get('heading') else ''}{mark}".strip(", "))
    return "; ".join(p for p in parts if p)


def persist(contract_id: str, title: str, jurisdiction: str, category: str, clauses, findings, run=None) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    desc = f"{len(clauses)} clauses, {len(findings)} findings"
    if run is not None:
        desc += f"; judge={run.stats.get('judge')}, classifier={run.config.get('classifier')}, retrieval={run.config.get('retrieval_method')}"
    cur.execute("INSERT INTO contracts (id, title, category, jurisdiction, description) VALUES (?,?,?,?,?);",
                (contract_id, title, category, jurisdiction, desc))
    for cl in clauses:
        tag = LABEL_TO_TAG.get(cl.labels[0]["label"] if cl.labels else "", "General")
        heading = cl.heading or f"Clause {cl.number or cl.ordinal}"
        cur.execute("INSERT INTO clauses (id, contract_id, clause_num, title, tag, text, ordinal) VALUES (?,?,?,?,?,?,?);",
                    (cl.id, contract_id, cl.number or str(cl.ordinal), heading[:80], tag, cl.text[:4000], cl.ordinal))
    for f in findings:
        tgt = f.related_clause_ids[0] if f.related_clause_ids else f.target_clause_id
        cur.execute("INSERT INTO graph_edges (contract_id, source_clause_id, target_clause_id, label, relation_type, severity, color, width, dashes) VALUES (?,?,?,?,?,?,?,?,?);",
                    (contract_id, f.target_clause_id, tgt, f.relation_type.upper().replace("_", " "),
                     EDGE_TYPE.get(f.relation_type, "semantic"), f.severity,
                     SEVERITY_COLOUR.get(f.severity, "#64748b"), 2.0 + 2 * f.risk_score, 0))
        cur.execute("INSERT INTO findings (id, contract_id, title, severity, relation_type, source_clause_ref, target_clause_ref, description, statute_citation, remedy_suggestion) VALUES (?,?,?,?,?,?,?,?,?,?);",
                    (f.id, contract_id, f.relation_type.replace("_", " ").title()[:120], f.severity, f.relation_type,
                     f.target_clause_id, tgt, f.rationale[:900], _refs_text(f.refs)[:600],
                     "Use 'Expand' for a drafted fix." if "gemini" not in f.surfaced_by else f.rationale[:300]))
    conn.commit()
    conn.close()


def _stream(text_source, title: str, config: dict, category: str):
    """Shared SSE generator. text_source: ("text", str) or ("file", path)."""
    from legalagent.core.ingestion import ingest_with_stats, normalize
    from legalagent.core.extraction import extract
    from legalagent.core.classification import classify, available_backend
    from legalagent.core.candidate_selection import select_candidates
    from legalagent.core.pipeline import judge_pairs, SEVERITY_ORDER
    from legalagent.core.analysis import analyse_statutory, validate_findings

    t0 = time.time()
    contract_id = f"custom_{uuid.uuid4().hex[:6]}"

    def ev(stage, label, detail, **extra):
        return _sse({"stage": stage, "label": label, "detail": detail,
                     "elapsed": round(time.time() - t0, 2), "done": extra.pop("done", False), **extra})

    try:
        yield ev("received", "Contract Received", f"Processing \"{title}\" · judge={config['judge']} · retrieval={config['retrieval_method']}")

        # 1. Ingestion (+ OCR)
        if text_source[0] == "file":
            path = text_source[1]
            text, stats = ingest_with_stats(path)
            how = f"{stats.get('pages', 1)} page(s)"
            if stats.get("ocr_pages"):
                how += f", {stats['ocr_pages']} OCR'd with Tesseract" + (" (cached)" if stats.get("cached") else "")
            yield ev("ingestion", "Document Ingested", f"{how} → {len(text):,} characters of normalised text", meta=stats)
        else:
            text = normalize(text_source[1])
            yield ev("ingestion", "Text Ingested", f"Normalised {len(text):,} characters")

        # 2. Extraction
        clauses = extract(text, contract_id)
        parts = len({c.part for c in clauses if c.part})
        xrefs = sum(x["resolved"] for c in clauses for x in c.xrefs)
        yield ev("extraction", "Clauses Extracted",
                 f"{len(clauses)} clauses in {parts or 1} part(s), {xrefs} resolved cross-references")
        if not clauses:
            yield ev("error", "No Clauses Found", "No numbered clauses were detected in this document.", done=True)
            return

        # 3. Classification
        backend = available_backend(config["classifier"])
        t = time.time()
        clauses = classify(clauses, backend=backend)
        counts = {}
        for c in clauses:
            for l in c.labels:
                counts[l["label"]] = counts.get(l["label"], 0) + 1
        top = ", ".join(f"{k} ({v})" for k, v in sorted(counts.items(), key=lambda x: -x[1])[:4]) or "none"
        yield ev("classification", "Clauses Classified",
                 f"{backend} classifier in {time.time() - t:.2f}s — top: {top}", meta={"backend": backend, "counts": counts})

        # 4. Candidate pairs
        pairs = select_candidates(clauses, config)
        n = len(clauses)
        total = n * (n - 1) // 2
        by_method = {}
        for _, _, how in pairs:
            for m in how:
                by_method[m] = by_method.get(m, 0) + 1
        yield ev("candidates", "Candidate Pair Shortlisting",
                 f"{len(pairs)} of {total:,} possible pairs ({(1 - len(pairs) / max(1, total)) * 100:.1f}% pruned)",
                 meta={"total_clauses": n, "total_possible": total, "shortlisted": len(pairs), "by_method": by_method,
                       "xref_count": by_method.get("xref", 0), "type_matrix_count": by_method.get("type_matrix", 0),
                       "bm25_count": by_method.get("bm25", 0) + by_method.get("hybrid", 0), "dense_count": by_method.get("dense", 0),
                       "reduction_pct": round((1 - len(pairs) / max(1, total)) * 100, 1),
                       "methods": sorted(by_method), "limit_mode": f"Budget Capped ({config['max_candidates']})" if config["max_candidates"] else "Unset (Exhaustive)"})

        # 5. Judge
        by_id = {c.id: c for c in clauses}
        pair_objects = [(by_id[a], by_id[b], how) for a, b, how in pairs]
        t = time.time()
        findings, no_issue, used = judge_pairs(pair_objects, config)
        where = {"local": "on-device Kev decision model (no data left this machine)",
                 "rules": "deterministic rules", "gemini": "Gemini API (cloud)"}[used]
        fallback = "" if used == config["judge"] else f" — requested '{config['judge']}' unavailable, fell back"
        yield ev("analysis", "Cross-Clause Analysis",
                 f"{len(pairs)} pairs judged by {where} in {time.time() - t:.2f}s → {len(findings)} issue(s), {no_issue} clear{fallback}",
                 meta={"judge": used})

        # 6. Statutes: deterministic checks + grounding
        statutory = analyse_statutory(clauses, config["jurisdiction"])
        findings.extend(statutory)
        grounded = 0
        try:
            from legalagent.core.statutes import attach_statute_refs
            attach_statute_refs(findings, by_id)
            grounded = sum(1 for f in findings if any(r.get("verified") for r in f.refs))
        except Exception as exc:
            yield ev("log", "Statute grounding skipped", str(exc))
        validate_findings(findings, clauses)
        findings.sort(key=lambda f: (SEVERITY_ORDER.get(f.severity, 3), -f.risk_score))
        yield ev("statutory", "Indian Statute Grounding",
                 f"{len(statutory)} statutory flag(s); {grounded}/{len(findings)} findings linked to verified India Code sections")

        # 7. Persist
        persist(contract_id, title, config["jurisdiction"], category, clauses, findings)
        yield ev("persisted", "Graph Saved", f"{len(clauses)} clause nodes + {len(findings)} finding edges")

        high = sum(1 for f in findings if f.severity == "high")
        yield ev("complete", "Analysis Complete",
                 f"{len(clauses)} clauses · {len(findings)} findings ({high} high) · {len(pairs)} pairs examined",
                 done=True, contract_id=contract_id,
                 stats={"clauses": len(clauses), "findings": len(findings), "critical": high, "pairs": len(pairs), "judge": used})
    except Exception as exc:  # surface, never hang the browser
        yield ev("error", "Analysis Failed", f"{type(exc).__name__}: {exc}", done=True)
    finally:
        if text_source[0] == "file":
            Path(text_source[1]).unlink(missing_ok=True)


def _streaming(gen):
    return StreamingResponse(gen, media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"})


@router.post("/api/contracts/analyze/stream")
def analyze_stream(req: AnalyzeRequest):
    config = _config(req.judge, req.retrieval, req.max_candidates, req.jurisdiction, req.use_gnn)
    return _streaming(_stream(("text", req.text), req.title or "Untitled Agreement", config, "Live Analysis"))


@router.post("/api/contracts/upload/stream")
async def upload_stream(
    file: UploadFile = File(...),
    title: str = Form(""),
    judge: str = Form("local"),
    retrieval: str = Form("hybrid"),
    max_candidates: int = Form(30),
    jurisdiction: str = Form("India"),
    use_gnn: bool = Form(False),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported file type {suffix!r}; use {sorted(ALLOWED_SUFFIXES)}")
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File larger than 40 MB")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(data)
    tmp.close()
    config = _config(judge, retrieval, max_candidates or None, jurisdiction, use_gnn)
    return _streaming(_stream(("file", tmp.name), title or Path(file.filename).stem, config, "Uploaded Document"))


@router.post("/api/contracts/analyze")
def analyze(req: AnalyzeRequest):
    """Non-streaming variant: runs the same generator and returns the final event."""
    config = _config(req.judge, req.retrieval, req.max_candidates, req.jurisdiction, req.use_gnn)
    last = None
    for chunk in _stream(("text", req.text), req.title or "Untitled Agreement", config, "Live Analysis"):
        last = json.loads(chunk[len("data: "):])
    if not last or last.get("stage") == "error":
        raise HTTPException(500, (last or {}).get("detail", "analysis failed"))
    return {"status": "success", "contract_id": last["contract_id"], "stats": last.get("stats")}


@router.post("/api/findings/{finding_id}/expand")
def expand_finding(finding_id: str):
    """
    Opt-in cloud assist: Gemini explains ONE finding in plain English and drafts a fix,
    given only the two clauses and the statute sections our local retriever found.
    Every section Gemini cites is checked against the local library.
    """
    from legalagent.core.gemini import generate_json
    from legalagent.core.statutes import retrieve_sections, verify_citation

    conn = get_db_connection()
    row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(404, "finding not found")
    f = dict(row)
    texts = {}
    for cid in (f["source_clause_ref"], f["target_clause_ref"]):
        c = conn.execute("SELECT clause_num, text FROM clauses WHERE id = ?", (cid,)).fetchone()
        if c:
            texts[cid] = (c["clause_num"], c["text"])
    conn.close()

    sections = [s for s, _ in retrieve_sections(f"{f['description']} " + " ".join(t for _, t in texts.values()), k=5)]
    law = "\n".join(f"[{i}] {s['act']}, Section {s['section']} ({s['heading']}): {s['text'][:700]}" for i, s in enumerate(sections))
    clauses_txt = "\n\n".join(f"Clause {num}:\n{text[:1500]}" for num, text in texts.values())
    prompt = f"""You are assisting an Indian contract reviewer. A local model flagged this issue:
Type: {f['relation_type']} | Severity: {f['severity']}
Finding: {f['description']}

{clauses_txt}

Indian statute sections retrieved for this issue (cite ONLY these, by their [index]):
{law}

Return JSON: {{"explanation": "<3-5 plain-English sentences for a business reader>",
"legal_basis": [{{"index": <int>, "why": "<one sentence>"}}],
"suggested_redline": "<replacement or added wording for the weaker clause>",
"confidence": "<low|medium|high>"}}"""
    try:
        out = generate_json(prompt)
    except Exception as exc:
        raise HTTPException(503, f"Gemini unavailable: {exc}")
    basis = []
    for b in out.get("legal_basis", []):
        try:
            s = sections[int(b.get("index"))]
            basis.append({"act": s["act"], "section": s["section"], "heading": s["heading"], "url": s["url"],
                          "why": b.get("why", ""), "verified": verify_citation(f"{s['act']} section {s['section']}") is not None})
        except (TypeError, ValueError, IndexError):
            continue
    return {"finding_id": finding_id, "explanation": out.get("explanation", ""), "legal_basis": basis,
            "suggested_redline": out.get("suggested_redline", ""), "confidence": out.get("confidence", ""),
            "sent_to_cloud": True, "retrieved_sections": [{"act": s["act"], "section": s["section"]} for s in sections]}


@router.get("/api/system/status")
def system_status():
    import os
    from legalagent.core.classification import available_backend
    from legalagent.core import local_judge
    status = {"classifier": available_backend("auto"), "kev_server": local_judge.available(), "kev_url": local_judge.KEV_URL,
              "gemini_configured": bool(os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEYS"))}
    try:
        import torch
        status["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except Exception:
        status["gpu"] = None
    try:
        from legalagent.core.statutes import load_library
        status["statute_sections"] = len(load_library())
    except Exception:
        status["statute_sections"] = 0
    return status
