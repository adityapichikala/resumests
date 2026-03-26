"""
ATS Scorer — Computes match scores across 5 dimensions and makes PASS/FAIL decision.
"""

import re
from typing import Dict, List, Any, Tuple


def _normalize_skill(skill: str) -> str:
    """Normalize a skill name for comparison."""
    return skill.lower().strip().replace('-', ' ').replace('.', '').replace('/', ' ')


def _build_keyword_set(text: str) -> set:
    """Build a set of normalized keywords from text."""
    text = text.lower()
    # Split on non-alphanumeric (keeping common tech characters)
    words = re.findall(r'[a-z0-9#+./\-]+', text)
    # Also add bigrams for multi-word skills
    bigrams = set()
    for i in range(len(words) - 1):
        bigrams.add(f"{words[i]} {words[i+1]}")
    # And trigrams
    for i in range(len(words) - 2):
        bigrams.add(f"{words[i]} {words[i+1]} {words[i+2]}")
    return set(words) | bigrams


def score_keyword_match(parsed_resume: Dict, parsed_jd: Dict) -> int:
    """
    Score keyword overlap between resume and JD (0-100).
    Uses TF-IDF-style matching: checks what % of JD keywords appear in the resume.
    """
    jd_keywords = parsed_jd.get('keywords', [])
    if not jd_keywords:
        return 50  # No keywords to match against

    resume_text = parsed_resume.get('raw_text', '').lower()
    resume_keyword_set = _build_keyword_set(resume_text)

    matched = 0
    for kw in jd_keywords:
        normalized = _normalize_skill(kw)
        if normalized in resume_keyword_set or normalized in resume_text:
            matched += 1

    score = int((matched / len(jd_keywords)) * 100)
    return min(100, score)


def score_skills_match(parsed_resume: Dict, parsed_jd: Dict) -> Tuple[int, List[str], List[str]]:
    """
    Score required skills coverage (0-100).
    Returns: (score, matched_skills, missing_skills)
    """
    required = parsed_jd.get('required_skills', [])
    if not required:
        # Fall back to all skills
        required = parsed_jd.get('all_skills', [])
    if not required:
        return 50, [], []

    resume_skills = set(_normalize_skill(s) for s in parsed_resume.get('skills', []))
    resume_text = parsed_resume.get('raw_text', '').lower()

    matched = []
    missing = []

    for skill in required:
        normalized = _normalize_skill(skill)
        if normalized in resume_skills or normalized in resume_text:
            matched.append(skill)
        else:
            missing.append(skill)

    score = int((len(matched) / len(required)) * 100) if required else 50
    return min(100, score), matched, missing


def score_experience(parsed_resume: Dict, parsed_jd: Dict) -> int:
    """
    Score experience alignment (0-100).
    Considers: years of experience, seniority level, domain match.
    """
    resume_years = parsed_resume.get('years_of_experience', 0)
    jd_years = parsed_jd.get('required_years', 0)
    resume_seniority = parsed_resume.get('seniority_level', 1)
    jd_seniority = parsed_jd.get('seniority_level', 1)

    # Years score (0-40 points)
    years_score = 40
    if jd_years > 0:
        if resume_years >= jd_years:
            years_score = 40
        elif resume_years >= jd_years * 0.7:
            years_score = 30
        elif resume_years >= jd_years * 0.5:
            years_score = 20
        else:
            years_score = int(10 * (resume_years / max(jd_years, 1)))

    # Seniority score (0-35 points)
    seniority_diff = resume_seniority - jd_seniority
    if seniority_diff >= 0:
        seniority_score = 35
    elif seniority_diff == -1:
        seniority_score = 25
    elif seniority_diff == -2:
        seniority_score = 15
    else:
        seniority_score = 5

    # Domain score (0-25 points)
    jd_domain = parsed_jd.get('domain', 'general')
    resume_text_lower = parsed_resume.get('raw_text', '').lower()
    if jd_domain == 'general':
        domain_score = 20
    elif jd_domain in resume_text_lower:
        domain_score = 25
    else:
        domain_score = 10

    total = years_score + seniority_score + domain_score
    return min(100, total)


