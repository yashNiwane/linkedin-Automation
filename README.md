LinkedIn Auto Outreach (Flask + Gemini)

A full-stack Flask app that imports leads from Excel, automates personalized LinkedIn messaging using Gemini, monitors replies, and sends follow-ups. Data is persisted in SQLite with conversation memory.

Features
- Upload Excel leads (columns: name, profile url, role, company, email, phone)
- Generate first messages and follow-ups via Gemini
- Automate LinkedIn sending via undetected-chromedriver (Selenium)
- Monitor inbox and auto-reply using AI
- Classify replies (interested / not interested / unsure)
- Export enriched leads to Excel

Stack
- Flask, SQLAlchemy (SQLite)
- APScheduler background jobs
- Selenium (undetected-chromedriver)
- google-generativeai (Gemini)
- Bootstrap templates

Setup
1. Python 3.11+
2. Install dependencies: `pip install -r requirements.txt`
3. Create `.env` with:
   - SECRET_KEY=change-me
   - GEMINI_API_KEY=your_api_key
   - SELENIUM_HEADLESS=true
   - SELENIUM_PROFILE_DIR=selenium_profile
   - JOB_CHECK_INBOX_INTERVAL_MIN=10
   - JOB_FOLLOWUP_INTERVAL_MIN=30
   - FOLLOWUP_AFTER_HOURS=24
4. Run: `python app.py` then open http://localhost:5000

LinkedIn Login
- Use the login form to store a session. If MFA prompts, set headless to false and login once; the session persists in `SELENIUM_PROFILE_DIR`.

Excel Format
Required columns (case-insensitive): name, profile url, role, company, email, phone.

Notes
- LinkedIn UI may change; selectors might require updates.
- Inbox-to-lead correlation is naive; map thread IDs for production use.
- Respect LinkedIn ToS and rate limits.

"# linkedin-Automation" 
