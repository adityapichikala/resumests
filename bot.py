"""
ATS Resume Analyzer — Telegram Bot
Flow: Resume → JD → Analysis (scores/faults) → Ask to generate → Format → Optimized resume
"""

import os
import io
import json
import logging
import asyncio
from typing import Dict

from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
)

try:
    from PyPDF2 import PdfReader
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

from engine.pipeline import run_analysis_only, run_optimization
from engine.pdf_generator import generate_ats_report_pdf, generate_resume_pdf
from engine.visuals import generate_radar_chart

# ─── Config ───────────────────────────────────────────────────────────────────
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in .env file")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in .env file")

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Conversation States ─────────────────────────────────────────────────────
RESUME, JOB_DESCRIPTION, GENERATE_CHOICE, FORMAT_TYPE = range(4)

# ─── Keyboards ───────────────────────────────────────────────────────────────
FORMAT_KEYBOARD = ReplyKeyboardMarkup(
    [
        ['📋 Modern - Clean & Simple'],
        ['📊 Sidebar - Skills on Left'],
        ['📄 One-Page - Compact'],
        ['📑 Two-Page - Full Detail'],
    ],
    one_time_keyboard=True,
    resize_keyboard=True,
)

FORMAT_MAP = {
    '📋 modern - clean & simple': 'modern',
    '📊 sidebar - skills on left': 'sidebar',
    '📄 one-page - compact': 'one-page',
    '📑 two-page - full detail': 'two-page',
    'modern': 'modern', # Keep original for direct input if needed
    'sidebar': 'sidebar',
    'one-page': 'one-page',
    'two-page': 'two-page',
}

