"""
Indian statute library: retrieval-augmented grounding for findings.

Source: Open India Law (vaquill.ai), central legislation from India Code, one row per
section. `build_library()` keeps the Acts that govern commercial contracts and writes
data/statutes/india_commercial_sections.jsonl (small, committed). At analysis time:

  retrieve_sections(query)        hybrid BM25 + dense (RRF) over section text
  attach_statute_refs(findings)   adds the top matching sections to every finding as
                                  refs with the official India Code URL, and verifies
                                  any citation a judge produced (Gemini / Kev) against
                                  the library: refs[].verified = True/False.

Citations are therefore never only "from model memory": each one either points at
real section text in the library or is flagged unverified in the UI.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW_PARQUET = ROOT / "dataset" / "in_central_legislation.parquet"
LIBRARY = ROOT / "data" / "statutes" / "india_commercial_sections.jsonl"
ADDITIONS_DIR = ROOT / "data" / "statutes" / "additions"
MIRROR_URL = "https://oss-data-in.vaquill.ai/v2026.08.1/in_central_legislation.parquet"

# Acts a commercial-contract reviewer in India actually cites. Title substrings.
ACTS = [
    "The Indian Contract Act, 1872",
    "The Specific Relief Act, 1963",
    "The Arbitration and Conciliation Act, 1996",
    "The Sale of Goods Act, 1930",
    "The Indian Partnership Act, 1932",
    "The Information Technology Act, 2000",
    "The Digital Personal Data Protection Act, 2023",
    "The Competition Act, 2002",
    "The Indian Stamp Act, 1899",
    "The Limitation Act, 1963",
    "The Transfer of Property Act, 1882",
    "The Companies Act, 2013",
    "The Consumer Protection Act, 2019",
    "The Insolvency and Bankruptcy Code, 2016",
    "The Micro, Small and Medium Enterprises Development Act, 2006",
    "The Copyright Act, 1957",
    "The Patents Act, 1970",
    "The Trade Marks Act, 1999",
    "The Industrial Disputes Act, 1947",
    "The Commercial Courts Act, 2015",
    "The Mediation Act, 2023",
    "The Negotiable Instruments Act, 1881",
    "The Foreign Exchange Management Act, 1999",
]

# Short names models tend to write -> canonical title.
ALIASES = {
    "ica": "The Indian Contract Act, 1872", "contract act": "The Indian Contract Act, 1872",
    "specific relief": "The Specific Relief Act, 1963",
    "arbitration": "The Arbitration and Conciliation Act, 1996",
    "sale of goods": "The Sale of Goods Act, 1930",
    "information technology": "The Information Technology Act, 2000", "it act": "The Information Technology Act, 2000",
    "dpdp": "The Digital Personal Data Protection Act, 2023", "personal data": "The Digital Personal Data Protection Act, 2023",
    "competition": "The Competition Act, 2002", "stamp": "The Indian Stamp Act, 1899",
    "limitation": "The Limitation Act, 1963", "transfer of property": "The Transfer of Property Act, 1882",
    "companies act": "The Companies Act, 2013", "consumer protection": "The Consumer Protection Act, 2019",
    "insolvency": "The Insolvency and Bankruptcy Code, 2016", "msme": "The Micro, Small and Medium Enterprises Development Act, 2006",
    "micro, small": "The Micro, Small and Medium Enterprises Development Act, 2006",
    "copyright": "The Copyright Act, 1957", "patents": "The Patents Act, 1970", "trade marks": "The Trade Marks Act, 1999",
    "industrial disputes": "The Industrial Disputes Act, 1947", "commercial courts": "The Commercial Courts Act, 2015",
    "mediation": "The Mediation Act, 2023", "negotiable instruments": "The Negotiable Instruments Act, 1881",
    "fema": "The Foreign Exchange Management Act, 1999", "foreign exchange": "The Foreign Exchange Management Act, 1999",
    "partnership": "The Indian Partnership Act, 1932",
    "constitution": "The Constitution of India",
    "code on wages": "The Code on Wages, 2019", "negotiable": "The Negotiable Instruments Act, 1881",
}


def _all_acts() -> list[str]:
    """Every Act title present in the library (ACTS + curated additions)."""
    try:
        return sorted({s["act"] for s in load_library()}, key=len, reverse=True)
    except FileNotFoundError:
        return ACTS

DENSE_MODEL = "bhavyagiri/InLegal-Sbert"
_MD_RE = re.compile(r"[*_`]+|\(\s*_?(\d+)_?\s*\)")


def _clean(text: str) -> str:
    # Drop the "Act: ... | India | Central | In Force" header line and markdown noise.
    body = text.split("\n", 1)[1] if text.startswith("Act:") and "\n" in text else text
    body = _MD_RE.sub(lambda m: f"({m.group(1)})" if m.group(1) else "", body)
    return re.sub(r"\s+", " ", body).strip()


def build_library(parquet: Path = RAW_PARQUET, out: Path = LIBRARY) -> int:
    """Filter central legislation to the commercial Acts; merge chunks into sections."""
    import pandas as pd
    df = pd.read_parquet(parquet)
    df["title"] = df["title"].str.strip().str.rstrip(".")
    df = df[df["title"].isin(ACTS)]
    rows = {}
    for r in df.itertuples():
        key = (r.title, str(r.section_number))
        entry = rows.setdefault(key, {
            "id": f"{r.act_id}:s{r.section_number}",
            "act": r.title,
            "section": str(r.section_number),
            "heading": "",
            "text": "",
            "url": r.source_url,
            "pdf": r.mirror_url,
            "in_force": bool(r.in_force),
        })
        txt = _clean(r.text)
        m = re.match(r"Chapter [^|]*\|\s*Section [^:]*:\s*(.*?)\s*\.\s*—\s*(.*)", txt)
        if m and not entry["heading"]:
            entry["heading"] = m.group(1).strip()
            txt = m.group(2)
        else:
            txt = re.sub(r"^(Chapter [^|]*\|\s*)?Section [^:]*:\s*", "", txt)
        entry["text"] = (entry["text"] + " " + txt).strip()
    # Additions curated in the taxonomy research (BNS/BNSS/BSA 2023, CPC 1908, landmark
    # precedents), already in this schema. Merged here so a rebuild never drops them.
    for extra in sorted(ADDITIONS_DIR.glob("*.jsonl")) if ADDITIONS_DIR.exists() else []:
        for line in extra.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            key = (e["act"], str(e["section"]))
            if key not in rows:
                rows[key] = {"id": e.get("id", f"{e['act']}:s{e['section']}"), "act": e["act"], "section": str(e["section"]),
                             "heading": e.get("heading", ""), "text": re.sub(r"\s+", " ", e.get("text", "")).strip(),
                             "url": e.get("url", ""), "pdf": e.get("pdf", ""), "in_force": e.get("in_force", True),
                             "source": extra.name}
    merge_nyaya(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as f:
        for e in rows.values():
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    for stale in out.parent.glob(out.stem + ".*.npy"):
        stale.unlink()  # embedding caches are per library version
    return len(rows)


# nyaya-statute-db (NyayaLabs98, India Code text, MIT tooling): section-level JSONL for 28 Acts.
# Only Acts relevant to commercial / employment contracts are merged; family and criminal-procedure
# law would only add noise for contract review. Its Contract Act is more complete than our parse.
NYAYA_DIR = ROOT / "dataset" / "nyaya"
NYAYA_FILES = {
    "constitution_1950.jsonl": "The Constitution of India",
    "contract_act_1872.jsonl": "The Indian Contract Act, 1872",
    "cpa_2019.jsonl": "The Consumer Protection Act, 2019",
    "it_act_2000.jsonl": "The Information Technology Act, 2000",
    "limitation_1963.jsonl": "The Limitation Act, 1963",
    "ni_act_1881.jsonl": "The Negotiable Instruments Act, 1881",
    "tpa_1882.jsonl": "The Transfer of Property Act, 1882",
    "wages_code_2019.jsonl": "The Code on Wages, 2019",
    "posh_2013.jsonl": "The Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act, 2013",
    "bns_2023.jsonl": None, "bnss_2023.jsonl": None, "bsa_2023.jsonl": None,   # keep the act names they ship
}


def merge_nyaya(rows: dict) -> None:
    """Union nyaya sections into `rows` (keyed by (act, section)); on overlap keep the fuller text."""
    if not NYAYA_DIR.exists():
        return
    acts_by_low = {a.lower().replace("the ", "", 1): a for a, _ in rows}
    added = replaced = 0
    for fname, canon in NYAYA_FILES.items():
        p = NYAYA_DIR / fname
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            name = canon or acts_by_low.get(r["act_name"].lower().replace("the ", "", 1), r["act_name"])
            key = (name, str(r["section"]))
            text = re.sub(r"\s+", " ", r.get("text") or "").strip()
            if not text:
                continue
            entry = {"id": f"nyaya:{r['act_id']}:s{r['section']}", "act": name, "section": str(r["section"]),
                     "heading": r.get("title") or "", "text": text, "url": r.get("source_url") or "", "pdf": "",
                     "in_force": True, "source": "nyaya-statute-db"}
            if key not in rows:
                rows[key] = entry
                added += 1
            elif len(text) > 1.3 * len(rows[key]["text"]):
                rows[key] = {**rows[key], "text": text, "heading": rows[key]["heading"] or entry["heading"], "source": "nyaya-statute-db"}
                replaced += 1
    print(f"nyaya-statute-db: +{added} sections, {replaced} replaced with fuller text")


@lru_cache(maxsize=1)
def load_library() -> list[dict]:
    if not LIBRARY.exists():
        raise FileNotFoundError(f"{LIBRARY} missing: run python -m legalagent.core.statutes build")
    return [json.loads(l) for l in LIBRARY.read_text(encoding="utf-8").splitlines() if l.strip()]


def _doc_text(s: dict) -> str:
    return f"{s['heading']}. {s['heading']}. {s['text'][:1200]}"


# Acts that govern the contract relationship itself. A reviewer looks here first, so
# retrieval gets a small, documented prior towards them (ablated in eval_statutes).
CORE_ACTS = {
    "The Indian Contract Act, 1872": 1.0, "The Specific Relief Act, 1963": 0.6,
    "The Arbitration and Conciliation Act, 1996": 0.6, "The Sale of Goods Act, 1930": 0.4,
    "The Limitation Act, 1963": 0.3, "The Digital Personal Data Protection Act, 2023": 0.3,
    "The Commercial Courts Act, 2015": 0.2, "The Mediation Act, 2023": 0.2,
}
ACT_PRIOR = 0.004  # in RRF units: ~ the gap between rank 1 and rank 15

_STOP = set("""a an and are as at be been by for from has have in into is it its of on or such that the
their there these this those to was were which with shall may any all not no other under than any said
section sub act provided including include includes whether same also upon""".split())


def _tok(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z]{3,}", text.lower()) if w not in _STOP]


@lru_cache(maxsize=1)
def _bm25():
    from rank_bm25 import BM25Okapi
    return BM25Okapi([_tok(_doc_text(s)) for s in load_library()])


@lru_cache(maxsize=2)
def _dense(model_name: str):
    from legalagent.core.retrieval import _load_model, safe_encode
    model = _load_model(model_name)
    cache = LIBRARY.with_suffix(f".{model_name.replace('/', '__')}.npy")
    import numpy as np
    if cache.exists():
        emb = np.load(cache)
        if len(emb) == len(load_library()):
            return model, emb
    emb = safe_encode(model, [_doc_text(s) for s in load_library()], normalize_embeddings=True, batch_size=64)
    np.save(cache, emb)
    return model, emb


def default_dense_model() -> str:
    """Fine-tuned statute retriever if trained (train/finetune_retriever.py), else base InLegal-SBERT."""
    ft = ROOT / "models" / "inlegal_sbert_statutes"
    return str(ft) if (ft / "config.json").exists() else DENSE_MODEL


def safe_encode(model, texts, **kw):
    from legalagent.core.retrieval import safe_encode as _se
    return _se(model, texts, **kw)


RERANKER = "BAAI/bge-reranker-v2-m3"     # Apache-2.0 multilingual cross-encoder
NYAYA_EMBED = "NyayaLabs98/nyaya-embed-v1"  # trained to map queries to Indian statute sections


@lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder
    from legalagent.core.device import pick_device
    return CrossEncoder(RERANKER, max_length=512, device=pick_device(1.2))


def rerank(query: str, cands: list[tuple[dict, float]], k: int) -> list[tuple[dict, float]]:
    """Cross-encoder re-scoring of (clause, section text) pairs; reads both texts jointly."""
    if not cands:
        return cands
    scores = _reranker().predict([(query[:1500], _doc_text(s)[:1500]) for s, _ in cands], batch_size=16)
    order = sorted(range(len(cands)), key=lambda i: -float(scores[i]))
    return [(cands[i][0], float(scores[i])) for i in order[:k]]


def retrieve_sections(query: str, k: int = 3, method: str = "hybrid", model_name: str | None = None,
                      act_prior: bool = True, rerank_top: int = 0) -> list[tuple[dict, float]]:
    if rerank_top:
        return rerank(query, retrieve_sections(query, rerank_top, method, model_name, act_prior, 0), k)
    import numpy as np
    lib = load_library()
    model_name = model_name or default_dense_model()
    ranks = []
    if method in ("bm25", "hybrid"):
        ranks.append(np.argsort(-_bm25().get_scores(_tok(query))))
    if method in ("dense", "hybrid"):
        model, emb = _dense(model_name)
        q = safe_encode(model, [query], normalize_embeddings=True)[0]
        ranks.append(np.argsort(-(emb @ q)))
    fused = np.zeros(len(lib))
    for order in ranks:
        fused[order] += 1.0 / (60 + np.arange(1, len(order) + 1))
    if act_prior:
        fused += ACT_PRIOR * np.array([CORE_ACTS.get(s["act"], 0.0) for s in lib])
    top = np.argsort(-fused)[:k]
    return [(lib[i], float(fused[i])) for i in top]


def explain_sections(query: str, k: int = 5, model_name: str | None = None) -> list[dict]:
    """
    The same hybrid ranking as retrieve_sections(), with every intermediate score exposed:
    BM25 score + rank, dense cosine + rank, reciprocal-rank-fusion contributions, Act prior.
    Used by the dashboard's "under the hood" view.
    """
    import numpy as np
    lib = load_library()
    model_name = model_name or default_dense_model()
    bm = _bm25().get_scores(_tok(query))
    model, emb = _dense(model_name)
    cos = emb @ safe_encode(model, [query], normalize_embeddings=True)[0]
    bm_rank = np.empty(len(lib), int); bm_rank[np.argsort(-bm)] = np.arange(1, len(lib) + 1)
    de_rank = np.empty(len(lib), int); de_rank[np.argsort(-cos)] = np.arange(1, len(lib) + 1)
    rrf_bm = 1.0 / (60 + bm_rank)
    rrf_de = 1.0 / (60 + de_rank)
    prior = ACT_PRIOR * np.array([CORE_ACTS.get(s["act"], 0.0) for s in lib])
    fused = rrf_bm + rrf_de + prior
    top = np.argsort(-fused)[:k]
    return [{
        "act": lib[i]["act"], "section": lib[i]["section"], "heading": lib[i]["heading"], "url": lib[i].get("url", ""),
        "bm25": round(float(bm[i]), 3), "bm25_rank": int(bm_rank[i]),
        "dense_cosine": round(float(cos[i]), 4), "dense_rank": int(de_rank[i]),
        "rrf_bm25": round(float(rrf_bm[i]), 5), "rrf_dense": round(float(rrf_de[i]), 5),
        "act_prior": round(float(prior[i]), 5), "fused": round(float(fused[i]), 5),
        "dense_model": Path(model_name).name,
    } for i in top]


_SEC_RE = re.compile(r"(?:section|sec\.?|s\.|article|art\.)\s*(\d+[A-Z]?)(?:\s*(?:-|to|–)\s*(\d+[A-Z]?))?", re.I)


def verify_citation(citation: str) -> dict | None:
    """Resolve a free-text citation ("Indian Contract Act 1872, Section 27") to a library section."""
    if not citation:
        return None
    low = citation.lower()
    acts = _all_acts()
    act = next((a for a in acts if a.lower().replace("the ", "", 1).split(",")[0] in low), None)
    if act is None:
        alias_target = next((title for alias, title in ALIASES.items() if alias in low), None)
        act = alias_target if alias_target in acts else None
    if act is None:
        for alias, frag in (("bns", "bharatiya nyaya"), ("bnss", "nagarik suraksha"), ("bsa", "sakshya"), ("cpc", "civil procedure")):
            if re.search(rf"\b{alias}\b", low):
                act = next((a for a in acts if frag in a.lower()), None)
    m = _SEC_RE.search(citation)
    if not act or not m:
        return None
    by_key = {(s["act"], s["section"]): s for s in load_library()}
    return by_key.get((act, m.group(1)))


def _ref(section: dict, how: str, verified: bool) -> dict:
    return {
        "source": section["act"],
        "section": f"Section {section['section']}",
        "heading": section["heading"],
        "snippet": section["text"][:300],
        "url": section.get("url", ""),
        "grounding": how,
        "verified": verified,
    }


def attach_statute_refs(findings, clauses_by_id: dict, k: int = 2) -> None:
    """Verify judge citations and add retrieved sections to every finding (in place)."""
    load_library()  # fail fast if not built
    for f in findings:
        new_refs = []
        for ref in f.refs:
            cited = verify_citation(f"{ref.get('source', '')} {ref.get('section', '')}")
            if cited:
                new_refs.append(_ref(cited, "judge_citation", True))
            else:
                new_refs.append({**ref, "grounding": "judge_citation", "verified": False})
        texts = [clauses_by_id[cid].text[:600] for cid in [f.target_clause_id, *f.related_clause_ids] if cid in clauses_by_id]
        query = f"{f.rationale} {' '.join(texts)}"
        have = {(r["source"], r["section"]) for r in new_refs}
        for rank, (section, score) in enumerate(retrieve_sections(query, k=k, **RETRIEVAL_DEFAULT)):
            key = (section["act"], f"Section {section['section']}")
            if key not in have:
                ref = _ref(section, "retrieved", True)
                # Retrieved law is a lead, not a verdict: always shown, with how sure the retriever is.
                ref["confidence"] = retrieval_confidence(rank, score)
                ref["retrieval_score"] = round(float(score), 4)
                new_refs.append(ref)
                have.add(key)
        f.refs = new_refs


# Chosen from scripts/eval_all.py statutes (independent gold: statutes applied by the Supreme
# Court + planted irregularities). Updated after evaluation; see results/eval_statutes.json.
RETRIEVAL_DEFAULT: dict = {}


def retrieval_confidence(rank: int, score: float) -> str:
    """Reranker scores are relevance logits/probabilities; fused RRF scores are rank-based."""
    if RETRIEVAL_DEFAULT.get("rerank_top"):
        return "high" if score > 0.5 else "medium" if score > 0.1 else "low"
    return "medium" if rank == 0 else "low"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        if not RAW_PARQUET.exists():
            import urllib.request
            RAW_PARQUET.parent.mkdir(exist_ok=True)
            urllib.request.urlretrieve(MIRROR_URL, RAW_PARQUET)
        n = build_library()
        from collections import Counter
        c = Counter(s["act"] for s in load_library())
        print(f"{n} sections from {len(c)} Acts -> {LIBRARY}")
        for act, cnt in c.most_common():
            print(f"  {cnt:5d}  {act}")
        missing = [a for a in ACTS if a not in c]
        print("missing:", missing)
    else:
        q = " ".join(sys.argv[1:]) or "post-termination non-compete restraint of trade"
        for s, sc in retrieve_sections(q, k=5):
            print(f"{sc:.4f}  {s['act']} s.{s['section']} {s['heading']}")
