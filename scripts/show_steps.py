#!/bin/sh
''''exec "$(dirname "$0")/../venv/bin/python" "$0" "$@" #'''
"""
Backend walk-through for the panel: runs the pipeline ONE STAGE AT A TIME on a contract and prints
everything each stage produced, as tables (terminal, via rich). Press Enter to go to the next stage.

    ./scripts/show_steps.py                                   # Supreme Court casebook, everything shown
    ./scripts/show_steps.py data/demo/generated/pune_metro_15_planted_clean.md
    ./scripts/show_steps.py <file> --rows 15 --pairs 20       # limit table rows / judged pairs (0 = all)
    ./scripts/show_steps.py --no-pause                        # run straight through

Stages: 1 ingest · 2 extract · 3 classify (+chart) · 4 shortlist · 5 Kev pair judge (+chart) ·
        6 Kev clause-vs-law (+chart) · 7 statute RAG · 8 result
Charts open in a window when a display is available and are saved to logs/steps_plots/ (--no-plots to skip).
Everything printed is also saved to logs/steps_<file>.html (open it in a browser afterwards).
Needs the Kev server on :8008 for stages 5-7 (bash scripts/start_demo.sh); otherwise those parts are skipped.
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

con = Console(record=True, width=180)


def flat(s):
    return " ".join((s or "").split())


def first(seq, n):
    return seq if not n or n <= 0 else seq[:n]


def stage(n, title, what, args):
    if n > 1 and args.pause:
        con.input("\n[dim]Enter → next stage[/dim] ")
    con.rule(f"[bold]Stage {n} · {title}")
    con.print(f"[dim]{what}[/dim]\n")


def pct(p):
    return f"{float(p):.2f}"


PLOTS = []


def chart(name, draw, args):
    """Draw a matplotlib chart, save it to logs/steps_plots/, and show it in a window when a display is available."""
    if not args.plots:
        return
    try:
        import matplotlib
        if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(10, 5.5))
        draw(ax)
        fig.tight_layout()
        out = ROOT / "logs" / "steps_plots" / f"{name}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out, dpi=130)
        PLOTS.append(out)
        con.print(f"[dim]chart → {out}[/dim]")
        if matplotlib.get_backend().lower() != "agg":
            plt.show(block=False)
            plt.pause(0.3)
    except Exception as exc:   # charts are a bonus; never break the walk-through
        con.print(f"[dim]chart skipped ({exc})[/dim]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", default=str(ROOT / "data/demo/generated/supreme_court_casebook.md"),
                    help="contract file (default: the Supreme Court casebook)")
    ap.add_argument("--rows", type=int, default=0, help="rows shown per table (0 = all)")
    ap.add_argument("--pairs", type=int, default=0, help="pairs sent to Kev in stage 5 (0 = all shortlisted)")
    ap.add_argument("--no-pause", dest="pause", action="store_false")
    ap.add_argument("--no-plots", dest="plots", action="store_false", help="skip the matplotlib charts")
    args = ap.parse_args()
    path = Path(args.file)
    if not path.exists() and (ROOT / args.file).exists():   # allow repo-relative paths from any folder
        path = ROOT / args.file
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
    con.print(Panel(flat(text)[:1500] + (" …" if len(text) > 1500 else ""), title="start of the extracted text", border_style="dim"))

    # 2 ── extraction
    stage(2, "Extraction (text → clauses)", "numbering patterns, TOC filter, ARTICLE/SCHEDULE parts, parent links, cross-references (xref = one clause names another)", args)
    from legalagent.core.extraction import extract
    clauses = extract(text, cid)
    xr = sum(1 for c in clauses for x in c.xrefs if x.get("resolved"))
    con.print(f"[bold]{len(clauses)}[/bold] clauses · [bold]{len({c.part for c in clauses if c.part})}[/bold] parts · "
              f"[bold]{xr}[/bold] resolved cross-references\n")
    tb = Table(box=box.SIMPLE_HEAVY, show_lines=True)
    tb.add_column("#", justify="right"); tb.add_column("clause"); tb.add_column("part", max_width=34, overflow="fold")
    tb.add_column("parent"); tb.add_column("cross-refs →"); tb.add_column("text", overflow="fold", ratio=1)
    for i, c in enumerate(first(clauses, args.rows), 1):
        tb.add_row(str(i), c.number or "", flat(c.part), (c.parent_id or "").split("::")[-1],
                   ", ".join(x["clause_id"].split("::")[-1] for x in c.xrefs if x.get("resolved") and x.get("clause_id")),
                   flat(c.text))
    con.print(tb)

    # 3 ── classification
    stage(3, "Classification (CLAUSE-22)", "fine-tuned InLegalBERT (multi-label, threshold 0.5) + keyword backstop + heading prior + 7 Indian rule labels", args)
    import yaml
    spec = yaml.safe_load((ROOT / "clause20" / "labels.yaml").read_text(encoding="utf-8"))
    trained = [l for l in spec["labels"] if l != "other"]
    lt = Table(title="All labels a clause can get", box=box.SIMPLE_HEAVY, show_lines=False)
    lt.add_column(f"22 trained types (InLegalBERT) + other", overflow="fold", ratio=2)
    lt.add_column("7 rule-based Indian labels (keyword rules)", overflow="fold", ratio=1)
    lt.add_row(" · ".join(f"{i}. {l}" for i, l in enumerate(trained, 1)) + " · other",
               " · ".join(spec.get("known_gaps", [])))
    con.print(lt)
    from legalagent.core.classification import available_backend, classify
    backend = available_backend("auto")
    clauses = classify(clauses, backend=backend)
    con.print(f"backend: [bold]{backend}[/bold]\n")
    tb = Table(box=box.SIMPLE_HEAVY, show_lines=True)
    tb.add_column("clause"); tb.add_column("labels (score, source)", overflow="fold", max_width=60); tb.add_column("text", overflow="fold", ratio=1)
    for c in first(clauses, args.rows):
        labs = ", ".join(f"{l['label']} {float(l.get('confidence', l.get('score', 0))):.2f}"
                         + (f" [{l['source']}]" if l.get("source") and l.get("source") != backend else "") for l in c.labels) or "— (no label above 0.5)"
        tb.add_row(c.number or "", labs, flat(c.text))
    con.print(tb)
    dist = Counter(l["label"] for c in clauses for l in c.labels)
    tb = Table(title="label distribution in this contract", box=box.MINIMAL)
    tb.add_column("label"); tb.add_column("clauses", justify="right")
    for k, v in dist.most_common():
        tb.add_row(k, str(v))
    con.print(tb)

    def _labels(ax):
        items = dist.most_common()[::-1]
        ax.barh([k for k, _ in items], [v for _, v in items], color="#2f4fd8")
        ax.set_xlabel("clauses"); ax.set_title(f"Clause types predicted in {path.name} (InLegalBERT + rules)")
        for i, (_, v) in enumerate(items):
            ax.text(v, i, f" {v}", va="center")
    chart("3_clause_types", _labels, args)

    # 4 ── shortlist
    stage(4, "Shortlisting clause pairs", "xref (cross-reference) + type_matrix (40 clause-type clash pairs, weight) + hybrid (BM25 keywords + dense semantic search, RRF)", args)
    from legalagent.core.candidate_selection import select_candidates, TYPE_MATRIX
    from legalagent.core.retrieval import index_text, _dense_matrix, DEFAULT_MODEL
    total = len(clauses) * (len(clauses) - 1) // 2
    pairs = select_candidates(clauses, {"retrieval_method": "hybrid", "top_k": 5, "max_candidates": 60})
    by = {c.id: c for c in clauses}
    pos = {c.id: i for i, c in enumerate(clauses)}
    sim = _dense_matrix([index_text(c) for c in clauses], DEFAULT_MODEL)   # cosine similarity of every clause pair
    sig = Counter(s for _, _, ss in pairs for s in ss)
    con.print(f"all possible pairs: [bold]{total:,}[/bold] → shortlisted: [bold]{len(pairs)}[/bold]   signals: {dict(sig)}\n")

    def clash(a, b):
        la, lb = [l["label"] for l in by[a].labels], [l["label"] for l in by[b].labels]
        return max([TYPE_MATRIX.get((x, y), TYPE_MATRIX.get((y, x), 0.0)) for x in la for y in lb] or [0.0])

    tb = Table(box=box.SIMPLE_HEAVY)
    for c in ("A", "B", "why paired", "clash weight", "semantic similarity", "A types", "B types"):
        tb.add_column(c, overflow="fold")
    for a, b, ss in first(pairs, args.rows):
        tb.add_row(by[a].number, by[b].number, ", ".join(ss), f"{clash(a, b):.2f}", f"{float(sim[pos[a], pos[b]]):.2f}",
                   ", ".join(l["label"] for l in by[a].labels), ", ".join(l["label"] for l in by[b].labels))
    con.print(tb)
    con.print("[dim]clash weight = how risky this combination of clause types usually is (type matrix); "
              "semantic similarity = cosine of the two clauses' meaning vectors (MiniLM). A pair can come from several signals.[/dim]")

    # 5 ── Kev pair judge
    stage(5, "Pair judge (Kev-0.8B, local GPU)", "for each pair Kev answers: relation (choice), severity (score), statute (choice among 4 RETRIEVED India Code sections, or none)", args)
    from legalagent.core import local_judge as lj
    flagged = []
    kev_up = lj.available()
    if not kev_up:
        con.print("[yellow]Kev server not running on :8008 — start it with: bash scripts/start_demo.sh[/yellow]")
    else:
        tau = lj.threshold()
        tb = Table(box=box.SIMPLE_HEAVY)
        for c in ("A", "B", "P(no_issue)", "P(conflict)", "P(dependency)", "P(overlap)", "P(ambiguity)", "decision", "severity", "statute Kev chose (from retrieved)", "ms"):
            tb.add_column(c, overflow="fold")
        judged = []
        for a, b, ss in first(pairs, args.pairs):
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
                       f"[{style}]{dec}[/{style}]", sev, st_choice, str(ms))
            if dec != "no_issue":
                flagged.append((A, B))
        con.print(tb)
        con.print(f"decision rule: {'argmax (highest probability wins)' if tau is None else f'flag if P(no_issue) < τ={tau}'} · "
                  f"{len(judged)} pairs judged, {len(flagged)} flagged")

        def _pairs(ax):
            rows = sorted(judged, key=lambda x: x[0])[:15][::-1]
            names = [f"{A.number} ↔ {B.number}" for _, A, B, *_ in rows]
            left = [0.0] * len(rows)
            colors = {"conflict": "#c2342b", "dependency": "#a15c00", "overlap": "#7a2e86", "ambiguity": "#2f4fd8", "no_issue": "#b8bfcc"}
            for rel, col in colors.items():
                vals = [float(r[3].get(rel, 0)) for r in rows]
                ax.barh(names, vals, left=left, color=col, label=rel)
                left = [l + v for l, v in zip(left, vals)]
            ax.set_xlim(0, 1); ax.set_xlabel("Kev probability"); ax.legend(loc="lower right", fontsize=8)
            ax.set_title("Kev's answer per clause pair (15 most risky pairs)")
        chart("5_kev_pair_probabilities", _pairs, args)

    # 6 ── clause vs Indian law (Kev, categories)
    stage(6, "Clause vs Indian law: Kev's risk check", "regex rules vs Kev single-clause check (7 risk categories → Act + section); P(risk) = 1 − P(none); confidence high ≥0.70, medium ≥0.45", args)
    from legalagent.core.analysis import analyse_statutory
    from legalagent.core import statutory_kev as sk
    regex_hits = {f.target_clause_id for f in analyse_statutory(clauses, "India")}
    law_rows = []
    if kev_up:
        cands = [c for c in clauses if ({l["label"] for l in c.labels} or {"other"}) & sk.RISK_TYPES]
        tb = Table(box=box.SIMPLE_HEAVY, show_lines=True)
        tb.add_column("clause"); tb.add_column("regex"); tb.add_column("P(risk)"); tb.add_column("risk type")
        tb.add_column("law", overflow="fold", max_width=30); tb.add_column("confidence"); tb.add_column("text", overflow="fold", ratio=1)
        for c in cands:
            p = sk.assess(c.text)["probabilities"]
            top = max((k for k in p if k != "none"), key=lambda k: float(p[k]))
            law_rows.append((1 - float(p.get("none", 0)), c, top))
        for risk, c, top in first(sorted(law_rows, key=lambda x: -x[0]), args.rows):   # most risky clauses first
            _, act, sec = sk.CATEGORIES[top]
            conf = sk.confidence_label(risk) if risk >= 0.3 else "—"
            style = {"high": "bold red", "medium": "yellow", "low": "dim"}.get(conf, "dim")
            tb.add_row(c.number, "✓" if c.id in regex_hits else "", pct(risk), top,
                       f"{act.replace('The ', '')}, {sec}" if act else "", f"[{style}]{conf}[/{style}]", flat(c.text))
        con.print(tb)

        def _law(ax):
            rows = sorted(law_rows, key=lambda x: x[0])
            names = [f"{c.number} · {top}" for _, c, top in rows]
            vals = [r for r, _, _ in rows]
            cols = ["#c2342b" if v >= 0.7 else "#d98c00" if v >= 0.45 else "#9aa4bd" for v in vals]
            ax.barh(names, vals, color=cols)
            for x, lab in ((0.45, "medium"), (0.7, "high")):
                ax.axvline(x, color="#5b6478", linestyle="--", linewidth=0.8); ax.text(x, len(rows) - 0.5, f" {lab}", fontsize=8)
            ax.set_xlim(0, 1); ax.set_xlabel("P(risk) = 1 − P(none)")
            ax.set_title("Kev's Indian-law risk per clause (red = high, amber = medium confidence)")
        chart("6_kev_law_risk", _law, args)
    else:
        con.print(f"regex rules flagged {len(regex_hits)} clauses; Kev check skipped (server not running)")

    # 7 ── statute RAG for the flagged clauses
    stage(7, "Statute grounding (RAG over India Code)",
          "for every clause flagged in stage 6 (P(risk) ≥ 0.45): the section its risk category maps to, plus the top India Code sections "
          "retrieved by BM25 + fine-tuned InLegal-SBERT (RRF, Act prior). Every citation is checked to exist; the text is shown as evidence", args)
    from legalagent.core.statutes import retrieve_sections, retrieval_confidence, verify_citation
    to_check = [(risk, c, top) for risk, c, top in sorted(law_rows, key=lambda x: -x[0]) if risk >= 0.45]
    if not to_check:
        to_check = [(0.0, c, "") for c in clauses if c.id in regex_hits] or [(0.0, clauses[0], "")]
    for risk, c, top in first(to_check, args.rows):
        mapped = ""
        if top:
            _, act, sec = sk.CATEGORIES[top]
            v = verify_citation(f"{act}, {sec}") if act else None
            mapped = f"{act.replace('The ', '')}, {sec}" + (" (verified in India Code)" if v else "") if act else ""
        tb = Table(title=f"clause {c.number}: {flat(c.text)}", title_justify="left", box=box.SIMPLE_HEAVY)
        for col in ("rank", "retrieved section", "heading", "retrieval score", "confidence"):
            tb.add_column(col, overflow="fold")
        for i, (s, sc) in enumerate(retrieve_sections(c.text[:900], k=4)):
            tb.add_row(str(i + 1), f"{s['act'].replace('The ', '')}, s.{s['section']}", flat(s["heading"]), f"{sc:.4f}", retrieval_confidence(i, sc))
        if mapped:
            con.print(f"[bold]Kev's risk category:[/bold] {top} (P(risk) {risk:.2f}) → [bold]{mapped}[/bold]")
        con.print(tb)

    # 8 ── summary
    stage(8, "Result", "what goes to the database and the dashboard", args)
    tb = Table(box=box.SIMPLE_HEAVY)
    tb.add_column("stage"); tb.add_column("output", justify="right")
    n_judged = len(first(pairs, args.pairs)) if kev_up else 0
    for k, v in [("clauses", len(clauses)), ("possible pairs", f"{total:,}"), ("shortlisted pairs", len(pairs)),
                 ("pairs judged by Kev", n_judged), ("pairs Kev flagged", len(flagged)),
                 ("regex statutory flags", len(regex_hits)),
                 ("clauses Kev flagged vs Indian law (P(risk) ≥ 0.45)", sum(1 for r in law_rows if r[0] >= 0.45))]:
        tb.add_row(k, str(v))
    con.print(tb)
    con.print("Full run of this contract: dashboard → Upload & analyse, or scripts/seed_demo.py")

    out = ROOT / "logs" / f"steps_{path.stem}.html"
    out.parent.mkdir(exist_ok=True)
    con.save_html(str(out))
    con.print(f"\n[dim]saved → {out}[/dim]")


if __name__ == "__main__":
    main()