GENERATE_KEYBOARD = ReplyKeyboardMarkup(
    [['✅ Yes, generate optimized resume', '❌ No, thanks']],
    one_time_keyboard=True,
    resize_keyboard=True,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _extract_text_from_pdf(file_bytes: bytes) -> str:
    if not PDF_SUPPORT:
        return ""
    reader = PdfReader(io.BytesIO(file_bytes))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text.strip()


def _score_emoji(score: int) -> str:
    if score >= 80: return "🟢"
    elif score >= 60: return "🟡"
    elif score >= 40: return "🟠"
    else: return "🔴"


def _format_analysis_message(result: Dict) -> str:
    """Format Phase 1 analysis results (scores, faults, suggestions). Uses plain text to avoid Markdown errors."""
    ma = result['match_analysis']
    decision = result['ats_decision']
    d_emoji = "✅" if decision == "PASS" else "❌"

    msg = []
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append(f"  {d_emoji} ATS DECISION: {decision}")
    msg.append(f"  📊 Overall Score: {ma['match_score']}/100")
    msg.append(f"  🎯 Confidence: {ma['confidence_level'].upper()}")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")

    # Score breakdown
    msg.append("📈 SCORE BREAKDOWN")
    msg.append(f"  {_score_emoji(ma['keyword_match_score'])} Keyword Match: {ma['keyword_match_score']}/100")
    msg.append(f"  {_score_emoji(ma['skills_match_score'])} Skills Match: {ma['skills_match_score']}/100")
    msg.append(f"  {_score_emoji(ma['experience_score'])} Experience: {ma['experience_score']}/100")
    msg.append(f"  {_score_emoji(ma['achievement_score'])} Achievements: {ma['achievement_score']}/100")
    msg.append(f"  {_score_emoji(ma['formatting_score'])} Formatting: {ma['formatting_score']}/100")
    msg.append(f"  📋 Experience Match: {ma['experience_match'].upper()}")
    msg.append("")

    # Matched skills
    matched = ma.get('matched_skills', [])
    if matched:
        msg.append(f"✅ MATCHED SKILLS ({len(matched)})")
        msg.append(f"  {', '.join(matched[:15])}")
        if len(matched) > 15:
            msg.append(f"  ... and {len(matched)-15} more")
        msg.append("")

    # Missing skills
    missing = ma.get('missing_skills', [])
    if missing:
        msg.append(f"❌ MISSING SKILLS ({len(missing)})")
        msg.append(f"  {', '.join(missing[:10])}")
        if len(missing) > 10:
            msg.append(f"  ... and {len(missing)-10} more")
        msg.append("")

    # Failure reasons
    failures = result.get('failure_reasons', [])
    if failures:
        msg.append("🚫 FAILURE REASONS")
        for i, reason in enumerate(failures, 1):
            msg.append(f"  {i}. {reason}")
        msg.append("")

    # ATS Issues
    issues = result.get('ats_issues', [])
    if issues:
        msg.append(f"⚠️ ATS ISSUES ({len(issues)})")
        for i, issue in enumerate(issues[:8], 1):
            if len(issue) > 200:
                issue = issue[:197] + "..."
            msg.append(f"  {i}. {issue}")
        if len(issues) > 8:
            msg.append(f"  ... and {len(issues)-8} more issues found")
        msg.append("")

    # Suggestions
    suggestions = result.get('improvement_suggestions', [])
    if suggestions:
        msg.append(f"💡 IMPROVEMENT SUGGESTIONS ({len(suggestions)})")
        for i, suggestion in enumerate(suggestions[:6], 1):
            if len(suggestion) > 200:
                suggestion = suggestion[:197] + "..."
            msg.append(f"  {i}. {suggestion}")
        if len(suggestions) > 6:
            msg.append(f"  ... and {len(suggestions)-6} more")
        msg.append("")

    return '\n'.join(msg)


def _format_optimized_resume_message(result: Dict) -> str:
    """Format the optimized resume for Telegram."""
    opt = result.get('optimized_resume', {})
    msg = []

    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("  📄 OPTIMIZED RESUME")
    msg.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    msg.append("")

    msg.append(f"**{opt.get('name', '')}**")
    contact = opt.get('contact', '')
    if contact:
        msg.append(contact)
    msg.append("")

    summary = opt.get('summary', '')
    if summary:
        msg.append("**Summary**")
        msg.append(summary)
        msg.append("")

    skills = opt.get('skills', [])
    if skills:
        msg.append("**Skills**")
        msg.append(', '.join(skills))
        msg.append("")

    experience = opt.get('experience', [])
    if experience:
        msg.append("**Experience**")
        for job in experience:
            parts = [p for p in [job.get('title'), job.get('company'), job.get('dates')] if p]
            msg.append(f"▸ {' | '.join(parts)}")
            for bullet in job.get('bullets', []):
                msg.append(f"  • {bullet}")
            msg.append("")

    projects = opt.get('projects', [])
    if projects:
        msg.append("**Projects**")
        for proj in projects:
            msg.append(f"▸ {proj.get('name', '')} [{proj.get('tech', '')}]")
            desc = proj.get('description', '')
            if desc:
                msg.append(f"  {desc}")
            msg.append("")

    education = opt.get('education', [])
    if education:
        msg.append("**Education**")
        for edu in education:
            parts = [p for p in [edu.get('degree'), edu.get('institution'), edu.get('year')] if p]
            msg.append(f"▸ {' | '.join(parts)}")
            details = edu.get('details', '')
            if details:
                msg.append(f"  {details}")
        msg.append("")

    certs = opt.get('certifications', [])
    if certs:
        msg.append("**Certifications**")
        for cert in certs:
            msg.append(f"  ✓ {cert}")
        msg.append("")

    notes = result.get('tailoring_notes', '')
    if notes:
        msg.append("📝 **TAILORING NOTES**")
        msg.append(f"  {notes}")
        msg.append("")

    return '\n'.join(msg)


async def _send_long_message(update: Update, text: str, parse_mode=None):
    """Send a message, splitting into chunks if >4000 chars."""
    if len(text) <= 4000:
        await update.message.reply_text(text, parse_mode=parse_mode)
        return

    chunks = []
    current = ""
    for line in text.split('\n'):
        if len(current) + len(line) + 1 > 3900:
            chunks.append(current)
            current = line
        else:
            current += '\n' + line
    if current:
        chunks.append(current)

    for chunk in chunks:
        await update.message.reply_text(chunk, parse_mode=parse_mode)


# ─── Bot Handlers ────────────────────────────────────────────────────────────

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    welcome = (
        "👋 **Welcome to ATS Resume Analyzer!**\n\n"
        "I analyze your resume against a job description and give you:\n"
        "  📊 ATS match scores across 5 dimensions\n"
        "  ✅ Binary PASS/FAIL decision\n"
        "  ❌ Missing skills & specific issues\n"
        "  💡 Actionable improvement suggestions\n"
        "  📄 AI-optimized resume (powered by Gemini)\n\n"
        "Use /analyze to start.\n"
        "Use /cancel to cancel at any time."
    )
    await update.message.reply_text(welcome, parse_mode='Markdown')


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "📖 **How to Use**\n\n"
        "1. Send /analyze to start\n"
        "2. Paste your resume text OR upload a .txt/.pdf file\n"
        "3. Paste the job description\n"
        "4. View your ATS scores, issues, and suggestions\n"
        "5. Choose to generate an optimized resume\n"
        "6. Pick a format (modern, sidebar, one-page, two-page)\n"
        "7. Get your AI-optimized resume!\n\n"
        "**Commands:**\n"
        "  /analyze — Start new analysis\n"
        "  /cancel — Cancel current analysis\n"
        "  /help — Show this help"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "📄 Step 1/2: Resume\n\n"
        "Send me your resume. You can:\n"
        "  • Paste the text directly\n"
        "  • Upload a .txt or .pdf file\n\n"
        "Use /cancel to abort."
    )
    return RESUME


