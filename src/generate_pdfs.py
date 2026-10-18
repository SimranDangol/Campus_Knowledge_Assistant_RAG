"""
generate_pdfs.py - Generates 7 realistic university policy PDFs for Greenfield University.

Documents generated:
1. student_handbook.pdf (Access Level: 1) - Mentions Form F-12 and CS-301 with prerequisites
2. attendance_2023.pdf   (Access Level: 1) - 75% attendance rule (superseded)
3. attendance_2025.pdf   (Access Level: 1) - 70% attendance rule (current, supersedes 2023)
4. fee_structure.pdf     (Access Level: 1) - Includes detailed fee tables by program & semester
5. exam_rules.pdf        (Access Level: 1) - Examination rules, hall tickets, penalties
6. grading_faculty.pdf   (Access Level: 2) - Confidential grading moderation guidelines for faculty
7. disciplinary_report.pdf (Access Level: 3) - Confidential administrative disciplinary committee report
"""

import os
from fpdf import FPDF

DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "docs")
os.makedirs(DOCS_DIR, exist_ok=True)


class UniversityPDF(FPDF):
    """Custom FPDF class that outputs header and automatic footer with page number."""

    def __init__(self, title, effective_date, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doc_title = title
        self.effective_date = effective_date
        self.set_auto_page_break(auto=True, margin=25)

    def header(self):
        if self.page_no() == 1:
            self.set_font("Helvetica", "B", 18)
            self.cell(0, 10, "Greenfield University", new_x="LMARGIN", new_y="NEXT", align="C")
            self.set_font("Helvetica", "B", 14)
            self.cell(0, 8, self.doc_title, new_x="LMARGIN", new_y="NEXT", align="C")
            self.set_font("Helvetica", "I", 10)
            self.cell(0, 6, f"Effective Date: {self.effective_date}", new_x="LMARGIN", new_y="NEXT", align="C")
            self.ln(2)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(5)
        else:
            self.set_font("Helvetica", "I", 8)
            self.cell(0, 6, f"Greenfield University - {self.doc_title}", align="R", new_x="LMARGIN", new_y="NEXT")
            self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def create_document(filename, title, effective_date, sections, tables=None):
    pdf = UniversityPDF(title, effective_date)
    pdf.add_page()

    for item in sections:
        if isinstance(item, tuple) and item[0] == "PAGE_BREAK":
            pdf.add_page()
        elif isinstance(item, tuple):
            heading, body = item
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, heading, new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5.5, body)
            pdf.ln(3)
        elif isinstance(item, str) and item == "PAGE_BREAK":
            pdf.add_page()

    if tables:
        for table_title, headers, rows in tables:
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, table_title, new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

            # Header row
            pdf.set_font("Helvetica", "B", 10)
            col_width = 190 / len(headers)
            for h in headers:
                pdf.cell(col_width, 7, h, border=1, align="C")
            pdf.ln()

            # Data rows
            pdf.set_font("Helvetica", "", 9)
            for row in rows:
                for val in row:
                    pdf.cell(col_width, 6, str(val), border=1, align="C")
                pdf.ln()
            pdf.ln(4)

    filepath = os.path.join(DOCS_DIR, filename)
    pdf.output(filepath)
    print(f"  [OK] Generated {filename}")


