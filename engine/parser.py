"""
ATS Resume Parser — Uses Gemini AI to extract structured data from resume text.
Falls back to regex-based parsing if Gemini is unavailable.
JD parsing remains regex-based (no API needed).
"""

import os
import re
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


# ─── Common skill/keyword dictionaries ───────────────────────────────────────

PROGRAMMING_LANGUAGES = {
    'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'c', 'go', 'golang',
    'rust', 'ruby', 'php', 'swift', 'kotlin', 'scala', 'r', 'matlab', 'perl',
    'haskell', 'dart', 'lua', 'objective-c', 'shell', 'bash', 'powershell', 'sql',
    'html', 'css', 'sass', 'less', 'graphql', 'assembly'
}

FRAMEWORKS_TOOLS = {
    'react', 'angular', 'vue', 'vue.js', 'next.js', 'nextjs', 'nuxt', 'svelte',
    'django', 'flask', 'fastapi', 'spring', 'spring boot', 'express', 'express.js',
    'node.js', 'nodejs', '.net', 'asp.net', 'rails', 'ruby on rails', 'laravel',
    'tensorflow', 'pytorch', 'keras', 'scikit-learn', 'pandas', 'numpy', 'opencv',
    'docker', 'kubernetes', 'k8s', 'terraform', 'ansible', 'jenkins', 'circleci',
    'github actions', 'gitlab ci', 'aws', 'azure', 'gcp', 'google cloud',
    'firebase', 'heroku', 'vercel', 'netlify', 'nginx', 'apache',
    'mongodb', 'postgresql', 'mysql', 'redis', 'elasticsearch', 'kafka',
    'rabbitmq', 'dynamodb', 'cassandra', 'neo4j', 'sqlite',
    'git', 'jira', 'confluence', 'figma', 'sketch', 'postman', 'swagger',
    'webpack', 'vite', 'babel', 'eslint', 'prettier', 'jest', 'mocha',
    'cypress', 'selenium', 'playwright', 'pytest', 'junit',
    'linux', 'unix', 'windows server', 'macos',
    'rest', 'restful', 'grpc', 'soap', 'websocket', 'graphql',
    'ci/cd', 'devops', 'agile', 'scrum', 'kanban',
    'machine learning', 'deep learning', 'nlp', 'natural language processing',
    'computer vision', 'data science', 'data engineering', 'data analytics',
    'microservices', 'serverless', 'lambda', 'api gateway',
    'tableau', 'power bi', 'looker', 'grafana', 'prometheus',
    'airflow', 'spark', 'hadoop', 'hive', 'databricks', 'snowflake',
    'oauth', 'jwt', 'saml', 'ldap', 'sso',
    'blockchain', 'solidity', 'web3',
    's3', 'ec2', 'rds', 'cloudformation', 'ecs', 'eks', 'fargate',
    'azure devops', 'azure functions', 'cosmos db',
    'bigquery', 'cloud functions', 'cloud run', 'pub/sub',
}

SOFT_SKILLS = {
    'leadership', 'communication', 'teamwork', 'problem-solving', 'problem solving',
    'critical thinking', 'time management', 'project management', 'collaboration',
    'mentoring', 'cross-functional', 'stakeholder management', 'presentation',
    'analytical', 'strategic thinking', 'decision making', 'adaptability',
    'innovation', 'creativity', 'negotiation', 'conflict resolution',
}

SECTION_HEADERS = {
    'experience': ['experience', 'work experience', 'professional experience', 'employment', 'work history', 'career history'],
    'education': ['education', 'academic', 'academics', 'qualifications', 'academic background'],
    'skills': ['skills', 'technical skills', 'core competencies', 'competencies', 'technologies', 'tech stack', 'tools', 'proficiencies'],
    'projects': ['projects', 'personal projects', 'side projects', 'portfolio', 'key projects'],
    'certifications': ['certifications', 'certificates', 'professional certifications', 'licenses', 'credentials'],
    'summary': ['summary', 'professional summary', 'profile', 'objective', 'career objective', 'about', 'about me', 'overview'],
    'contact': ['contact', 'contact information', 'personal information', 'personal details'],
}

