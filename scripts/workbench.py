"""
LegalAgent Workbench — a desktop window onto the engine (Tkinter + matplotlib).

    venv/bin/python scripts/workbench.py          # on the laptop's own screen

Tabs
  Playground   paste two clauses → every method's raw output: classifier probabilities,
               BM25 / MiniLM / InLegal-SBERT similarity, type-matrix weight, rules, Kev base vs
               fine-tuned (probability bars), GNN risk, India Code retrieval scores
  Document     PDF/DOCX/TXT → page image, OCR vs native per page, clause tree (parts → clauses),
               then "Analyse" runs the full pipeline (local judge) and lists the findings
  Console      every stage's log line with timings, and the raw JSON of the last result

Same engine as the web dashboard and CLI (legalagent.core.playground / pipeline), so all three agree.
"""
import json
import logging
import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

BG, PANEL, FG, MUTED, ACCENT, RED, GREEN, AMBER = "#0f172a", "#111827", "#e2e8f0", "#94a3b8", "#38bdf8", "#f87171", "#34d399", "#fbbf24"
MONO = ("DejaVu Sans Mono", 10)
DOCS = {
    "Pune Metro + 15 planted irregularities (305 pp, scanned)": "data/demo/india/adversarial/pune_metro_adversarial_15_changes.pdf",
    "Pune Metro concession, signed (300 pp, scanned)": "data/demo/india/official/pune_metro_signed_concession.pdf",
    "NHAI model concession (276 pp, scanned)": "data/demo/india/official/model_concession_4_laning.pdf",
    "Indian tech MSA (PDF, native text)": "data/demo/india/indian_tech_msa_demo.pdf",
    "Pune Metro excerpt with injections (MD)": "data/demo/samples/02_pune_metro_adversarial_15_injections.md",
}


class QueueHandler(logging.Handler):
    def __init__(self, q):
        super().__init__()
        self.q = q

    def emit(self, record):
        self.q.put(("log", f"{time.strftime('%H:%M:%S')} {record.levelname:5s} {record.name}: {record.getMessage()}"))


