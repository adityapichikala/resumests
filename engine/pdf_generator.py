"""
PDF Generator — Creates professional PDF reports for ATS analysis and optimized resumes.
Uses only built-in fonts (Helvetica) with aggressive text sanitization for compatibility.
"""

import io
import re
from typing import Dict, Any, List
from fpdf import FPDF


def _safe(text) -> str:
    """Sanitize text to be safe for FPDF's built-in Helvetica font (latin-1 only).
    Strips/replaces any characters outside latin-1."""
    if not text:
        return ""
    if not isinstance(text, str):
        text = str(text)
    # Replace common Unicode characters with ASCII equivalents
    replacements = {
        '\u2019': "'", '\u2018': "'",  # Smart quotes
        '\u201c': '"', '\u201d': '"',
        '\u2013': '-', '\u2014': '-',  # En/em dash
        '\u2022': '-',  # Bullet
        '\u2026': '...',  # Ellipsis
        '\u00b7': '-',  # Middle dot
        '\u2192': '->',  # Arrow
        '\u2713': 'v',  # Checkmark
        '\u2714': 'v',
        '\u2715': 'x',
        '\u2716': 'x',
        '\uf0b7': '-',  # Bullet variant
        '\uf0a7': '-',
        '\u25cf': '-',  # Black circle
        '\u25cb': 'o',  # White circle
        '\u25aa': '-',  # Black small square
        '\u25ab': '-',  # White small square
        '\u2023': '>',  # Triangle bullet
        '\u00a0': ' ',  # Non-breaking space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    # Remove all remaining non-latin-1 characters
    cleaned = []
    for ch in text:
        try:
            ch.encode('latin-1')
            cleaned.append(ch)
        except UnicodeEncodeError:
            cleaned.append(' ')
    return ''.join(cleaned)


class ATSReportPDF(FPDF):
    """Custom PDF class for ATS reports."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font('Helvetica', 'B', 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, 'ATS Resume Analyzer Report', align='C')
        self.ln(4)
        self.set_draw_color(99, 102, 241)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Page {self.page_no()}/{{nb}}', align='C')

    def section_title(self, title: str):
        self.set_font('Helvetica', 'B', 13)
        self.set_text_color(99, 102, 241)
        self.cell(0, 10, _safe(title), new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(99, 102, 241)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def sub_title(self, title: str):
        self.set_font('Helvetica', 'B', 11)
        self.set_text_color(50, 50, 50)
        self.cell(0, 8, _safe(title), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def body_text(self, text: str):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(60, 60, 60)
        self.multi_cell(0, 6, _safe(text))
        self.ln(2)

    def bullet_point(self, text: str):
        self.set_font('Helvetica', '', 10)
        self.set_text_color(60, 60, 60)
        self.cell(6, 6, '-')
        self.multi_cell(0, 6, _safe(text))
        self.ln(1)

    def score_bar(self, label: str, score: int):
        """Draw a score bar with label and value."""
        self.set_font('Helvetica', '', 10)
        self.set_text_color(60, 60, 60)
        self.cell(55, 7, _safe(label))

        bar_x = self.get_x()
        bar_y = self.get_y() + 1
        bar_width = 100
        bar_height = 5

        self.set_fill_color(230, 230, 230)
        self.rect(bar_x, bar_y, bar_width, bar_height, 'F')

        fill_width = int(bar_width * score / 100)
        if score >= 80:
            self.set_fill_color(34, 197, 94)
        elif score >= 60:
            self.set_fill_color(234, 179, 8)
        elif score >= 40:
            self.set_fill_color(249, 115, 22)
        else:
            self.set_fill_color(239, 68, 68)

        if fill_width > 0:
            self.rect(bar_x, bar_y, fill_width, bar_height, 'F')

        self.set_x(bar_x + bar_width + 3)
        self.set_font('Helvetica', 'B', 10)
        self.cell(20, 7, f'{score}/100')
        self.ln(8)

    def decision_badge(self, decision: str, score: int, confidence: str):
        self.set_font('Helvetica', 'B', 18)
        if decision == "PASS":
            self.set_text_color(34, 197, 94)
        else:
            self.set_text_color(239, 68, 68)

        self.cell(0, 12, f'ATS Decision: {_safe(decision)}', new_x="LMARGIN", new_y="NEXT")

        self.set_font('Helvetica', 'B', 14)
        self.set_text_color(50, 50, 50)
        self.cell(0, 10, f'Overall Score: {score}/100    |    Confidence: {_safe(confidence).upper()}',
                  new_x="LMARGIN", new_y="NEXT")
        self.ln(4)


def generate_ats_report_pdf(result: Dict[str, Any]) -> bytes:
    """Generate a professional ATS analysis report as PDF."""
    pdf = ATSReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    ma = result.get('match_analysis', {})

    pdf.decision_badge(
        result.get('ats_decision', 'N/A'),
        ma.get('match_score', 0),
        ma.get('confidence_level', 'unknown')
    )

    pdf.section_title('Score Breakdown')
    pdf.score_bar('Keyword Match', ma.get('keyword_match_score', 0))
    pdf.score_bar('Skills Match', ma.get('skills_match_score', 0))
    pdf.score_bar('Experience', ma.get('experience_score', 0))
    pdf.score_bar('Achievements', ma.get('achievement_score', 0))
    pdf.score_bar('Formatting', ma.get('formatting_score', 0))
    pdf.ln(4)

    matched = ma.get('matched_skills', [])
    if matched:
        pdf.section_title(f'Matched Skills ({len(matched)})')
        pdf.body_text(', '.join(str(s) for s in matched))

    missing = ma.get('missing_skills', [])
    if missing:
        pdf.section_title(f'Missing Skills ({len(missing)})')
        pdf.body_text(', '.join(str(s) for s in missing))

    failures = result.get('failure_reasons', [])
    if failures:
        pdf.section_title('Failure Reasons')
        for reason in failures:
            pdf.bullet_point(str(reason))

    issues = result.get('ats_issues', [])
    if issues:
        pdf.section_title(f'ATS Issues ({len(issues)})')
        for issue in issues:
            pdf.bullet_point(str(issue))

    suggestions = result.get('improvement_suggestions', [])
    if suggestions:
        pdf.section_title(f'Improvement Suggestions ({len(suggestions)})')
        for suggestion in suggestions:
            pdf.bullet_point(str(suggestion))

    notes = result.get('tailoring_notes', '')
    if notes:
        pdf.section_title('Tailoring Notes')
        pdf.body_text(str(notes))

    return pdf.output()


def generate_resume_pdf(result: Dict[str, Any]) -> bytes:
    """Generate the optimized resume as a professional PDF."""
    opt = result.get('optimized_resume', {})
    if isinstance(opt, str):
        # If optimizer returned a string instead of dict, just put it as body
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        pdf.set_font('Helvetica', '', 11)
        pdf.multi_cell(0, 6, _safe(opt))
        return pdf.output()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Name header
    name = str(opt.get('name', 'Resume'))
    pdf.set_font('Helvetica', 'B', 20)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 12, _safe(name), new_x="LMARGIN", new_y="NEXT", align='C')

    # Contact
    contact = str(opt.get('contact', ''))
    if contact:
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 7, _safe(contact), new_x="LMARGIN", new_y="NEXT", align='C')

    pdf.ln(4)
    pdf.set_draw_color(99, 102, 241)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)

    def section_header(title: str):
        pdf.set_font('Helvetica', 'B', 13)
        pdf.set_text_color(99, 102, 241)
        pdf.cell(0, 9, _safe(title).upper(), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.2)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(4)

    def body(text: str):
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(50, 50, 50)
        pdf.multi_cell(0, 6, _safe(text))
        pdf.ln(2)

    def bullet(text: str):
        pdf.set_font('Helvetica', '', 10)
        pdf.set_text_color(50, 50, 50)
        pdf.cell(6, 6, '-')
        pdf.multi_cell(0, 6, _safe(text))
        pdf.ln(1)

    # Summary
    summary = opt.get('summary', '')
    if summary:
        section_header('Professional Summary')
        body(str(summary))

    # Skills
    skills = opt.get('skills', [])
    if skills:
        section_header('Technical Skills')
        if isinstance(skills, list):
            body(', '.join(str(s) for s in skills))
        else:
            body(str(skills))

    # Experience
    experience = opt.get('experience', [])
    if experience and isinstance(experience, list):
        section_header('Professional Experience')
        for job in experience:
            if not isinstance(job, dict):
                body(str(job))
                continue
            title = str(job.get('title', ''))
            company = str(job.get('company', ''))
            dates = str(job.get('dates', ''))

            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(0, 7, _safe(title), new_x="LMARGIN", new_y="NEXT")

            if company or dates:
                pdf.set_font('Helvetica', 'I', 10)
                pdf.set_text_color(100, 100, 100)
                parts = [p for p in [company, dates] if p]
                pdf.cell(0, 6, _safe(' | '.join(parts)), new_x="LMARGIN", new_y="NEXT")

            pdf.ln(2)
            bullets = job.get('bullets', [])
            if isinstance(bullets, list):
                for b in bullets:
                    bullet(str(b))
            pdf.ln(2)

    # Projects
    projects = opt.get('projects', [])
    if projects and isinstance(projects, list):
        section_header('Projects')
        for proj in projects:
            if not isinstance(proj, dict):
                body(str(proj))
                continue

            # Project name - bold, on its own line
            name_text = str(proj.get('name', ''))
            if name_text:
                pdf.set_font('Helvetica', 'B', 11)
                pdf.set_text_color(30, 30, 30)
                pdf.multi_cell(0, 7, _safe(name_text), new_x="LMARGIN", new_y="NEXT")

            # Tech stack - italic, on its own line (like company/dates in experience)
            tech = str(proj.get('tech', ''))
            if tech:
                pdf.set_font('Helvetica', 'I', 10)
                pdf.set_text_color(100, 100, 100)
                pdf.cell(0, 6, _safe(tech), new_x="LMARGIN", new_y="NEXT")

            pdf.ln(2)
            # Description as body text
            desc = proj.get('description', '')
            if desc:
                bullet(str(desc))
            pdf.ln(2)

    # Education
    education = opt.get('education', [])
    if education and isinstance(education, list):
        section_header('Education')
        for edu in education:
            if not isinstance(edu, dict):
                body(str(edu))
                continue
            pdf.set_font('Helvetica', 'B', 11)
            pdf.set_text_color(30, 30, 30)
            pdf.cell(0, 7, _safe(str(edu.get('degree', ''))), new_x="LMARGIN", new_y="NEXT")

            inst = str(edu.get('institution', ''))
            year = str(edu.get('year', ''))
            if inst or year:
                pdf.set_font('Helvetica', 'I', 10)
                pdf.set_text_color(100, 100, 100)
                parts = [p for p in [inst, year] if p]
                pdf.cell(0, 6, _safe(' | '.join(parts)), new_x="LMARGIN", new_y="NEXT")

            details = edu.get('details', '')
            if details:
                pdf.set_font('Helvetica', '', 10)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(0, 6, _safe(str(details)), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(3)

    # Certifications
    certs = opt.get('certifications', [])
    if certs and isinstance(certs, list):
        section_header('Certifications')
        for cert in certs:
            bullet(str(cert))

    return pdf.output()
