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
                ("c1", "1.1", "Definitions & Interpretation", "General", "(a) In this Master Services Agreement (the \"Agreement\"), capitalized terms shall have the meanings assigned herein:\n(i) \"Applicable Laws\" means all statutory enactments, rules, regulations, ordinances, and court decrees of India, specifically including the Information Technology Act, 2000 and the Digital Personal Data Protection Act, 2023.\n(ii) \"Authorized Users\" means personnel, contractors, or agents of Customer authorized to access the Cloud Services.\n(iii) \"Customer Data\" means all electronic data, personal data, transaction records, and confidential materials uploaded or processed by Customer through the Vendor platform.\n(iv) \"Data Fiduciary\" and \"Data Processor\" shall have the meanings ascribed to them under Section 2 of the Digital Personal Data Protection Act, 2023.\n(v) \"Service Levels\" means the performance benchmarks, uptime percentages, and availability criteria set forth in Schedule B.\n(b) Principles of Interpretation: References to any statute include statutory amendments, substitutions, and subsidiary rules issued thereunder. Headings are inserted for convenience of reference only.", 1),
                ("c2", "3.2", "Scope of Services & SLAs", "Commercial", "(a) Vendor shall provide enterprise cloud hosting, API access, and managed technical support services to Customer in accordance with the Service Level Agreements (SLAs) set forth herein.\n(b) Uptime Commitment: Vendor warrants that the Cloud Services shall maintain an aggregate monthly availability of not less than 99.9% (ninety-nine point nine percent) across each calendar month, measured 24 hours a day, 7 days a week, excluding Scheduled Maintenance Windows.\n(c) Maintenance Windows: Scheduled maintenance shall occur exclusively on Sundays between 02:00 IST and 04:00 IST, upon not less than 72 (seventy-two) hours prior written notice to Customer.\n(d) Technical Support Tiers: Vendor shall respond to Severity 1 (Critical Outage) incidents within 15 minutes of logging, and Severity 2 (Degraded Performance) incidents within 60 minutes.", 2),
                ("c3", "4.1", "Service Credits & Rebates", "Payment", "(a) In the event that Vendor fails to achieve the 99.9% monthly availability commitment specified in Section 3.2, Customer shall be entitled to liquidated Service Credits calculated as follows:\n(i) Availability between 99.0% and 99.8%: 2% credit against the applicable monthly billing invoice;\n(ii) Availability between 95.0% and 98.9%: 5% credit against the applicable monthly billing invoice;\n(iii) Availability below 95.0%: 10% credit against the applicable monthly billing invoice.\n(b) Cap on Service Credits: Subject to Section 3.2, Customer may deduct accumulated service credits up to a maximum aggregate ceiling of 5% (five percent) of total monthly billing for any single billing cycle. Service Credits shall constitute Customer's sole and exclusive financial remedy for routine availability shortfalls, without prejudice to termination rights for chronic default under Section 15.", 3),
                ("c4", "7.1", "Data Protection & Security", "Compliance", "(a) Statutory Recognition: The Parties expressly acknowledge and agree that in processing personal data under this Agreement, Customer functions as the \"Data Fiduciary\" and Vendor functions as the \"Data Processor\" within the meaning of the Digital Personal Data Protection Act, 2023 (DPDPA).\n(b) Technical Safeguards: Vendor shall implement and maintain rigorous administrative, technical, and physical safeguards—including AES-256 bit encryption at rest, TLS 1.3 encryption in transit, multi-factor authentication, and ISO/IEC 27001 certified data center controls—to protect Customer Data against unauthorized processing, accidental loss, disclosure, or destruction.\n(c) Data Breach Notification: In the event of any confirmed or suspected personal data breach, Vendor shall notify Customer in writing within 6 (six) hours of becoming aware of the incident, providing detailed telemetry to enable compliance with statutory reporting to the Data Protection Board of India.", 4),
                ("c5", "7.4", "Data Breach Penalty Allocation", "DPDPA Risk", "(a) Vendor's total aggregate liability arising out of or related to any personal data breach, security incident, regulatory non-compliance, or enforcement proceedings initiated by the Data Protection Board of India under the Digital Personal Data Protection Act, 2023 shall in no event exceed the total professional fees actually paid by Customer to Vendor in the 3 (three) months immediately preceding the incident.\n(b) In no event shall Vendor be liable for any statutory penalties, administrative fines, or punitive compensation levied by the Data Protection Board or any appellate tribunal beyond the aforesaid 3-month fee cap.", 5),
                ("c6", "8.1", "Limitation of Liability", "Liability", "(a) To the maximum extent permitted by applicable Indian law, neither Party's total aggregate liability arising out of, under, or in connection with this Agreement—whether in contract, tort (including negligence), strict liability, breach of statutory duty, indemnity, or otherwise—shall exceed INR 15,00,000 (Rupees Fifteen Lakhs only).\n(b) Exclusion of Consequential Damages: In no event shall either Party, its directors, officers, or affiliates be liable for any indirect, incidental, consequential, special, punitive, or exemplary damages, loss of profits, loss of data, loss of anticipated revenue, or business interruption, even if advised of the possibility of such damages in advance.", 6),
                ("c7", "12.1", "Intellectual Property Indemnity", "Indemnity", "(a) Vendor shall defend, indemnify, and hold harmless Customer, its parent companies, subsidiaries, directors, officers, and employees from and against any and all third-party claims, suits, actions, demands, liabilities, damages, judgments, losses, fines, costs, and expenses (including reasonable advocates' fees) arising out of or resulting from any allegation that the Cloud Services, software, documentation, or deliverables infringe, misappropriate, or violate any patent, copyright, trademark, trade secret, or other proprietary intellectual property right of any third party.\n(b) Uncapped Scope: The indemnification obligations of Vendor under this Section 12.1 shall apply without any financial limitation whatsoever, and shall not be subject to, qualified by, or reduced by any liability cap set forth in Section 8.1 or elsewhere in this Agreement.", 7),
                ("c8", "12.3", "Regulatory Fines Indemnity", "Indemnity", "(a) Customer warrants that all personal data transferred or made available to Vendor has been collected pursuant to explicit, itemized, and verifiable consent notices in strict compliance with Section 6 of the Digital Personal Data Protection Act, 2023.\n(b) Indemnity for Consent Deficiencies: Customer shall defend, indemnify, and hold harmless Vendor from and against all administrative fines, penalties, regulatory sanctions, and legal costs imposed upon Vendor by the Data Protection Board of India resulting from Customer's failure to maintain lawful consent records or provide valid statutory withdrawal mechanisms.", 8),
                ("c9", "15.1", "Term and Termination", "Term", "(a) Term: This Agreement shall commence on the Effective Date and shall continue in full force and effect for an initial term of 3 (three) years, unless terminated earlier in accordance with this Section 15.\n(b) Termination for Convenience: Either Party may terminate this Agreement for convenience and without assigning any reason upon giving not less than 60 (sixty) days prior written notice to the other Party.\n(c) Termination for Cause: Either Party may terminate this Agreement immediately by written notice if the other Party commits a material breach which remains uncured for 30 (thirty) days following written notice of default, or becomes insolvent, bankrupt, or enters into liquidation.\n(d) Transition Assistance: Upon termination, Vendor shall provide full data extraction assistance for 30 days to facilitate migration.", 9),
                ("c10", "15.4", "Survival of Provisions", "Survival", "(a) The expiration or termination of this Agreement for any reason shall not affect or prejudice any accrued rights, remedies, obligations, or liabilities of either Party existing as of the date of termination.\n(b) Indefinite Survival: The provisions of Section 7 (Data Protection & Security), Section 8 (Limitation of Liability), Section 12 (Indemnification), Section 13 (Confidentiality), Section 15.4 (Survival), and Section 18 (Dispute Resolution & Governing Law) shall survive termination of this Agreement indefinitely and remain fully enforceable thereafter.", 10),
                ("c11", "18.1", "Governing Law & Jurisdiction", "Governing Law", "(a) Governing Law: This Agreement, and all claims or causes of action (whether in contract, tort, or statute) that may be based upon, arise out of, or relate to this Agreement, shall be governed by, and enforced in accordance with, the substantive and procedural laws of the Republic of India.\n(b) Jurisdiction: Subject to the dispute resolution provisions of Section 18.2, the competent civil courts located at Bengaluru, Karnataka shall have exclusive jurisdiction over all legal proceedings arising under this Agreement.", 11),
                ("c12", "18.2", "Dispute Resolution (Arbitration)", "Dispute", "(a) In the event of any dispute, difference, controversy, or claim arising out of or relating to this Agreement, including any question regarding its existence, validity, or termination, the Parties agree to resolve the dispute through binding arbitration administered under the Arbitration and Conciliation Act, 1996.\n(b) Tribunal Composition & Seat: The arbitration shall be conducted by a sole arbitrator mutually appointed by the Parties. The seat and venue of arbitration shall be Bengaluru, Karnataka, India, and the language shall be English.\n(c) Exclusion of Pre-Litigation Mediation: The Parties explicitly agree to exclude and bypass pre-litigation commercial mediation under The Mediation Act, 2023, and agree that all disputes shall proceed directly and immediately to unilateral arbitration.", 12),
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
                ("e1", "1.0", "Appointment & Role", "General", "(a) The Company hereby engages Executive as Chief Technology Officer (CTO), and Executive accepts such executive employment subject to the terms and conditions of this Agreement.\n(b) Executive shall devote substantially all professional business time, attention, skill, and best efforts to the business affairs, technological innovations, and operational growth of the Company in Maharashtra, India.\n(c) Fiduciary Duties: Executive owes the Company the highest fiduciary duties of loyalty, good faith, and confidential stewardship.", 1),
                ("e2", "4.2", "Compensation & ESOPs", "Commercial", "(a) Executive agrees that all technological inventions, computer software, algorithms, architectures, neural network models, patentable workflows, trade secrets, and proprietary methodologies conceived, developed, or reduced to practice by Executive during employment shall constitute \"work made for hire\" under the Indian Copyright Act, 1957.\n(b) Absolute Assignment: Executive irrevocably assigns to Company all right, title, and interest worldwide in all Intellectual Property Rights created in connection with Company operations, and waives all moral rights to the fullest extent permitted by law.", 2),
                ("e3", "6.1", "Confidentiality & Trade Secrets", "IP", "(a) Executive shall hold in strictest confidence and shall not disclose, publish, or use for personal gain any Confidential Information of the Company, including proprietary source code, customer databases, algorithmic weights, and commercial trade secrets, both during employment and at all times thereafter without limitation in time.\n(b) Permitted Disclosures: Disclosures compelled by judicial subpoena or statutory authority under Indian law shall not constitute a breach, provided advance notice is delivered to Company.", 3),
                ("e4", "8.1", "Post-Termination Non-Compete", "High Risk", "(a) For a period of twenty-four (24) months following the termination of Executive's employment for any reason (whether voluntary or involuntary, with or without cause), Executive shall not directly or indirectly engage in, manage, advise, invest in, or perform services for any competing enterprise or technology venture operating within the Union of India.\n(b) Legal Audit Finding: Void ab initio under Section 27, Indian Contract Act, 1872. Indian courts reject the doctrine of reasonableness for post-employment restrictive covenants.", 4),
                ("e5", "8.3", "Non-Solicitation of Employees", "Restrictive", "(a) Section 6 (Confidentiality) and Section 8 (Post-Termination Non-Compete) shall survive termination of Executive's employment for the full duration specified therein, and shall remain enforceable notwithstanding any claim of wrongful termination.\n(b) Dependency Nexus: Surfaced in LegalAgent benchmark as termination_survival_dependency risk linking an invalid restraint into perpetuity.", 5),
                ("e6", "11.1", "Survival Clause", "Survival", "(a) Governing Law: This Agreement shall be governed by and construed in accordance with the substantive laws of the Republic of India.\n(b) Jurisdiction: The courts situated in Mumbai, Maharashtra shall have exclusive jurisdiction over all claims and disputes arising out of this Agreement.", 6),
                ("e7", "14.1", "Governing Law (India)", "Governing Law", "(a) In the event of any executive dispute arising out of this Agreement, the Parties shall attempt amicable resolution within 30 days before initiating arbitration under the Arbitration and Conciliation Act, 1996 in Mumbai, India.", 7),
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
                ("v1", "2.1", "Supply Deliverables", "Commercial", "(a) Supplier agrees to manufacture, package, inspect, and deliver specialized industrial automation hardware components and robotics tooling to Purchaser in accordance with the technical specifications and delivery schedules set forth in Purchase Orders issued under Schedule A.\n(b) Quality Assurance: All components shall strictly conform to ISO 9001 quality certifications and shall be free from manufacturing, design, and material defects.", 1),
                ("v2", "5.1", "Liquidated Damages & Penalties", "Risk", "(a) Any delay in delivery of components beyond 3 (three) business days from the scheduled delivery date shall incur automatic liquidated damages equal to 30% (thirty percent) of the total order value, immediately forfeited from Purchaser's security deposit without proof of actual damage.\n(b) Statutory Audit Finding: Flagged as an unenforceable penalty in terrorem under Section 74 of the Indian Contract Act, 1872 and the Supreme Court precedent in Kailash Nath Associates v. DDA (2015).", 2),
                ("v3", "8.2", "Limitation of Supplier Liability", "Liability", "(a) Supplier's total cumulative aggregate liability arising out of, under, or in connection with this Agreement—including breach of warranty, delayed delivery, or product liability—shall be strictly limited to an amount not exceeding 10% (ten percent) of the total fees actually received by Supplier under the applicable Purchase Order.\n(b) Direct Conflict: Clashes directly with Section 5.1 which attempts to impose a 30% penalty forfeiture against the 10% total liability cap.", 3),
                ("v4", "12.1", "Indian Stamp Duty & Stamping", "Compliance", "(a) This commercial supply agreement has been executed electronically without physical or electronic stamp paper validation under the Maharashtra Stamp Act, 1958.\n(b) The Parties agree that lack of formal stamping shall not affect enforceability and agree to waive all statutory impounding procedures before judicial authorities.", 4),
                ("v5", "14.1", "Arbitration Clause", "Dispute", "(a) Any dispute or controversy arising under this Agreement shall be finally settled by sole arbitration in Pune, Maharashtra under the Arbitration and Conciliation Act, 1996.\n(b) Stamping Interplay: In accordance with the Supreme Court 7-Judge Constitution Bench ruling (Dec 2023), unstamped arbitration agreements are not void ab initio, but stamp duty must be impounded and cured prior to substantive adjudication.", 5),
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

        # --- PUNE METRO LINE III PPP CONCESSION AGREEMENT (2019) ---
        "pune_metro_ppp": {
            "title": "Pune Metro Line III — PPP Concession Agreement (2019)",
            "category": "Infrastructure & PPP",
            "jurisdiction": "India (Maharashtra)",
            "description": "Signed concession agreement between PMRDA and Pune IT City Metro Rail Limited for Hinjawadi–Shivajinagar metro line. Real Government of India PPP contract with adversarial clauses included for risk detection demonstration.",
            "clauses": [
                ("pm1", "1.1", "Definitions & Interpretation", "General", "(a) In this Concession Agreement, the following capitalised terms shall have the meanings assigned herein:\n(i) \"Authority\" means Pune Metropolitan Region Development Authority (PMRDA), constituted under Section 3 of the Maharashtra Metropolitan Region Development Authority Act, 2016.\n(ii) \"Concessionaire\" means Pune IT City Metro Rail Limited, a special purpose vehicle incorporated under the Companies Act, 2013 by the Consortium of TRIL Urban Transport Private Limited and Siemens Project Ventures GmbH.\n(iii) \"Project\" means the design, finance, construction, operation, and maintenance of Pune Metro Line III (Hinjawadi to Shivajinagar), comprising 23.205 km of elevated dual-track rail system on DBFOT basis.\n(iv) \"Applicable Laws\" means all Indian federal and state statutes, enactments, rules, notifications, and judicial orders in force from time to time.\n(v) \"Commercial Operation Date\" or \"COD\" means the date on which the Completion Certificate is issued by the Independent Engineer pursuant to Article 15.\n(vi) \"Right of Way\" means the constructive, unencumbered possession of the Site granted by the Authority to the Concessionaire.", 1),
                ("pm2", "4.1", "Concession Grant & Exclusivity", "Commercial", "(a) Grant of Exclusive Concession: The Authority hereby grants to the Concessionaire, and the Concessionaire hereby accepts, the exclusive right, license, and authority for a period of 35 (thirty-five) years commencing from the Appointed Date (the \"Concession Period\") to develop, finance, design, construct, equip, operate, maintain, and transfer the Rail System.\n(b) Corridor Exclusivity: The Concessionaire shall have the exclusive right to operate passenger transit rail services along the Hinjawadi–Shivajinagar alignment.\n(c) Protected Boundary: The Authority covenants that it shall not sponsor, construct, or license any competing mass rapid transit rail alignment within a 2 (two) kilometre radius parallel to Line III during the initial 15 years of commercial operation without the prior written consent of the Concessionaire.", 2),
                ("pm3", "8.2", "Revenue Share & Ridership Guarantee", "Payment", "(a) Concession Fee and Revenue Share: The Concessionaire shall pay to the Authority an annual Concession Fee of INR 1 (Rupee One) per annum, plus the revenue share percentage of Gross Revenue specified in Schedule 3.\n(b) Minimum Ridership Guarantee: The Authority guarantees to the Concessionaire a minimum design ridership threshold of 80,000 (eighty thousand) passenger trips per day for Operating Years 1 through 10.\n(c) Shortfall Compensation: If the actual audited daily ridership falls below the guaranteed threshold due to macro-economic or feeder connectivity factors outside the Concessionaire's control, the Authority shall compensate the shortfall from the Grant Annuity Escrow Fund within 60 (sixty) days of Independent Engineer audit.", 3),
                ("pm4", "14.1", "Force Majeure & Risk Allocation", "Risk", "(a) Definition of Force Majeure: A Force Majeure Event shall mean any event or circumstance beyond the reasonable control of the affected Party which could not have been prevented by reasonable foresight or due diligence, categorized as Non-Political Events (natural catastrophes, earthquakes, pandemics), Indirect Political Events (nationwide civil unrest, strikes), and Direct Political Events (unlawful expropriation or regulatory revocation).\n(b) Performance Relief: The affected Party shall be excused from performance of its obligations to the extent prevented by the Force Majeure Event.\n(c) Risk Allocation: Land acquisition risks and environmental Right-of-Way handover delays shall reside solely with the Authority. Unforeseen construction cost overruns up to 5% variation remain the Concessionaire's responsibility.", 4),
                ("pm5", "18.3", "Termination for Authority Default", "Term", "(a) In the event that the Authority commits a material breach of this Agreement—including failure to deliver 100% Right of Way within statutory timelines, default in payment of Grant Annuity, or wrongful revocation of Applicable Permits—the Concessionaire may issue a 90-day Notice of Intention to Terminate.\n(b) Senior Lenders' Cure: The Authority and Senior Lenders shall have a 90-day cure period to remedy the default.\n(c) Termination Payment Formula: Upon termination for Authority Default, the Authority shall pay to the Concessionaire within 60 days: (i) 100% of Debt Due; (ii) 150% of Adjusted Equity; and (iii) the Adjusted Depreciated Value of rolling stock and signaling installations.", 5),
                ("pm6", "22.1", "Dispute Resolution — Arbitration", "Dispute", "(a) Any dispute, controversy, or claim arising out of or in connection with this Agreement shall be resolved through binding arbitration administered under the Arbitration and Conciliation Act, 1996.\n(b) Arbitral Tribunal: The arbitral tribunal shall consist of 3 (three) arbitrators: one appointed by each Party, and the third presiding arbitrator chosen by the two appointed arbitrators.\n(c) Seat and Exclusive Jurisdiction: The seat and legal venue of arbitration shall be Pune, Maharashtra, India. The courts of Pune and the High Court of Judicature at Bombay shall have exclusive jurisdiction over supervisory and enforcement proceedings.", 6),
                ("pm7", "91.1", "Limitation of Liability (Adversarial Test Clause)", "Liability", "(a) The aggregate liability of the Authority arising out of or in connection with this Concession Agreement shall not exceed INR 1,000 (Rupees One Thousand only) for any and all claims, including without limitation claims founded in fraud, death, personal injury, gross negligence, wilful misconduct, and statutory regulatory penalties.\n(b) Adversarial Test Clause Note: This clause is a synthetic addition appended to the signed 2019 agreement to evaluate automated risk detection pipelines against Indian Contract Act Section 23 public policy rules.", 7),
                ("pm8", "91.2", "Unlimited Indemnity (Adversarial Test Clause)", "Indemnity", "(a) The Concessionaire shall defend, indemnify, save, and hold harmless the Authority, its officers, agents, and successors against every suit, claim, damage, fine, penalty, and expense without any financial limitation whatsoever, and notwithstanding any cap on liability contained in Clause 91.1 or elsewhere in this Agreement.\n(b) Adversarial Test Clause Note: Synthetically appended clause creating an internal contradiction with Clause 91.1 liability ceiling and eliminating bilateral reciprocal protection.", 8),
                ("pm9", "91.3", "Post-Termination Non-Compete (Adversarial Test Clause)", "High Risk", "(a) For a period of 36 (thirty-six) months following the expiration or termination of this Agreement for any reason whatsoever, the Concessionaire, its sponsors, and affiliates shall not directly or indirectly compete with, advise, consult for, or participate in any competing mass transit, metro rail, or transport infrastructure business within the territory of India.\n(b) Adversarial Test Clause Note: Synthetically planted covenant. Void ab initio under Section 27 of the Indian Contract Act, 1872 (Percept D'Mark v. Zaheer Khan, 2006).", 9),
                ("pm10", "91.4", "Survival of Restrictions (Adversarial Test Clause)", "Survival", "(a) Clauses 91.2 (Unlimited Indemnity) and 91.3 (Post-Termination Non-Compete) shall survive termination of this Agreement indefinitely and remain fully enforceable after termination, notwithstanding any other provision or statutory determination.\n(b) Adversarial Test Clause Note: Synthetically planted cross-clause dependency risk. Perpetuates unlawful restraint of trade beyond the life of the contract.", 10),
                ("pm11", "91.6", "Capped DPDPA Penalties (Adversarial Test Clause)", "DPDPA Risk", "(a) Any penalty, fine, administrative levy, or sanction imposed on either Party under the Digital Personal Data Protection Act, 2023 in connection with the Rail System, AFC smart ticketing, or biometric passenger tracking shall be contractually capped and limited to INR 10,000 (Rupees Ten Thousand only) between the Parties.\n(b) Adversarial Test Clause Note: Synthetically planted statutory violation. DPDPA Section 33 penalties reach up to INR 250 Crore and cannot be contractually capped.", 11),
                ("pm12", "27.1", "Governing Law", "Governing Law", "(a) This Agreement shall be construed, interpreted, and governed exclusively by the laws of the Republic of India.\n(b) The courts of Pune and the High Court of Judicature at Bombay shall have exclusive jurisdiction over all matters arising hereunder that are not subject to arbitration under Clause 22.1.", 12),
            ],
            "edges": [
                ("pm7", "pm8", "CRITICAL CONFLICT: INR 1,000 Cap vs Unlimited Indemnity", "conflict", "high", "#ef4444", 3.0, 0),
                ("pm9", "pm10", "STATUTORY VOID: Section 27 ICA — Post-Termination Restraint", "statutory", "high", "#ec4899", 3.0, 0),
                ("pm11", "pm8", "DPDPA Cap Contradiction vs Indemnity Scope", "statutory", "high", "#ec4899", 2.5, 1),
                ("pm7", "pm12", "Illusory Cap vs Indian Courts — Enforceability Gap", "semantic", "low", "#10b981", 1.5, 1),
                ("pm5", "pm6", "Termination Trigger — Arbitration Nexus", "xref", "low", "#38bdf8", 1.5, 0),
                ("pm3", "pm4", "Revenue Guarantee vs Force Majeure Risk Interaction", "semantic", "low", "#10b981", 1.5, 1),
            ],
            "findings": [
                ("fpm1", "Illusory Liability Cap vs Uncapped Indemnity (Clauses 91.1/91.2)", "high", "contractual_conflict", "91.1 (Limitation of Liability)", "91.2 (Unlimited Indemnity)",
                 "Clause 91.1 caps Authority liability at INR 1,000 — even for fraud, death, and statutory violations — while Clause 91.2 simultaneously mandates unlimited indemnification from the Concessionaire with an express 'notwithstanding' override of Clause 91.1. This creates an irreconcilable and commercially absurd conflict.",
                 "Indian Contract Act, 1872 (Sections 124–125): Indemnity is a primary, independent obligation that cannot be silently subordinated to a liability cap unless an express carveout is included. An INR 1,000 cap on fraud and personal injury liability is contrary to public policy under Section 23 ICA.",
                 "Delete Clause 91.1 in its entirety. Replace with a commercially realistic aggregate liability cap (e.g., equal to Total Project Cost or fees paid in the preceding 24 months), with express carveouts for fraud, wilful misconduct, personal injury/death, and indemnity obligations under Clause 91.2."),
                ("fpm2", "Post-Termination Non-Compete Void Ab Initio — Section 27 ICA (Clauses 91.3/91.4)", "statutory", "statutory_violation", "91.3 (Non-Compete)", "91.4 (Survival)",
                 "Clause 91.3 imposes a 36-month post-termination restriction on participating in any competing infrastructure business in India. Clause 91.4 purports to extend this restriction indefinitely after termination. Both provisions are void and unenforceable under Section 27 of the Indian Contract Act, 1872.",
                 "Section 27, Indian Contract Act, 1872: Every agreement restraining a person from exercising a lawful profession, trade, or business is void. Confirmed by the Supreme Court in Percept D'Mark (India) Pvt. Ltd. v. Zaheer Khan (2006) 4 SCC 227, which held that post-employment non-compete covenants have no place in Indian law.",
                 "Delete Clauses 91.3 and 91.4. Protect legitimate interests through (a) trade secret and IP non-disclosure obligations under a separate NDA, (b) non-solicitation of key PMRDA personnel for 12 months (enforceable), and (c) assignment restrictions on project-specific intellectual property."),
                ("fpm3", "Contractual Cap on DPDPA Statutory Penalties is Unenforceable (Clause 91.6)", "statutory", "statutory_violation", "91.6 (Capped DPDPA Penalties)", "DPDPA 2023",
                 "Clause 91.6 purports to limit DPDPA statutory penalties to INR 10,000 between the parties. The Digital Personal Data Protection Act, 2023 empowers the Data Protection Board to levy penalties up to INR 250 Crore. These are public-law sanctions that cannot be contractually limited by private agreement.",
                 "Digital Personal Data Protection Act, 2023 (Schedule: Grounds for penalties — Items 1–7): Penalties for significant data fiduciary violations range from INR 50 Crore to INR 250 Crore. Parties cannot contract out of regulatory enforcement obligations owed to a statutory authority.",
                 "Delete Clause 91.6. The parties may separately agree on contractual indemnification for losses caused by the other party's data breach (e.g., Concessionaire causing a passenger data breach triggers indemnity to PMRDA for civil liability), but cannot limit the quantum of fines imposed directly by the Data Protection Board of India."),
            ]
        },

        # --- MODEL 4-LANING HIGHWAY CONCESSION AGREEMENT (NHAI MODEL CONTRACT) ---
        "highway_concession": {
            "title": "NHAI Model Concession Agreement — 4-Laning of National Highways (BOT-Toll)",
            "category": "Infrastructure & PPP",
            "jurisdiction": "India (Central Government — NHAI)",
            "description": "Government of India Model Concession Agreement for four-laning of national highways under Build-Operate-Transfer (Toll) mode. Issued by Ministry of Road Transport & Highways through NHAI. Includes standard risk matrix, toll terms, and termination payment framework. Demonstrates a well-structured PPP with Indian-law compliant liquidated damages.",
            "clauses": [
                ("hw1", "1.1", "Definitions & Interpretation", "General", "(a) The National Highways Authority of India (\"NHAI\") hereby grants to the Concessionaire the exclusive right, concession, and authority for a period of 25 (twenty-five) years to design, engineer, finance, construct, operate, and maintain the Four-Laning of National Highway on Build-Operate-Transfer (BOT-Toll) mode.\n(b) Right of Way: NHAI warrants that it shall deliver not less than 80% of unencumbered Right of Way prior to the Appointed Date.", 1),
                ("hw2", "5.1", "Grant of Concession (BOT-Toll)", "Commercial", "(a) Concession Fee: The Concessionaire shall pay to NHAI an annual concession fee of INR 1 (Rupee One) per annum, plus premium revenue share commencing from the 5th year of commercial operation as detailed in Schedule C.", 2),
                ("hw3", "10.2", "Toll Rates & Traffic Guarantee", "Payment", "(a) Toll Collection Rights: The Concessionaire shall have the exclusive right and authority to demand, collect, and appropriate toll fees from commercial and passenger vehicles using the Project Highway in strict accordance with the National Highways Fee Rules, 2008.", 3),
                ("hw4", "14.1", "Construction Obligations & Milestones", "Commercial", "(a) Independent Engineer: An Independent Engineer appointed from the NHAI approved panel shall inspect construction works, verify safety compliance, and issue Completion Certificates upon satisfaction of IRC specifications.", 4),
                ("hw5", "15.3", "Liquidated Damages for Construction Delay", "Risk", "(a) Liquidated Damages for Delay: In the event of failure to achieve completion by Scheduled Four-Laning Date, Concessionaire shall pay damages at 0.1% per week of Total Project Cost, capped at 10% of TPC, representing a genuine pre-estimate of toll diversion losses.", 5),
                ("hw6", "16.1", "Limitation of Concessionaire Liability", "Liability", "(a) Aggregate Liability Ceiling: Except for indemnity obligations in Article 31, neither Party's total liability under this Concession Agreement shall exceed the total Performance Security value deposited under Article 8.", 6),
                ("hw7", "18.1", "Indemnity by Concessionaire", "Indemnity", "(a) Indemnification: Concessionaire shall indemnify and save harmless NHAI against all third-party environmental claims, structural collapses, and accident liabilities arising from roadway defects.", 7),
                ("hw8", "23.1", "Termination for Concessionaire Default", "Term", "(a) Termination for Concessionaire Default: Upon termination for Concessionaire Default, NHAI shall pay 90% (ninety percent) of Senior Debt Due; all Sponsor equity and subordinated shareholder loans shall be entirely forfeited to the Authority.", 8),
                ("hw9", "23.3", "Termination for NHAI Default", "Term", "(a) Termination for NHAI Default: Upon termination for NHAI Default, NHAI shall pay: (i) 100% of Debt Due; (ii) Adjusted Equity; and (iii) 150% of Sponsor's Base Return across the remaining concession period.", 9),
                ("hw10", "28.1", "Dispute Resolution Board & Arbitration", "Dispute", "(a) Tiered Dispute Resolution: All disputes shall be referred first to the Dispute Resolution Board (DRB) under Schedule G. DRB recommendations bind the parties unless challenged by formal arbitration within 30 days under the Arbitration and Conciliation Act, 1996 in New Delhi.", 10),
                ("hw11", "30.1", "Governing Law", "Governing Law", "(a) Governing Law: This Agreement shall be governed by and construed in accordance with the laws of India. The courts of New Delhi shall have exclusive jurisdiction over supervisory matters.", 11),
            ],
            "edges": [
                ("hw6", "hw7", "Coherent Cap Carveout for Indemnity (Well-Drafted)", "semantic", "low", "#10b981", 1.5, 1),
                ("hw5", "hw6", "LD Cap Subordinated to Aggregate Cap — Consistent", "xref", "low", "#38bdf8", 1.5, 0),
                ("hw8", "hw9", "Termination Payment Asymmetry — NHAI vs Concessionaire Default", "conflict", "medium", "#f59e0b", 2.0, 1),
                ("hw3", "hw5", "Revenue Guarantee — Delay Penalty Interaction", "semantic", "low", "#10b981", 1.5, 1),
                ("hw10", "hw11", "DRB-Arbitration-Courts Tiered Dispute Mechanism", "xref", "low", "#38bdf8", 1.5, 0),
            ],
            "findings": [
                ("fhw1", "Asymmetric Termination Payments Disadvantage Concessionaire", "medium", "contractual_conflict", "23.1 (Concessionaire Default Termination)", "23.3 (NHAI Default Termination)",
                 "On Concessionaire default (Clause 23.1), the termination payment covers only 90% of senior debt — equity is entirely forfeited. On NHAI default (Clause 23.3), the Concessionaire recovers full debt, Adjusted Equity, AND 150% Sponsor Return. This asymmetry significantly disadvantages private parties and has been litigated in multiple High Courts.",
                 "Indian Contract Act, 1872 (Section 74) and NHAI v. Sole Arbitrator (various HC judgments 2019–2024): Courts have scrutinised asymmetric termination matrices in BOT agreements and in some cases granted equity recovery even under concessionaire-default scenarios where Authority breach was contributory.",
                 "Re-negotiate Clause 23.1 to include a proportional equity recovery mechanism (e.g., 50–75% of Adjusted Equity), reduced by a fault-severity factor certified by an Independent Engineer — rather than a blanket forfeiture of all equity on any Concessionaire Default event."),
                ("fhw2", "Liquidated Damages Rate Requires Contemporaneous Loss Evidence", "medium", "statutory_violation", "15.3 (Liquidated Damages for Delay)", "16.1 (Aggregate Liability Cap)",
                 "Clause 15.3 states liquidated damages at 0.1% per week capped at 10% of Total Project Cost represent 'a genuine pre-estimate of delay loss.' However, no contemporaneous evidence of how this rate was calculated is referenced in the Agreement or Schedules.",
                 "Section 74, Indian Contract Act, 1872 & Kailash Nath Associates v. DDA (2015) 4 SCC 136: For liquidated damages to be enforceable, they must represent a genuine pre-estimate of loss. The party claiming LD must prove actual loss suffered (unless the clause expressly says it is a genuine pre-estimate and is reasonable). Clauses stating 'genuine pre-estimate' without evidentiary basis are still subject to judicial reduction.",
                 "Prepare and maintain a cost model or technical note calculating actual delay costs (including opportunity cost of toll revenue loss, financing charges, and administrative overhead) as the basis for the 0.1% per week rate. Attach the calculation as a confidential annex to support enforceability in any arbitration."),
            ]
        },

        # --- LOREM IPSUM DEMO CONTRACT ---
        "lorem_ipsum_demo": {
            "title": "Lorem Ipsum Synthetic Legal Instrument",
            "category": "Synthetic Test & Stress Benchmark",
            "jurisdiction": "Simulated Jurisdiction (Latinate Code)",
            "description": "Standardised pseudo-Latin dummy contract structured with mock legal cross-clause conflicts and statutory assertions for UI/graph verification.",
            "clauses": [
                ("l1", "1.1", "Pactum Primarium (Definitions)", "General", "(a) In hoc Pacto Primario, termini subsequentes significatum habent: \"Lex Applicanda\" significat omnes regulas syntheticis legibus comprehensas; \"Promissor\" et \"Acceptor\" partes designant.\n(b) Interpretationis Regulae: Verba singularia pluralia includunt, et tituli solummodo ad facilitatem legendi adhibentur.", 1),
                ("l2", "2.4", "Obligatio Praestationis (Performance)", "Commercial", "(a) Promissor praestabit servitia commercialia iuxta specificationes in Tabula A descriptas, cum gradu fidelitatis non minore quam 99.9% mensura computata.\n(b) Defectus in servitiis corrigi debent intra quadraginta et octo horas post notificationem scriptam.", 2),
                ("l3", "5.1", "Limitatio Responsibilitatis (Liability Cap)", "Liability", "(a) Tota responsibilitas Promissoris erga Acceptorem ex quacumque causa oritur sub hoc pacto non excedet centum aureos (100 AUR).\n(b) Exclusio Damnorum: Nullatenus pars ulla tenebitur ad damna indirecta, specialia, vel consequentia solvere.", 3),
                ("l4", "8.2", "Clausula Indemnitatis (Indemnity)", "Indemnity", "(a) Promissor defendet et indemnificabit Acceptorem contra omnes actiones tertiarum partium sine ulla limitatione pecuniaria et non obstante Clausula 5.1.\n(b) Direct Clash: Directus conflictus inter limitationem responsibilitatis (100 AUR) et obligationem indemnificationis infinitam.", 4),
                ("l5", "10.3", "Pactum de Non-Competendo (Mock Restraint)", "High Risk", "(a) Nulla pars exercebit negotium aemulum post terminationem contractus per spatium triginta mensium in toto territorio nationali.\n(b) Simulatio Restraint: Simulat clausulam prohibitam sub Sectione 27 Legis Contractuum Indicae.", 5),
                ("l6", "13.1", "Superstitio Clausularum (Survival)", "Survival", "(a) Clausula 8.2 (Indemnitas) et Clausula 10.3 (Non-Competendo) post terminationem pacti in perpetuum permanebunt.\n(b) Perpetuitas: Invalida perpetuatio obligationum post exitum contractus.", 6),
                ("l7", "16.1", "Lex Applicanda (Governing Law)", "Governing Law", "(a) Hoc pactum regetur legibus commercialibus syntheticis. Iurisdictio curiae metropolitanae electa est ad omnes lites dirimendas.", 7),
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

