"""
Resume Optimizer — Uses Gemini AI to rewrite and optimize the resume for ATS.
"""

import json
import re
from typing import Dict, Any, Optional

import google.generativeai as genai


def _build_optimization_prompt(parsed_resume: Dict, parsed_jd: Dict) -> str:
    """Build the prompt for Gemini to optimize the resume."""

    resume_summary = parsed_resume.get('summary', '')
    skills = ', '.join(parsed_resume.get('skills', []))
    experience_text = ""
    for job in parsed_resume.get('experience', []):
        bullets = '\n    - '.join(job.get('bullets', []))
        experience_text += f"\n  Title: {job.get('title', '')}\n  Company: {job.get('company', '')}\n  Dates: {job.get('dates', '')}\n  Bullets:\n    - {bullets}\n"

    projects_text = ""
    for proj in parsed_resume.get('projects', []):
        projects_text += f"\n  Name: {proj.get('name', '')}\n  Tech: {proj.get('tech', '')}\n  Description: {proj.get('description', '')}\n"

    education_text = ""
    for edu in parsed_resume.get('education', []):
        education_text += f"\n  Degree: {edu.get('degree', '')}\n  Institution: {edu.get('institution', '')}\n  Year: {edu.get('year', '')}\n  Details: {edu.get('details', '')}\n"

    certs = ', '.join(parsed_resume.get('certifications', []))

    jd_required = ', '.join(parsed_jd.get('required_skills', []))
    jd_preferred = ', '.join(parsed_jd.get('preferred_skills', []))
    jd_responsibilities = '\n- '.join(parsed_jd.get('responsibilities', []))

    prompt = f"""You are an expert ATS resume optimizer. Your job is to rewrite the candidate's resume to maximize ATS match score for the given job description.

STRICT RULES (NON-NEGOTIABLE):
1. NEVER invent job titles, companies, dates, or metrics not in the original resume
2. NEVER add certifications or degrees the candidate does not have
3. NEVER keyword-stuff — all keywords must appear naturally in context
4. Rewrite every bullet with: [Strong Past-Tense Action Verb] + [What Was Done] + [Measurable Result or Scale]
5. Tailor the summary directly to the JD's top 3 priorities
6. Inject missing JD keywords ONLY where the candidate's actual experience justifies it
7. Elevate weak language: "helped with" → "led", "worked on" → "engineered", "responsible for" → "owned"
8. Remove filler phrases: "team player", "hard worker", "detail-oriented" unless backed by evidence

ORIGINAL RESUME DATA:
Name: {parsed_resume.get('name', 'Unknown')}
Contact: {parsed_resume.get('contact', '')}
Summary: {resume_summary}
Skills: {skills}
Experience: {experience_text}
Projects: {projects_text}
Education: {education_text}
Certifications: {certs}

JOB DESCRIPTION REQUIREMENTS:
Required Skills: {jd_required}
Preferred Skills: {jd_preferred}
Key Responsibilities:
- {jd_responsibilities}
Domain: {parsed_jd.get('domain', 'general')}
Seniority: Level {parsed_jd.get('seniority_level', 'unknown')}
Required Years: {parsed_jd.get('required_years', 'not specified')}

Return ONLY a valid JSON object with this exact structure (no markdown, no code blocks):
{{
  "summary": "<2-3 sentence summary targeting JD's top priorities, using JD keywords naturally>",
  "skills": ["<skill1>", "<skill2>", ...],
  "experience": [
    {{
      "title": "<Exact original job title>",
      "company": "<Exact original company>",
      "dates": "<Exact original dates>",
      "bullets": [
        "<Past-tense action verb + specific action + quantified result>"
      ]
    }}
  ],
  "projects": [
    {{
      "name": "<Project name>",
      "tech": "<Tech stack>",
      "description": "<What it does + measurable impact>"
    }}
  ],
  "education": [
    {{
      "degree": "<Degree>",
      "institution": "<Institution>",
      "year": "<Year>",
      "details": "<GPA, honors, relevant coursework>"
    }}
  ],
  "certifications": ["<Only certs from original resume>"],
  "tailoring_notes": "<2-3 sentences: what was changed, which JD requirements drove those changes, and how the changes improve ATS match>"
}}"""

    return prompt


