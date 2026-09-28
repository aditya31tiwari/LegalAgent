from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, Generator
import asyncio
import time
import os
import sys
import uuid
import json
import numpy as np
from pathlib import Path

from dotenv import load_dotenv

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from legalagent.db import (
    get_db_connection,
    fetch_all_contracts_summary,
    fetch_contract_graph_json,
    init_db,
    seed_database,
    DB_PATH,
    fetch_clause_embeddings,
    store_clause_embeddings,
)
from legalagent.core.embeddings import embed_texts

load_dotenv(PROJECT_ROOT / ".env")

app = FastAPI(
    title="LegalAgent Core Intelligence API",
    description="Cross-Clause Contract Risk Detection & Indian Statutory Compliance Engine",
    version="0.4.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).parent


class AnalyzeRequest(BaseModel):
    title: str
    text: str
    jurisdiction: Optional[str] = "India"


@app.on_event("startup")
def startup_event():
    database_exists = DB_PATH.exists()
    init_db()
    if not database_exists:
        seed_database()


@app.get("/api/contracts/{contract_id}/embeddings")
def get_contract_embeddings(contract_id: str, model: str = "bhavyagiri/InLegal-Sbert"):
    """Return a compact 2D projection plus metadata for the embedding graph."""
    data = fetch_contract_graph_json(contract_id)
    if not data or not data.get("contract"):
        raise HTTPException(status_code=404, detail="Contract not found")

    stored = fetch_clause_embeddings(contract_id, model)
    if len(stored) != len(data["clauses"]):
        try:
            vectors = embed_texts([clause["text"] for clause in data["clauses"]], model)
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Embedding model unavailable: {exc}") from exc
        stored = [
            {
                "clause_id": clause["id"],
                "dimension": int(vectors[index].shape[0]),
                "vector": vectors[index].tolist(),
            }
            for index, clause in enumerate(data["clauses"])
        ]
        store_clause_embeddings(contract_id, model, stored)

    vectors = np.asarray([json.loads(item["vector_json"]) if "vector_json" in item else item["vector"] for item in stored], dtype=np.float32)
    centered = vectors - vectors.mean(axis=0, keepdims=True)
    if len(vectors) > 1:
        _, _, components = np.linalg.svd(centered, full_matrices=False)
        coordinates = centered @ components[:2].T
    else:
        coordinates = np.zeros((len(vectors), 2), dtype=np.float32)
    scale = np.max(np.abs(coordinates), axis=0, keepdims=True)
    coordinates = np.divide(coordinates, np.where(scale == 0, 1, scale))
    clauses_by_id = {clause["id"]: clause for clause in data["clauses"]}
    return {
        "contract_id": contract_id,
        "model": model,
        "dimension": int(vectors.shape[1]) if len(vectors) else 0,
        "stored_count": len(stored),
        "points": [
            {
                "id": item["clause_id"],
                "x": float(coordinates[index][0]),
                "y": float(coordinates[index][1]),
                "number": clauses_by_id[item["clause_id"]].get("clause_num", ""),
                "title": clauses_by_id[item["clause_id"]].get("title", "Clause"),
            }
            for index, item in enumerate(stored)
        ],
    }


@app.get("/api/contracts")
def get_contracts():
    """Returns list of all stored contracts with high-level statistics."""
    summary = fetch_all_contracts_summary()
    conn = get_db_connection()
    cursor = conn.cursor()

    enriched = []
    for c in summary:
        cursor.execute("SELECT COUNT(*) as count FROM clauses WHERE contract_id = ?;", (c["id"],))
        clause_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM graph_edges WHERE contract_id = ?;", (c["id"],))
        edge_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM findings WHERE contract_id = ? AND severity IN ('high', 'statutory');", (c["id"],))
        critical_count = cursor.fetchone()["count"]

        cursor.execute("SELECT COUNT(*) as count FROM findings WHERE contract_id = ?;", (c["id"],))
        total_findings = cursor.fetchone()["count"]

        # Calculate a mock contract health score (100 - (critical * 25) - (total * 5))
        health_score = max(15, 100 - (critical_count * 28) - (total_findings * 6))

        enriched.append({
            **c,
            "clause_count": clause_count,
            "edge_count": edge_count,
            "critical_count": critical_count,
            "total_findings": total_findings,
            "health_score": health_score
        })

    conn.close()
    return enriched


@app.get("/api/contracts/{contract_id}")
def get_contract_details(contract_id: str):
    """Fetches full graph topology, clauses, and findings for a contract."""
    data = fetch_contract_graph_json(contract_id)
    if not data or not data.get("contract"):
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Calculate health & severity metrics
    findings = data.get("findings", [])
    critical = sum(1 for f in findings if f.get("severity") in ("high", "statutory"))
    health_score = max(10, 100 - (critical * 28) - (len(findings) * 5))
    data["contract"]["health_score"] = health_score
    data["contract"]["critical_count"] = critical
    
    return data


@app.post("/api/contracts/analyze")
def analyze_custom_contract(req: AnalyzeRequest):
    """
    Parses and analyses user-submitted contract text. Runs through core.pipeline
    (ingestion → extraction → classification → candidate selection → analysis) and
    persists the resulting graph to SQLite. Falls back to heuristic analysis if the
    pipeline raises an error.
    """
    import tempfile, uuid as _uuid
    conn = get_db_connection()
    cursor = conn.cursor()

    contract_id = f"custom_{_uuid.uuid4().hex[:6]}"
    title = req.title or "Untitled Custom Agreement"
    jurisdiction = req.jurisdiction or "India"

    # ── 1. Try the unified core pipeline ──────────────────────────────────────
    pipeline_ok = False
    pipeline_clauses: list = []
    pipeline_findings: list = []

    try:
        from legalagent.core.pipeline import analyse as pipeline_analyse
        from legalagent.core.ingestion import normalize

        # Write text to a temporary .txt file so pipeline.ingest() can read it
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                        delete=False, encoding="utf-8") as tmp:
            tmp.write(req.text)
            tmp_path = tmp.name

        config = {"retrieval_method": "bm25", "top_k": 10, "jurisdiction": jurisdiction}
        run, pipeline_clauses, pipeline_findings = pipeline_analyse(
            tmp_path, config, contract_id=contract_id
        )
        Path(tmp_path).unlink(missing_ok=True)
        pipeline_ok = True

    except Exception as exc:
        print(f"[backend] core.pipeline failed ({exc}), falling back to heuristic")

    # ── 2. Insert contract row ─────────────────────────────────────────────────
    n_clauses = len(pipeline_clauses) if pipeline_ok else len(
        [p for p in req.text.split("\n\n") if len(p.strip()) > 20] or [req.text.strip()]
    )
    cursor.execute(
        "INSERT INTO contracts (id, title, category, jurisdiction, description) VALUES (?,?,?,?,?);",
        (contract_id, title, "User Uploaded / Custom Review", jurisdiction,
         f"Custom agreement: {n_clauses} clauses analysed via {'core.pipeline' if pipeline_ok else 'heuristic'}."),
    )

    # ── 3a. Pipeline path — persist clauses, edges, findings ──────────────────
    if pipeline_ok:
        # Map core Clause → DB row
        LABEL_TO_TAG = {
            "indemnification": "Indemnity", "liability_limitation": "Liability",
            "termination": "Term", "survival": "Survival",
            "confidentiality": "IP", "governing_law": "Governing Law",
            "assignment": "General", "warranty": "Risk", "non_compete": "High Risk",
            "data_protection": "Compliance", "dispute_resolution": "Dispute",
            "payment": "Payment",
        }
        for cl in pipeline_clauses:
            tag = "General"
            if cl.labels:
                first_label = cl.labels[0].get("label", "")
                tag = LABEL_TO_TAG.get(first_label, "General")
            cursor.execute(
                "INSERT INTO clauses (id, contract_id, clause_num, title, tag, text, ordinal) VALUES (?,?,?,?,?,?,?);",
                (cl.id, contract_id, cl.number or str(cl.ordinal),
                 (cl.heading or f"Clause {cl.number or cl.ordinal}")[:80],
                 tag, cl.text[:2000], cl.ordinal),
            )

        SEVERITY_MAP = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}
        TYPE_TO_ETYPE = {
            "conflict": "conflict", "dependency": "xref",
            "overlap": "semantic", "ambiguity": "semantic", "no_issue": "semantic",
        }
        for f in pipeline_findings:
            if not f.related_clause_ids:
                continue
            src = f.target_clause_id
            tgt = f.related_clause_ids[0]
            etype = TYPE_TO_ETYPE.get(f.relation_type, "semantic")
            color = SEVERITY_MAP.get(f.severity, "#64748b")
            cursor.execute(
                "INSERT INTO graph_edges (contract_id, source_clause_id, target_clause_id, label, relation_type, severity, color, width, dashes) VALUES (?,?,?,?,?,?,?,?,?);",
                (contract_id, src, tgt, f.relation_type.upper().replace("_", " "), etype, f.severity, color, 2.0, 0),
            )
            statute = "; ".join(r.get("text", "") for r in f.refs) if f.refs else "Indian Contract Act, 1872"
            remedy = f.rationale[:300] if f.rationale else "Review and redraft the identified clauses."
            cursor.execute(
                "INSERT INTO findings (id, contract_id, title, severity, relation_type, source_clause_ref, target_clause_ref, description, statute_citation, remedy_suggestion) VALUES (?,?,?,?,?,?,?,?,?,?);",
                (f.id, contract_id,
                 f.relation_type.replace("_", " ").title()[:120],
                 f.severity, f.relation_type, src, tgt,
                 f.rationale[:600], statute[:400], remedy[:400]),
            )

    # ── 3b. Heuristic fallback ─────────────────────────────────────────────────
    else:
        raw_paragraphs = [p.strip() for p in req.text.split("\n\n") if len(p.strip()) > 20] or [req.text.strip()]
        clauses_to_insert: list = []
        for idx, para in enumerate(raw_paragraphs):
            cid = f"{contract_id}_c{idx+1}"
            num = f"{idx+1}.0"
            title_snippet = para[:40].replace("\n", " ") + "..."
            tag = "General"
            lower = para.lower()
            if "indemnif" in lower or "hold harmless" in lower:
                tag = "Indemnity"
            elif "limit" in lower and "liab" in lower:
                tag = "Liability"
            elif "non-compete" in lower or "restraint" in lower or "competing business" in lower:
                tag = "High Risk"
            elif "data" in lower or "dpdpa" in lower:
                tag = "Compliance"
            elif "dispute" in lower or "arbitrat" in lower:
                tag = "Dispute"
            elif "payment" in lower or "fee" in lower:
                tag = "Payment"
            clauses_to_insert.append((cid, num, title_snippet, tag, para, idx + 1))
            cursor.execute(
                "INSERT INTO clauses (id, contract_id, clause_num, title, tag, text, ordinal) VALUES (?,?,?,?,?,?,?);",
                (cid, contract_id, num, title_snippet, tag, para, idx + 1),
            )

        edges_to_insert, findings_to_insert = [], []
        cap_clause = next((c for c in clauses_to_insert if c[3] == "Liability"), None)
        indemnity_clause = next((c for c in clauses_to_insert if c[3] == "Indemnity"), None)
        non_compete_clause = next((c for c in clauses_to_insert if c[3] == "High Risk" or "compete" in c[4].lower()), None)

        if cap_clause and indemnity_clause:
            edges_to_insert.append((contract_id, cap_clause[0], indemnity_clause[0],
                                    "CONFLICT: Cap vs Indemnity", "conflict", "high", "#ef4444", 3.0, 0))
            findings_to_insert.append((
                f"{contract_id}_f1", contract_id, "Liability Cap Nullified by Uncapped Indemnity",
                "high", "contractual_conflict",
                f"Section {cap_clause[1]} ({cap_clause[2]})",
                f"Section {indemnity_clause[1]} ({indemnity_clause[2]})",
                "The limitation of liability clause imposes an aggregate ceiling, but the indemnification clause mandates uncapped defense without an exclusion carveout.",
                "Indian Contract Act, 1872 (Sections 124 & 125)",
                f"Amend Section {cap_clause[1]} to explicitly carve out Section {indemnity_clause[1]} indemnity obligations.",
            ))
        if non_compete_clause and "india" in jurisdiction.lower():
            edges_to_insert.append((contract_id, non_compete_clause[0], non_compete_clause[0],
                                    "STATUTORY VOID: Sec 27 ICA", "statutory", "high", "#ec4899", 3.5, 0))
            findings_to_insert.append((
                f"{contract_id}_f2", contract_id, "Post-Termination Non-Compete is Void Ab Initio",
                "statutory", "statutory_violation",
                f"Section {non_compete_clause[1]} (Non-Compete)", "Section 27, Indian Contract Act 1872",
                "Post-contractual non-competes are void under Indian law.",
                "Section 27 ICA & Percept D'Mark v. Zaheer Khan (2006)",
                "Delete post-termination non-compete; rely on NDA and trade-secret protections.",
            ))
        if not edges_to_insert and len(clauses_to_insert) > 1:
            for i in range(len(clauses_to_insert) - 1):
                edges_to_insert.append((
                    contract_id, clauses_to_insert[i][0], clauses_to_insert[i + 1][0],
                    "Sequential Clause Flow", "semantic", "low", "#0ea5e9", 1.5, 1,
                ))

        for e in edges_to_insert:
            cursor.execute(
                "INSERT INTO graph_edges (contract_id, source_clause_id, target_clause_id, label, relation_type, severity, color, width, dashes) VALUES (?,?,?,?,?,?,?,?,?);",
                e,
            )
        for f in findings_to_insert:
            cursor.execute(
                "INSERT INTO findings (id, contract_id, title, severity, relation_type, source_clause_ref, target_clause_ref, description, statute_citation, remedy_suggestion) VALUES (?,?,?,?,?,?,?,?,?,?);",
                f,
            )

    conn.commit()
    conn.close()
    return {"status": "success", "contract_id": contract_id,
            "engine": "core.pipeline" if pipeline_ok else "heuristic"}


