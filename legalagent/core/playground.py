"""
Playground: run EVERY method in LegalAgent on one pair of clauses and return all raw outputs.

Used by the dashboard (POST /api/playground) and the CLI (scripts/playground.py), so the
viva can show exactly what each component computes behind the scenes:

  classifiers   fine-tuned InLegalBERT vs MiniLM+LogReg: per-label probabilities
  similarity    BM25 (pair-local), MiniLM / InLegal-SBERT (base, fine-tuned) cosine, type-matrix weight
  judges        rules · Kev base (zero-shot, :8009) · Kev fine-tuned (:8008) · Gemini (opt-in)
  gnn           GraphSAGE risk probability on the 2-clause graph
  statutes      India Code sections retrieved for the pair, with BM25 / dense / fused scores
"""
import os
import time

from legalagent.core.types import Clause

KEV_FT_URL = os.environ.get("KEV_URL", "http://127.0.0.1:8008/v1/systemone")
KEV_BASE_URL = os.environ.get("KEV_BASE_URL", "http://127.0.0.1:8009/v1/systemone")


def _clause(tag: str, text: str) -> Clause:
    text = text.strip()
    first = text.split()[0] if text.split() else tag
    number = first.rstrip(".") if first[:1].isdigit() else tag
    return Clause(id=f"pg::{number}::{tag}", contract_id="pg", number=number, text=text)


def _probs(texts, backend):
    from legalagent.core.classification import predict_proba, _strip_number
    try:
        labels, P = predict_proba([_strip_number(t) for t in texts], backend)
    except Exception as exc:
        return {"error": str(exc)}
    out = []
    for row in P:
        top = sorted(zip(labels, row.tolist()), key=lambda x: -x[1])[:5]
        out.append([{"label": l, "p": round(p, 4)} for l, p in top])
    return out


def _kev(url, a, b, sections):
    from legalagent.core import local_judge
    old = local_judge.KEV_URL
    local_judge.KEV_URL = url
    try:
        if not local_judge.available():
            return {"available": False}
        t = time.perf_counter()
        resp = local_judge._post(local_judge.pair_request(a, b, ["playground"], sections))
        ans = resp["answers"]
        return {"available": True, "relation": ans["relation"]["choice"], "relation_probs": ans["relation"]["probabilities"],
                "severity_probs": ans["severity"]["probabilities"], "statute": ans.get("statute", {}).get("choice"),
                "statute_probs": ans.get("statute", {}).get("probabilities"), "ms": round(1000 * (time.perf_counter() - t), 1)}
    except Exception as exc:
        return {"available": True, "error": str(exc)}
    finally:
        local_judge.KEV_URL = old


