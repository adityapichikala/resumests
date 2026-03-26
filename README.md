# 🤖 ATS Resume Analyzer — Telegram Bot

A Telegram bot that performs enterprise-grade ATS (Applicant Tracking System) analysis of your resume against any job description, powered by Google Gemini AI.

## Features

- 📊 **5-Dimension Scoring** — Keyword match, skills match, experience, achievements, formatting
- ✅ **Binary PASS/FAIL Decision** — With specific failure reasons
- 💡 **Actionable Suggestions** — Exact steps to improve your resume
- 📄 **AI-Optimized Resume** — Gemini rewrites your bullets with strong action verbs + metrics
- 🎨 **4 Format Styles** — Modern, sidebar, one-page, two-page
- 📁 **JSON Report** — Full analysis exported as JSON file
- 📤 **File Upload** — Supports .txt and .pdf resume uploads

## Setup

### 1. Get API Keys

1. **Telegram Bot Token**: Message [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → copy the token
2. **Gemini API Key**: Get from [Google AI Studio](https://aistudio.google.com/apikey) (free tier available)

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your keys:
```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the Bot

```bash
python bot.py
```

## Usage

1. Open Telegram and search for your bot
2. Send `/start` for a welcome message
3. Send `/analyze` to begin
4. Paste your resume text or upload a `.txt`/`.pdf` file
5. Paste the job description
6. Choose a format: `modern` | `sidebar` | `one-page` | `two-page`
7. Receive your results!

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and introduction |
| `/analyze` | Start a new resume analysis |
| `/help` | Usage instructions and format types |
| `/cancel` | Cancel the current analysis |

## ATS Scoring Formula

```
Overall = (Keyword × 0.25) + (Skills × 0.30) + (Experience × 0.20) + (Achievement × 0.15) + (Formatting × 0.10)
```

**FAIL criteria** (any one triggers failure):
- Overall score < 55
- Missing ≥ 3 critical required skills
- Achievement score < 30
- Experience score < 40

## Project Structure

```
resumests/
├── bot.py                  # Telegram bot entry point
├── engine/
│   ├── __init__.py
│   ├── parser.py           # Resume & JD text parser
│   ├── scorer.py           # 5-dimension scorer + ATS decision
│   ├── optimizer.py        # Gemini-powered resume optimizer
│   ├── formatter.py        # 4 resume format generators
│   └── pipeline.py         # Full analysis orchestrator
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```