async def receive_resume_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    resume_text = update.message.text
    if len(resume_text.strip()) < 50:
        await update.message.reply_text(
            "⚠️ That seems too short for a resume. Please paste your full resume text or upload a file."
        )
        return RESUME

    context.user_data['resume_text'] = resume_text
    logger.info(f"Received resume text ({len(resume_text)} chars) from user {update.effective_user.id}")

    await update.message.reply_text(
        "✅ Resume received!\n\n"
        "📋 Step 2/2: Job Description\n\n"
        "Now paste the job description you're targeting."
    )
    return JOB_DESCRIPTION


async def receive_resume_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    document = update.message.document
    file_name = document.file_name.lower() if document.file_name else ''

    if not (file_name.endswith('.txt') or file_name.endswith('.pdf')):
        await update.message.reply_text("⚠️ Please upload a `.txt` or `.pdf` file.")
        return RESUME

    try:
        file = await document.get_file()
        file_bytes = await file.download_as_bytearray()

        if file_name.endswith('.pdf'):
            if not PDF_SUPPORT:
                await update.message.reply_text("⚠️ PDF support not available. Please paste your resume text.")
                return RESUME
            resume_text = _extract_text_from_pdf(bytes(file_bytes))
        else:
            resume_text = file_bytes.decode('utf-8', errors='replace')

        if len(resume_text.strip()) < 50:
            await update.message.reply_text("⚠️ Couldn't extract enough text. Please paste your resume text directly.")
            return RESUME

        context.user_data['resume_text'] = resume_text
        logger.info(f"Received resume file ({file_name}, {len(resume_text)} chars) from user {update.effective_user.id}")

        await update.message.reply_text(
            f"✅ Resume extracted from {document.file_name}!\n\n"
            "📋 Step 2/2: Job Description\n\n"
            "Now paste the job description you're targeting."
        )
        return JOB_DESCRIPTION

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        await update.message.reply_text("⚠️ Error reading file. Please paste your resume text directly.")
        return RESUME


async def receive_jd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive JD, run Phase 1 analysis, show results, and ask about optimization."""
    jd_text = update.message.text
    if len(jd_text.strip()) < 30:
        await update.message.reply_text("⚠️ That seems too short. Please paste the full job description.")
        return JOB_DESCRIPTION

    context.user_data['jd_text'] = jd_text
    logger.info(f"Received JD ({len(jd_text)} chars) from user {update.effective_user.id}")

    await update.message.reply_text("⏳ Analyzing your resume against the JD...")

    resume_text = context.user_data['resume_text']

    try:
        # Phase 1: Parse via Gemini + Score + Issues + Suggestions
        analysis_result = run_analysis_only(resume_text, jd_text, gemini_api_key=GEMINI_API_KEY)
        context.user_data['analysis_result'] = analysis_result

        # Generate and send the radar chart FIRST
        try:
            ma = analysis_result['match_analysis']
            scores_dict = {
                'keyword': ma['keyword_match_score'],
                'skills': ma['skills_match_score'],
                'experience': ma['experience_score'],
                'achievement': ma['achievement_score'],
                'formatting': ma['formatting_score'],
            }
            chart_buf = generate_radar_chart(scores_dict)
            await update.message.reply_photo(
                photo=chart_buf,
                caption="\U0001f4ca Your ATS Performance Breakdown"
            )
        except Exception as e:
            logger.error(f"Radar chart error: {e}")

        # Send detailed analysis text
        analysis_msg = _format_analysis_message(analysis_result)
        await _send_long_message(update, analysis_msg)

        # Ask if they want to generate optimized resume
        await update.message.reply_text(
            "📄 Would you like me to generate an AI-optimized resume?\n\n"
            "I'll use Gemini AI to rewrite your bullets with strong action verbs, "
            "inject missing keywords naturally, and tailor your summary to this JD.",
            reply_markup=GENERATE_KEYBOARD,
        )
        return GENERATE_CHOICE

    except Exception as e:
        logger.error(f"Analysis error: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ **Error during analysis:**\n`{str(e)[:500]}`\n\nPlease try again with /analyze.",
            parse_mode='Markdown'
        )
        context.user_data.clear()
        return ConversationHandler.END


async def receive_generate_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle user's choice to generate or skip optimized resume."""
    choice = update.message.text.strip().lower()

    if 'no' in choice:
        # Send analysis as PDF and end
        analysis_result = context.user_data.get('analysis_result', {})

        try:
            report_pdf = generate_ats_report_pdf(analysis_result)
            pdf_file = io.BytesIO(report_pdf)
            pdf_file.name = 'ats_analysis_report.pdf'

            await update.message.reply_document(
                document=pdf_file,
                filename='ats_analysis_report.pdf',
                caption="📊 ATS Analysis Report (PDF)",
            )
        except Exception as e:
            logger.error(f"PDF generation error: {e}")
            # Fallback to JSON
            json_result = {k: v for k, v in analysis_result.items() if not k.startswith('_')}
            json_str = json.dumps(json_result, indent=2, ensure_ascii=False)
            json_file = io.BytesIO(json_str.encode('utf-8'))
            json_file.name = 'ats_analysis_result.json'
            await update.message.reply_document(
                document=json_file,
                filename='ats_analysis_result.json',
                caption="📁 ATS analysis report (JSON)",
            )

        await update.message.reply_text(
            "✅ Done! Use /analyze to analyze another resume.",
            reply_markup=ReplyKeyboardRemove(),
        )
        context.user_data.clear()
        return ConversationHandler.END

    # User wants optimized resume → ask for format
    await update.message.reply_text(
        "🎨 Choose your resume format:\n\n"
        "📋 Modern - Clean single-column layout\n"
        "📊 Sidebar - Skills on left, experience on right\n"
        "📄 One-Page - Compact, max 4 bullets per role\n"
        "📑 Two-Page - Full detail, all sections expanded",
        reply_markup=FORMAT_KEYBOARD,
    )
    return FORMAT_TYPE


