"""
LegalAgent v0: Contract clause analysis pipeline.

Layers:
  1. ingestion  - Load and normalize contract text (PDF/DOCX/TXT)
  2. extraction - Regex-based clause extraction with decimal numbering
  3. classification - Keyword-based clause labeling
  4. retrieval  - Related-clause ranking: bm25 | dense | hybrid (RRF)
  5. candidate_selection - retrieval + xref + type_matrix pair scoring
  6. analysis (stub) - LLM analysis per pair (to be implemented)
  7. pipeline - Orchestration: file -> clauses -> findings -> JSON

  evaluation - Scores retrieval methods against gold pairs derived from the
               contract's own cross-references (python -m legalagent eval)

Data shapes (final, mirrored in DB/API):
  - Clause: extracted paragraph with offsets, labels, cross-references
  - Finding: conflict/overlap/dependency between clause pairs
  - Run: metadata for one contract analysis run
"""

from legalagent.core.types import Clause, Finding, Run
from legalagent.core.pipeline import analyse
from legalagent.core.retrieval import retrieve
from legalagent.core.evaluation import compare, gold_pairs

__all__ = ["Clause", "Finding", "Run", "analyse", "retrieve", "compare", "gold_pairs"]
