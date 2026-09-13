"""
LegalAgent v0: Contract clause analysis pipeline.

Layers:
  1. ingestion  - Load and normalize contract text (PDF/DOCX/TXT)
  2. extraction - Regex-based clause extraction with decimal numbering
  3. classification - Keyword-based clause labeling
  4. candidate_selection - BM25 + xref + type_matrix pair scoring
  5. analysis (stub) - LLM analysis per pair (to be implemented)
  6. pipeline - Orchestration: file -> clauses -> findings -> JSON

Data shapes (final, mirrored in DB/API):
  - Clause: extracted paragraph with offsets, labels, cross-references
  - Finding: conflict/overlap/dependency between clause pairs
  - Run: metadata for one contract analysis run
"""

from core.types import Clause, Finding, Run
from core.pipeline import analyse

__all__ = ["Clause", "Finding", "Run", "analyse"]
