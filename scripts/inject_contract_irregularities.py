"""Append labelled synthetic irregularities to an official Indian contract PDF."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pymupdf


ROOT = Path(__file__).parent.parent
SOURCE = ROOT / "data/demo/india/adversarial/source_pune_metro_signed_concession.pdf"
OUTPUT = ROOT / "data/demo/india/adversarial/pune_metro_adversarial_15_changes.pdf"
MANIFEST = ROOT / "data/demo/india/adversarial/INJECTIONS.json"

INJECTIONS = [
    ("91.1", "Limitation of Liability", "The aggregate liability of the Authority shall not exceed INR 1,000 for any claim, including fraud, death, personal injury, gross negligence, and statutory penalties."),
    ("91.2", "Unlimited Indemnity", "The Concessionaire shall defend, indemnify, and hold harmless the Authority against every claim, loss, fine, and expense without any financial limitation and notwithstanding Clause 91.1."),
    ("91.3", "Post-Termination Non-Compete", "For 36 months following termination, the Concessionaire shall not compete with, advise, or participate in any competing infrastructure business in India."),
    ("91.4", "Survival of Restrictions", "Clauses 91.2 and 91.3 shall survive termination indefinitely and remain enforceable after termination of this Agreement."),
    ("91.5", "Punitive Delay Penalty", "A delay of one day shall incur automatic liquidated damages equal to 75 percent of the total concession value, regardless of actual loss."),
    ("91.6", "Capped Statutory Penalties", "Any penalty imposed under the Digital Personal Data Protection Act, 2023 shall be limited to INR 10,000 between the parties."),
    ("91.7", "Data Processing Without Consent", "The Concessionaire may collect, sell, and process all passenger personal data for any commercial purpose without notice or affirmative consent."),
    ("91.8", "Excluded Mediation", "No party shall attempt pre-litigation mediation and all disputes shall proceed directly to unilateral arbitration."),
    ("91.9", "Repealed Criminal Reference", "A breach shall be treated as cheating under Section 420 of the Indian Penal Code, even after the Bharatiya Nyaya Sanhita comes into force."),
    ("91.10", "Unilateral Amendment", "The Authority may amend any commercial term, fee, or risk allocation without notice or consent from the Concessionaire."),
    ("91.11", "Assignment Contradiction", "The Concessionaire shall not assign this Agreement, but the Authority may freely assign all obligations to any third party without consent."),
    ("91.12", "Absolute Warranty Disclaimer", "The Authority gives no warranty whatsoever, including for title, legality, safety, or fitness, and the Concessionaire waives every statutory remedy."),
    ("91.13", "Unstamped Execution", "The parties agree that this concession is intentionally unstamped and that no party may seek impounding or cure of stamp duty."),
    ("91.14", "Perpetual Confidentiality", "Every operational fact, public filing, safety report, and statutory disclosure shall remain confidential forever and may never be disclosed to any regulator."),
    ("91.15", "Foreign Forum Override", "This Agreement shall be governed by the laws of England and disputes shall be decided exclusively by courts in London notwithstanding the Indian project and Indian governing approvals."),
]


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"Missing source PDF: {SOURCE}")
    source = pymupdf.open(SOURCE)
    document = pymupdf.open()
    document.insert_pdf(source)
    source.close()

    for page_start in range(0, len(INJECTIONS), 3):
        page = document.new_page()
        page.insert_text((48, 48), "LEGALAGENT SYNTHETIC ADVERSARIAL TEST", fontsize=15, fontname="hebo", color=(0.55, 0.08, 0.08))
        page.insert_text((48, 68), "Appended to an official Indian source PDF. Not part of the source agreement.", fontsize=8, fontname="heit", color=(0.35, 0.35, 0.35))
        y = 100
        for number, title, text in INJECTIONS[page_start:page_start + 3]:
            block = f"{number} {title}\n{text}"
            page.insert_textbox((48, y, page.rect.width - 48, y + 130), block, fontsize=10, lineheight=1.3, fontname="helv", color=(0.1, 0.14, 0.2))
            y += 155

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    document.save(OUTPUT)
    document.close()
    MANIFEST.write_text(json.dumps({
        "source_pdf": str(SOURCE.relative_to(ROOT)),
        "modified_pdf": str(OUTPUT.relative_to(ROOT)),
        "warning": "Synthetic appended clauses are not part of the official agreement and are only for robustness testing.",
        "injections": [
            {"number": number, "title": title, "expected_current_detector": number in {"91.1", "91.2", "91.3", "91.4"}, "text": text}
            for number, title, text in INJECTIONS
        ],
    }, indent=2), encoding="utf-8")
    print(OUTPUT)
    print(MANIFEST)


if __name__ == "__main__":
    main()
