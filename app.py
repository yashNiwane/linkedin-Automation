import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

from src.config import Config
from src.models import db, Lead, Conversation
from src.services.excel_service import import_leads_from_excel, export_leads_to_excel
from src.services.gemini_service import GeminiClient
from src.services.linkedin_service import LinkedInAutomation
from src.services.scheduler_service import scheduler, schedule_jobs
from src.services.event_bus import bus


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()

    # Initialize services
    app.gemini_client = GeminiClient(api_key=app.config.get("GEMINI_API_KEY"))
    app.linkedin_bot = LinkedInAutomation(headless=app.config.get("SELENIUM_HEADLESS", True))

    # Scheduler
    schedule_jobs(app)

    register_routes(app)
    return app


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index():
        leads = Lead.query.order_by(Lead.created_at.desc()).all()
        return render_template("index.html", leads=leads)

    @app.route("/linkedin_login", methods=["POST"]) 
    def linkedin_login():
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        if not username or not password:
            flash("Username and password required", "warning")
            return redirect(url_for("index"))
        ok = app.linkedin_bot.login(username, password)
        if ok:
            flash("LinkedIn login successful", "success")
        else:
            flash("LinkedIn login failed. If MFA is required, set SELENIUM_HEADLESS=false and login once manually.", "danger")
        return redirect(url_for("index"))

    @app.route("/upload", methods=["POST"])
    def upload():
        file = request.files.get("file")
        if not file:
            flash("No file uploaded", "danger")
            return redirect(url_for("index"))
        filename = secure_filename(file.filename)
        if not filename.lower().endswith((".xlsx", ".xls")):
            flash("Please upload an Excel file (.xlsx or .xls)", "warning")
            return redirect(url_for("index"))
        try:
            count = import_leads_from_excel(file)
            flash(f"Imported {count} leads", "success")
        except Exception as exc:
            flash(f"Failed to import leads: {exc}", "danger")
        return redirect(url_for("index"))

    @app.route("/send_first_messages", methods=["POST"]) 
    def send_first_messages():
        leads = Lead.query.filter_by(message_sent=False).all()
        sent = 0
        for lead in leads:
            try:
                message = app.gemini_client.generate_first_message(lead)
                ok = app.linkedin_bot.send_message(lead.profile_url, message)
                if ok:
                    lead.message_sent = True
                    lead.last_contact_time = datetime.utcnow()
                    # best-effort: try to set thread_url if available via JS (stored in bot last nav)
                    conv = Conversation(lead_id=lead.id, role="assistant", content=message, timestamp=datetime.utcnow())
                    db.session.add(conv)
                    db.session.commit()
                    sent += 1
            except Exception as exc:
                db.session.rollback()
                app.logger.exception("Failed to send first message to %s: %s", lead.profile_url, exc)
        flash(f"Sent {sent} messages", "info")
        return redirect(url_for("index"))

    @app.route("/manual_followup/<int:lead_id>", methods=["POST"]) 
    def manual_followup(lead_id: int):
        lead = Lead.query.get_or_404(lead_id)
        try:
            followup = app.gemini_client.generate_followup_message(lead)
            ok = app.linkedin_bot.send_message(lead.profile_url, followup)
            if ok:
                lead.follow_up_taken = True
                lead.last_contact_time = datetime.utcnow()
                conv = Conversation(lead_id=lead.id, role="assistant", content=followup, timestamp=datetime.utcnow())
                db.session.add(conv)
                db.session.commit()
                flash("Follow-up sent", "success")
            else:
                flash("Failed to send follow-up", "danger")
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("Manual follow-up failed for %s: %s", lead.profile_url, exc)
            flash("Manual follow-up failed", "danger")
        return redirect(url_for("index"))

    @app.route("/export", methods=["GET"]) 
    def export():
        try:
            path = export_leads_to_excel()
            return send_file(path, as_attachment=True)
        except Exception as exc:
            app.logger.exception("Export failed: %s", exc)
            flash("Export failed", "danger")
            return redirect(url_for("index"))

    @app.route("/events")
    def sse_events():
        def stream():
            # send history first
            for e in bus.get_history():
                yield f"data: {json.dumps(e)}\n\n"
            q = bus.subscribe()
            try:
                while True:
                    event = q.get()
                    yield f"data: {json.dumps(event)}\n\n"
            finally:
                bus.unsubscribe(q)
        return app.response_class(stream(), mimetype="text/event-stream")


if __name__ == "__main__":
    app = create_app()
    if not scheduler.running:
        scheduler.start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)


