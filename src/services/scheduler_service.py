from __future__ import annotations

import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app

from src.models import db, Lead, Conversation


scheduler = BackgroundScheduler()


def schedule_jobs(app):
    # High-frequency inbox checks: every 30 seconds
    scheduler.add_job(check_inbox_job, "interval", seconds=30, id="check_inbox", replace_existing=True, args=[app])
    scheduler.add_job(send_followups_job, "interval", minutes=app.config["JOB_FOLLOWUP_INTERVAL_MIN"], id="send_followups", replace_existing=True, args=[app])


def check_inbox_job(app):
    with app.app_context():
        logger = app.logger
        logger.info("Running inbox check job")
        # Build allowlist of leads we messaged
        sent_leads = Lead.query.filter_by(message_sent=True).all()
        url_allow = {l.profile_url for l in sent_leads}
        messages = app.linkedin_bot.fetch_inbox_latest(allowed_profile_urls=url_allow)
        for msg in messages:
            if msg.sender_name != "user":
                continue
            # Map to lead by normalized profile URL or by fuzzy name match if URL missing
            lead = None
            if getattr(msg, "profile_url", None):
                lead = Lead.query.filter_by(profile_url=msg.profile_url).first()
            if not lead:
                # Try fuzzy match on participant name
                name = (getattr(msg, "participant_name", None) or "").lower()
                if name:
                    lead = (
                        Lead.query.filter(Lead.name.ilike(f"%{name}%")).order_by(Lead.updated_at.desc()).first()
                    )
            if not lead:
                lead = Lead.query.order_by(Lead.updated_at.desc()).first()

            if not lead:
                continue
            # Deduplicate: skip if an identical recent user message exists
            recent = (
                Conversation.query.filter_by(lead_id=lead.id, role="user", content=msg.text)
                .order_by(Conversation.timestamp.desc())
                .first()
            )
            if recent:
                continue
            # Tokenize message time to avoid duplicates; use timestamp seconds as simple token
            msg_token = str(int(msg.timestamp)) + ":" + (msg.profile_url or "")
            if lead.last_seen_msg_token == msg_token:
                continue
            lead.last_seen_msg_token = msg_token

            # Save user message and refresh conversation context
            conv = Conversation(lead_id=lead.id, role="user", content=msg.text)
            db.session.add(conv)
            lead.reply_status = "replied"
            db.session.commit()

            # Classify and generate reply
            try:
                classification = app.gemini_client.classify_reply(lead, msg.text)
                lead.interest_level = classification.get("interest", lead.interest_level)
                db.session.commit()
                # Get full conversation context for this lead
                context_msgs = Conversation.query.filter_by(lead_id=lead.id).order_by(Conversation.timestamp.asc()).all()
                history_text = "\n".join([f"[{m.timestamp}] {m.role}: {m.content}" for m in context_msgs][-30:])
                reply = app.gemini_client.generate_reply(lead, msg.text)
                if app.linkedin_bot.send_reply(reply):
                    db.session.add(Conversation(lead_id=lead.id, role="assistant", content=reply))
                    lead.last_contact_time = datetime.utcnow()
                    db.session.commit()
            except Exception as exc:
                logger.exception("AI reply flow failed: %s", exc)


def send_followups_job(app):
    with app.app_context():
        logger = app.logger
        logger.info("Running follow-up job")
        cutoff = datetime.utcnow() - timedelta(hours=app.config["FOLLOWUP_AFTER_HOURS"])
        leads = Lead.query.filter(Lead.message_sent == True, Lead.reply_status == "not replied").all()
        for lead in leads:
            if not lead.last_contact_time or lead.last_contact_time < cutoff:
                try:
                    followup = app.gemini_client.generate_followup_message(lead)
                    if app.linkedin_bot.send_message(lead.profile_url, followup):
                        db.session.add(Conversation(lead_id=lead.id, role="assistant", content=followup))
                        lead.follow_up_taken = True
                        lead.last_contact_time = datetime.utcnow()
                        db.session.commit()
                except Exception as exc:
                    logger.exception("Follow-up failed for %s: %s", lead.profile_url, exc)


