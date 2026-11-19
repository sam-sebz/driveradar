"""Generate the HELD-OUT synthetic notice in eval/notices/synthetic/.

It is written in a different style from samples/synthetic/ on purpose (other labels,
bullets, arrows, "standing arrears", month-only joining date). The rule-based extractor
was NOT tuned on it, so its score is a fairer (still synthetic) signal.

    cd backend && python ../eval/make_heldout.py
"""

from datetime import datetime
from pathlib import Path

from docx import Document

OUT = Path(__file__).resolve().parent / "notices" / "synthetic"

LINES = [
    "SYNTHETIC SAMPLE (held-out) - fictional company, for evaluating DriveRadar only",
    "Recruitment Drive – Vaigai Fintech Solutions",
    "About the company: Vaigai Fintech Solutions builds payment software for co-operative banks.",
    "Profile Offered: Software Development Engineer - I",
    "Place of posting: Coimbatore / Remote",
    "Compensation: INR 9,50,000 per annum (fixed) + joining bonus",
    "Eligibility:",
    "• B.E./B.Tech (CSE / IT / ECE) and MCA – 2026 batch only",
    "• Aggregate of 65% or 6.5 CGPA in UG",
    "• Minimum 75% in Std X and Std XII",
    "• Candidates with standing arrears are not eligible",
    "Desired skills: Strong in DSA, OOPS, any one of Java/C++/Python; knowledge of SQL & REST "
    "APIs is a plus.",
    "Process: Coding test (HackerRank) → 2 technical rounds → HR",
    "Last date for registration: 30th Nov, 2026 by 10 AM",
    "The selected candidates must sign a service agreement of 24 months; breaking it attracts "
    "a penalty of ₹2 lakh.",
    "Joining: July 2027",
]

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    doc = Document()
    doc.core_properties.created = datetime(2026, 11, 19)
    for line in LINES:
        doc.add_paragraph(line)
    path = OUT / "vaigai_fintech_heldout.docx"
    doc.save(str(path))
    print(f"wrote {path} ({path.stat().st_size} bytes)")
