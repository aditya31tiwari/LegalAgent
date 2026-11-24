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
        if r.get("confidence"):
            mark += f" [{r['confidence']} confidence]"
        parts.append(f"{r.get('source', '')}, {r.get('section', '')}{(' — ' + r['heading']) if r.get('heading') else ''}{mark}".strip(", "))
    return "; ".join(p for p in parts if p)


DETAILS_DDL = """CREATE TABLE IF NOT EXISTS finding_details (
    finding_id TEXT PRIMARY KEY, contract_id TEXT, details TEXT)"""


def persist(contract_id: str, title: str, jurisdiction: str, category: str, clauses, findings, run=None) -> None:
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(DETAILS_DDL)
    for f in findings:  # everything the "under the hood" view needs, kept verbatim
        cur.execute("INSERT OR REPLACE INTO finding_details VALUES (?,?,?)", (f.id, contract_id, json.dumps({
            "surfaced_by": f.surfaced_by, "scores": f.scores, "refs": f.refs, "risk_score": f.risk_score,
            "relation_type": f.relation_type, "severity": f.severity, "rationale": f.rationale,
            "run": {"stats": run.stats, "config": run.config} if run is not None else None}, default=str)))
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
        from legalagent.core.types import Run
        persist(contract_id, title, config["jurisdiction"], category, clauses, findings,
                Run(id="live", contract_id=contract_id, config={**config, "classifier": backend},
                    stats={"judge": used, "pairs": len(pairs), "clauses": len(clauses)}))
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


# ---------------------------------------------------------------- under the hood

_SCORE_CACHE: dict = {}


def _contract_scores(contract_id: str):
    """All pairwise retrieval signals for one contract, computed once and cached in memory."""
    if contract_id in _SCORE_CACHE:
        return _SCORE_CACHE[contract_id]
    import numpy as np
    from legalagent.core.types import Clause
    from legalagent.core.classification import classify
    from legalagent.core.extraction import XREF_RE
    from legalagent.core.retrieval import index_text, _bm25_matrix, _dense_matrix, _rrf_matrix, DEFAULT_MODEL
    from legalagent.core.candidate_selection import TYPE_MATRIX
    from pathlib import Path as _P

    conn = get_db_connection()
    rows = [dict(r) for r in conn.execute("SELECT id, clause_num, title, text FROM clauses WHERE contract_id=? ORDER BY ordinal", (contract_id,))]
    conn.close()
    if len(rows) < 2:
        raise HTTPException(404, "contract has fewer than two clauses")
    clauses = classify([Clause(id=r["id"], contract_id=contract_id, number=r["clause_num"], text=r["text"]) for r in rows], backend="auto")
    texts = [index_text(c) for c in clauses]
    num_to_idx = {}
    for i, c in enumerate(clauses):
        num_to_idx.setdefault(c.number, i)
    xref = np.zeros((len(rows), len(rows)), bool)
    for i, c in enumerate(clauses):
        for m in XREF_RE.finditer(c.text):
            j = num_to_idx.get(m.group(1))
            if j is not None and j != i:
                xref[i, j] = xref[j, i] = True
    models = {"minilm": DEFAULT_MODEL, "inlegal_sbert": "bhavyagiri/InLegal-Sbert"}
    ft = _P(__file__).resolve().parents[1] / "models" / "inlegal_sbert_clauses"
    if (ft / "config.json").exists():
        models["inlegal_sbert_ft"] = str(ft)
    mats = {"bm25": _bm25_matrix(texts)}
    for name, m in models.items():
        mats[f"cos_{name}"] = _dense_matrix(texts, m)
    mats["rrf_hybrid"] = _rrf_matrix([mats["bm25"], mats["cos_minilm"]], len(rows))
    labels = [[l["label"] for l in c.labels] for c in clauses]
    gnn = None
    try:
        from legalagent.core.gnn import _load, build_graph, type_weight
        import torch
        model = _load()
        if model is not None:
            cl = [{"id": c.id, "text": c.text, "labels": labels[i], "xrefs": [clauses[j].id for j in np.where(xref[i])[0]]}
                  for i, c in enumerate(clauses)]
            x, ei, _ = build_graph(cl)
            with torch.no_grad():
                h = model.encode(torch.tensor(x), torch.tensor(ei))
            gnn = (model, h, type_weight)
    except Exception:
        gnn = None
    data = {"rows": rows, "clauses": clauses, "labels": labels, "mats": mats, "xref": xref, "gnn": gnn,
            "type_matrix": TYPE_MATRIX, "models": models}
    _SCORE_CACHE[contract_id] = data
    return data


