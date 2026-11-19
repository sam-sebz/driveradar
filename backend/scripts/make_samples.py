"""Generate the three SYNTHETIC sample notices in samples/synthetic/.

All companies, people and numbers are invented for testing. Run:
    python scripts/make_samples.py
"""

from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "samples" / "synthetic"
BANNER = "SYNTHETIC SAMPLE - fictional company, for testing DriveRadar only"

PDF_LINES = [
    BANNER,
    "",
    "Training & Placement Cell - Campus Recruitment Notice",
    "Company: Kaveri Analytics Pvt. Ltd.",
    "Role: Associate Software Engineer",
    "Job Location: Chennai, Bengaluru",
    "CTC: Rs. 6.5 - 8 LPA",
    "Date of Joining: 01-07-2027",
    "Last date to register: 28 November 2026, 11:59 PM",
    "",
    "Eligibility Criteria",
    "Eligible Branches: B.Tech CSE, IT, ECE",
    "Batch: 2026 passouts",
    "Minimum 7.0 CGPA in B.Tech",
    "60% in 10th and 12th",
    "No active backlogs at the time of application",
    "",
    "Skills Required",
    "Java, Python, SQL, Data Structures and Git",
    "",
    "Selection Process",
    "1. Online Assessment",
    "2. Technical Interview",
    "3. HR Interview",
    "",
    "Service Agreement: 2 years. Bond penalty of Rs. 1,50,000 if you leave before 2 years.",
    "Note: Students who already hold an offer above 10 LPA are not eligible.",
]


def make_pdf(path: Path) -> None:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in PDF_LINES:
        pdf.multi_cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    pdf.set_creation_date(datetime(2026, 11, 1))  # deterministic output
    pdf.output(str(path))


def make_docx(path: Path) -> None:
    from docx import Document

    doc = Document()
    doc.core_properties.created = datetime(2026, 11, 1)
    doc.add_paragraph(BANNER)
    doc.add_heading("Placement Drive: Nilgiri Cloudworks LLP", level=1)
    doc.add_paragraph("Company Name: Nilgiri Cloudworks LLP")
    doc.add_paragraph("Position: Cloud Engineer Intern (with PPO)")
    doc.add_paragraph("Work Location: Hyderabad (Hybrid)")
    doc.add_paragraph("Stipend: ₹30,000 per month during the 6-month internship")
    doc.add_paragraph("CTC on conversion: ₹12 LPA")
    doc.add_paragraph("Apply by: 02/12/2026 5:00 PM")

    doc.add_heading("Eligibility", level=2)
    table = doc.add_table(rows=0, cols=2)
    for key, value in [
        ("Branches", "Computer Science or equivalent"),
        ("Batch", "2026 & 2027"),
        ("CGPA", "7.5 and above"),
        ("Backlogs", "Maximum 1 active backlog"),
        ("10th / 12th", "70% in Class X and 70% in Class XII"),
        ("Bond", "No bond"),
    ]:
        cells = table.add_row().cells
        cells[0].text = key
        cells[1].text = value

    doc.add_heading("Technical Skills", level=2)
    doc.add_paragraph("AWS, Linux, Docker, Kubernetes, Python, Computer Networks")
    doc.add_heading("Selection Process", level=2)
    doc.add_paragraph("Online Test -> Group Discussion -> Technical Interview -> HR Interview")
    doc.save(str(path))


def make_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    wb.properties.created = datetime(2026, 11, 1)
    info = wb.active
    if info is None:  # pragma: no cover - a new Workbook always has a sheet
        raise RuntimeError("workbook has no active sheet")
    info.title = "Drive Details"
    for row in [
        ("Note", BANNER),
        ("Company", "Thamirabarani Systems Ltd."),
        ("Location", "Chennai"),
        ("Registration Deadline", "25-Nov-2026 6:00 PM"),
        ("Eligible Batch", "2026"),
        ("Backlogs", "No standing arrears"),
        ("Class X / XII", "Minimum 65% in 10th and 12th"),
        ("Selection Process", "Aptitude Test, Technical Interview, HR Interview"),
        ("Bond", "1 year service agreement, penalty ₹75,000"),
    ]:
        info.append(row)

    roles = wb.create_sheet("Roles")
    roles.append(["Role", "CTC", "Minimum CGPA", "Eligible Branches", "Skills"])
    roles.append(
        [
            "Graduate Engineer Trainee",
            "4.5 LPA",
            "6.5",
            "All branches",
            "Communication, Aptitude, C",
        ]
    )
    roles.append(
        [
            "Data Analyst",
            "6 LPA",
            "7",
            "CSE, IT, CSE-DS",
            "SQL, Python, Power BI, Excel, Statistics",
        ]
    )
    roles.append(
        [
            "Embedded Engineer",
            "5.5 - 7 LPA",
            "7",
            "ECE, EEE, EIE",
            "Embedded C, Microcontrollers, RTOS, C",
        ]
    )
    wb.save(str(path))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make_pdf(OUT / "kaveri_analytics_notice.pdf")
    make_docx(OUT / "nilgiri_cloudworks_notice.docx")
    make_xlsx(OUT / "thamirabarani_systems_3roles.xlsx")
    for p in sorted(OUT.iterdir()):
        print(f"{p.name}: {p.stat().st_size} bytes")
