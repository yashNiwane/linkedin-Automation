from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func


db = SQLAlchemy()


class Lead(db.Model):
    __tablename__ = "leads"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    profile_url = db.Column(db.String(512), nullable=False, unique=True)
    role = db.Column(db.String(255))
    company = db.Column(db.String(255))
    email = db.Column(db.String(255))
    phone = db.Column(db.String(64))

    message_sent = db.Column(db.Boolean, default=False, nullable=False)
    reply_status = db.Column(db.String(32), default="not replied", nullable=False)  # replied/not replied
    interest_level = db.Column(db.String(32), default="unsure", nullable=False)  # interested/not interested/unsure
    follow_up_taken = db.Column(db.Boolean, default=False, nullable=False)
    last_contact_time = db.Column(db.DateTime)
    thread_url = db.Column(db.String(512))
    last_seen_msg_token = db.Column(db.String(128))

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    conversations = db.relationship("Conversation", backref="lead", lazy=True, cascade="all, delete-orphan")


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    role = db.Column(db.String(32), nullable=False)  # system|user|assistant
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


