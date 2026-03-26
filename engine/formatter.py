"""
Resume Formatter — Generates clean plain-text formatted resumes in 4 styles.
"""

from typing import Dict, Any, List


def _wrap_text(text: str, width: int = 80) -> str:
    """Simple word-wrap for plain text."""
    words = text.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 <= width:
            current_line += (" " if current_line else "") + word
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return '\n'.join(lines)


def _section_divider(char: str = '─', width: int = 60) -> str:
    return char * width


def format_modern(resume: Dict[str, Any]) -> str:
    """Modern format: single-column, clean header, section dividers."""
    lines = []

    # Header
    lines.append(resume.get('name', '').upper())
    lines.append(resume.get('contact', ''))
    lines.append(_section_divider('═'))
    lines.append('')

    # Summary
    summary = resume.get('summary', '')
    if summary:
        lines.append('PROFESSIONAL SUMMARY')
        lines.append(_section_divider())
        lines.append(_wrap_text(summary))
        lines.append('')

    # Skills
    skills = resume.get('skills', [])
    if skills:
        lines.append('TECHNICAL SKILLS')
        lines.append(_section_divider())
        # Display as chips-style groups (comma separated)
        skill_line = ' • '.join(skills)
        lines.append(_wrap_text(skill_line))
        lines.append('')

    # Experience
    experience = resume.get('experience', [])
    if experience:
        lines.append('PROFESSIONAL EXPERIENCE')
        lines.append(_section_divider())
        for job in experience:
            title = job.get('title', '')
            company = job.get('company', '')
            dates = job.get('dates', '')
            header = f"{title}"
            if company:
                header += f" | {company}"
            if dates:
                header += f" | {dates}"
            lines.append(header)
            for bullet in job.get('bullets', []):
                lines.append(f"  • {_wrap_text(bullet, 76)}")
            lines.append('')

    # Projects
    projects = resume.get('projects', [])
    if projects:
        lines.append('PROJECTS')
        lines.append(_section_divider())
        for proj in projects:
            name = proj.get('name', '')
            tech = proj.get('tech', '')
            desc = proj.get('description', '')
            header = name
            if tech:
                header += f" [{tech}]"
            lines.append(header)
            if desc:
                lines.append(f"  {_wrap_text(desc, 76)}")
            lines.append('')

    # Education
    education = resume.get('education', [])
    if education:
        lines.append('EDUCATION')
        lines.append(_section_divider())
        for edu in education:
            degree = edu.get('degree', '')
            institution = edu.get('institution', '')
            year = edu.get('year', '')
            details = edu.get('details', '')
            header = degree
            if institution:
                header += f" | {institution}"
            if year:
                header += f" | {year}"
            lines.append(header)
            if details:
                lines.append(f"  {details}")
            lines.append('')

    # Certifications
    certs = resume.get('certifications', [])
    if certs:
        lines.append('CERTIFICATIONS')
        lines.append(_section_divider())
        for cert in certs:
            lines.append(f"  • {cert}")
        lines.append('')

    return '\n'.join(lines)


def format_sidebar(resume: Dict[str, Any]) -> str:
    """Sidebar format: two-column layout (left: contact/skills/edu, right: experience)."""
    lines = []
    left_width = 28
    right_width = 48
    separator = ' │ '

    # Header (full width)
    lines.append(resume.get('name', '').upper())
    lines.append(resume.get('contact', ''))
    lines.append(_section_divider('═'))
    lines.append('')

    # Build left column content
    left_lines = []
    left_lines.append('CONTACT')
    left_lines.append('─' * left_width)
    contact = resume.get('contact', '')
    for part in contact.split(' | '):
        part = part.strip()
        if part:
            left_lines.append(part[:left_width])
    left_lines.append('')

    skills = resume.get('skills', [])
    if skills:
        left_lines.append('SKILLS')
        left_lines.append('─' * left_width)
        for skill in skills:
            left_lines.append(f"• {skill[:left_width-2]}")
        left_lines.append('')

    education = resume.get('education', [])
    if education:
        left_lines.append('EDUCATION')
        left_lines.append('─' * left_width)
        for edu in education:
            left_lines.append(edu.get('degree', '')[:left_width])
            inst = edu.get('institution', '')
            if inst:
                left_lines.append(inst[:left_width])
            year = edu.get('year', '')
            if year:
                left_lines.append(year)
            left_lines.append('')

    certs = resume.get('certifications', [])
    if certs:
        left_lines.append('CERTIFICATIONS')
        left_lines.append('─' * left_width)
        for cert in certs:
            left_lines.append(f"• {cert[:left_width-2]}")
        left_lines.append('')

    # Build right column content
    right_lines = []
    summary = resume.get('summary', '')
    if summary:
        right_lines.append('SUMMARY')
        right_lines.append('─' * right_width)
        # Word wrap summary
        words = summary.split()
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= right_width:
                current += (" " if current else "") + word
            else:
                right_lines.append(current)
                current = word
        if current:
            right_lines.append(current)
        right_lines.append('')

    experience = resume.get('experience', [])
    if experience:
        right_lines.append('EXPERIENCE')
        right_lines.append('─' * right_width)
        for job in experience:
            title = job.get('title', '')
            company = job.get('company', '')
            dates = job.get('dates', '')
            header = title
            if company:
                header += f" @ {company}"
            right_lines.append(header[:right_width])
            if dates:
                right_lines.append(dates)
            for bullet in job.get('bullets', []):
                wrapped = f"• {bullet}"[:right_width]
                right_lines.append(wrapped)
            right_lines.append('')

    projects = resume.get('projects', [])
    if projects:
        right_lines.append('PROJECTS')
        right_lines.append('─' * right_width)
        for proj in projects:
            name = proj.get('name', '')
            tech = proj.get('tech', '')
            right_lines.append(f"{name} [{tech}]"[:right_width])
            desc = proj.get('description', '')
            if desc:
                right_lines.append(desc[:right_width])
            right_lines.append('')

    # Merge columns
    max_rows = max(len(left_lines), len(right_lines))
    for i in range(max_rows):
        left = left_lines[i] if i < len(left_lines) else ''
        right = right_lines[i] if i < len(right_lines) else ''
        lines.append(f"{left:<{left_width}}{separator}{right}")

    return '\n'.join(lines)