async def receive_format(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receive format type, run Phase 2 optimization via Gemini, send results."""
    raw_choice = update.message.text.strip().lower()
    format_type = FORMAT_MAP.get(raw_choice)

    if not format_type:
        await update.message.reply_text(
            "⚠️ Please tap one of the buttons below:",
            reply_markup=FORMAT_KEYBOARD,
        )
        return FORMAT_TYPE

    await update.message.reply_text(
        "⏳ **Generating your AI-optimized resume...**\n"
        "This takes 10-20 seconds (Gemini is rewriting your resume).",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode='Markdown'
    )

    analysis_result = context.user_data.get('analysis_result', {})

    try:
        # Phase 2: Optimize via Gemini
        complete_result = run_optimization(analysis_result, format_type, GEMINI_API_KEY)

        # Send optimized resume text preview
        opt_msg = _format_optimized_resume_message(complete_result)
        await _send_long_message(update, opt_msg)

        # Send ATS Report PDF
        try:
            report_pdf = generate_ats_report_pdf(complete_result)
            report_file = io.BytesIO(report_pdf)
            report_file.name = 'ats_full_report.pdf'

            await update.message.reply_document(
                document=report_file,
                filename='ats_full_report.pdf',
                caption="📊 Full ATS Report (PDF)"
            )
        except Exception as e:
            logger.error(f"Report PDF error: {e}")

        # Send Optimized Resume PDF
        try:
            resume_pdf = generate_resume_pdf(complete_result)
            resume_file = io.BytesIO(resume_pdf)
            resume_file.name = f'optimized_resume_{format_type}.pdf'

            await update.message.reply_document(
                document=resume_file,
                filename=f'optimized_resume_{format_type}.pdf',
                caption=f"📄 Optimized Resume - {format_type.title()} (PDF)"
            )
        except Exception as e:
            logger.error(f"Resume PDF error: {e}")

        await update.message.reply_text(
            "✅ All done! Use /analyze to analyze another resume."
        )

    except Exception as e:
        logger.error(f"Optimization error: {e}", exc_info=True)
        await update.message.reply_text(
            f"❌ Error during optimization. Please try again with /analyze."
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "❌ Analysis cancelled. Use /analyze to start over.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('analyze', analyze_start)],
        states={
            RESUME: [
                MessageHandler(filters.Document.ALL, receive_resume_file),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_resume_text),
            ],
            JOB_DESCRIPTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_jd),
            ],
            GENERATE_CHOICE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_generate_choice),
            ],
            FORMAT_TYPE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_format),
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(conv_handler)

    logger.info("🤖 ATS Resume Analyzer bot is running!")
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
