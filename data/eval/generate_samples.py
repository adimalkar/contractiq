"""Generate synthetic enterprise contract PDFs with realistic clauses for evaluation and testing."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

OUTPUT_DIR = Path(__file__).parent / "sample_contracts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def build_pdf(filename: str, title: str, pages_data: list[list[tuple[str, str]]]) -> Path:
    """Build a multi-page PDF document."""
    pdf_path = OUTPUT_DIR / filename
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#1e1e2f"),
        spaceAfter=12,
        alignment=1,
    )
    section_style = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#2a2a4a"),
        spaceBefore=14,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#333333"),
        spaceAfter=8,
    )

    story = []

    # Title Banner
    story.append(Paragraph(title, title_style))
    story.append(
        HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#7c5cfc"), spaceAfter=15)
    )

    for page_idx, sections in enumerate(pages_data):
        if page_idx > 0:
            story.append(PageBreak())

        for header, content in sections:
            if header:
                story.append(Paragraph(header, section_style))
            story.append(Paragraph(content, body_style))
            story.append(Spacer(1, 4))

    doc.build(story)
    print(f"Generated contract PDF: {pdf_path}")
    return pdf_path


def generate_all_contracts():
    """Create the 5 realistic evaluation contracts."""

    # 1. Master Services Agreement (MSA)
    build_pdf(
        "sample_msa.pdf",
        "MASTER SERVICES AGREEMENT",
        [
            [
                (
                    "PREAMBLE & RECITALS",
                    "This Master Services Agreement ('Agreement') is entered into as of March 1, 2024 ('Effective Date'), by and between Acme Enterprise Solutions Inc., a Delaware corporation having its principal place of business at 100 Enterprise Way, Suite 400, New York, NY 10001 ('Client'), and CloudTech Global Systems LLC, a California limited liability company having its office at 500 Silicon Ave, San Jose, CA 95110 ('Provider').",
                ),
                (
                    "ARTICLE 1: SCOPE OF SERVICES",
                    "1.1 Statements of Work. Provider shall provide software engineering, cloud architecture, and cybersecurity management services as described in individual Statements of Work executed under this Agreement.\n1.2 Standard of Performance. Provider warrants that all services shall be performed in a professional, workmanlike manner in accordance with prevailing industry standards.",
                ),
                (
                    "ARTICLE 2: TERM AND TERMINATION",
                    "2.1 Initial Term. The initial term of this Agreement shall commence on the Effective Date and continue for a period of three (3) years.\n2.2 Renewal. This Agreement shall automatically renew for successive one (1) year periods unless either party gives written notice of non-renewal at least sixty (60) days prior to the expiration of the then-current term.\n2.3 Termination for Cause. Either party may terminate this Agreement immediately upon written notice if the other party breaches any material term and fails to cure such breach within thirty (30) days of receiving written notice.",
                ),
            ],
            [
                (
                    "ARTICLE 3: FEES, INVOICING & PAYMENT",
                    "3.1 Fees. Client agrees to compensate Provider in accordance with the fee schedules specified in the applicable Statement of Work.\n3.2 Invoicing Schedule. Invoices shall be submitted electronically on the first business day of each calendar month.\n3.3 Payment Terms. All undisputed invoices are payable net forty-five (45) days from the date of invoice receipt.\n3.4 Late Payments. Overdue payments shall accrue interest at the rate of 1.5% per month or the maximum rate permitted by law, whichever is less.",
                ),
                (
                    "ARTICLE 4: INTELLECTUAL PROPERTY RIGHTS",
                    "4.1 Client IP. Client retains sole ownership of all pre-existing data, customer records, and proprietary materials provided to Provider.\n4.2 Work Product Ownership. All custom code, deliverables, documentation, and algorithms developed specifically for Client under any SOW shall constitute 'Work Made for Hire' and belong exclusively to Client upon full payment.",
                ),
            ],
            [
                (
                    "ARTICLE 5: CONFIDENTIALITY & DATA SECURITY",
                    "5.1 Confidential Information. Each party agrees to protect the other party's Confidential Information with the same degree of care as its own confidential materials, but not less than reasonable care.\n5.2 Data Protection. Provider shall maintain SOC 2 Type II compliance and ISO 27001 certifications throughout the term of this Agreement.",
                ),
                (
                    "ARTICLE 6: LIMITATION OF LIABILITY",
                    "6.1 Liability Cap. EXCEPT FOR BREACHES OF CONFIDENTIALITY UNDER ARTICLE 5 OR INDEMNIFICATION OBLIGATIONS UNDER ARTICLE 7, NEITHER PARTY'S TOTAL AGGREGATE LIABILITY ARISING OUT OF OR RELATED TO THIS AGREEMENT SHALL EXCEED $2,500,000 OR THE TOTAL AMOUNTS PAID BY CLIENT IN THE PRECEDING TWELVE (12) MONTHS, WHICHEVER IS GREATER.\n6.2 Consequential Damages. IN NO EVENT SHALL EITHER PARTY BE LIABLE FOR INDIRECT, SPECIAL, INCIDENTAL, PUNITIVE, OR CONSEQUENTIAL DAMAGES.",
                ),
                (
                    "ARTICLE 7: GOVERNING LAW & JURISDICTION",
                    "7.1 Governing Law. This Agreement shall be governed by and construed in accordance with the laws of the State of New York, without regard to its conflict of laws principles.\n7.2 Dispute Resolution. Any dispute arising out of this Agreement shall be resolved through binding arbitration in New York County, New York, under the Commercial Rules of the American Arbitration Association.",
                ),
            ],
        ],
    )

    # 2. Statement of Work (SOW)
    build_pdf(
        "sample_sow.pdf",
        "STATEMENT OF WORK: CLOUD MIGRATION (SOW-2024-08)",
        [
            [
                (
                    "SOW OVERVIEW & SCHEDULE",
                    "This Statement of Work No. SOW-2024-08 is executed pursuant to the Master Services Agreement dated March 1, 2024, between Acme Enterprise Solutions Inc. ('Client') and CloudTech Global Systems LLC ('Provider'). Project Start Date: April 15, 2024. Estimated Completion Date: December 31, 2024.",
                ),
                (
                    "SECTION 1: DELIVERABLES AND MILESTONES",
                    "Milestone 1 (Target: June 1, 2024): Architecture assessment and containerization of legacy billing microservices. Fixed fee: $150,000.\nMilestone 2 (Target: September 15, 2024): Deployment of PostgreSQL pgvector cluster and high-throughput Kafka streaming pipelines. Fixed fee: $220,000.\nMilestone 3 (Target: November 30, 2024): End-to-end load testing, penetration testing, and zero-downtime cutover. Fixed fee: $180,000.\nTotal Fixed Project Budget: $550,000.",
                ),
            ],
            [
                (
                    "SECTION 2: ACCEPTANCE CRITERIA & SLA",
                    "Client shall have fifteen (15) business days following delivery of each milestone to review and perform user acceptance testing (UAT). If deliverables do not meet specifications, Client will provide written rejection notices with detailed defect logs.\nProvider shall remediate all severity 1 and severity 2 defects within five (5) business days at no additional charge.",
                ),
                (
                    "SECTION 3: STAFFING AND KEY PERSONNEL",
                    "Provider designates lead cloud architect Dr. Marcus Vance as Key Personnel. Provider shall not substitute Key Personnel without Client's prior written consent, subject to a mandatory 30-day knowledge transfer overlap period.",
                ),
            ],
        ],
    )

    # 3. Non-Disclosure Agreement (NDA)
    build_pdf(
        "sample_nda.pdf",
        "MUTUAL NON-DISCLOSURE AGREEMENT",
        [
            [
                (
                    "NDA TERMS & DEFINITION OF CONFIDENTIAL INFORMATION",
                    "This Mutual Non-Disclosure Agreement ('NDA') is entered into as of January 10, 2024, between Acme Enterprise Solutions Inc. and TechVentures Capital Partners LLC.\n'Confidential Information' includes all non-public financial reports, AI models, training datasets, algorithm benchmarks, customer lists, and patent filings disclosed by either party.",
                ),
                (
                    "OBLIGATIONS OF RECEIVING PARTY",
                    "The receiving party agrees to hold all Confidential Information in strict confidence and shall not disclose it to any third party without prior written authorization. Access shall be restricted strictly to employees and contractors with a need-to-know basis who have executed non-disclosure covenants at least as restrictive as this Agreement.",
                ),
                (
                    "EXCLUSIONS FROM CONFIDENTIALITY",
                    "Confidential Information does not include information that: (a) is or becomes publicly known through no breach by the receiving party; (b) was already in receiving party's rightful possession before disclosure; or (c) is independently developed without reference to the disclosing party's materials.",
                ),
                (
                    "TERM & SURVIVAL",
                    "The term of disclosure under this NDA shall be two (2) years. The confidentiality obligations herein shall survive for a period of five (5) years following the termination or expiration of this Agreement.",
                ),
            ]
        ],
    )

    # 4. Vendor Services Agreement & SLA
    build_pdf(
        "sample_vendor.pdf",
        "VENDOR SERVICE LEVEL AGREEMENT (SLA)",
        [
            [
                (
                    "SERVICE COMMITMENT & UPTIME GUARANTEE",
                    "Provider warrants that the Hosted Cloud Platform shall achieve a Monthly Uptime Percentage of at least 99.95% during each calendar month.\nService downtime excludes scheduled maintenance windows occurring on Sundays between 02:00 AM and 04:00 AM UTC with at least 48 hours advance notice.",
                ),
                (
                    "SERVICE CREDITS & PENALTIES",
                    "If Monthly Uptime falls below 99.95%, Client shall be entitled to the following Service Credits:\n- 99.00% to 99.94% Uptime: 10% monthly fee credit\n- 95.00% to 98.99% Uptime: 25% monthly fee credit\n- Below 95.00% Uptime: 50% monthly fee credit and immediate right to terminate without penalty.\nMaximum aggregate service credits in any single billing month shall not exceed 50% of the total monthly recurring charge.",
                ),
            ],
            [
                (
                    "SUPPORT RESPONSE TIMES",
                    "Severity 1 (System Down / Critical Outage): Response within 15 minutes, 24x7x365. Hourly executive status updates.\nSeverity 2 (Major Feature Impairment): Response within 1 hour during business hours.\nSeverity 3 (Minor Defect / General Inquiry): Response within 8 business hours.",
                ),
                (
                    "SECURITY & AUDIT RIGHTS",
                    "Provider shall permit Client's independent third-party auditors to inspect and audit Provider's security controls, SOC reports, and disaster recovery testing records upon fourteen (14) days written notice once per calendar year.",
                ),
            ],
        ],
    )

    # 5. Commercial Real Estate Lease Agreement
    build_pdf(
        "sample_lease.pdf",
        "COMMERCIAL OFFICE LEASE AGREEMENT",
        [
            [
                (
                    "LEASE PREMISES & TERM",
                    "This Commercial Lease Agreement ('Lease') is dated February 1, 2024, by and between Hudson Yards Tower LLC ('Landlord') and Acme Enterprise Solutions Inc. ('Tenant').\nPremises: Floor 34, Suite 3400, consisting of approximately 25,000 rentable square feet at 500 Hudson Yards Boulevard, New York, NY 10001.\nCommencement Date: May 1, 2024. Expiration Date: April 30, 2029 (Initial Term of 5 Years).",
                ),
                (
                    "BASE RENT & ESCALATIONS",
                    "Base Rent shall be $125,000 per month ($1,500,000 annualized) for Year 1.\nBase Rent shall escalate by three percent (3.0%) annually on each anniversary of the Commencement Date.\nSecurity Deposit: Tenant shall deliver a standby letter of credit in the amount of $375,000 upon lease execution.",
                ),
            ],
            [
                (
                    "PERMITTED USE & ALTERATIONS",
                    "The Premises shall be used solely for general corporate offices, software engineering, and customer briefing facilities. No structural alterations may be made without Landlord's prior written consent.\nTenant shall have 24/7 keycard access to the Building and freight elevators subject to building security protocols.",
                ),
                (
                    "EARLY TERMINATION & EXTENSION OPTION",
                    "Tenant shall have a one-time right to terminate this Lease effective at the end of the thirty-sixth (36th) full calendar month, subject to providing nine (9) months prior written notice and paying an early termination fee equal to three (3) months Base Rent plus unamortized tenant improvement allowances.\nTenant is granted one (1) option to renew this Lease for an additional term of five (5) years at 95% of Fair Market Value.",
                ),
            ],
        ],
    )

    print("All 5 synthetic contract PDFs successfully generated.")


if __name__ == "__main__":
    generate_all_contracts()
