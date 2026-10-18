

from fpdf import FPDF
import os

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
os.makedirs(DOCS_DIR, exist_ok=True)


def make_pdf(filename, title, effective_date, sections):
    """Create a styled university policy PDF."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()

    # Header
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 12, "Greenfield University", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 8, f"Effective Date: {effective_date}", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(4)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    # Body sections
    for heading, body in sections:
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, heading, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 11)
        pdf.multi_cell(0, 6, body)
        pdf.ln(4)

    # Footer with page number
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 10, f"Page {pdf.page_no()}", align="C")

    path = os.path.join(DOCS_DIR, filename)
    pdf.output(path)
    print(f"  Created: {path}")


# ── PDF 1: Attendance Policy 2023 ───────────────────────────────────────────

make_pdf(
    "attendance_2023.pdf",
    "Attendance Policy 2023",
    "January 1, 2023",
    [
        ("1. Purpose", 
         "This policy establishes the minimum attendance requirements for all undergraduate and postgraduate students enrolled at Greenfield University. It applies to all courses across all departments effective from the Spring 2023 semester."),
        
        ("2. Minimum Attendance Requirement",
         "All students must maintain a minimum attendance of 75% in each enrolled course to be eligible to sit for the end-of-semester examinations. Attendance is calculated based on the total number of scheduled lectures, tutorials, and laboratory sessions for each course."),
        
        ("3. Attendance Tracking",
         "Attendance shall be recorded by the course instructor at the beginning of each class session using the university's digital attendance system (GU-Attend v2.1). Students must tap their university ID card at the reader installed at the entrance of each classroom. Manual attendance may be recorded only in cases of system failure, with prior approval from the department head."),
        
        ("4. Consequences of Non-Compliance",
         "Students whose attendance falls below 75% in any course shall be barred from appearing in the final examination for that course. A warning notification will be sent to the student via email when attendance drops below 80%. Students barred from examinations due to attendance shortage will receive an 'FA' (Failure due to Attendance) grade for the course and must re-register in the subsequent semester."),
        
        ("5. Exemptions",
         "Medical exemptions may be granted for absences exceeding 5 consecutive class days, provided the student submits a medical certificate from a registered medical practitioner within 7 working days of returning to class. Students representing the university in official sports, cultural, or academic events may be granted authorized absence for up to 10 class days per semester, with prior written approval from the Dean of Student Affairs."),
        
        ("6. Appeals Process",
         "Students who wish to appeal an attendance shortage must submit Form A-7 (Attendance Appeal Form) to the Office of the Registrar within 14 calendar days of receiving the barring notification. The Attendance Review Committee, comprising 3 faculty members, will review appeals within 21 working days. The committee's decision is final and binding."),
    ]
)


# ── PDF 2: Attendance Policy 2025 ───────────────────────────────────────────

make_pdf(
    "attendance_2025.pdf",
    "Attendance Policy 2025",
    "January 1, 2025",
    [
        ("1. Purpose and Scope",
         "This policy supersedes the Attendance Policy 2023 and establishes updated minimum attendance requirements for all students at Greenfield University. This revision reflects feedback from the Student Welfare Committee and aligns with updated UGC guidelines on student engagement."),
        
        ("2. Minimum Attendance Requirement",
         "All students must maintain a minimum attendance of 70% in each enrolled course to be eligible to sit for the end-of-semester examinations. This is a reduction from the previous requirement of 75%, following analysis showing that the higher threshold disproportionately affected students with long commutes and part-time employment. Attendance is calculated based on lectures, tutorials, labs, and mandatory workshops."),
        
        ("3. Enhanced Attendance Tracking",
         "Attendance shall be recorded using the upgraded GU-Attend v3.0 system, which supports both ID card tap and biometric verification. Students may also mark attendance via the GU Mobile App using geo-fenced check-in within a 50-meter radius of the classroom. The system generates automated weekly attendance reports for students and faculty."),
        
        ("4. Early Warning System",
         "An automated early warning notification will be sent when a student's attendance falls below 80% (first warning) and 75% (second warning). Academic advisors will be notified at the second warning stage and must schedule a meeting with the student within 5 working days. Students who fail to meet with their advisor after the second warning may be referred to the Student Support Services office."),
        
        ("5. Consequences of Non-Compliance",
         "Students whose attendance falls below 70% in any course shall be barred from the final examination. Barred students will receive an 'FA' grade and must re-register. The re-registration fee is Rs. 2,500 per course. Students barred in 3 or more courses in a single semester will be placed on academic probation for the following semester."),
        
        ("6. Exemptions and Special Provisions",
         "Medical exemptions require a certificate from a registered practitioner submitted within 7 working days. Students with disabilities registered with the Office of Inclusive Education may receive modified attendance requirements (minimum 60%) as part of their Individual Accommodation Plan. Student athletes and cultural representatives may receive up to 15 days of authorized absence per semester with written approval from the Dean of Student Affairs."),
        
        ("7. Appeals",
         "Appeals must be submitted using Form A-7 (Revised) within 14 calendar days. The Attendance Review Committee will process appeals within 15 working days (reduced from 21 days). Students may request a second review by the Academic Standards Board if they believe the committee's decision was procedurally flawed."),
    ]
)


# ── PDF 3: Grading Guidelines for Faculty ──────────────────────────────────

make_pdf(
    "grading_faculty.pdf",
    "Grading Guidelines for Faculty",
    "June 1, 2024",
    [
        ("CONFIDENTIAL - For Faculty and Administrative Use Only",
         "This document contains internal grading procedures and moderation guidelines. Distribution to students is strictly prohibited. Unauthorized sharing may result in disciplinary action under Section 14.2 of the Faculty Code of Conduct."),
        
        ("1. Grading Scale",
         "Greenfield University follows a 10-point grading scale:\n"
         "  A+: 90-100 (Grade Point 10)\n"
         "  A : 80-89  (Grade Point 9)\n"
         "  B+: 70-79  (Grade Point 8)\n"
         "  B : 60-69  (Grade Point 7)\n"
         "  C+: 50-59  (Grade Point 6)\n"
         "  C : 45-49  (Grade Point 5)\n"
         "  D : 40-44  (Grade Point 4)\n"
         "  F : Below 40 (Grade Point 0)\n"
         "The minimum passing grade is D (40 marks) for undergraduate courses and C (45 marks) for postgraduate courses."),
        
        ("2. Grade Moderation Procedure",
         "All final grades are subject to moderation before submission to the Registrar. The moderation procedure is as follows:\n\n"
         "Step 1: The primary examiner submits provisional grades to the Department Grade Moderation Committee.\n\n"
         "Step 2: A second marker is assigned to independently review any grade change exceeding 10 marks from the student's continuous assessment average. The second marker must provide written justification for agreement or disagreement with the grade change.\n\n"
         "Step 3: If the primary and second markers disagree, a third examiner from a related department is appointed. The third examiner's assessment is final.\n\n"
         "Step 4: The Department Head reviews the moderated grades and signs off before submission. Any course with a failure rate exceeding 30% must include a written explanation from the course instructor."),
        
        ("3. Grade Change Requests",
         "Faculty may request a grade change after submission only under the following circumstances: (a) clerical or calculation error, (b) discovery of a grading irregularity during audit, or (c) resolution of an academic integrity case. All grade changes must be submitted using Form G-3 (Grade Amendment Request) within 30 calendar days of the original grade submission. Changes require approval from the Department Head and the Dean of Academic Affairs. A maximum of 5% of total grades in any course may be amended post-submission."),
        
        ("4. Internal Assessment Weightage",
         "The standard assessment breakdown for all courses is:\n"
         "  Mid-semester examination: 25%\n"
         "  Assignments and quizzes: 15%\n"
         "  Class participation: 10%\n"
         "  End-semester examination: 50%\n"
         "Departments may propose alternative weightages with written approval from the Academic Council. Laboratory courses may allocate up to 40% to practical assessments."),
        
        ("5. Academic Integrity in Grading",
         "Faculty must report any suspected cases of academic dishonesty to the Academic Integrity Office within 48 hours of discovery. Pending investigation, the student receives an 'I' (Incomplete) grade. If found guilty, the student receives an 'F' grade for the course and a notation on their transcript. Faculty must not independently reduce grades as a penalty for suspected dishonesty without going through the formal process."),
        
        ("6. Grade Submission Deadlines",
         "All final grades must be submitted within 10 working days of the last examination date. Late submissions will be flagged in the faculty performance review. Grades not submitted within 20 working days will be escalated to the Dean's office. The Registrar's office will send automated reminders at 5-day and 8-day marks."),
    ]
)


print("\n  All 3 PDFs created in docs/ folder!")
print("  You can now run: uv run python src/ingest.py")