@router.get("/api/contracts/{contract_id}/scores/{clause_id}")
def clause_scores(contract_id: str, clause_id: str, k: int = 6):
    """Every retrieval signal for one clause against its most related clauses (union of each method's top-k)."""
    import numpy as np
    d = _contract_scores(contract_id)
    ids = [r["id"] for r in d["rows"]]
    if clause_id not in ids:
        raise HTTPException(404, "clause not found")
    i = ids.index(clause_id)
    cand = set(np.where(d["xref"][i])[0].tolist())
    for name, m in d["mats"].items():
        row = m[i].copy()
        row[i] = -np.inf
        cand |= set(np.argsort(-row)[:k].tolist())
    cand.discard(i)

    def rank(name, j):
        row = d["mats"][name][i].copy()
        row[i] = -np.inf
        return int((row > row[j]).sum()) + 1

    out = []
    for j in cand:
        tw = max([d["type_matrix"].get((a, b), d["type_matrix"].get((b, a), 0.0)) for a in d["labels"][i] for b in d["labels"][j]] or [0.0])
        item = {"clause_id": ids[j], "number": d["rows"][j]["clause_num"], "text": d["rows"][j]["text"][:300],
                "labels": d["labels"][j], "xref": bool(d["xref"][i, j]), "type_matrix_weight": tw}
        for name in d["mats"]:
            item[name] = round(float(d["mats"][name][i, j]), 4)
            item[f"{name}_rank"] = rank(name, j)
        if d["gnn"]:
            import torch
            model, h, _ = d["gnn"]
            with torch.no_grad():
                p = torch.sigmoid(model.score(h, torch.tensor([i]), torch.tensor([j]), torch.tensor([tw], dtype=torch.float32)))
            item["gnn_prob"] = round(float(p[0]), 4)
        out.append(item)
    out.sort(key=lambda x: -x["rrf_hybrid"])
    bm_max = max([x["bm25"] for x in out] or [1]) or 1
    for x in out:
        x["bm25_norm"] = round(x["bm25"] / bm_max, 4)
    return {"clause": {"id": clause_id, "number": d["rows"][i]["clause_num"], "text": d["rows"][i]["text"][:600], "labels": d["labels"][i]},
            "methods": list(d["mats"]), "dense_models": d["models"], "neighbours": out[:15]}


@router.get("/api/findings/{finding_id}/scores")
def finding_scores(finding_id: str):
    """What the judge actually output for this finding + how its statutes were retrieved."""
    from legalagent.core.statutes import explain_sections
    conn = get_db_connection()
    conn.execute(DETAILS_DDL)
    f = conn.execute("SELECT * FROM findings WHERE id=?", (finding_id,)).fetchone()
    det = conn.execute("SELECT details FROM finding_details WHERE finding_id=?", (finding_id,)).fetchone()
    texts = []
    if f:
        for cid in (f["source_clause_ref"], f["target_clause_ref"]):
            c = conn.execute("SELECT clause_num, text FROM clauses WHERE id=?", (cid,)).fetchone()
            if c:
                texts.append({"id": cid, "number": c["clause_num"], "text": c["text"][:600]})
    conn.close()
    if not f:
        raise HTTPException(404, "finding not found")
    details = json.loads(det["details"]) if det else {}
    query = f"{f['description']} " + " ".join(t["text"] for t in texts)
    return {"finding": dict(f), "clauses": texts, "details": details, "statute_retrieval": explain_sections(query, k=6)}


@router.get("/api/results")
def all_results():
    """Every evaluation result file, for the charts on /scores."""
    from pathlib import Path as _P
    res = _P(__file__).resolve().parents[1] / "results"
    out = {}
    for p in sorted(res.glob("*.json")):
        try:
            out[p.stem] = json.loads(p.read_text())
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- document -> clauses (visual)

