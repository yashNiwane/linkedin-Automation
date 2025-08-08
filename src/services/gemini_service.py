from __future__ import annotations

import logging
from typing import List

import google.generativeai as genai

from src.models import Conversation, Lead, db
from src.services.event_bus import bus


class GeminiClient:
    def __init__(self, api_key: str):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.api_key = api_key
        if not api_key:
            self.logger.warning("GEMINI_API_KEY missing; AI features disabled until configured.")
            self.model = None
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")

    def _conversation_context(self, lead: Lead) -> str:
        messages: List[Conversation] = (
            Conversation.query.filter_by(lead_id=lead.id).order_by(Conversation.timestamp.asc()).all()
        )
        history_lines = []
        for m in messages:
            history_lines.append(f"[{m.timestamp.isoformat()}] {m.role}: {m.content}")
        return "\n".join(history_lines[-20:])  # cap context

    def generate_first_message(self, lead: Lead) -> str:
        prompt = (
            "You are a helpful SDR writing a concise, warm LinkedIn first message. "
            "Avoid sounding salesy; personalize using the info. 400 characters max.\n"
            f"Lead: name={lead.name}, role={lead.role}, company={lead.company}."
        )
        if not self.model:
            return f"Hi {lead.name}, great to connect!"
        try:
            resp = self.model.generate_content(prompt)
            return (resp.text or f"Hi {lead.name}, great to connect!").strip()
        except Exception as e:
            bus.emit("warning", f"Gemini first-message error; using fallback: {e}")
            return f"Hi {lead.name}, great to connect! I enjoyed learning about your work at {lead.company or 'your company'}. If you’re open, I’d love to share a quick idea relevant to your role as {lead.role or 'your role'}."

    def generate_followup_message(self, lead: Lead) -> str:
        context = self._conversation_context(lead)
        prompt = (
            "Write a short, friendly follow-up for LinkedIn referencing the ongoing context if useful. "
            "Be human, 350 characters max.\n"
            f"Lead: name={lead.name}, role={lead.role}, company={lead.company}.\n"
            f"Context:\n{context}"
        )
        if not self.model:
            return "Just bumping this to the top of your inbox—open to a quick chat?"
        try:
            resp = self.model.generate_content(prompt)
            return (resp.text or "Just bumping this to the top of your inbox—open to a quick chat?").strip()
        except Exception as e:
            bus.emit("warning", f"Gemini follow-up error; using fallback: {e}")
            return "Just bumping this up—open to a quick chat next week?"

    def classify_reply(self, lead: Lead, reply_text: str) -> dict:
        prompt = (
            "Classify the user's reply from a sales prospecting conversation. "
            "Return JSON with keys: interest (interested|not interested|unsure), action (next step), summary.\n"
            f"Reply: {reply_text}"
        )
        if not self.model:
            return {"interest": "unsure", "action": "ack", "summary": reply_text[:200]}
        try:
            resp = self.model.generate_content(prompt)
            text = resp.text or "{\"interest\": \"unsure\", \"action\": \"ack\", \"summary\": \"\"}"
        except Exception as e:
            bus.emit("warning", f"Gemini classify error; defaulting: {e}")
            text = "{\"interest\": \"unsure\", \"action\": \"ack\", \"summary\": \"\"}"
        # naive parse fallback
        try:
            import json

            data = json.loads(text)
        except Exception:
            data = {"interest": "unsure", "action": "ack", "summary": text[:500]}
        return data

    def generate_reply(self, lead: Lead, latest_user_msg: str) -> str:
        context = self._conversation_context(lead)
        prompt = (
            "Write a helpful, succinct LinkedIn reply. Be natural, avoid over-formality. 500 characters max.\n"
            f"Context:\n{context}\n"
            f"Prospect said: {latest_user_msg}"
        )
        if not self.model:
            return "Thanks for the note—would a quick 10–15 min chat work next week?"
        try:
            resp = self.model.generate_content(prompt)
            return (resp.text or "Thanks for the note—would a quick 10–15 min chat work next week?").strip()
        except Exception as e:
            bus.emit("warning", f"Gemini reply error; using fallback: {e}")
            return "Appreciate the reply—would a quick 10–15 min chat work next week?"


