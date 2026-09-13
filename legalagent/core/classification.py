from legalagent.core.types import Clause

# Simple keyword dictionary for v0
KEYWORDS = {
    "indemnification": ["indemnif", "hold harmless", "defend"],
    "limitation_of_liability": ["limitation of liability", "in no event shall", "aggregate liability", "consequential damages"],
    "termination": ["terminate", "termination for cause", "termination rights"],
    "confidentiality": ["confidential information", "non-disclosure", "nda"],
    "governing_law": ["governed by the laws", "governing law", "jurisdiction"],
    "assignment": ["assign", "successors and assigns", "assignment and delegation"],
    "survival": ["survive", "shall survive termination"],
    "exclusivity": ["exclusive", "sole and exclusive", "exclusive license"],
    "warranty": ["warranty", "warranties", "represent and warrant"],
    "force_majeure": ["force majeure", "act of god", "unforeseeable"],
    "payment": ["payment", "invoice", "compensation", "fee"],
    "intellectual_property": ["intellectual property", "patent", "trademark", "copyright"],
}


def classify(clauses: list[Clause]) -> list[Clause]:
    """
    Keyword-based classification v0: substring match (case-insensitive).
    Appends labels to each clause.
    """
    for clause in clauses:
        text_lower = clause.text.lower()

        for label_name, keywords in KEYWORDS.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    clause.labels.append({
                        "label": label_name,
                        "confidence": 1.0,
                        "source": "keyword"
                    })
                    break  # Only add label once per clause

    return clauses