class Workbench(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LegalAgent Workbench — local engine")
        self.geometry("1500x920")
        self.configure(bg=BG)
        self.q = queue.Queue()
        self._style()
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=6)
        self.tab_play, self.tab_doc, self.tab_con = ttk.Frame(nb), ttk.Frame(nb), ttk.Frame(nb)
        nb.add(self.tab_play, text="  Playground  ")
        nb.add(self.tab_doc, text="  Document → clauses → findings  ")
        nb.add(self.tab_con, text="  Console  ")
        self._build_console()
        self._build_playground()
        self._build_document()
        h = QueueHandler(self.q)
        logging.getLogger().addHandler(h)
        logging.getLogger().setLevel(logging.INFO)
        self.after(100, self._drain)
        self.log("workbench ready — engine: " + str(ROOT))
        threading.Thread(target=self._status, daemon=True).start()

    # ---------------------------------------------------------------- plumbing
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL, font=("DejaVu Sans", 10))
        s.configure("TNotebook.Tab", background=PANEL, foreground=MUTED, padding=(10, 5))
        s.map("TNotebook.Tab", background=[("selected", BG)], foreground=[("selected", ACCENT)])
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=22, font=MONO)
        s.configure("Treeview.Heading", background="#1f2937", foreground=ACCENT, font=("DejaVu Sans", 9, "bold"))
        s.configure("TButton", background="#1f2937", foreground=FG, padding=6)
        s.map("TButton", background=[("active", "#334155")])
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Muted.TLabel", foreground=MUTED)
        s.configure("TCheckbutton", background=BG, foreground=FG)

    def log(self, msg):
        self.q.put(("log", f"{time.strftime('%H:%M:%S')} {msg}"))

    def _drain(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.console.insert("end", payload + "\n")
                    self.console.see("end")
                    self.statusbar.config(text=payload[:180])
                elif kind == "call":
                    payload()
        except queue.Empty:
            pass
        self.after(100, self._drain)

    def ui(self, fn):
        self.q.put(("call", fn))

    def run_bg(self, fn):
        threading.Thread(target=fn, daemon=True).start()

    def _status(self):
        try:
            import torch
            from legalagent.core.classification import available_backend
            from legalagent.core import local_judge
            from legalagent.core.playground import KEV_BASE_URL
            gpu = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "CPU only"
            local_judge.KEV_URL = "http://127.0.0.1:8008/v1/systemone"
            ft = local_judge.available()
            local_judge.KEV_URL = KEV_BASE_URL
            base = local_judge.available()
            local_judge.KEV_URL = "http://127.0.0.1:8008/v1/systemone"
            self.log(f"GPU: {gpu} · classifier: {available_backend('auto')} · Kev judge :8008 {'UP' if ft else 'down'}" + (" · comparison Kev :8009 UP" if base else ""))
        except Exception as exc:
            self.log(f"status check failed: {exc}")

    def _build_console(self):
        self.console = tk.Text(self.tab_con, bg="#020617", fg="#a7f3d0", insertbackground=FG, font=MONO, wrap="word")
        self.console.pack(fill="both", expand=True)
        self.statusbar = tk.Label(self, text="", bg="#020617", fg=MUTED, anchor="w", font=MONO)
        self.statusbar.pack(fill="x", side="bottom")

    def _tree(self, parent, cols, widths, height=8):
        t = ttk.Treeview(parent, columns=cols, show="headings", height=height)
        for c, w in zip(cols, widths):
            t.heading(c, text=c)
            t.column(c, width=w, anchor="w")
        return t

    # ---------------------------------------------------------------- playground
    def _build_playground(self):
        from playground import EXAMPLES
        top = ttk.Frame(self.tab_play)
        top.pack(fill="x", padx=6, pady=4)
        ttk.Label(top, text="Example:").pack(side="left")
        self.ex = ttk.Combobox(top, values=list(EXAMPLES), width=14, state="readonly")
        self.ex.pack(side="left", padx=4)
        self.ex.bind("<<ComboboxSelected>>", lambda e: self._load_example())
        self.gem = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="also ask Gemini (sends text to Google)", variable=self.gem).pack(side="left", padx=12)
        ttk.Button(top, text="▶ Run every method", command=self._run_play).pack(side="left", padx=8)
        ttk.Label(top, text="Kev (served judge) :8008 · local GPU", style="Muted.TLabel").pack(side="right")

        boxes = ttk.Frame(self.tab_play)
        boxes.pack(fill="x", padx=6)
        self.ta = tk.Text(boxes, height=6, bg=PANEL, fg=FG, insertbackground=FG, wrap="word", font=("DejaVu Sans", 10))
        self.tb = tk.Text(boxes, height=6, bg=PANEL, fg=FG, insertbackground=FG, wrap="word", font=("DejaVu Sans", 10))
        self.ta.pack(side="left", fill="both", expand=True, padx=(0, 3))
        self.tb.pack(side="left", fill="both", expand=True, padx=(3, 0))

        body = ttk.Frame(self.tab_play)
        body.pack(fill="both", expand=True, padx=6, pady=4)
        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="Clause types (top probabilities)").pack(anchor="w")
        self.t_cls = self._tree(left, ("model", "clause", "types"), (110, 50, 420), 4)
        self.t_cls.pack(fill="x")
        ttk.Label(left, text="Shortlisting signals").pack(anchor="w", pady=(6, 0))
        self.t_sim = self._tree(left, ("signal", "value"), (230, 350), 7)
        self.t_sim.pack(fill="x")
        ttk.Label(left, text="Judges").pack(anchor="w", pady=(6, 0))
        self.t_jud = self._tree(left, ("judge", "verdict", "detail"), (130, 100, 360), 5)
        self.t_jud.pack(fill="x")
        ttk.Label(left, text="Indian law retrieved (RAG over India Code)").pack(anchor="w", pady=(6, 0))
        self.t_stat = self._tree(left, ("section", "fused", "BM25 #", "dense #"), (380, 70, 60, 60), 4)
        self.t_stat.pack(fill="x")
        self.fig = Figure(figsize=(7.2, 7.4), facecolor=BG)
        self.canvas = FigureCanvasTkAgg(self.fig, master=body)
        self.canvas.get_tk_widget().pack(side="right", fill="both", expand=True)
        self.ex.set("cap")
        self._load_example()

    def _load_example(self):
        from playground import EXAMPLES
        a, b = EXAMPLES[self.ex.get()]
        for box, txt in ((self.ta, a), (self.tb, b)):
            box.delete("1.0", "end")
            box.insert("1.0", txt)

    def _run_play(self):
        a, b, g = self.ta.get("1.0", "end").strip(), self.tb.get("1.0", "end").strip(), self.gem.get()
        self.log(f"playground: running all methods on A[{len(a)} chars] × B[{len(b)} chars]{' + Gemini' if g else ''}")

        def work():
            from legalagent.core.playground import compare_pair
            t = time.time()
            r = compare_pair(a, b, use_gemini=g)
            self.log(f"playground: done in {time.time() - t:.2f}s")
            self.log("RAW " + json.dumps(r, default=str)[:4000])
            self.ui(lambda: self._show_play(r))
        self.run_bg(work)

    def _show_play(self, r):
        for t in (self.t_cls, self.t_sim, self.t_jud, self.t_stat):
            t.delete(*t.get_children())
        for model, rows in r["classifiers"].items():
            if isinstance(rows, list):
                for tag, row in zip("AB", rows):
                    self.t_cls.insert("", "end", values=(model, tag, "  ".join(f"{x['label']} {x['p']:.2f}" for x in row[:4])))
        for k, v in r["similarity"].items():
            self.t_sim.insert("", "end", values=(k, v))
        g = r.get("gnn", {})
        self.t_sim.insert("", "end", values=("gnn_risk_probability", g.get("risk_probability", g)))
        for name, j in r["judges"].items():
            if j.get("available") is False:
                self.t_jud.insert("", "end", values=(name, "—", "server not running"))
            elif "error" in j:
                self.t_jud.insert("", "end", values=(name, "error", j["error"][:80]))
            else:
                det = f"{j.get('ms', '')} ms · statute: {j.get('statute')}" if "relation_probs" in j else (j.get("rationale") or "")[:90]
                self.t_jud.insert("", "end", values=(name, j.get("relation"), det))
        if isinstance(r.get("statutes"), list):
            for s in r["statutes"]:
                self.t_stat.insert("", "end", values=(f"{s['act'].replace('The ', '')} s.{s['section']} {s['heading'][:40]}", s["fused"], s["bm25_rank"], s["dense_rank"]))
        self._plot(r)

    def _plot(self, r):
        self.fig.clear()
        ax1, ax2, ax3 = self.fig.add_subplot(311), self.fig.add_subplot(312), self.fig.add_subplot(313)
        for ax in (ax1, ax2, ax3):
            ax.set_facecolor(PANEL)
            ax.tick_params(colors=MUTED, labelsize=8)
            for sp in ax.spines.values():
                sp.set_color("#334155")
        sim = {k: v for k, v in r["similarity"].items() if isinstance(v, (int, float)) and not isinstance(v, bool) and k != "bm25_a_to_b"}
        if isinstance(r.get("gnn", {}).get("risk_probability"), float):
            sim["gnn_risk"] = r["gnn"]["risk_probability"]
        ax1.bar(list(sim), list(sim.values()), color=[ACCENT, "#a78bfa", GREEN, AMBER, RED][:len(sim)])
        ax1.set_ylim(0, 1)
        ax1.set_title("similarity / risk signals (0–1)", color=FG, fontsize=10)
        ax1.tick_params(axis="x", rotation=12)
        rels = ["conflict", "dependency", "overlap", "ambiguity", "no_issue"]
        judges = [(n, j) for n, j in r["judges"].items() if j.get("relation_probs")]
        w = 0.8 / max(1, len(judges))
        for i, (n, j) in enumerate(judges):
            ax2.bar([x + i * w for x in range(len(rels))], [float(j["relation_probs"].get(rel, 0)) for rel in rels], width=w,
                    label=n, color=[ACCENT, AMBER, GREEN][i % 3])
        ax2.set_xticks([x + w * (len(judges) - 1) / 2 for x in range(len(rels))])
        ax2.set_xticklabels(rels)
        ax2.set_ylim(0, 1)
        ax2.set_title("Kev P(relation): base vs fine-tuned" if judges else "Kev servers not running", color=FG, fontsize=10)
        if judges:
            ax2.legend(fontsize=8, facecolor=PANEL, labelcolor=FG)
        st = r.get("statutes") if isinstance(r.get("statutes"), list) else []
        if st:
            names = [f"{s['act'].replace('The ', '').split(',')[0][:22]} s.{s['section']}" for s in st]
            ax3.barh(names, [s["rrf_bm25"] for s in st], color="#b26b3c", label="BM25")
            ax3.barh(names, [s["rrf_dense"] for s in st], left=[s["rrf_bm25"] for s in st], color="#a78bfa", label="InLegal-SBERT")
            ax3.barh(names, [s["act_prior"] for s in st], left=[s["rrf_bm25"] + s["rrf_dense"] for s in st], color=MUTED, label="Act prior")
            ax3.invert_yaxis()
            ax3.legend(fontsize=7, facecolor=PANEL, labelcolor=FG)
            ax3.set_title("statute retrieval: fused score = Σ 1/(60+rank) + prior", color=FG, fontsize=10)
        self.fig.tight_layout()
        self.canvas.draw()

    # ---------------------------------------------------------------- document
    def _build_document(self):
        top = ttk.Frame(self.tab_doc)
        top.pack(fill="x", padx=6, pady=4)
        self.doc = ttk.Combobox(top, values=list(DOCS), width=58, state="readonly")
        self.doc.pack(side="left")
        self.doc.set(list(DOCS)[0])
        ttk.Button(top, text="Open file…", command=self._open_file).pack(side="left", padx=4)
        ttk.Button(top, text="① Ingest + extract", command=self._ingest).pack(side="left", padx=4)
        self.judge = ttk.Combobox(top, values=["local", "rules", "gemini"], width=7, state="readonly")
        self.judge.set("local")
        ttk.Button(top, text="② Analyse (judge:)", command=self._analyse).pack(side="left", padx=(12, 2))
        self.judge.pack(side="left")
        self.doc_info = ttk.Label(top, text="", style="Muted.TLabel")
        self.doc_info.pack(side="left", padx=10)
        self.doc_path = None

        body = ttk.Frame(self.tab_doc)
        body.pack(fill="both", expand=True, padx=6)
        left = ttk.Frame(body)
        left.pack(side="left", fill="y")
        nav = ttk.Frame(left)
        nav.pack(fill="x")
        ttk.Button(nav, text="◀", width=3, command=lambda: self._page(-1)).pack(side="left")
        ttk.Button(nav, text="▶", width=3, command=lambda: self._page(1)).pack(side="left")
        self.page_lbl = ttk.Label(nav, text="")
        self.page_lbl.pack(side="left", padx=6)
        self.page_img = tk.Label(left, bg=PANEL)
        self.page_img.pack()
        mid = ttk.Frame(body)
        mid.pack(side="left", fill="both", expand=True, padx=6)
        self.t_tree = ttk.Treeview(mid, columns=("types", "xrefs"), height=20)
        self.t_tree.heading("#0", text="part / clause")
        self.t_tree.heading("types", text="types")
        self.t_tree.heading("xrefs", text="cross-refs")
        self.t_tree.column("#0", width=320)
        self.t_tree.column("types", width=260)
        self.t_tree.column("xrefs", width=110)
        self.t_tree.pack(fill="both", expand=True)
        self.t_tree.bind("<<TreeviewSelect>>", self._show_clause)
        self.clause_txt = tk.Text(mid, height=7, bg=PANEL, fg=FG, wrap="word", font=("DejaVu Sans", 10))
        self.clause_txt.pack(fill="x", pady=4)
        ttk.Label(mid, text="Findings").pack(anchor="w")
        self.t_find = self._tree(mid, ("severity", "relation", "clauses", "judge", "statute"), (70, 120, 130, 80, 330), 8)
        self.t_find.pack(fill="x")
        self.t_find.bind("<<TreeviewSelect>>", self._show_finding)
        self.pages, self.page_no, self.clauses, self.findings = 0, 1, {}, {}

    def _open_file(self):
        p = filedialog.askopenfilename(filetypes=[("Contracts", "*.pdf *.docx *.txt *.md *.png *.jpg")])
        if p:
            self.doc_path = Path(p)
            self.doc_info.config(text=self.doc_path.name)

    def _current_path(self):
        return self.doc_path or (ROOT / DOCS[self.doc.get()])

    def _ingest(self):
        path = self._current_path()
        self.doc_path = path
        self.log(f"ingest: {path.name}")

        def work():
            from legalagent.core.ingestion import ingest_with_stats
            from legalagent.core.extraction import extract
            from legalagent.core.classification import classify, available_backend
            t = time.time()
            text, st = ingest_with_stats(str(path), progress=lambda d, n: self.log(f"  OCR page {d}/{n}") if d % 25 == 0 else None)
            self.log(f"  ingestion: {st.get('pages')} pages, {st.get('ocr_pages', 0)} OCR'd, cached={st.get('cached')}, "
                     f"{len(text):,} chars in {time.time() - t:.1f}s")
            t = time.time()
            cl = extract(text, path.stem)
            self.log(f"  extraction: {len(cl)} clauses, {len({c.part for c in cl if c.part})} parts, "
                     f"{sum(x['resolved'] for c in cl for x in c.xrefs)} cross-refs in {time.time() - t:.2f}s")
            t = time.time()
            cl = classify(cl, backend="auto")
            self.log(f"  classification ({available_backend('auto')}): {time.time() - t:.2f}s")
            self.text, self.clause_list = text, cl
            self.ui(lambda: self._show_doc(path, st, cl))
        self.run_bg(work)

    def _show_doc(self, path, st, cl):
        self.doc_info.config(text=f"{st.get('pages')} pages · {st.get('ocr_pages', 0)} OCR · {len(cl)} clauses")
        self.t_tree.delete(*self.t_tree.get_children())
        self.clauses = {c.id: c for c in cl}
        parts = {}
        for c in cl:
            p = c.part or "(no part)"
            if p not in parts:
                parts[p] = self.t_tree.insert("", "end", text=p, open=len(parts) < 3)
            self.t_tree.insert(parts[p], "end", iid=c.id, text=("   " * c.number.count(".")) + f"{c.number}  {(c.heading or '')[:40]}",
                               values=(", ".join(l["label"] for l in c.labels), ", ".join(x["clause_id"].split("::")[-1] for x in c.xrefs if x["resolved"])))
        self.pages = st.get("pages", 0) if path.suffix.lower() == ".pdf" else 0
        self.page_no = 1
        self._page(0)

    def _page(self, delta):
        if not self.pages:
            self.page_lbl.config(text="(no page images)")
            return
        self.page_no = max(1, min(self.pages, self.page_no + delta))
        import pymupdf
        with pymupdf.open(self._current_path()) as d:
            pg = d[self.page_no - 1]
            ocr = len(pg.get_text().strip()) < 80
            pix = pg.get_pixmap(dpi=55)
            self._img = tk.PhotoImage(data=pix.tobytes("ppm"))
        self.page_img.config(image=self._img)
        self.page_lbl.config(text=f"page {self.page_no}/{self.pages} · {'scanned → OCR' if ocr else 'native text'}")

    def _show_clause(self, _e):
        sel = self.t_tree.selection()
        if sel and sel[0] in self.clauses:
            c = self.clauses[sel[0]]
            self.clause_txt.delete("1.0", "end")
            self.clause_txt.insert("1.0", f"[{c.number}] {c.part or ''}\nparent: {c.parent_id}\nlabels: {c.labels}\n\n{c.text[:3000]}")

    def _analyse(self):
        if not getattr(self, "clause_list", None):
            self.log("ingest a document first")
            return
        judge = self.judge.get()
        self.log(f"analyse: judge={judge} on {len(self.clause_list)} clauses")

        def work():
            from legalagent.core.pipeline import analyse_clauses
            import copy
            t = time.time()
            run, cl, fs = analyse_clauses(copy.deepcopy(self.clause_list), {"judge": judge, "retrieval_method": "hybrid", "max_candidates": 40})
            s = run.stats
            self.log(f"  pairs={s['pairs']} judge_used={s['judge']} findings={s['findings']} "
                     f"(classify {s.get('classify_s')}s, shortlist {s.get('candidates_s')}s, judge {s.get('judge_s')}s) total {time.time() - t:.1f}s")
            self.ui(lambda: self._show_findings(cl, fs, s))
        self.run_bg(work)

    def _show_findings(self, cl, fs, stats):
        by = {c.id: c for c in cl}
        self.t_find.delete(*self.t_find.get_children())
        self.findings = {}
        for f in fs:
            nums = " ↔ ".join(by[i].number for i in [f.target_clause_id, *f.related_clause_ids] if i in by)
            ref = next((f"{r['source'].replace('The ', '')}, {r['section']}" for r in f.refs if r.get("verified")), "")
            judge = "kev" if "kev" in f.surfaced_by else "rule" if "statutory_rule" in f.surfaced_by else "rules"
            iid = self.t_find.insert("", "end", values=(f.severity, f.relation_type, nums, judge, ref))
            self.findings[iid] = f

    def _show_finding(self, _e):
        sel = self.t_find.selection()
        if sel and sel[0] in self.findings:
            f = self.findings[sel[0]]
            self.clause_txt.delete("1.0", "end")
            self.clause_txt.insert("1.0", f"{f.severity.upper()} {f.relation_type} · risk {f.risk_score}\n{f.rationale}\n\n"
                                          f"scores: {json.dumps(f.scores, default=str)[:600]}\nrefs: {json.dumps(f.refs, default=str)[:600]}")


if __name__ == "__main__":
    Workbench().mainloop()
