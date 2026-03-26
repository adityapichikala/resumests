"""
ATS Pipeline — Orchestrates the full analysis in two phases:
  Phase 1: parse → score → issues → suggestions (uses Gemini for parsing)
  Phase 2: optimize → format (uses Gemini for rewriting)
"""

import os
from typing import Dict, Any

from engine.parser import parse_resume, parse_job_description
from engine.scorer import (
    score_keyword_match,
    score_skills_match,
    score_experience,
    score_achievements,
    score_formatting,
    compute_overall_score,
    make_ats_decision,
    get_confidence_level,
    generate_ats_issues,
    generate_suggestions,
)
from engine.optimizer import optimize_resume
from engine.formatter import format_resume


def run_analysis_only(resume_text: str, jd_text: str, gemini_api_key: str = None) -> Dict[str, Any]:
    """
    Phase 1: Parse (via Gemini) + Score + Issues + Suggestions.
    Returns analysis results with parsed data stored for Phase 2.
    """
    # Get API key from env if not passed
    if not gemini_api_key:
        gemini_api_key = os.getenv('GEMINI_API_KEY', '')

    parsed_resume = parse_resume(resume_text, gemini_api_key=gemini_api_key)
    parsed_jd = parse_job_description(jd_text)

    keyword_score = score_keyword_match(parsed_resume, parsed_jd)
    skills_score, matched_skills, missing_skills = score_skills_match(parsed_resume, parsed_jd)
    exp_score = score_experience(parsed_resume, parsed_jd)
    achievement_score = score_achievements(parsed_resume)
    formatting_score = score_formatting(parsed_resume)

    overall_score = compute_overall_score(
        keyword_score, skills_score, exp_score, achievement_score, formatting_score
    )

    # make_ats_decision now returns 3 values: (decision, failure_reasons, capped_score)
    decision, failure_reasons, capped_score = make_ats_decision(
        overall_score, skills_score, achievement_score, exp_score,
        missing_skills, parsed_resume, parsed_jd
    )

    # Use the capped score for display
    display_score = capped_score

    confidence = get_confidence_level(
        display_score, keyword_score, skills_score, exp_score,
        achievement_score, formatting_score
    )

    if exp_score >= 70:
        exp_match = "high"
    elif exp_score >= 45:
        exp_match = "medium"
    else:
        exp_match = "low"

    ats_issues = generate_ats_issues(parsed_resume, parsed_jd)
    scores_dict = {
        'keyword': keyword_score,
        'skills': skills_score,
        'experience': exp_score,
        'achievement': achievement_score,
        'formatting': formatting_score,
    }
    suggestions = generate_suggestions(parsed_resume, parsed_jd, missing_skills, scores_dict)

    return {
        "match_analysis": {
            "match_score": display_score,
            "keyword_match_score": keyword_score,
            "skills_match_score": skills_score,
            "experience_score": exp_score,
            "achievement_score": achievement_score,
            "formatting_score": formatting_score,
            "matched_skills": matched_skills,
            "missing_skills": missing_skills,
            "experience_match": exp_match,
            "confidence_level": confidence,
        },
        "ats_decision": decision,
        "failure_reasons": failure_reasons,
        "ats_issues": ats_issues,
        "improvement_suggestions": suggestions,
        # Store parsed data for Phase 2
        "_parsed_resume": parsed_resume,
        "_parsed_jd": parsed_jd,
    }


def run_optimization(
    analysis_result: Dict[str, Any],
    format_type: str,
    gemini_api_key: str,
) -> Dict[str, Any]:
    """
    Phase 2: Optimize resume via Gemini + Format it.
    Takes the analysis result from Phase 1 and adds optimization.
    """
    parsed_resume = analysis_result['_parsed_resume']
    parsed_jd = analysis_result['_parsed_jd']

    optimization_result = optimize_resume(parsed_resume, parsed_jd, gemini_api_key)
    optimized = optimization_result['optimized_resume']
    tailoring_notes = optimization_result['tailoring_notes']

    formatted = format_resume(optimized, format_type)

    # Build the complete result (without internal parsed data)
    complete = {
        "match_analysis": analysis_result["match_analysis"],
        "ats_decision": analysis_result["ats_decision"],
        "failure_reasons": analysis_result["failure_reasons"],
        "ats_issues": analysis_result["ats_issues"],
        "improvement_suggestions": analysis_result["improvement_suggestions"],
        "optimized_resume": optimized,
        "tailoring_notes": tailoring_notes,
        "formatted_resume": formatted,
    }

    return complete
