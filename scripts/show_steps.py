"""
Backend walk-through for the panel: runs the pipeline ONE STAGE AT A TIME on a contract and prints
what each stage produced as tables (terminal, via rich). Press Enter to go to the next stage.

    venv/bin/python scripts/show_steps.py data/demo/generated/supreme_court_casebook.md
    venv/bin/python scripts/show_steps.py data/demo/samples/02_pune_metro_adversarial_15_injections.md --no-pause
    venv/bin/python scripts/show_steps.py <file> --rows 15 --pairs 8

Everything printed is also saved to logs/steps_<file>.html (open it in a browser afterwards).
Needs the Kev server on :8008 for stages 5-6 (bash scripts/start_demo.sh); otherwise they are skipped.
"""
import argparse
import os
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("LEGALAGENT_DEVICE", "cpu")   # the GPU belongs to Kev

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

con = Console(record=True, width=170)


def short(s, n=90):
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1] + "…"


def stage(n, title, what, args):
    if n > 1 and args.pause:
        con.input("\n[dim]Enter → next stage[/dim] ")
    con.rule(f"[bold]Stage {n} · {title}")
    con.print(f"[dim]{what}[/dim]\n")


def pct(p):
    return f"{float(p):.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--rows", type=int, default=20, help="rows shown per table")
    ap.add_argument("--pairs", type=int, default=10, help="pairs sent to Kev in stage 5")
    ap.add_argument("--no-pause", dest="pause", action="store_false")
    args = ap.parse_args()
    path = Path(args.file)
    cid = path.stem[:24]

    con.print(Panel.fit(f"[bold]LegalAgent — pipeline, stage by stage[/bold]\n{path}", border_style="blue"))

    # 1 ── ingestion
    stage(1, "Ingestion (file → text)", "pymupdf4llm for digital pages, Tesseract OCR (parallel, cached) for scanned pages", args)
    from legalagent.core.ingestion import ingest_with_stats
    t = time.time()
    text, st = ingest_with_stats(str(path))
    tb = Table(box=box.SIMPLE_HEAVY)
    for c in ("file", "type", "pages", "OCR pages", "from cache", "characters", "seconds"):
        tb.add_column(c)
    tb.add_row(path.name, path.suffix, str(st.get("pages", 1)), str(st.get("ocr_pages", 0)),
               str(st.get("cached", False)), f"{len(text):,}", f"{time.time() - t:.1f}")
    con.print(tb)
    con.print(Panel(short(text, 700), title="first characters of the text", border_style="dim"))

    # 2 ── extraction
    stage(2, "Extraction (text → clauses)", "numbering patterns, TOC filter, ARTICLE/SCHEDULE parts, parent links, cross-references", args)
    from legalagent.core.extraction import extract
    clauses = extract(text, cid)
    xr = sum(1 for c in clauses for x in c.xrefs if x.get("resolved"))
    con.print(f"[bold]{len(clauses)}[/bold] clauses · [bold]{len({c.part for c in clauses if c.part})}[/bold] parts · "
              f"[bold]{xr}[/bold] resolved cross-references\n")
    tb = Table(box=box.SIMPLE_HEAVY)
    for c in ("#", "clause", "part", "parent", "cross-refs →", "text"):
        tb.add_column(c, overflow="fold")
    for i, c in enumerate(clauses[: args.rows], 1):
        tb.add_row(str(i), c.number or "", short(c.part, 28), (c.parent_id or "").split("::")[-1],
                   ", ".join(x["clause_id"].split("::")[-1] for x in c.xrefs if x.get("resolved") and x.get("clause_id")),
                   short(c.text, 70))
    con.print(tb)

    # 3 ── classification
    stage(3, "Classification (CLAUSE-22)", "fine-tuned InLegalBERT (multi-label) + keyword backstop + heading prior + Indian rule labels", args)
    from legalagent.core.classification import available_backend, classify
    backend = available_backend("auto")
    clauses = classify(clauses, backend=backend)
    con.print(f"backend: [bold]{backend}[/bold]\n")
    tb = Table(box=box.SIMPLE_HEAVY)
    for c in ("clause", "labels (score)", "text"):
        tb.add_column(c, overflow="fold")
    for c in clauses[: args.rows]:
        tb.add_row(c.number or "", ", ".join(f"{l['label']} ({float(l.get('confidence', l.get('score', 0))):.2f})" for l in c.labels[:3]),
                   short(c.text, 70))
    con.print(tb)
    dist = Counter(l["label"] for c in clauses for l in c.labels)
    tb = Table(title="label distribution", box=box.MINIMAL)
    tb.add_column("label"); tb.add_column("clauses", justify="right")
    for k, v in dist.most_common(10):
        tb.add_row(k, str(v))
    con.print(tb)

    # 4 ── shortlist
    stage(4, "Shortlisting clause pairs", "cross-references + 40-pair clause-type clash matrix + hybrid BM25/dense retrieval (RRF)", args)
    from legalagent.core.candidate_selection import select_candidates
    total = len(clauses) * (len(clauses) - 1) // 2
    pairs = select_candidates(clauses, {"retrieval_method": "hybrid", "top_k": 5, "max_candidates": 60})
    by = {c.id: c for c in clauses}
    sig = Counter(s for _, _, ss in pairs for s in ss)
    con.print(f"all possible pairs: [bold]{total:,}[/bold] → shortlisted: [bold]{len(pairs)}[/bold]   "
              f"signals: {dict(sig)}\n")
    tb = Table(box=box.SIMPLE_HEAVY)
    for c in ("A", "B", "why paired", "A types", "B types"):
        tb.add_column(c, overflow="fold")
    for a, b, ss in pairs[: args.rows]:
        tb.add_row(by[a].number, by[b].number, ", ".join(ss),
                   ", ".join(l["label"] for l in by[a].labels[:2]), ", ".join(l["label"] for l in by[b].labels[:2]))
    con.print(tb)

    # 5 ── Kev pair judge
    stage(5, "Pair judge (Kev-0.8B, local GPU)", "for each pair Kev answers: relation (choice), severity (score), statute (choice of 4 retrieved sections)", args)
    from legalagent.core import local_judge as lj
    flagged = []
    if not lj.available():
        con.print("[yellow]Kev server not running on :8008 — start it with: bash scripts/start_demo.sh[/yellow]")
    else:
        tau = lj.threshold()
        tb = Table(box=box.SIMPLE_HEAVY)
        for c in ("A", "B", "P(no_issue)", "P(conflict)", "P(dependency)", "P(overlap)", "P(ambiguity)", "decision", "severity", "statute chosen", "ms"):
            tb.add_column(c, overflow="fold")
        judged = []
        for a, b, ss in pairs[: args.pairs]:
            A, B = by[a], by[b]
            secs = lj.statute_options(A, B)
            r = lj._post(lj.pair_request(A, B, ss, secs))
            ans = r["answers"]; rp = ans["relation"]["probabilities"]
            dec = lj.decide(rp, tau)
            sp = ans["severity"]["probabilities"]
            sev = lj.SEVERITIES[max(range(3), key=lambda i: float(sp[str(i)]))]
            judged.append((float(rp.get("no_issue", 0)), A, B, rp, dec, sev, ans.get("statute", {}).get("choice", ""), r.get("latency_ms", "")))
        for _, A, B, rp, dec, sev, st_choice, ms in sorted(judged, key=lambda x: x[0]):   # most risky pairs first
            style = "bold red" if dec != "no_issue" else "dim"
            tb.add_row(A.number, B.number, *(pct(rp.get(k, 0)) for k in ("no_issue", "conflict", "dependency", "overlap", "ambiguity")),
                       f"[{style}]{dec}[/{style}]", sev, short(st_choice, 30), str(ms))
            if dec != "no_issue":
                flagged.append((A, B))
        con.print(tb)
        con.print(f"decision rule: {'argmax' if tau is None else f'flag if P(no_issue) < τ={tau}'}")

    # 6 ── clause vs Indian law
    stage(6, "Clause vs Indian law", "regex rules vs Kev single-clause check (7 risk categories → Act + section); confidence high ≥0.7, medium ≥0.45", args)
    from legalagent.core.analysis import analyse_statutory
    from legalagent.core import statutory_kev as sk
    regex_hits = {f.target_clause_id for f in analyse_statutory(clauses, "India")}
    if lj.available():
        cands = [c for c in clauses if ({l["label"] for l in c.labels} or {"other"}) & sk.RISK_TYPES][: max(args.rows, 30)]
        tb = Table(box=box.SIMPLE_HEAVY)
        # P(risk) = 1 − P(none): how sure Kev is that the clause carries SOME Indian-law risk (the confidence label uses it);
        # "risk type" = the most likely of the 7 categories, mapped to its Act and section.
        for c in ("clause", "regex", "P(risk)", "risk type", "law", "confidence", "text"):
            tb.add_column(c, overflow="fold")
        rows = []
        for c in cands:
            p = sk.assess(c.text)["probabilities"]
            top = max((k for k in p if k != "none"), key=lambda k: float(p[k]))
            rows.append((1 - float(p.get("none", 0)), c, top))
        for risk, c, top in sorted(rows, key=lambda x: -x[0])[: args.rows]:   # most risky clauses first
            _, act, sec = sk.CATEGORIES[top]
            conf = sk.confidence_label(risk) if risk >= 0.3 else "—"
            style = {"high": "bold red", "medium": "yellow", "low": "dim"}.get(conf, "dim")
            tb.add_row(c.number, "✓" if c.id in regex_hits else "", pct(risk), top,
                       f"{act.replace('The ', '')}, {sec}" if act else "", f"[{style}]{conf}[/{style}]", short(c.text, 50))
        con.print(tb)
    else:
        con.print(f"regex rules flagged {len(regex_hits)} clauses; Kev check skipped (server not running)")

    # 7 ── statute RAG
    stage(7, "Statute grounding (RAG over India Code)", "4,408 sections / 37 Acts · BM25 + fine-tuned InLegal-SBERT, fused (RRF) + Act prior · every citation verified", args)
    from legalagent.core.statutes import retrieve_sections, retrieval_confidence
    queries = [(f"{A.number} ↔ {B.number}", f"{A.text[:600]} {B.text[:600]}") for A, B in flagged[:3]]
    if not queries:
        queries = [(c.number, c.text[:900]) for c in clauses if c.id in regex_hits][:3] or [(clauses[0].number, clauses[0].text[:900])]
    for name, q in queries:
        tb = Table(title=f"query: clause {name}", box=box.SIMPLE_HEAVY)
        for c in ("rank", "Act", "section", "heading", "fused score", "confidence"):
            tb.add_column(c, overflow="fold")
        for i, (s, sc) in enumerate(retrieve_sections(q, k=5), 1):
            tb.add_row(str(i), s["act"].replace("The ", ""), str(s["section"]), short(s["heading"], 50), f"{sc:.4f}",
                       retrieval_confidence(i - 1, sc))
        con.print(tb)

    # 8 ── summary
    stage(8, "Result", "what goes to the database and the dashboard", args)
    tb = Table(box=box.SIMPLE_HEAVY)
    tb.add_column("stage"); tb.add_column("output", justify="right")
    for k, v in [("clauses", len(clauses)), ("possible pairs", f"{total:,}"), ("shortlisted pairs", len(pairs)),
                 (f"pairs judged here (of {len(pairs)})", min(args.pairs, len(pairs))), ("flagged by Kev here", len(flagged)),
                 ("regex statutory flags", len(regex_hits))]:
        tb.add_row(k, str(v))
    con.print(tb)
    con.print("Full run of this contract: dashboard → Upload & analyse, or scripts/seed_demo.py")

    out = ROOT / "logs" / f"steps_{path.stem}.html"
    out.parent.mkdir(exist_ok=True)
    con.save_html(str(out))
    con.print(f"\n[dim]saved → {out}[/dim]")


if __name__ == "__main__":
    main()