SENIORITY_KEYWORDS = {
    'intern': 1, 'internship': 1, 'trainee': 1, 'apprentice': 1,
    'junior': 2, 'associate': 2, 'entry level': 2, 'entry-level': 2,
    'mid': 3, 'mid-level': 3, 'intermediate': 3,
    'senior': 4, 'sr.': 4, 'sr': 4, 'lead': 4, 'staff': 4,
    'principal': 5, 'architect': 5, 'distinguished': 5,
    'manager': 4, 'director': 5, 'vp': 6, 'vice president': 6,
    'head of': 5, 'chief': 6, 'cto': 6, 'ceo': 6, 'cfo': 6, 'coo': 6,
}

ACTION_VERBS = {
    'led', 'developed', 'designed', 'implemented', 'engineered', 'built',
    'created', 'managed', 'directed', 'launched', 'deployed', 'optimized',
    'improved', 'increased', 'reduced', 'automated', 'streamlined',
    'architected', 'mentored', 'coordinated', 'established', 'delivered',
    'spearheaded', 'orchestrated', 'transformed', 'pioneered', 'scaled',
    'integrated', 'migrated', 'refactored', 'resolved', 'analyzed',
}


# ─── Helper functions ────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def _find_skills_in_text(text: str) -> List[str]:
    text_lower = text.lower()
    found = []
    all_skills = PROGRAMMING_LANGUAGES | FRAMEWORKS_TOOLS
    for skill in sorted(all_skills, key=len, reverse=True):
        pattern = r'(?<![a-zA-Z])' + re.escape(skill) + r'(?![a-zA-Z])'
        if re.search(pattern, text_lower):
            found.append(skill)
    return found


def _find_soft_skills_in_text(text: str) -> List[str]:
    text_lower = text.lower()
    return [skill for skill in SOFT_SKILLS if skill in text_lower]


def _detect_seniority(text: str) -> int:
    text_lower = text.lower()
    max_level = 1
    for keyword, level in SENIORITY_KEYWORDS.items():
        if keyword in text_lower:
            max_level = max(max_level, level)
    return max_level