def optimize_resume(
    parsed_resume: Dict,
    parsed_jd: Dict,
    gemini_api_key: str,
) -> Dict[str, Any]:
    """
    Use Gemini to optimize the resume for ATS match.
    Returns the optimized resume dict + tailoring notes.
    """
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-2.0-flash')

    prompt = _build_optimization_prompt(parsed_resume, parsed_jd)

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=4096,
            )
        )

        response_text = response.text.strip()

        # Clean markdown code blocks if present
        response_text = re.sub(r'^```(?:json)?\s*\n?', '', response_text)
        response_text = re.sub(r'\n?```\s*$', '', response_text)
        response_text = response_text.strip()

        optimized = json.loads(response_text)

        # Validate and ensure original data is preserved where needed
        optimized_resume = {
            'name': parsed_resume.get('name', 'Unknown'),
            'contact': parsed_resume.get('contact', ''),
            'summary': optimized.get('summary', parsed_resume.get('summary', '')),
            'skills': optimized.get('skills', parsed_resume.get('skills', [])),
            'experience': optimized.get('experience', []),
            'projects': optimized.get('projects', []),
            'education': optimized.get('education', []),
            'certifications': optimized.get('certifications', parsed_resume.get('certifications', [])),
        }

        tailoring_notes = optimized.get('tailoring_notes', 'Resume was optimized to better match the job description keywords and requirements.')

        return {
            'optimized_resume': optimized_resume,
            'tailoring_notes': tailoring_notes,
        }

    except json.JSONDecodeError as e:
        # Fallback: return original resume with minor enhancements
        return _fallback_optimize(parsed_resume, parsed_jd, str(e))
    except Exception as e:
        return _fallback_optimize(parsed_resume, parsed_jd, str(e))


def _fallback_optimize(parsed_resume: Dict, parsed_jd: Dict, error: str) -> Dict[str, Any]:
    """Fallback optimization when Gemini fails — rule-based enhancement."""

    # Enhance skills list with JD keywords that are justified
    resume_skills = list(parsed_resume.get('skills', []))
    jd_skills = parsed_jd.get('required_skills', []) + parsed_jd.get('preferred_skills', [])
    resume_text_lower = parsed_resume.get('raw_text', '').lower()

    for skill in jd_skills:
        if skill.lower() in resume_text_lower and skill not in resume_skills:
            resume_skills.append(skill)

    # Basic bullet enhancement
    enhanced_experience = []
    weak_to_strong = {
        'responsible for': 'Managed',
        'helped with': 'Contributed to',
        'worked on': 'Developed',
        'assisted in': 'Supported',
        'involved in': 'Participated in',
        'duties included': 'Executed',
        'tasked with': 'Delivered',
    }

    for job in parsed_resume.get('experience', []):
        enhanced_bullets = []
        for bullet in job.get('bullets', []):
            enhanced = bullet
            for weak, strong in weak_to_strong.items():
                if enhanced.lower().startswith(weak):
                    enhanced = strong + enhanced[len(weak):]
            enhanced_bullets.append(enhanced)

        enhanced_experience.append({
            'title': job.get('title', ''),
            'company': job.get('company', ''),
            'dates': job.get('dates', ''),
            'bullets': enhanced_bullets,
        })

    return {
        'optimized_resume': {
            'name': parsed_resume.get('name', 'Unknown'),
            'contact': parsed_resume.get('contact', ''),
            'summary': parsed_resume.get('summary', ''),
            'skills': resume_skills,
            'experience': enhanced_experience,
            'projects': [
                {
                    'name': p.get('name', ''),
                    'tech': p.get('tech', ''),
                    'description': p.get('description', ''),
                }
                for p in parsed_resume.get('projects', [])
            ],
            'education': [
                {
                    'degree': e.get('degree', ''),
                    'institution': e.get('institution', ''),
                    'year': e.get('year', ''),
                    'details': e.get('details', ''),
                }
                for e in parsed_resume.get('education', [])
            ],
            'certifications': parsed_resume.get('certifications', []),
        },
        'tailoring_notes': 'Resume was optimized using rule-based enhancement. Skills list enhanced with JD keywords found in resume text. Weak bullet phrases replaced with stronger action verbs.',
    }
