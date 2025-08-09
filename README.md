# LinkedIn Auto Outreach Bot

## Overview
Automated LinkedIn messaging system with AI-powered personalization using Google Gemini. Handles lead import, message sending, reply monitoring, and auto-responses.

## Features
- **Lead Management**: Import from Excel, export enriched data
- **AI Messaging**: Gemini-powered personalized messages and replies
- **Auto-Reply**: Monitors inbox and responds to prospects automatically
- **Conversation Tracking**: Maintains message history and context
- **Real-time Dashboard**: Live activity monitoring with SSE

## Tech Stack
- **Backend**: Flask + SQLAlchemy (SQLite)
- **AI**: Google Gemini API
- **Automation**: Selenium + undetected-chromedriver
- **Scheduling**: APScheduler
- **Frontend**: Bootstrap + Server-Sent Events

## Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Configure `.env`:
   ```
SECRET_KEY=
GEMINI_API_KEY=
SELENIUM_HEADLESS=false
SELENIUM_PROFILE_DIR=C:\chrome_profile
JOB_CHECK_INBOX_INTERVAL_MIN=10
JOB_FOLLOWUP_INTERVAL_MIN=30
FOLLOWUP_AFTER_HOURS=24
   ```
3. Run: `python app.py`

## Usage
1. **Login**: Store LinkedIn session via web interface
2. **Import**: Upload Excel with leads (name, profile_url, role, company, email, phone)
3. **Send**: Trigger first messages to all leads
4. **Monitor**: Bot automatically replies to incoming messages
5. **Export**: Download results with engagement metrics

## Key Components
- `linkedin_service.py`: LinkedIn automation & message detection
- `gemini_service.py`: AI message generation & classification
- `scheduler_service.py`: Background jobs for inbox monitoring
- `excel_service.py`: Lead import/export functionality

## Message Detection
Uses reliable methods instead of CSS classes:
- Profile picture presence detection
- Data attribute analysis (`data-event-urn`)
- Message structure validation

## Workflow
1. **Import** → **AI Generate** → **Send Messages**
2. **Monitor Inbox** (30s intervals) → **Detect Replies**
3. **AI Classify** → **Generate Response** → **Send Reply**
4. **Track Conversations** → **Export Results**