def score_achievements(parsed_resume: Dict) -> int:
    """
    Score bullet point quality (0-100).
    Checks: action verbs, quantified metrics, specificity.
    """
    experience = parsed_resume.get('experience', [])
    if not experience:
        return 20

    total_bullets = 0
    strong_bullets = 0
    has_metrics = 0
    has_action_verb = 0

    action_verbs = {
        'led', 'developed', 'designed', 'implemented', 'engineered', 'built',
        'created', 'managed', 'directed', 'launched', 'deployed', 'optimized',
        'improved', 'increased', 'reduced', 'automated', 'streamlined',
        'architected', 'mentored', 'coordinated', 'established', 'delivered',
        'spearheaded', 'orchestrated', 'transformed', 'pioneered', 'scaled',
        'integrated', 'migrated', 'refactored', 'resolved', 'analyzed',
        'achieved', 'accelerated', 'consolidated', 'drove', 'executed',
        'generated', 'negotiated', 'overhauled', 'revamped', 'secured',
    }

    weak_phrases = [
        'responsible for', 'helped with', 'worked on', 'assisted',
        'involved in', 'participated', 'duties included', 'tasked with',
    ]

    for job in experience:
        for bullet in job.get('bullets', []):
            total_bullets += 1
            bullet_lower = bullet.lower().strip()

            # Check for action verb start
            first_word = bullet_lower.split()[0] if bullet_lower.split() else ''
            if first_word in action_verbs:
                has_action_verb += 1

            # Check for metrics/numbers
            if re.search(r'\d+[%$kKmMbB]|\d+\s*(?:percent|%|users|customers|clients|projects|team|members|revenue|savings)', bullet):
                has_metrics += 1

            # Check for weak phrases
            has_weak = any(wp in bullet_lower for wp in weak_phrases)

            # A strong bullet has action verb + no weak phrases + ideally a metric
            if first_word in action_verbs and not has_weak:
                strong_bullets += 1

    if total_bullets == 0:
        return 20

    # Metric density (0-40 points)
    metric_ratio = has_metrics / total_bullets
    metric_score = int(metric_ratio * 40)

    # Action verb usage (0-30 points)
    verb_ratio = has_action_verb / total_bullets
    verb_score = int(verb_ratio * 30)

    # Strong bullet ratio (0-30 points)
    strong_ratio = strong_bullets / total_bullets
    strength_score = int(strong_ratio * 30)

    return min(100, metric_score + verb_score + strength_score)


def score_formatting(parsed_resume: Dict) -> int:
    """
    Score ATS-friendliness of formatting (0-100).
    Checks: standard sections present, clean structure, no problematic elements.
    """
    sections = parsed_resume.get('sections', {})
    score = 0

    # Has essential sections (40 points)
    essential = ['experience', 'education', 'skills']
    for section in essential:
        if section in sections and sections[section].strip():
            score += 13
    if score >= 39:
        score = 40

    # Has contact info (15 points)
    if parsed_resume.get('email'):
        score += 8
    if parsed_resume.get('phone'):
        score += 7

    # Has summary (10 points)
    if 'summary' in sections and sections['summary'].strip():
        score += 10

    # Has name (5 points)
    if parsed_resume.get('name') != 'Unknown':
        score += 5

    # Has reasonable number of bullets (15 points)
    total_bullets = sum(len(job.get('bullets', [])) for job in parsed_resume.get('experience', []))
    if total_bullets >= 6:
        score += 15
    elif total_bullets >= 3:
        score += 10
    elif total_bullets >= 1:
        score += 5

    # Has consistent formatting (15 points) — check for dates in experience
    experience = parsed_resume.get('experience', [])
    if experience:
        dated = sum(1 for job in experience if job.get('dates'))
        if dated == len(experience):
            score += 15
        elif dated > 0:
            score += 8

    return min(100, score)


