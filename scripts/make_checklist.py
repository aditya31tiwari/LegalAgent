"""
Known-answer "checklist" clause pairs (CheckList-style minimal pairs) for validating the
teacher and scoring every judge independently of teacher labels.

For each classic cross-clause risk there is a BAD pair (expected: risky) and a FIXED pair,
the same clauses minimally edited to resolve the interaction (expected: no_issue). A judge
that reacts to surface words (e.g. "indemnify" near "liability") fails the FIXED half.
Plus the planted Pune Metro injections whose interaction is explicit in the text.

    venv/bin/python scripts/make_checklist.py
    -> research/teacher_labels/checklist_pairs.jsonl   (same format as pairs_to_label.jsonl
       + expected_risky, expected_relation)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "teacher_labels" / "checklist_pairs.jsonl"

# (id, relation_if_bad, clause A, clause B BAD, clause B FIXED)
CASES = [
    ("cap_indemnity", "conflict",
     "12.1 The aggregate liability of the Supplier under or in connection with this Agreement shall not exceed the fees paid in the twelve months preceding the claim.",
     "14.2 The Supplier shall indemnify the Customer against all losses arising from third-party intellectual property claims, without limit and notwithstanding any other provision of this Agreement.",
     "14.2 Subject to the limitation in Clause 12.1, the Supplier shall indemnify the Customer against losses arising from third-party intellectual property claims."),
    ("survival_confidentiality", "ambiguity",
     "18.4 On expiry or termination, only Clauses 9 (Payment) and 21 (Governing Law) shall survive.",
     "11.1 Each party shall keep the other's Confidential Information confidential for five years from disclosure.",
     "11.1 Each party shall keep the other's Confidential Information confidential for five years from disclosure, and this obligation shall survive termination of this Agreement notwithstanding Clause 18.4."),
    ("notice_periods", "conflict",
     "17.1 Either party may terminate this Agreement for convenience by giving ninety (90) days' written notice.",
     "17.3 The Customer may terminate this Agreement for convenience on thirty (30) days' written notice, and such notice shall prevail.",
     "17.3 Any notice of termination for convenience under Clause 17.1 shall be served in accordance with Clause 25 (Notices)."),
    ("arbitration_vs_courts", "conflict",
     "22.1 All disputes arising out of this Agreement shall be finally resolved by arbitration seated in New Delhi under the Arbitration and Conciliation Act, 1996.",
     "22.4 The courts at Mumbai shall have exclusive jurisdiction to decide all disputes arising out of this Agreement on their merits.",
     "22.4 Subject to Clause 22.1, the courts at New Delhi shall have exclusive supervisory jurisdiction over the arbitration, including applications under Sections 9 and 34 of the Act."),
    ("ld_vs_cap", "conflict",
     "12.1 The Contractor's total liability shall not exceed ten percent (10%) of the Contract Price.",
     "8.5 For delay in completion the Contractor shall pay liquidated damages of two percent (2%) of the Contract Price per week, without any upper limit.",
     "8.5 For delay in completion the Contractor shall pay liquidated damages of 0.5% of the Contract Price per week, subject to a maximum of five percent (5%), which counts towards the limit in Clause 12.1."),
    ("noncompete_survival", "conflict",
     "19.2 Clauses 15 (Non-Compete) and 16 (Confidentiality) shall survive termination for a period of three years.",
     "15.1 The Employee shall not, during employment and for three years after it ends, engage in any business competing with the Company anywhere in India.",
     "15.1 During the term of employment only, the Employee shall not engage in any business competing with the Company."),
    ("assignment_change_of_control", "conflict",
     "24.1 Neither party may assign this Agreement without the prior written consent of the other.",
     "24.3 A change of control of the Vendor shall not require any consent, and the Vendor may transfer this Agreement to its acquirer at any time.",
     "24.3 A change of control of the Vendor shall be treated as an assignment requiring consent under Clause 24.1."),
    ("payment_tax_grossup", "ambiguity",
     "9.1 The Customer shall pay the Fees within thirty days of a valid invoice; all Fees are inclusive of applicable taxes.",
     "9.4 The Customer shall pay all Fees free of any withholding, and shall gross up any payment from which tax is deducted at source.",
     "9.4 Where the Customer is required by law to deduct tax at source, it shall do so and provide the Vendor a TDS certificate; the Fees in Clause 9.1 are otherwise inclusive of taxes."),
    ("warranty_disclaimer", "conflict",
     "10.1 The Supplier warrants that the Goods shall be free from defects and fit for the purpose stated in Schedule A for twenty-four months.",
     "10.6 The Goods are supplied 'as is' and the Supplier disclaims all warranties, express or implied, including fitness for purpose.",
     "10.6 Except for the express warranty in Clause 10.1, the Supplier disclaims all other warranties, express or implied."),
    ("ip_assignment_vs_license", "conflict",
     "13.1 All Intellectual Property created by the Developer under this Agreement shall vest absolutely in the Client upon creation.",
     "13.4 The Developer retains ownership of all deliverables and grants the Client a non-exclusive, revocable licence to use them.",
     "13.4 The Developer retains ownership of its pre-existing tools and grants the Client a perpetual, royalty-free licence to use them as embedded in the deliverables."),
    ("force_majeure_payment", "ambiguity",
     "20.1 Neither party shall be liable for failure to perform any obligation due to a Force Majeure Event.",
     "9.2 The Customer's obligation to pay the monthly Service Fee shall continue regardless of any interruption of the Services.",
     "9.2 The Customer's obligation to pay the monthly Service Fee shall be suspended for any period in which the Services are suspended by a Force Majeure Event under Clause 20.1."),
    ("confidentiality_vs_regulator", "conflict",
     "16.1 Neither party shall disclose any Confidential Information to any person, including any governmental or regulatory authority, under any circumstances.",
     "26.2 Each party shall comply with all applicable laws, including mandatory reporting obligations to regulators.",
     "26.2 Each party shall comply with all applicable laws; disclosure required by law or a regulator is permitted notwithstanding Clause 16.1, after notice to the other party."),
]

# Planted Pune Metro injections whose interaction is stated in the text itself.
INJ = {i["number"]: i["text"] for i in json.loads((ROOT / "data/demo/india/adversarial/INJECTIONS.json").read_text())["injections"]}
INJECTION_PAIRS = [("91.1", "91.2", "conflict"), ("91.2", "91.4", "dependency"), ("91.3", "91.4", "dependency"),
                   ("91.6", "91.7", "overlap")]


def row(pid, a_text, b_text, risky, relation, group):
    num = lambda t: t.split()[0]
    return {"pair_id": pid, "contract": f"checklist:{group}", "split": "checklist",
            "a_id": f"checklist::{pid}::{num(a_text)}", "b_id": f"checklist::{pid}::{num(b_text)}",
            "a_text": a_text, "b_text": b_text, "a_labels": [], "b_labels": [], "surfaced_by": ["type_matrix"],
            "expected_risky": risky, "expected_relation": relation}


def main():
    # Order = all BAD pairs, then injections, then all FIXED pairs, so with batch size 7 a
    # bad pair and its fixed twin never share a prompt. Pair ids are neutral (ck01..) and
    # the contract tag is generic, so nothing in the prompt reveals the expected answer.
    bad = [(f"{cid}_bad", a, b, True, rel, cid) for cid, rel, a, b, _ in CASES]
    inj = [(f"inj_{x}_{y}", f"{x} {INJ[x]}", f"{y} {INJ[y]}", True, rel, "pune_injections") for x, y, rel in INJECTION_PAIRS]
    fixed = [(f"{cid}_fixed", a, b, False, "no_issue", cid) for cid, _, a, _, b in CASES]
    rows = []
    for n, (case, a, b, risky, rel, group) in enumerate(bad + inj + fixed, 1):
        r = row(f"ck{n:02d}", a, b, risky, rel, group)
        r["case"] = case
        r["contract"] = "checklist"
        r["a_id"], r["b_id"] = f"checklist::{a.split()[0]}", f"checklist::{b.split()[0]}"
        rows.append(r)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} checklist pairs ({sum(r['expected_risky'] for r in rows)} risky) -> {OUT}")


if __name__ == "__main__":
    main()