def format_one_page(resume: Dict[str, Any]) -> str:
    """One-page format: compressed, max 4 bullets per role, no fluff."""
    lines = []

    lines.append(resume.get('name', '').upper())
    lines.append(resume.get('contact', ''))
    lines.append(_section_divider('─', 50))

    summary = resume.get('summary', '')
    if summary:
        lines.append(_wrap_text(summary, 70))
        lines.append('')

    skills = resume.get('skills', [])
    if skills:
        lines.append(f"Skills: {', '.join(skills[:15])}")
        lines.append('')

    experience = resume.get('experience', [])
    if experience:
        lines.append('EXPERIENCE')
        for job in experience[:4]:  # Max 4 roles
            title = job.get('title', '')
            company = job.get('company', '')
            dates = job.get('dates', '')
            parts = [p for p in [title, company, dates] if p]
            lines.append(' | '.join(parts))
            for bullet in job.get('bullets', [])[:4]:  # Max 4 bullets
                lines.append(f"  • {bullet[:90]}")
            lines.append('')

    education = resume.get('education', [])
    if education:
        lines.append('EDUCATION')
        for edu in education[:2]:
            parts = [p for p in [edu.get('degree'), edu.get('institution'), edu.get('year')] if p]
            lines.append(' | '.join(parts))
        lines.append('')

    certs = resume.get('certifications', [])
    if certs:
        lines.append(f"Certifications: {', '.join(certs[:4])}")

    return '\n'.join(lines)


def format_two_page(resume: Dict[str, Any]) -> str:
    """Two-page format: expanded, full detail, all sections."""
    lines = []

    # Full header
    lines.append('=' * 60)
    lines.append(f"  {resume.get('name', '').upper()}")
    lines.append(f"  {resume.get('contact', '')}")
    lines.append('=' * 60)
    lines.append('')

    # Full summary
    summary = resume.get('summary', '')
    if summary:
        lines.append('━' * 40)
        lines.append('  PROFESSIONAL SUMMARY')
        lines.append('━' * 40)
        lines.append('')
        lines.append(_wrap_text(summary))
        lines.append('')

    # Full skills with categories
    skills = resume.get('skills', [])
    if skills:
        lines.append('━' * 40)
        lines.append('  TECHNICAL SKILLS & TOOLS')
        lines.append('━' * 40)
        lines.append('')
        # Group in rows of 5
        for i in range(0, len(skills), 5):
            chunk = skills[i:i+5]
            lines.append('  ' + '  |  '.join(chunk))
        lines.append('')

    # Full experience — all roles, all bullets
    experience = resume.get('experience', [])
    if experience:
        lines.append('━' * 40)
        lines.append('  PROFESSIONAL EXPERIENCE')
        lines.append('━' * 40)
        lines.append('')
        for job in experience:
            title = job.get('title', '')
            company = job.get('company', '')
            dates = job.get('dates', '')
            lines.append(f"  {title}")
            if company:
                lines.append(f"  {company}")
            if dates:
                lines.append(f"  {dates}")
            lines.append('')
            for bullet in job.get('bullets', []):
                wrapped = _wrap_text(f"  • {bullet}", 76)
                lines.append(wrapped)
            lines.append('')
            lines.append('  ' + '·' * 40)
            lines.append('')

    # Full projects
    projects = resume.get('projects', [])
    if projects:
        lines.append('━' * 40)
        lines.append('  PROJECTS')
        lines.append('━' * 40)
        lines.append('')
        for proj in projects:
            name = proj.get('name', '')
            tech = proj.get('tech', '')
            desc = proj.get('description', '')
            lines.append(f"  {name}")
            if tech:
                lines.append(f"  Technologies: {tech}")
            if desc:
                lines.append(f"  {_wrap_text(desc, 74)}")
            lines.append('')

    # Full education
    education = resume.get('education', [])
    if education:
        lines.append('━' * 40)
        lines.append('  EDUCATION')
        lines.append('━' * 40)
        lines.append('')
        for edu in education:
            lines.append(f"  {edu.get('degree', '')}")
            inst = edu.get('institution', '')
            year = edu.get('year', '')
            if inst:
                lines.append(f"  {inst}")
            if year:
                lines.append(f"  Graduated: {year}")
            details = edu.get('details', '')
            if details:
                lines.append(f"  {details}")
            lines.append('')

    # Full certifications
    certs = resume.get('certifications', [])
    if certs:
        lines.append('━' * 40)
        lines.append('  CERTIFICATIONS')
        lines.append('━' * 40)
        lines.append('')
        for cert in certs:
            lines.append(f"  ✓ {cert}")
        lines.append('')

    lines.append('=' * 60)
    return '\n'.join(lines)


def format_resume(optimized_resume: Dict[str, Any], format_type: str) -> Dict[str, str]:
    """
    Generate formatted resume content.
    Returns: { "format_type": str, "content": str }
    """
    formatters = {
        'modern': format_modern,
        'sidebar': format_sidebar,
        'one-page': format_one_page,
        'two-page': format_two_page,
    }

    formatter = formatters.get(format_type, format_modern)
    content = formatter(optimized_resume)

    return {
        'format_type': format_type,
        'content': content,
    }