def compute_overall_score(keyword: int, skills: int, experience: int, achievement: int, formatting: int) -> int:
    """Compute weighted overall score."""
    weighted = (keyword * 0.25) + (skills * 0.30) + (experience * 0.20) + (achievement * 0.15) + (formatting * 0.10)
    return int(weighted)


def make_ats_decision(
    overall_score: int,
    skills_score: int,
    achievement_score: int,
    experience_score: int,
    missing_skills: List[str],
    parsed_resume: Dict,
    parsed_jd: Dict,
) -> Tuple[str, List[str], int]:
    """
    Make binary ATS PASS/FAIL decision.
    Returns: (decision, failure_reasons, capped_score)
    If FAIL, the overall score is capped at 69 max to avoid confusing UX.
    """
    failure_reasons = []

    if overall_score < 55:
        failure_reasons.append(
            f"Overall match score is {overall_score}/100 (threshold: 55). "
            f"Resume does not meet minimum qualification bar for this role."
        )

    # Count critical missing skills (from required, not preferred)
    critical_missing = missing_skills[:10]  # Cap at 10 for readability
    if len(missing_skills) >= 3:
        skills_list = ', '.join(missing_skills[:5])
        failure_reasons.append(
            f"Missing {len(missing_skills)} critical required skills: {skills_list}. "
            f"These are listed as must-haves in the job description."
        )

    if achievement_score < 30:
        failure_reasons.append(
            f"Achievement score is {achievement_score}/100 (threshold: 30). "
            f"Resume bullets lack quantified metrics, measurable results, or impact statements. "
            f"Most bullets use weak/passive language."
        )

    if experience_score < 40:
        resume_years = parsed_resume.get('years_of_experience', 0)
        jd_years = parsed_jd.get('required_years', 0)
        failure_reasons.append(
            f"Experience score is {experience_score}/100 (threshold: 40). "
            f"Resume shows ~{resume_years} years vs. {jd_years}+ years required. "
            f"Severe seniority/experience level mismatch."
        )

    decision = "FAIL" if failure_reasons else "PASS"

    # Cap the score at 69 if FAIL — a failing resume should never display 70+
    capped_score = min(overall_score, 69) if decision == "FAIL" else overall_score

    return decision, failure_reasons, capped_score


def get_confidence_level(
    overall_score: int,
    keyword_score: int,
    skills_score: int,
    experience_score: int,
    achievement_score: int,
    formatting_score: int,
) -> str:
    """Determine confidence level of the ATS decision."""
    scores = [keyword_score, skills_score, experience_score, achievement_score, formatting_score]
    min_score = min(scores)
    below_50_count = sum(1 for s in scores if s < 50)

    if overall_score > 80 and min_score >= 60:
        return "high"
    elif overall_score < 55 or below_50_count >= 2:
        return "low"
    else:
        return "medium"