DEMO_DOCS = {
    "pune_adversarial_pdf": "data/demo/india/adversarial/pune_metro_adversarial_15_changes.pdf",
    "pune_signed_pdf": "data/demo/india/official/pune_metro_signed_concession.pdf",
    "nhai_model_pdf": "data/demo/india/official/model_concession_4_laning.pdf",
    "indian_msa_pdf": "data/demo/india/indian_tech_msa_demo.pdf",
    "pune_adversarial_md": "data/demo/samples/02_pune_metro_adversarial_15_injections.md",
    "indian_msa_md": "data/demo/samples/03_indian_tech_services_msa.md",
    "employment_md": "data/demo/samples/04_executive_employment_agreement.md",
}
_DOC_CACHE: dict = {}


def _doc_path(doc: str):
    from pathlib import Path as _P
    if doc not in DEMO_DOCS:
        raise HTTPException(404, "unknown document")
    return _P(__file__).resolve().parents[1] / DEMO_DOCS[doc]


@router.get("/api/docs")
def list_docs():
    out = []
    for key, rel in DEMO_DOCS.items():
        p = _doc_path(key)
        if p.exists():
            out.append({"id": key, "name": p.name, "kind": p.suffix.lstrip(".")})
    return out


@router.get("/api/docs/{doc}/structure")
def doc_structure(doc: str):
    """Ingestion + extraction exactly as the pipeline runs it, with everything needed to draw it."""
    if doc in _DOC_CACHE:
        return _DOC_CACHE[doc]
    from legalagent.core.ingestion import extract_raw, normalize, PAGE_BREAK, MIN_NATIVE_CHARS
    from legalagent.core.extraction import extract
    from legalagent.core.classification import classify
    path = _doc_path(doc)
    t0 = time.time()
    raw, stats = extract_raw(str(path))
    pages = raw.split(PAGE_BREAK) if path.suffix == ".pdf" else [raw]
    page_info = [{"page": i + 1, "chars": len(p), "ocr": False} for i, p in enumerate(pages)]
    if path.suffix == ".pdf":
        import pymupdf
        with pymupdf.open(path) as d:
            for i, pg in enumerate(d):
                page_info[i]["ocr"] = len(pg.get_text().strip()) < MIN_NATIVE_CHARS
    text = normalize(raw)
    clauses = classify(extract(text, doc), backend="auto")
    out = {
        "doc": doc, "name": path.name, "stats": stats, "pages": page_info, "text": text,
        "seconds": round(time.time() - t0, 2),
        "clauses": [{"id": c.id, "number": c.number, "part": c.part, "parent_id": c.parent_id, "heading": c.heading,
                     "start": c.char_start, "end": c.char_end, "labels": [l["label"] for l in c.labels],
                     "xrefs": [x["clause_id"] for x in c.xrefs if x["resolved"]]} for c in clauses],
    }
    _DOC_CACHE[doc] = out
    return out


@router.get("/api/docs/{doc}/page/{n}")
def doc_page(doc: str, n: int, dpi: int = 70):
    from fastapi.responses import Response
    path = _doc_path(doc)
    if path.suffix != ".pdf":
        raise HTTPException(400, "not a PDF")
    import pymupdf
    with pymupdf.open(path) as d:
        if not 1 <= n <= len(d):
            raise HTTPException(404, "page out of range")
        png = d[n - 1].get_pixmap(dpi=max(40, min(dpi, 120))).tobytes("png")
    return Response(png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


class PlaygroundRequest(BaseModel):
    a: str
    b: str
    use_gemini: Optional[bool] = False


@router.post("/api/playground")
def playground(req: PlaygroundRequest):
    """Every method on one clause pair (local by default; Gemini only if use_gemini)."""
    if not req.a.strip() or not req.b.strip():
        raise HTTPException(400, "both clauses are required")
    from legalagent.core.playground import compare_pair
    return compare_pair(req.a[:4000], req.b[:4000], use_gemini=bool(req.use_gemini))


@router.get("/scores")
def scores_page():
    from fastapi.responses import FileResponse
    from pathlib import Path as _P
    return FileResponse(_P(__file__).parent / "scores.html")


@router.get("/vendor/{name}")
def vendor_file(name: str):
    """Locally vendored front-end libraries (works without internet in the viva room)."""
    from fastapi.responses import FileResponse
    from pathlib import Path as _P
    base = (_P(__file__).parent / "vendor").resolve()
    p = (base / name).resolve()
    if base not in p.parents or not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p)


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
