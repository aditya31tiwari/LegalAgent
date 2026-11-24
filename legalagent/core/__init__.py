"""
LegalAgent: cross-clause contract review pipeline.

Layers:
  1. ingestion           - Load and normalise contract text (PDF/DOCX/TXT/MD, OCR fallback)
  2. extraction          - Clause extraction (decimal numbering, markdown headings) + xref resolution
  3. classification      - CLAUSE-20 labelling: keyword | MiniLM+LogReg | fine-tuned InLegalBERT
  4. retrieval           - Related-clause ranking: bm25 | dense | hybrid (RRF)
  5. candidate_selection - xref + type matrix + retrieval (+ optional GNN) pair shortlist
  6. judge               - rules | local fine-tuned decision model | Gemini
  7. statutes            - Grounding findings in retrieved Indian statute sections
  8. pipeline            - Orchestration: file -> clauses -> findings -> JSON

  evaluation - Scores retrieval methods against gold pairs derived from the
               contract's own cross-references (python -m legalagent eval)
"""

from legalagent.core.types import Clause, Finding, Run
from legalagent.core.pipeline import analyse, analyse_text
from legalagent.core.retrieval import retrieve
from legalagent.core.evaluation import compare, gold_pairs

__all__ = ["Clause", "Finding", "Run", "analyse", "analyse_text", "retrieve", "compare", "gold_pairs"]