def generate_ats_issues(parsed_resume: Dict, parsed_jd: Dict) -> List[str]:
    """Generate specific structural/keyword/formatting issues."""
    issues = []

    # Check for weak bullet points
    for job in parsed_resume.get('experience', []):
        weak_phrases = ['responsible for', 'helped with', 'worked on', 'assisted in', 'involved in', 'duties included']
        for bullet in job.get('bullets', []):
            bullet_lower = bullet.lower()
            for wp in weak_phrases:
                if wp in bullet_lower:
                    issues.append(
                        f"Bullet under '{job.get('title', 'Unknown')}' role uses passive/weak language: "
                        f"'{bullet[:80]}...'. Replace '{wp}' with a strong action verb."
                    )
                    break

            # Check for lack of metrics
            if not re.search(r'\d', bullet):
                first_words = ' '.join(bullet.split()[:6])
                issues.append(
                    f"Bullet under '{job.get('title', 'Unknown')}' lacks quantified metrics: "
                    f"'{first_words}...'. Add numbers, percentages, or scale."
                )

    # Check for missing sections
    sections = parsed_resume.get('sections', {})
    if 'summary' not in sections or not sections.get('summary', '').strip():
        issues.append("Missing Professional Summary section. ATS systems favor resumes with a targeted summary.")

    if not parsed_resume.get('email'):
        issues.append("No email address detected. Ensure contact information is in plain text, not in headers/footers.")

    if not parsed_resume.get('skills'):
        issues.append("No dedicated Skills section detected, or skills are embedded in prose. Create a clear Skills section with comma-separated keywords.")

    # Check for too few bullets
    for job in parsed_resume.get('experience', []):
        bullet_count = len(job.get('bullets', []))
        if bullet_count < 2:
            issues.append(
                f"Role '{job.get('title', 'Unknown')}' at '{job.get('company', 'Unknown')}' has only {bullet_count} bullet(s). "
                f"Aim for 3-5 impactful bullets per role."
            )

    return issues[:15]  # Cap at 15


def generate_suggestions(
    parsed_resume: Dict,
    parsed_jd: Dict,
    missing_skills: List[str],
    scores: Dict[str, int],
) -> List[str]:
    """Generate actionable improvement suggestions."""
    suggestions = []

    # Missing skills suggestions
    if missing_skills:
        top_missing = missing_skills[:5]
        suggestions.append(
            f"Add these missing required skills to your Skills section: {', '.join(top_missing)}. "
            f"Reference them in your most recent role's bullet points where your experience justifies it."
        )

    # Achievement improvement
    if scores.get('achievement', 0) < 60:
        suggestions.append(
            "Rewrite bullet points using the formula: [Action Verb] + [What You Did] + [Measurable Result]. "
            "Example: 'Reduced API response time by 40% by implementing Redis caching layer, serving 2M+ daily requests.'"
        )

    # Keyword improvement
    if scores.get('keyword', 0) < 60:
        jd_keywords = parsed_jd.get('keywords', [])[:5]
        if jd_keywords:
            suggestions.append(
                f"Increase keyword density by naturally incorporating these JD terms: {', '.join(jd_keywords)}. "
                f"Place them in your summary, skills section, and relevant bullet points."
            )

    # Experience improvement
    if scores.get('experience', 0) < 60:
        suggestions.append(
            "Strengthen experience alignment by emphasizing projects and responsibilities that match "
            "the JD's core requirements. Lead with your most relevant role."
        )

    # Formatting improvement
    if scores.get('formatting', 0) < 70:
        sections = parsed_resume.get('sections', {})
        missing_sections = []
        for section in ['summary', 'experience', 'education', 'skills']:
            if section not in sections or not sections.get(section, '').strip():
                missing_sections.append(section.title())
        if missing_sections:
            suggestions.append(
                f"Add these standard resume sections: {', '.join(missing_sections)}. "
                f"ATS parsers expect these sections with standard headers."
            )

    # Summary improvement
    summary = parsed_resume.get('summary', '').strip()
    if not summary:
        suggestions.append(
            "Add a Professional Summary (2-3 sentences) directly targeting the JD's top priorities. "
            "Include your years of experience, key skills from the JD, and your strongest achievement."
        )
    elif len(summary) < 50:
        suggestions.append(
            "Expand your Professional Summary to 2-3 sentences. Include specific JD keywords, "
            "years of experience, and a highlight achievement."
        )

    # Certifications suggestion
    if not parsed_resume.get('certifications'):
        jd_text = parsed_jd.get('raw_text', '').lower()
        if any(word in jd_text for word in ['certified', 'certification', 'certificate']):
            suggestions.append(
                "The JD mentions certifications. If you have relevant certifications, "
                "add a Certifications section. If not, consider pursuing relevant certifications."
            )

    return suggestions[:10]  # Cap at 10
