import sqlite3
import json
import os
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "contracts.db"


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes the SQLite database schema for contracts, clauses, edges, and findings."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # Contracts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS contracts (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        category TEXT NOT NULL,
        jurisdiction TEXT DEFAULT 'India',
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Clauses table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clauses (
        id TEXT PRIMARY KEY,
        contract_id TEXT NOT NULL,
        clause_num TEXT NOT NULL,
        title TEXT NOT NULL,
        tag TEXT NOT NULL,
        text TEXT NOT NULL,
        ordinal INTEGER NOT NULL,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    """)

    # Graph Edges table (Connections between clauses)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS graph_edges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        contract_id TEXT NOT NULL,
        source_clause_id TEXT NOT NULL,
        target_clause_id TEXT NOT NULL,
        label TEXT NOT NULL,
        relation_type TEXT NOT NULL, -- conflict, statutory, xref, semantic
        severity TEXT DEFAULT 'medium', -- high, medium, low
        color TEXT NOT NULL,
        width REAL DEFAULT 2.0,
        dashes BOOLEAN DEFAULT 0,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
        FOREIGN KEY (source_clause_id) REFERENCES clauses(id) ON DELETE CASCADE,
        FOREIGN KEY (target_clause_id) REFERENCES clauses(id) ON DELETE CASCADE
    );
    """)

    # Findings table (Risks and statutory violations)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS findings (
        id TEXT PRIMARY KEY,
        contract_id TEXT NOT NULL,
        title TEXT NOT NULL,
        severity TEXT NOT NULL, -- high, statutory, medium, low
        relation_type TEXT NOT NULL,
        source_clause_ref TEXT NOT NULL,
        target_clause_ref TEXT NOT NULL,
        description TEXT NOT NULL,
        statute_citation TEXT,
        remedy_suggestion TEXT,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS clause_embeddings (
        clause_id TEXT PRIMARY KEY,
        contract_id TEXT NOT NULL,
        model_name TEXT NOT NULL,
        dimension INTEGER NOT NULL,
        vector_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (contract_id) REFERENCES contracts(id) ON DELETE CASCADE,
        FOREIGN KEY (clause_id) REFERENCES clauses(id) ON DELETE CASCADE
    );
    """)

    conn.commit()
    conn.close()
    print(f"Database schema initialized at: {DB_PATH}")


def seed_database():
    """Populates the SQLite database with Indian law contracts + the requested Lorem Ipsum demo contract."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("DELETE FROM findings;")
    cursor.execute("DELETE FROM graph_edges;")
    cursor.execute("DELETE FROM clauses;")
    cursor.execute("DELETE FROM contracts;")

    DATA = {
        "tech_msa": {
            "title": "Indian Tech Services MSA (IT/SaaS)",
            "category": "Technology & Commercial",
            "jurisdiction": "India (Karnataka)",
            "description": "Master Services Agreement featuring limitation of liability clash with uncapped indemnity and DPDPA penalty limitations.",
            "clauses": [
                ("c1", "1.1", "Definitions & Interpretation", "General", "In this Agreement, capitalised terms shall have meanings assigned herein. References to Indian Acts include amendments.", 1),
                ("c2", "3.2", "Scope of Services & SLAs", "Commercial", "Vendor shall provide cloud-managed services compliant with 99.9% uptime. SLA failures trigger service credits under Clause 4.1.", 2),
                ("c3", "4.1", "Service Credits & Rebates", "Payment", "Subject to Section 3.2, customer may deduct service credits up to a maximum of 5% of monthly billing.", 3),
                ("c4", "7.1", "Data Protection & Security", "Compliance", "Parties acknowledge Vendor is a Data Processor and Customer is Data Fiduciary under the Digital Personal Data Protection Act (DPDPA), 2023.", 4),
                ("c5", "7.4", "Data Breach Penalty Allocation", "DPDPA Risk", "Vendor's liability for data breaches and regulatory penalties under DPDPA 2023 shall in no event exceed fees paid in the prior 3 months.", 5),
                ("c6", "8.1", "Limitation of Liability", "Liability", "To the maximum extent permitted by law, neither party's aggregate liability arising under this Agreement shall exceed ₹15,00,000 INR.", 6),
                ("c7", "12.1", "Intellectual Property Indemnity", "Indemnity", "Vendor shall defend, indemnify, and hold harmless Customer against all third-party claims alleging IP infringement, without any financial limitation.", 7),
                ("c8", "12.3", "Regulatory Fines Indemnity", "Indemnity", "Customer shall indemnify Vendor from all fines imposed by the Data Protection Board of India resulting from Customer's improper consent records.", 8),
                ("c9", "15.1", "Term and Termination", "Term", "Either party may terminate for convenience upon 60 days written notice. Survival clauses apply as set forth in Section 15.4.", 9),
                ("c10", "15.4", "Survival of Provisions", "Survival", "Provisions of Section 7 (Data Protection), Section 8 (Liability Cap), and Section 12 (Indemnity) shall survive termination indefinitely.", 10),
                ("c11", "18.1", "Governing Law & Jurisdiction", "Governing Law", "This Agreement shall be governed by the laws of India. Courts of Bengaluru, Karnataka have exclusive jurisdiction.", 11),
                ("c12", "18.2", "Dispute Resolution (Arbitration)", "Dispute", "All disputes shall be resolved via sole arbitrator under Arbitration and Conciliation Act, 1996 in Bengaluru. Pre-litigation mediation is excluded.", 12),
            ],
            "edges": [
                ("c6", "c7", "CONFLICT: Cap vs Indemnity", "conflict", "high", "#ef4444", 3.0, 0),
                ("c4", "c5", "DPDPA Risk", "statutory", "high", "#ec4899", 2.5, 1),
                ("c5", "c6", "Cap Contradiction", "conflict", "high", "#ef4444", 2.0, 1),
                ("c2", "c3", "Explicit Xref", "xref", "low", "#38bdf8", 1.5, 0),
                ("c9", "c10", "Survival Link", "xref", "low", "#38bdf8", 1.5, 0),
                ("c10", "c6", "Survival of Cap", "semantic", "low", "#10b981", 1.5, 1),
                ("c10", "c7", "Survival of Indemnity", "semantic", "low", "#10b981", 1.5, 1),
                ("c11", "c12", "Indian Dispute Framework", "statutory", "medium", "#ec4899", 2.0, 0),
            ],
            "findings": [
                ("f1", "Liability Cap Voided by Uncapped Indemnity", "high", "contractual_conflict", "8.1 (Limitation of Liability)", "12.1 (IP Indemnity)",
                 "Section 8.1 caps all aggregate liability at ₹15,00,000, but Section 12.1 mandates uncapped indemnification without an express exclusion or coordination carveout.",
                 "Indian Contract Act, 1872 (Section 124/125): Indemnity is an absolute primary obligation; silent caps lead to protracted litigation on whether indemnification is covered by the liability ceiling.",
                 "Amend Section 8.1 to explicitly state: 'Except for indemnity obligations under Section 12.1, neither party's aggregate liability...'"),
                ("f2", "Illegal Cap on DPDPA Statutory Penalties", "statutory", "statutory_violation", "7.4 (Penalty Allocation)", "DPDPA, 2023",
                 "Section 7.4 attempts to cap regulatory fines and data breach liabilities under DPDPA 2023 at 3 months' fees (~₹3,00,000), while DPDPA statutory penalties reach up to ₹250 Crore.",
                 "Digital Personal Data Protection Act, 2023: Statutory penalties imposed by the Data Protection Board are public law obligations and cannot be contractually shifted or capped to evade compliance.",
                 "Revise Section 7.4 to clarify that statutory regulatory penalties assessed against a Data Fiduciary cannot be capped where direct fault/gross negligence of the processor is proven."),
                ("f3", "Bypassing Mandatory Pre-Litigation Mediation", "medium", "statutory_violation", "18.2 (Dispute Resolution)", "Mediation Act, 2023",
                 "Section 18.2 explicitly purports to exclude pre-litigation mediation in favor of immediate unilateral arbitration.",
                 "The Mediation Act, 2023: Commercial disputes are subject to institutional pre-litigation mediation unless urgent interim relief is sought from a court.",
                 "Include a tiered dispute resolution clause: Mandatory 30-day mediation under the Mediation Act, 2023 prior to invoking arbitration.")
            ]
        },

        "employment_nda": {
            "title": "Executive Employment & Restrictive Covenants",
            "category": "Employment & Labour",
            "jurisdiction": "India (Maharashtra)",
            "description": "Executive contract featuring an unenforceable 2-year post-termination non-compete covenant under Section 27 of ICA.",
            "clauses": [
                ("e1", "1.0", "Appointment & Role", "General", "Executive is engaged as Chief Technology Officer subject to terms and duties described herein.", 1),
                ("e2", "4.2", "Compensation & ESOPs", "Commercial", "Executive receives fixed base salary and vesting equity subject to the 4-year ESOP policy.", 2),
                ("e3", "6.1", "Confidentiality & Trade Secrets", "IP", "Executive shall never disclose proprietary algorithms, source code, or customer lists.", 3),
                ("e4", "8.1", "Post-Termination Non-Compete", "High Risk", "For a period of 24 months following termination of employment for any reason, Executive shall not engage in, advise, or consult for any competing fintech business in India.", 4),
                ("e5", "8.3", "Non-Solicitation of Employees", "Restrictive", "Executive shall not solicit or hire any company employee for 12 months post-termination.", 5),
                ("e6", "11.1", "Survival Clause", "Survival", "Provisions of Section 6 (Confidentiality) and Section 8.1 (Non-Compete) shall survive termination for 24 months.", 6),
                ("e7", "14.1", "Governing Law (India)", "Governing Law", "Governed exclusively by Indian law; courts of Mumbai have jurisdiction.", 7),
            ],
            "edges": [
                ("e4", "e6", "STATUTORY VOID: Sec 27 ICA", "statutory", "high", "#ec4899", 3.5, 0),
                ("e4", "e7", "Governing Law Conflict", "statutory", "high", "#ec4899", 2.5, 1),
                ("e3", "e6", "Valid Survival Xref", "xref", "low", "#38bdf8", 1.5, 0),
            ],
            "findings": [
                ("fe1", "Post-Termination Non-Compete is Void Ab Initio", "statutory", "statutory_violation", "8.1 (Non-Compete)", "11.1 (Survival)",
                 "Section 8.1 combined with survival clause 11.1 imposes a 24-month post-employment non-compete across India. Under Indian law, this clause is completely void and unenforceable.",
                 "Section 27, Indian Contract Act, 1872: 'Every agreement by which any one is restrained from exercising a lawful profession, trade or business... is to that extent void.' Established by Supreme Court in Percept D'Mark v. Zaheer Khan (2006).",
                 "Delete the post-termination non-compete restriction. Rely instead on strict non-disclosure of trade secrets (Section 6.1) and reasonable non-solicitation (Section 8.3), which remain defensible.")
            ]
        },

        "vendor_supply": {
            "title": "Vendor Supply Agreement (Liquidated Damages)",
            "category": "Procurement & Supply Chain",
            "jurisdiction": "India (Maharashtra)",
            "description": "Commercial supply agreement with penalty damages under Section 74 and unverified state e-stamping.",
            "clauses": [
                ("v1", "2.1", "Supply Deliverables", "Commercial", "Supplier shall deliver specialized hardware components in accordance with Schedule A.", 1),
                ("v2", "5.1", "Liquidated Damages & Penalties", "Risk", "Any delay in delivery beyond 3 business days incurs automatic liquidated damages of 30% of total order value, immediately forfeited from deposit.", 2),
                ("v3", "8.2", "Limitation of Supplier Liability", "Liability", "Supplier's total aggregate liability under this agreement shall be limited to 10% of total contract value.", 3),
                ("v4", "12.1", "Indian Stamp Duty & Stamping", "Compliance", "This agreement is executed on unstamped electronic stamp paper in Pune, Maharashtra.", 4),
                ("v5", "14.1", "Arbitration Clause", "Dispute", "Disputes to be arbitrated under Indian Arbitration Act. Lack of stamp duty shall not delay arbitral appointment.", 5),
            ],
            "edges": [
                ("v2", "v3", "CONFLICT: 30% Penalty vs 10% Cap", "conflict", "high", "#ef4444", 3.0, 0),
                ("v4", "v5", "7-Judge Bench Curable Stamp", "statutory", "medium", "#ec4899", 2.0, 1),
            ],
            "findings": [
                ("fv1", "Disproportionate Penalty under Section 74 ICA", "high", "statutory_violation", "5.1 (Liquidated Damages)", "8.2 (Liability Cap)",
                 "Section 5.1 imposes an automatic 30% forfeiture penalty for a 3-day delay, which is punitive and conflicts with the 10% liability cap in Section 8.2.",
                 "Section 74, Indian Contract Act, 1872 & Kailash Nath Associates v. DDA (2015): Agreed sums are not automatically payable upon breach; courts grant only reasonable compensation. Pure penalty clauses are struck down.",
                 "Replace automatic 30% forfeiture with a standard 0.5% per week delay liquidated damages formula capped at 10%, linked to demonstrable loss."),
                ("fv2", "Stamp Duty Curability & Arbitration Validity", "medium", "statutory_violation", "12.1 (Stamp Duty)", "14.1 (Arbitration)",
                 "The agreement notes electronic execution without verified Maharashtra Stamp Act duty.",
                 "Supreme Court 7-Judge Constitution Bench (Dec 2023): Unstamped arbitration agreements are not void ab initio, but stamp duty must be impounded and cured before the arbitral tribunal.",
                 "Ensure e-stamping under Maharashtra Stamp Act is completed and attached prior to commencement of supply operations.")
            ]
        },

        # --- LOREM IPSUM DEMO CONTRACT ---
        "lorem_ipsum_demo": {
            "title": "Lorem Ipsum Synthetic Legal Instrument",
            "category": "Synthetic Test & Stress Benchmark",
            "jurisdiction": "Simulated Jurisdiction (Latinate Code)",
            "description": "Standardised pseudo-Latin dummy contract structured with mock legal cross-clause conflicts and statutory assertions for UI/graph verification.",
            "clauses": [
                ("l1", "1.1", "Pactum Primarium (Definitions)", "General", "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Termini legales hic definiti.", 1),
                ("l2", "2.4", "Obligatio Praestationis (Performance)", "Commercial", "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Servitia praestari debent iuxta Clausulam 5.1.", 2),
                ("l3", "5.1", "Limitatio Responsibilitatis (Liability Cap)", "Liability", "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore. Tota responsibilitas partium non excedet centum aureos (100 AUR).", 3),
                ("l4", "8.2", "Clausula Indemnitatis (Indemnity)", "Indemnity", "Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit. Promissor defendet et indemnificabit sine ulla limitatione.", 4),
                ("l5", "10.3", "Pactum de Non-Competendo (Mock Restraint)", "High Risk", "Nulla pars exercebit negotium aemulum post terminationem contractus per spatium triginta mensium (Simulated Section 27 Restraint).", 5),
                ("l6", "13.1", "Superstitio Clausularum (Survival)", "Survival", "Clausula 8.2 (Indemnitas) et Clausula 10.3 (Non-Competendo) post terminationem pacti in perpetuum permanebunt.", 6),
                ("l7", "16.1", "Lex Applicanda (Governing Law)", "Governing Law", "Hoc pactum regetur legibus commercialibus syntheticis. Iurisdictio curiae metropolitanae electa est.", 7),
            ],
            "edges": [
                ("l3", "l4", "CONFLICT: Cap 100 AUR vs Indemnitas", "conflict", "high", "#ef4444", 3.0, 0),
                ("l5", "l6", "STATUTORY: Perpetua Restraint Void", "statutory", "high", "#ec4899", 3.0, 0),
                ("l2", "l3", "Referentia Xref 5.1", "xref", "low", "#38bdf8", 1.5, 0),
                ("l4", "l6", "Survival Link", "semantic", "low", "#10b981", 1.5, 1),
                ("l5", "l7", "Lex Applicanda Conflict", "statutory", "medium", "#ec4899", 2.0, 1),
            ],
            "findings": [
                ("fl1", "Conflictus Inter Limitationem et Indemnitatem", "high", "contractual_conflict", "5.1 (Limitatio Responsibilitatis)", "8.2 (Clausula Indemnitatis)",
                 "Clausula 5.1 responsum pecuniarium ad 100 AUR circumscribit, attamen Clausula 8.2 obligationem indemnificationis infinitam constituit.",
                 "Doctrina Contradictionis: Direct inter-clause clash between blanket liability ceiling and uncarved indemnity obligation.",
                 "Emendandum est: Addere exceptionem expressam in Clausula 5.1 respectu Clausulae 8.2."),
                ("fl2", "Pactum de Non-Competendo Post Terminationem", "statutory", "statutory_violation", "10.3 (Non-Competendo)", "13.1 (Superstitio)",
                 "Clausula 10.3 operatur ut prohibitio exercitii commercii post terminationem (30 menses). Similatur prohibitio sub Section 27 ICA 1872.",
                 "Regula Statutory: Any covenant restraining trade post-contract is invalid ab initio unless falling strictly within the sale-of-goodwill exception.",
                 "Expungenda est haec obligatio post-contractualis; limitetur ad protectionem secretorum comercialium tantum.")
            ]
        }
    }

    # Insert all contracts
    for c_id, c_data in DATA.items():
        cursor.execute("""
            INSERT INTO contracts (id, title, category, jurisdiction, description)
            VALUES (?, ?, ?, ?, ?);
        """, (c_id, c_data["title"], c_data["category"], c_data["jurisdiction"], c_data["description"]))

        for clause in c_data["clauses"]:
            cursor.execute("""
                INSERT INTO clauses (id, contract_id, clause_num, title, tag, text, ordinal)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (clause[0], c_id, clause[1], clause[2], clause[3], clause[4], clause[5]))

        for edge in c_data["edges"]:
            cursor.execute("""
                INSERT INTO graph_edges (contract_id, source_clause_id, target_clause_id, label, relation_type, severity, color, width, dashes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (c_id, edge[0], edge[1], edge[2], edge[3], edge[4], edge[5], edge[6], edge[7]))

        for finding in c_data["findings"]:
            cursor.execute("""
                INSERT INTO findings (id, contract_id, title, severity, relation_type, source_clause_ref, target_clause_ref, description, statute_citation, remedy_suggestion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (finding[0], c_id, finding[1], finding[2], finding[3], finding[4], finding[5], finding[6], finding[7], finding[8]))

    conn.commit()
    conn.close()
    print("Successfully seeded contracts database with 4 contracts (including Lorem Ipsum synthetic example)!")


def fetch_contract_graph_json(contract_id: str) -> dict:
    """Fetches all clauses, edges, and findings for a given contract ID from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM contracts WHERE id = ?;", (contract_id,))
    contract = cursor.fetchone()
    if not contract:
        conn.close()
        return {}

    cursor.execute("SELECT * FROM clauses WHERE contract_id = ? ORDER BY ordinal ASC;", (contract_id,))
    clauses = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM graph_edges WHERE contract_id = ?;", (contract_id,))
    edges = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT * FROM findings WHERE contract_id = ?;", (contract_id,))
    findings = [dict(row) for row in cursor.fetchall()]

    conn.close()
    return {
        "contract": dict(contract),
        "clauses": clauses,
        "edges": edges,
        "findings": findings
    }


def fetch_clause_embeddings(contract_id: str, model_name: str) -> list[dict]:
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT clause_id, model_name, dimension, vector_json FROM clause_embeddings "
        "WHERE contract_id = ? AND model_name = ? ORDER BY clause_id;",
        (contract_id, model_name),
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def store_clause_embeddings(contract_id: str, model_name: str, embeddings: list[dict]) -> None:
    conn = get_db_connection()
    conn.executemany(
        """INSERT OR REPLACE INTO clause_embeddings
           (clause_id, contract_id, model_name, dimension, vector_json)
           VALUES (?, ?, ?, ?, ?);""",
        [
            (
                item["clause_id"],
                contract_id,
                model_name,
                item["dimension"],
                json.dumps(item["vector"]),
            )
            for item in embeddings
        ],
    )
    conn.commit()
    conn.close()


def fetch_all_contracts_summary() -> list[dict]:
    """Fetches list of all contracts in database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, category, jurisdiction, description FROM contracts ORDER BY id;")
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


if __name__ == "__main__":
    init_db()
    seed_database()