def _extract_years_of_experience(text: str) -> float:
    date_patterns = re.findall(
        r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(\d{4})\s*[-–—]\s*(?:(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(\d{4})|[Pp]resent|[Cc]urrent|[Nn]ow)',
        text, re.IGNORECASE
    )
    total_years = 0
    current_year = 2026
    for match in date_patterns:
        start_year = int(match[0])
        end_year = int(match[1]) if match[1] else current_year
        total_years += max(0, end_year - start_year)
    return total_years if total_years > 0 else 0


def _split_sections(text: str) -> Dict[str, str]:
    sections = {}
    lines = text.split('\n')
    current_section = 'header'
    current_content = []

    for line in lines:
        stripped = line.strip().lower()
        cleaned = re.sub(r'[=\-_*#|:]+', '', stripped).strip()

        found_section = None
        for section_key, headers in SECTION_HEADERS.items():
            if cleaned in headers:
                found_section = section_key
                break

        if found_section:
            sections[current_section] = '\n'.join(current_content)
            current_section = found_section
            current_content = []
        else:
            current_content.append(line)

    sections[current_section] = '\n'.join(current_content)
    return sections


# ─── Gemini-Powered Resume Parser ────────────────────────────────────────────

def _parse_resume_with_gemini(text: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Send raw resume text to Gemini and get structured JSON back."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        prompt = f"""You are a professional resume parser. Parse the following resume text into a structured JSON object.

STRICT RULES:
1. Extract EXACTLY what is in the resume — do NOT invent or add any information.
2. For experience: carefully detect ALL job entries, even if formatting is inconsistent.
3. For bullets: capture every bullet point or responsibility line under each job.
4. For skills: extract ALL technical skills, tools, languages, and frameworks mentioned anywhere.
5. If a field is not found, use an empty string or empty array.

RESUME TEXT:
{text}

Return ONLY a valid JSON object with this EXACT structure (no markdown, no code blocks, no explanation):
{{
  "name": "<full name>",
  "email": "<email or empty string>",
  "phone": "<phone number or empty string>",
  "summary": "<professional summary/objective text or empty string>",
  "skills": ["<skill1>", "<skill2>", ...],
  "experience": [
    {{
      "title": "<job title>",
      "company": "<company name>",
      "dates": "<date range e.g. Jan 2020 - Present>",
      "bullets": [
        "<bullet point 1>",
        "<bullet point 2>"
      ]
    }}
  ],
  "education": [
    {{
      "degree": "<degree name>",
      "institution": "<university/college name>",
      "year": "<graduation year or date range>",
      "details": "<GPA, honors, relevant coursework, or empty string>"
    }}
  ],
  "projects": [
    {{
      "name": "<project name>",
      "tech": "<technologies used>",
      "description": "<what it does>"
    }}
  ],
  "certifications": ["<cert1>", "<cert2>"]
}}"""

        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=4096,
            )
        )

        response_text = response.text.strip()
        # Clean markdown code blocks if present
        response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
        response_text = re.sub(r'\n?```\s*$', '', response_text)
        response_text = response_text.strip()

        parsed = json.loads(response_text)
        logger.info("Gemini resume parsing succeeded")
        return parsed

    except Exception as e:
        logger.warning(f"Gemini resume parsing failed: {e}. Falling back to regex.")
        return None


# ─── Regex fallback parser (used when Gemini is unavailable) ─────────────────

def _regex_parse_experience(experience_text: str) -> List[Dict[str, Any]]:
    """Parse experience section into individual job blocks (regex fallback)."""
    if not experience_text.strip():
        return []

    blocks = []
    lines = experience_text.strip().split('\n')
    current_block = None
    bullet_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        has_dates = bool(re.search(r'\d{4}', stripped))
        is_bullet = stripped.startswith(('-', '•', '●', '▪', '◦', '*', '→', '‣'))

        if has_dates and not is_bullet:
            if current_block:
                current_block['bullets'] = bullet_lines
                blocks.append(current_block)
                bullet_lines = []

            date_match = re.search(
                r'((?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?\d{4}\s*[-–—]\s*(?:(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow))',
                stripped, re.IGNORECASE
            )
            dates = date_match.group(1).strip() if date_match else ""
            remainder = stripped[:date_match.start()] + stripped[date_match.end():] if date_match else stripped
            remainder = re.sub(r'[|,]', ' | ', remainder).strip()
            remainder = re.sub(r'\s+', ' ', remainder).strip(' |')
            parts = re.split(r'\s*[|@–—]\s*', remainder)
            title = parts[0].strip() if len(parts) > 0 else "Unknown"
            company = parts[1].strip() if len(parts) > 1 else ""
            title = re.sub(r'^[-•●▪*]\s*', '', title)
            current_block = {'title': title, 'company': company, 'dates': dates}
        elif is_bullet:
            bullet_text = re.sub(r'^[-•●▪◦*→‣]\s*', '', stripped)
            if bullet_text:
                bullet_lines.append(bullet_text)
        elif current_block and not has_dates:
            if not current_block.get('company'):
                current_block['company'] = stripped
            elif bullet_lines:
                bullet_lines[-1] += ' ' + stripped
            else:
                bullet_lines.append(stripped)

    if current_block:
        current_block['bullets'] = bullet_lines
        blocks.append(current_block)

    return blocks


def _regex_parse_education(education_text: str) -> List[Dict[str, str]]:
    """Parse education section (regex fallback)."""
    if not education_text.strip():
        return []

    blocks = []
    lines = [l.strip() for l in education_text.strip().split('\n') if l.strip()]
    current = {}

    for line in lines:
        is_bullet = line.startswith(('-', '•', '●', '▪', '*'))
        if is_bullet:
            detail = re.sub(r'^[-•●▪*]\s*', '', line)
            if current:
                current.setdefault('details', '')
                current['details'] += (', ' if current['details'] else '') + detail
            continue

        year_match = re.search(r'(\d{4})', line)
        has_degree = bool(re.search(
            r'(?:bachelor|master|phd|doctorate|associate|diploma|b\.?s\.?|b\.?a\.?|m\.?s\.?|m\.?a\.?|m\.?b\.?a\.?|b\.?tech|m\.?tech|b\.?e\.?|m\.?e\.?)',
            line, re.IGNORECASE
        ))

        if has_degree or year_match:
            if current:
                blocks.append(current)
            parts = re.split(r'\s*[|,–—@]\s*', line)
            degree = parts[0].strip() if parts else line
            institution = parts[1].strip() if len(parts) > 1 else ""
            year = year_match.group(1) if year_match else ""
            if year:
                degree = degree.replace(year, '').strip(' ,|-–')
                institution = institution.replace(year, '').strip(' ,|-–')
            current = {'degree': degree, 'institution': institution, 'year': year, 'details': ''}
        elif current and not current.get('institution'):
            current['institution'] = line

    if current:
        blocks.append(current)

    return blocks


def _regex_parse_projects(projects_text: str) -> List[Dict[str, str]]:
    """Parse projects section (regex fallback)."""
    if not projects_text.strip():
        return []

    projects = []
    lines = [l.strip() for l in projects_text.strip().split('\n') if l.strip()]
    current = None

    for line in lines:
        is_bullet = line.startswith(('-', '•', '●', '▪', '*', '→'))
        if not is_bullet and len(line) < 100:
            if current:
                projects.append(current)
            tech_match = re.search(r'\(([^)]+)\)', line)
            tech = tech_match.group(1) if tech_match else ""
            name = re.sub(r'\([^)]+\)', '', line).strip(' |-–:')
            current = {'name': name, 'tech': tech, 'description': ''}
        elif is_bullet and current:
            desc = re.sub(r'^[-•●▪*→]\s*', '', line)
            current['description'] += (' ' if current['description'] else '') + desc
        elif current:
            current['description'] += ' ' + line

    if current:
        projects.append(current)
    return projects


def _extract_certifications(text: str) -> List[str]:
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    certs = []
    for line in lines:
        cert = re.sub(r'^[-•●▪*→]\s*', '', line).strip()
        if cert and len(cert) > 3:
            certs.append(cert)
    return certs


# ─── Main parse functions ────────────────────────────────────────────────────

def parse_resume(text: str, gemini_api_key: str = None) -> Dict[str, Any]:
    """
    Parse resume text into structured data.
    Uses Gemini AI for accurate extraction, with regex fallback.
    """
    text = _clean_text(text)

    # Try to get the API key from env if not passed
    if not gemini_api_key:
        gemini_api_key = os.getenv('GEMINI_API_KEY', '')

    # ── Try Gemini-powered parsing first ──
    gemini_result = None
    if gemini_api_key:
        gemini_result = _parse_resume_with_gemini(text, gemini_api_key)

    if gemini_result:
        # Gemini succeeded — build the result from its output
        name = gemini_result.get('name', 'Unknown') or 'Unknown'
        email = gemini_result.get('email', '') or None
        phone = gemini_result.get('phone', '') or None

        contact_parts = [p for p in [email, phone] if p]
        contact = ' | '.join(contact_parts) if contact_parts else ""

        # Merge Gemini-detected skills with our dictionary-based scan
        gemini_skills = gemini_result.get('skills', [])
        dict_skills = _find_skills_in_text(text)
        all_skills = list(dict.fromkeys(
            [s.lower() for s in gemini_skills] + dict_skills
        ))

        experience = gemini_result.get('experience', [])
        # Ensure each experience entry has 'bullets' as a list
        for job in experience:
            if not isinstance(job, dict):
                continue
            if 'bullets' not in job:
                job['bullets'] = []

        education = gemini_result.get('education', [])
        projects = gemini_result.get('projects', [])
        certifications = gemini_result.get('certifications', [])
        summary = gemini_result.get('summary', '')

    else:
        # ── Regex fallback ──
        sections = _split_sections(text)

        # Extract contact
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
        email = email_match.group(0) if email_match else None
        phone_match = re.search(r'[\+]?[(]?[0-9]{1,4}[)]?[-\s./0-9]{7,15}', text)
        phone = phone_match.group(0).strip() if phone_match else None

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        first_line = lines[0] if lines else "Unknown"
        if len(first_line) < 60 and '@' not in first_line:
            name = re.sub(r'[^a-zA-Z\s.\-]', '', first_line).strip()
            if not name or len(name.split()) > 5:
                name = "Unknown"
        else:
            name = "Unknown"

        contact_parts = [p for p in [email, phone] if p]
        contact = ' | '.join(contact_parts) if contact_parts else ""

        skills_from_section = _find_skills_in_text(sections.get('skills', ''))
        skills_from_full = _find_skills_in_text(text)
        all_skills = list(dict.fromkeys(skills_from_section + skills_from_full))

        experience = _regex_parse_experience(sections.get('experience', ''))
        education = _regex_parse_education(sections.get('education', ''))
        projects = _regex_parse_projects(sections.get('projects', ''))
        certifications = _extract_certifications(sections.get('certifications', ''))
        summary = sections.get('summary', '').strip()

    soft_skills = _find_soft_skills_in_text(text)
    years_exp = _extract_years_of_experience(text)
    seniority = _detect_seniority(text)
    sections = _split_sections(text)

    return {
        'name': name,
        'contact': contact,
        'email': email,
        'phone': phone,
        'linkedin': re.search(r'(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?', text, re.IGNORECASE),
        'summary': summary.strip() if isinstance(summary, str) else '',
        'skills': all_skills,
        'soft_skills': soft_skills,
        'experience': experience,
        'education': education,
        'projects': projects,
        'certifications': certifications,
        'years_of_experience': years_exp,
        'seniority_level': seniority,
        'raw_text': text,
        'sections': sections,
    }


def parse_job_description(text: str) -> Dict[str, Any]:
    """Parse job description text into structured data (regex-based, no API needed)."""
    text = _clean_text(text)
    text_lower = text.lower()

    technical_skills = _find_skills_in_text(text)
    soft_skills_found = _find_soft_skills_in_text(text)

    required_skills = []
    preferred_skills = []

    required_section = text_lower
    preferred_section = ""

    for marker in ['preferred', 'nice to have', 'nice-to-have', 'bonus', 'plus', 'desired', 'optional']:
        idx = text_lower.find(marker)
        if idx > 0:
            required_section = text_lower[:idx]
            preferred_section = text_lower[idx:]
            break

    for skill in technical_skills:
        if skill in preferred_section and skill not in required_section:
            preferred_skills.append(skill)
        else:
            required_skills.append(skill)

    seniority = _detect_seniority(text)

    years_match = re.search(r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)?', text_lower)
    required_years = int(years_match.group(1)) if years_match else 0

    all_keywords = list(dict.fromkeys(technical_skills + soft_skills_found))

    responsibilities = []
    for line in text.split('\n'):
        stripped = line.strip()
        if stripped.startswith(('-', '•', '●', '▪', '*', '→')):
            resp = re.sub(r'^[-•●▪*→]\s*', '', stripped)
            if resp and len(resp) > 10:
                responsibilities.append(resp)

    domains = {
        'fintech': ['fintech', 'financial', 'banking', 'payment', 'trading'],
        'healthcare': ['healthcare', 'health', 'medical', 'clinical', 'pharma'],
        'e-commerce': ['e-commerce', 'ecommerce', 'retail', 'marketplace'],
        'saas': ['saas', 'platform', 'subscription'],
        'ai/ml': ['machine learning', 'artificial intelligence', 'ai', 'ml', 'deep learning'],
        'cybersecurity': ['security', 'cybersecurity', 'infosec', 'threat'],
        'gaming': ['gaming', 'game', 'unity', 'unreal'],
        'edtech': ['education', 'edtech', 'learning', 'lms'],
    }
    detected_domain = 'general'
    for domain, keywords in domains.items():
        if any(kw in text_lower for kw in keywords):
            detected_domain = domain
            break

    return {
        'required_skills': required_skills,
        'preferred_skills': preferred_skills,
        'all_skills': technical_skills,
        'soft_skills': soft_skills_found,
        'keywords': all_keywords,
        'responsibilities': responsibilities,
        'seniority_level': seniority,
        'required_years': required_years,
        'domain': detected_domain,
        'raw_text': text,
    }