def compare_pair(text_a: str, text_b: str, use_gemini: bool = False) -> dict:
    import numpy as np
    from legalagent.core.classification import classify, available_backend
    from legalagent.core.retrieval import index_text, _dense_matrix, DEFAULT_MODEL
    from legalagent.core.candidate_selection import TYPE_MATRIX
    from legalagent.core.analysis import analyse_pair, analyse_statutory
    from pathlib import Path

    t0 = time.perf_counter()
    a, b = _clause("A", text_a), _clause("B", text_b)
    a.xrefs = [{"raw": "", "clause_id": b.id, "resolved": True}] if b.number in text_a and b.number != "B" else []
    b.xrefs = [{"raw": "", "clause_id": a.id, "resolved": True}] if a.number in text_b and a.number != "A" else []
    out = {"clauses": {"A": text_a, "B": text_b}}

    # 1. classifiers
    out["classifiers"] = {"minilm_lr": _probs([a.text, b.text], "minilm_lr")}
    if available_backend("auto") == "inlegalbert":
        out["classifiers"]["inlegalbert"] = _probs([a.text, b.text], "inlegalbert")
    classify([a, b], backend="auto")
    out["labels"] = {"A": a.labels, "B": b.labels}

    # 2. similarity
    ta, tb = index_text(a), index_text(b)
    # BM25 needs a corpus for its IDF (with two documents it goes negative); inside a contract the
    # pipeline ranks against all clauses. For a lone pair we show plain lexical overlap instead.
    import re as _re
    wa, wb = set(_re.findall(r"[a-z]{3,}", ta.lower())), set(_re.findall(r"[a-z]{3,}", tb.lower()))
    sim = {"lexical_jaccard": round(len(wa & wb) / max(1, len(wa | wb)), 4)}
    models = {"minilm": DEFAULT_MODEL, "inlegal_sbert": "bhavyagiri/InLegal-Sbert"}
    ft = Path(__file__).resolve().parents[2] / "models" / "inlegal_sbert_clauses"
    if (ft / "config.json").exists():
        models["inlegal_sbert_ft"] = str(ft)
    for name, m in models.items():
        try:
            sim[f"cos_{name}"] = round(float(_dense_matrix([ta, tb], m)[0, 1]), 4)
        except Exception as exc:
            sim[f"cos_{name}"] = f"error: {exc}"
    la, lb = [l["label"] for l in a.labels], [l["label"] for l in b.labels]
    sim["type_matrix_weight"] = max([TYPE_MATRIX.get((x, y), TYPE_MATRIX.get((y, x), 0.0)) for x in la for y in lb] or [0.0])
    sim["cross_reference"] = bool(a.xrefs or b.xrefs)
    out["similarity"] = sim

    # 3. statutes (RAG) — also the options Kev chooses from
    try:
        from legalagent.core.statutes import explain_sections
        st = explain_sections(f"{a.text[:600]} {b.text[:600]}", k=4)
        out["statutes"] = st
        from legalagent.core.statutes import load_library
        lib = {(s["act"], s["section"]): s for s in load_library()}
        sections = [lib[(s["act"], s["section"])] for s in st if (s["act"], s["section"]) in lib]
    except Exception as exc:
        out["statutes"], sections = {"error": str(exc)}, []

    # 4. judges
    surfaced = ["xref"] if sim["cross_reference"] else ["playground"]
    f = analyse_pair(a, b, surfaced)
    stat = analyse_statutory([a, b], "India")
    out["judges"] = {
        "rules": {"relation": f.relation_type if f else "no_issue", "severity": f.severity if f else None,
                  "rationale": f.rationale if f else "", "statutory_flags": [s.rationale for s in stat]},
    }
    # Name the :8008 judge by what start_demo.sh actually serves (results/judge_selection.json);
    # the :8009 comparison server is shown only when it is running.
    served = "kev_base_zero_shot"
    try:
        import json as _json
        served = _json.loads((Path(__file__).resolve().parents[2] / "results" / "judge_selection.json").read_text()).get("judge", served)
    except Exception:
        pass
    main_name = "kev_base (served, zero-shot)" if "base" in served else "kev_finetuned (served)"
    out["judges"][main_name] = _kev(KEV_FT_URL, a, b, sections)
    other = _kev(KEV_BASE_URL, a, b, sections)
    if other.get("available"):
        out["judges"]["kev (comparison server :8009)"] = other
    if use_gemini:
        try:
            from legalagent.core.gemini_analysis import analyse_pairs_with_gemini
            g = analyse_pairs_with_gemini([(a, b, surfaced)])[0]
            out["judges"]["gemini"] = {"relation": g.relation_type if g else "no_issue", "severity": g.severity if g else None,
                                       "rationale": g.rationale if g else "", "sent_to_cloud": True}
        except Exception as exc:
            out["judges"]["gemini"] = {"error": str(exc)}

    # 5. GNN on the two-clause graph
    try:
        import torch
        from legalagent.core.gnn import _load, build_graph
        model = _load()
        if model is not None:
            cl = [{"id": a.id, "text": a.text, "labels": la, "xrefs": [b.id] if sim["cross_reference"] else []},
                  {"id": b.id, "text": b.text, "labels": lb, "xrefs": []}]
            x, ei, _ = build_graph(cl)
            with torch.no_grad():
                h = model.encode(torch.tensor(x), torch.tensor(ei))
                p = torch.sigmoid(model.score(h, torch.tensor([0]), torch.tensor([1]), torch.tensor([sim["type_matrix_weight"]], dtype=torch.float32)))
            out["gnn"] = {"risk_probability": round(float(p[0]), 4), "note": "2-node graph: less context than inside a full contract"}
        else:
            out["gnn"] = {"available": False}
    except Exception as exc:
        out["gnn"] = {"error": str(exc)}

    out["seconds"] = round(time.perf_counter() - t0, 2)
    return out