@app.post("/api/contracts/analyze/stream")
async def analyze_contract_stream(req: AnalyzeRequest):
    """
    SSE streaming version of contract analysis.
    Yields one 'data: {...}\\n\\n' event per pipeline stage so the browser
    can update a live progress panel in real time.

    Event schema:
        stage   – machine-readable stage name
        label   – human-readable stage label
        detail  – short description of what happened
        elapsed – seconds since start (float)
        done    – true on the final event
        contract_id – present only on the final event
    """
    import tempfile as _tempfile

    def _sse(payload: dict) -> str:
        return f"data: {json.dumps(payload)}\n\n"

    def generate() -> Generator[str, None, None]:
        t0 = time.time()
        contract_id = f"custom_{uuid.uuid4().hex[:6]}"
        title = req.title or "Untitled Custom Agreement"
        jurisdiction = req.jurisdiction or "India"

        def elapsed() -> float:
            return round(time.time() - t0, 2)

        # ── Stage 1: Received ────────────────────────────────────────────────
        yield _sse({"stage": "received", "label": "Contract Received",
                    "detail": f"Processing \"{title}\" · {len(req.text):,} characters · Jurisdiction: {jurisdiction}",
                    "elapsed": elapsed(), "done": False})

        # Write to temp file for pipeline
        tmp_path = None
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                            delete=False, encoding="utf-8") as tmp:
                tmp.write(req.text)
                tmp_path = tmp.name
        except Exception as e:
            yield _sse({"stage": "error", "label": "File Error",
                        "detail": str(e), "elapsed": elapsed(), "done": True})
            return

        # ── Stage 2: Ingestion ───────────────────────────────────────────────
        try:
            from legalagent.core.ingestion import ingest, normalize
            raw_text = ingest(tmp_path)
            yield _sse({"stage": "ingestion", "label": "Text Ingested",
                        "detail": f"Normalised {len(raw_text):,} characters from plain text input",
                        "elapsed": elapsed(), "done": False})
        except Exception as e:
            yield _sse({"stage": "error", "label": "Ingestion Failed",
                        "detail": str(e), "elapsed": elapsed(), "done": True})
            return

        # ── Stage 3: Extraction ──────────────────────────────────────────────
        try:
            from legalagent.core.extraction import extract
            clauses = extract(raw_text, contract_id)
            yield _sse({"stage": "extraction", "label": "Clauses Extracted",
                        "detail": f"Found {len(clauses)} numbered clause{'s' if len(clauses) != 1 else ''} with unique IDs and cross-reference offsets",
                        "elapsed": elapsed(), "done": False})
        except Exception as e:
            yield _sse({"stage": "error", "label": "Extraction Failed",
                        "detail": str(e), "elapsed": elapsed(), "done": True})
            return

        # ── Stage 4: Classification ──────────────────────────────────────────
        try:
            from legalagent.core.classification import classify
            clauses = classify(clauses)
            label_counts: dict[str, int] = {}
            for cl in clauses:
                for lb in cl.labels:
                    label_counts[lb["label"]] = label_counts.get(lb["label"], 0) + 1
            top = sorted(label_counts.items(), key=lambda x: -x[1])[:4]
            top_str = ", ".join(f"{k} ({v})" for k, v in top) or "none detected"
            yield _sse({"stage": "classification", "label": "Clauses Classified",
                        "detail": f"Keyword classification applied — top labels: {top_str}",
                        "elapsed": elapsed(), "done": False})
        except Exception as e:
            yield _sse({"stage": "error", "label": "Classification Failed",
                        "detail": str(e), "elapsed": elapsed(), "done": True})
            return

        # ── Stage 5: Candidate Selection ─────────────────────────────────────
        try:
            from legalagent.core.candidate_selection import select_candidates
            config = {"retrieval_method": "bm25", "top_k": 10, "jurisdiction": jurisdiction}
            pairs = select_candidates(clauses, config)
            methods_used = set()
            for _, _, surfaced in pairs:
                methods_used.update(surfaced)
            yield _sse({"stage": "candidates", "label": "Candidate Pairs Selected",
                        "detail": f"{len(pairs)} clause pair{'s' if len(pairs) != 1 else ''} shortlisted via {', '.join(sorted(methods_used)) or 'BM25'}",
                        "elapsed": elapsed(), "done": False})
        except Exception as e:
            yield _sse({"stage": "error", "label": "Candidate Selection Failed",
                        "detail": str(e), "elapsed": elapsed(), "done": True})
            return

        # ── Stage 6: Cross-Clause Analysis ───────────────────────────────────
        try:
            from legalagent.core.analysis import analyse_pair, analyse_statutory, validate_findings
            findings = []
            for clause_a_id, clause_b_id, surfaced_by in pairs:
                clause_a = next(c for c in clauses if c.id == clause_a_id)
                clause_b = next(c for c in clauses if c.id == clause_b_id)
                f = analyse_pair(clause_a, clause_b, surfaced_by)
                if f:
                    findings.append(f)
            conflicts = len(findings)
            yield _sse({"stage": "analysis", "label": "Cross-Clause Analysis",
                        "detail": f"Analysed {len(pairs)} pairs — {conflicts} contractual conflict{'s' if conflicts != 1 else ''} detected",
                        "elapsed": elapsed(), "done": False})
        except Exception as e:
            yield _sse({"stage": "error", "label": "Analysis Failed",
                        "detail": str(e), "elapsed": elapsed(), "done": True})
            return

        # ── Stage 7: Statutory Check ─────────────────────────────────────────
        try:
            statutory = analyse_statutory(clauses, jurisdiction)
            findings.extend(statutory)
            validate_findings(findings, clauses)
            stat_labels = list({f.relation_type for f in statutory})
            stat_str = ", ".join(stat_labels) if stat_labels else "none"
            yield _sse({"stage": "statutory", "label": "Indian Statutory Audit",
                        "detail": f"{len(statutory)} statutory flag{'s' if len(statutory) != 1 else ''} raised ({stat_str}) — ICA 1872, DPDPA 2023, BNS 2023",
                        "elapsed": elapsed(), "done": False})
        except Exception as e:
            yield _sse({"stage": "error", "label": "Statutory Check Failed",
                        "detail": str(e), "elapsed": elapsed(), "done": True})
            return

        # ── Stage 8: Persist to SQLite ───────────────────────────────────────
        try:
            findings.sort(key=lambda f: ({"high": 0, "medium": 1, "low": 2}.get(f.severity, 3), -f.risk_score))

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO contracts (id, title, category, jurisdiction, description) VALUES (?,?,?,?,?);",
                (contract_id, title, "Live Upload / Panel Demo", jurisdiction,
                 f"Live-analysed agreement: {len(clauses)} clauses, {len(findings)} findings."),
            )

            LABEL_TO_TAG = {
                "indemnification": "Indemnity", "liability_limitation": "Liability",
                "termination": "Term", "survival": "Survival", "confidentiality": "IP",
                "governing_law": "Governing Law", "assignment": "General",
                "warranty": "Risk", "non_compete": "High Risk",
                "data_protection": "Compliance", "dispute_resolution": "Dispute",
                "payment": "Payment",
            }
            for cl in clauses:
                tag = LABEL_TO_TAG.get((cl.labels[0]["label"] if cl.labels else ""), "General")
                cursor.execute(
                    "INSERT INTO clauses (id, contract_id, clause_num, title, tag, text, ordinal) VALUES (?,?,?,?,?,?,?);",
                    (cl.id, contract_id, cl.number or str(cl.ordinal),
                     (cl.heading or f"Clause {cl.number or cl.ordinal}")[:80],
                     tag, cl.text[:2000], cl.ordinal),
                )

            SMAP = {"high": "#ef4444", "medium": "#f59e0b", "low": "#10b981"}
            TMAP = {"conflict": "conflict", "dependency": "xref",
                    "overlap": "semantic", "ambiguity": "semantic"}
            for f in findings:
                if not f.related_clause_ids:
                    continue
                tgt = f.related_clause_ids[0]
                cursor.execute(
                    "INSERT INTO graph_edges (contract_id, source_clause_id, target_clause_id, label, relation_type, severity, color, width, dashes) VALUES (?,?,?,?,?,?,?,?,?);",
                    (contract_id, f.target_clause_id, tgt,
                     f.relation_type.upper().replace("_", " "),
                     TMAP.get(f.relation_type, "semantic"),
                     f.severity, SMAP.get(f.severity, "#64748b"), 2.0, 0),
                )
                statute = "; ".join(r.get("text", "") for r in f.refs) if f.refs else "Indian Contract Act, 1872"
                cursor.execute(
                    "INSERT INTO findings (id, contract_id, title, severity, relation_type, source_clause_ref, target_clause_ref, description, statute_citation, remedy_suggestion) VALUES (?,?,?,?,?,?,?,?,?,?);",
                    (f.id, contract_id,
                     f.relation_type.replace("_", " ").title()[:120],
                     f.severity, f.relation_type,
                     f.target_clause_id, tgt,
                     f.rationale[:600], statute[:400], f.rationale[:300]),
                )

            conn.commit()
            conn.close()
            Path(tmp_path).unlink(missing_ok=True)

            yield _sse({"stage": "persisted", "label": "Graph Saved",
                        "detail": f"Persisted {len(clauses)} clause nodes + {len(findings)} finding edges to SQLite",
                        "elapsed": elapsed(), "done": False})

        except Exception as e:
            yield _sse({"stage": "error", "label": "Database Error",
                        "detail": str(e), "elapsed": elapsed(), "done": True})
            return

        # ── Stage 9: Complete ────────────────────────────────────────────────
        high = sum(1 for f in findings if f.severity in ("high", "statutory"))
        yield _sse({
            "stage": "complete", "label": "Analysis Complete",
            "detail": (
                f"{len(clauses)} clauses · {len(findings)} total findings "
                f"({high} critical) · {len(pairs)} pairs examined"
            ),
            "elapsed": elapsed(), "done": True,
            "contract_id": contract_id,
            "stats": {
                "clauses": len(clauses),
                "findings": len(findings),
                "critical": high,
                "pairs": len(pairs),
            }
        })

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@app.get("/api/export/{contract_id}")
def export_audit_memo(contract_id: str):
    """Generates an executive legal risk memo in Markdown."""
    data = fetch_contract_graph_json(contract_id)
    if not data or not data.get("contract"):
        raise HTTPException(status_code=404, detail="Contract not found")

    c = data["contract"]
    findings = data.get("findings", [])

    memo = f"# LEGAL RISK AUDIT MEMO: {c['title'].upper()}\n\n"
    memo += f"**Jurisdiction:** {c['jurisdiction']}\n"
    memo += f"**Category:** {c['category']}\n"
    memo += f"**Evaluation Date:** {Path(DB_PATH).stat().st_mtime}\n"
    memo += f"**Engine:** LegalAgent Cross-Clause GraphRAG (InLegal-SBERT + SQLite3)\n\n"
    memo += "---\n\n"
    memo += "## Executive Summary\n\n"
    memo += f"Analysis of **{len(data['clauses'])} clauses** surfaced **{len(findings)} cross-clause risks** and statutory compliance red flags.\n\n"

    for idx, f in enumerate(findings, 1):
        memo += f"### {idx}. [{f['severity'].upper()}] {f['title']}\n"
        memo += f"- **Target Provisions:** `{f['source_clause_ref']}` vs `{f['target_clause_ref']}`\n"
        memo += f"- **Relation Type:** `{f['relation_type']}`\n"
        memo += f"- **Risk Rationale:** {f['description']}\n"
        memo += f"- **Statutory Authority:** {f['statute_citation']}\n"
        memo += f"- **Recommended Redline:** *{f['remedy_suggestion']}*\n\n"

    return JSONResponse(content={"markdown": memo, "filename": f"LegalAgent_Memo_{contract_id}.md"})


# Serve landing page, app, and adversarial injections explainer
@app.get("/")
def serve_landing():
    return FileResponse(STATIC_DIR / "landing.html")


@app.get("/app")
def serve_app():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/injections")
def serve_injections():
    return FileResponse(STATIC_DIR / "injections.html")


if __name__ == "__main__":
    import uvicorn
    print("\n" + "="*65)
    print(" [START] Launching LegalAgent FastAPI Full-Stack Engine")
    print(" [URL] Server URL    : http://localhost:8080")
    print(" [DOCS] Swagger Docs  : http://localhost:8080/docs")
    print(" [DB] SQLite Engine : contracts.db")
    print("="*65 + "\n")
    uvicorn.run("web.backend:app", host="0.0.0.0", port=8080, reload=False)