def main():
    print("\n============================================")
    print("   Generating 7 University Policy PDFs      ")
    print("============================================\n")

    # 1. Student Handbook
    create_document(
        "student_handbook.pdf",
        "Official Student Handbook 2024-2025",
        "August 1, 2024",
        [
            ("1. Academic Enrollment and Course Registration",
             "All undergraduate students must register for their semester coursework during the designated registration window. Course additions and section adjustments may be processed online through the student portal during the first two weeks of the academic term."),
            ("2. Course Withdrawal and Form F-12",
             "Students wishing to withdraw from an enrolled course after the second week must formally submit Form F-12 (Official Course Withdrawal Request) to the Registrar's Office. Form F-12 requires the written endorsement of both the academic advisor and the course instructor. The final deadline for submitting Form F-12 is the end of Week 8 of the semester. Courses dropped with Form F-12 receive a 'W' grade on the official transcript, which does not impact cumulative GPA."),
            ("PAGE_BREAK", ""),
            ("3. Computer Science Curriculum & CS-301 Prerequisites",
             "The Department of Computer Science requires strict sequential completion of core foundations. Course code CS-301 represents 'Advanced Algorithms and Data Optimization' (4 credits). Prerequisites for CS-301 are CS-101 (Introduction to Computer Science and Programming) and CS-201 (Data Structures and Algorithms). Students must obtain a grade of 'C' or higher in both prerequisites before enrolling in CS-301. No prerequisite waivers are granted for CS-301 under any circumstances."),
            ("4. Library Access and Operating Hours",
             "The Central Campus Library operates Monday through Saturday from 7:30 AM to 10:00 PM. During final examination weeks, the library operates on a 24-hour schedule. Students may borrow up to 5 books concurrently for a standard duration of 21 calendar days."),
            ("PAGE_BREAK", ""),
            ("5. Student Identity Cards and Campus Security",
             "Identity cards are issued by Student Services during freshman orientation. Lost cards must be reported immediately and incur a replacement fee of Rs. 500. Campus security conducts periodic spot checks at all main gates."),
        ]
    )

    # 2. Attendance Policy 2023 (Superseded)
    create_document(
        "attendance_2023.pdf",
        "Attendance Policy 2023",
        "January 1, 2023",
        [
            ("1. Purpose",
             "This policy establishes mandatory attendance standards across all undergraduate and graduate degree programs at Greenfield University effective January 1, 2023."),
            ("2. Minimum Attendance Threshold",
             "All registered students are required to maintain a minimum attendance rate of 75% in each registered course to qualify for end-of-semester examinations. Students failing to reach 75% attendance will receive an 'FA' (Failure to Attend) grade."),
            ("PAGE_BREAK", ""),
            ("3. Medical Leave Deductions",
             "Excused medical leaves must be certified by the University Health Center within 5 days of absence. Medical exemptions cannot reduce required physical attendance below 65% under the 2023 guidelines."),
        ]
    )

    # 3. Attendance Policy 2025 (Current, Supersedes 2023)
    create_document(
        "attendance_2025.pdf",
        "Attendance Policy 2025 (Supersedes 2023 Policy)",
        "January 1, 2025",
        [
            ("1. Policy Revision & Supersession",
             "This policy officially replaces and supersedes the Attendance Policy 2023 in its entirety effective January 1, 2025. Following Senate Resolution 2024-B, the university has revised attendance thresholds to accommodate blended and hybrid learning."),
            ("2. Revised Minimum Attendance Requirement",
             "The mandatory minimum attendance requirement to sit for end-of-semester examinations is 70% in each enrolled course. This replaces the previous 75% requirement. Any student who achieves between 65% and 69% attendance may petition the Academic Dean for condonation upon payment of a Rs. 1,500 review fee."),
            ("PAGE_BREAK", ""),
            ("3. Sanctions for Non-Compliance",
             "Students whose attendance drops below 70% without approved condonation are debarred from the final exam and assigned an 'FA' grade. Re-registering for a debarred course requires a course retake fee of Rs. 2,500."),
            ("4. Digital Attendance Recording",
             "Attendance is captured electronically through biometric RFID card readers at the entrance of each lecture hall. Instructors finalize digital records weekly."),
        ]
    )

    # 4. Fee Structure (Includes Tables)
    create_document(
        "fee_structure.pdf",
        "Comprehensive University Fee Structure 2024-2025",
        "July 1, 2024",
        [
            ("1. Tuition & Academic Fees Schedule",
             "The following official fee schedule governs all undergraduate degree programs for the 2024-2025 academic calendar. Fees are payable per semester by the invoice deadline."),
        ],
        tables=[
            ("Tuition Fee by Program and Semester (in INR)",
             ["Program Code", "Program Name", "Semester 1-2", "Semester 3-4", "Semester 5-8"],
             [
                 ["CS-UG", "B.Sc. Computer Science", "65,000", "70,000", "75,000"],
                 ["EE-UG", "B.Tech Electrical Eng.", "68,000", "72,000", "78,000"],
                 ["ME-UG", "B.Tech Mechanical Eng.", "66,000", "71,000", "76,000"],
                 ["BA-UG", "Bachelor of Business (BBA)", "52,000", "55,000", "60,000"],
                 ["DS-UG", "B.Sc. Data Science", "67,000", "72,000", "77,000"],
             ]),
            ("Ancillary and Facility Fees",
             ["Fee Category", "Applicability", "Amount (Per Semester)", "Refundable"],
             [
                 ["Laboratory Fee", "Science & Eng Programs", "8,500", "No"],
                 ["Library & Digital Access", "All Students", "3,000", "No"],
                 ["Campus Security Deposit", "First-time Registration", "10,000", "Yes (upon graduation)"],
                 ["Student Sports & Activity", "All Students", "2,500", "No"],
                 ["Late Registration Penalty", "After Day 14", "2,000", "No"],
             ])
        ]
    )

    # 5. Exam Rules
    create_document(
        "exam_rules.pdf",
        "Official Examination Regulations and Conduct",
        "September 1, 2024",
        [
            ("1. Hall Ticket and Candidate Identification",
             "Every student must present an original, physical Hall Ticket and their university photo ID card to enter the examination hall. Digital copies on smartphones will not be accepted under any circumstances."),
            ("2. Examination Arrival and Late Entry",
             "Candidates must be seated in their designated hall at least 30 minutes before the scheduled exam start time. No candidate will be admitted after 15 minutes have elapsed from the start of the examination."),
            ("PAGE_BREAK", ""),
            ("3. Grading Scale & Mark Distribution",
             "Grading follows an 8-point system: Grade 'A+' (90-100%), 'A' (80-89%), 'B' (70-79%), 'C' (60-69%), 'D' (50-59%), 'E' (40-49%), and 'F' (below 40% - Fail). A minimum of 40% aggregate in both continuous internal assessment and final examination is mandatory to pass."),
            ("4. Prohibited Materials & Cheating",
             "Possession of mobile phones, smartwatches, programmable calculators, or handwritten notes inside the exam room constitutes academic misconduct and results in immediate disqualification with an automatic 'F' grade."),
        ]
    )

    # 6. Grading Guidelines for Faculty (Confidential, Access Level 2)
    create_document(
        "grading_faculty.pdf",
        "Faculty Grading Guidelines & Moderation Procedure",
        "June 1, 2024",
        [
            ("1. Confidentiality and Access Restrictions",
             "This document is strictly confidential and reserved for Faculty Members, Department Chairs, and Examination Committee members. Distribution to students is strictly prohibited under institutional regulations."),
            ("2. Continuous Assessment Weightage",
             "All course syllabi must apportion final grades as follows: 40% Continuous Assessment (midterms, assignments, lab work) and 60% Final End-of-Semester Examination. Deviations must receive prior Dean approval."),
            ("PAGE_BREAK", ""),
            ("3. Grade Moderation Procedure",
             "To ensure consistency across parallel sections, the Department Grade Moderation Committee enforces the following standard procedure:\n"
             "Step 1: The primary instructor submits provisional grades within 5 business days of the examination.\n"
             "Step 2: A second marker is independently assigned to review any grade change exceeding 10 marks from the student's continuous assessment average. The second marker must provide written justification for agreement or adjustment.\n"
             "Step 3: If the primary and second marker differ by more than 5 marks, the Department Chair appoints a third senior referee whose assessment is definitive.\n"
             "Step 4: Any course section with a failure rate higher than 30% requires a mandatory committee investigation."),
        ]
    )

    # 7. Disciplinary Committee Report (Admin Only, Access Level 3)
    create_document(
        "disciplinary_report.pdf",
        "Disciplinary Committee Annual Report (Confidential Admin)",
        "November 1, 2024",
        [
            ("1. Executive Summary & Jurisdiction",
             "This annual report compiles all formal disciplinary proceedings, hearings, and sanctions adjudicated during the 2023-2024 academic year. Access is strictly restricted to University Executive Officers, the Board of Trustees, and the Office of the Registrar (Access Level 3)."),
            ("2. Case Sanction Guidelines",
             "The disciplinary committee applies the following statutory sanctions for confirmed offenses:\n"
             "- Academic Plagiarism (first offense): Grade 'F' in course and formal written reprimand on student record.\n"
             "- Academic Plagiarism (second offense): Mandatory suspension for 1 academic semester.\n"
             "- Examination Tampering or Paper Leakage: Immediate expulsion from Greenfield University and forfeiture of all academic credits.\n"
             "- Destruction of University Property: Full financial restitution plus mandatory community service of 40 hours."),
            ("PAGE_BREAK", ""),
            ("3. Statistical Summary of Cases",
             "A total of 14 cases were heard during the 2023-2024 academic session: 8 plagiarism violations, 3 examination impersonation incidents, and 3 code-of-conduct violations. Two students received 1-semester suspensions, and one student was permanently expelled."),
        ]
    )

    print("\n  [OK] Successfully created all 7 policy PDFs in docs/!\n")


if __name__ == "__main__":
    main()
