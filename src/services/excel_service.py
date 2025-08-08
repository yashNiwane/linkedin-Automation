from __future__ import annotations

import os
import tempfile
from datetime import datetime
from io import BytesIO
from typing import BinaryIO

import pandas as pd

from src.models import db, Lead


REQUIRED_COLUMNS = ["name", "profile url", "role", "company", "email", "phone"]


def _normalize_columns(columns):
    return [str(c).strip().lower() for c in columns]


def import_leads_from_excel(file: BinaryIO) -> int:
    df = pd.read_excel(file)
    cols = _normalize_columns(df.columns)
    df.columns = cols
    missing = [c for c in REQUIRED_COLUMNS if c not in cols]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    count = 0
    for _, row in df.iterrows():
        profile_url = str(row.get("profile url", "")).strip()
        if not profile_url:
            continue
        lead = Lead.query.filter_by(profile_url=profile_url).first()
        if not lead:
            lead = Lead(
                name=str(row.get("name", "")).strip() or "",
                profile_url=profile_url,
                role=str(row.get("role", "")).strip() or None,
                company=str(row.get("company", "")).strip() or None,
                email=str(row.get("email", "")).strip() or None,
                phone=str(row.get("phone", "")).strip() or None,
            )
            db.session.add(lead)
            count += 1
        else:
            # Update fields if provided
            lead.name = str(row.get("name", lead.name) or lead.name)
            lead.role = str(row.get("role", lead.role) or lead.role)
            lead.company = str(row.get("company", lead.company) or lead.company)
            lead.email = str(row.get("email", lead.email) or lead.email)
            lead.phone = str(row.get("phone", lead.phone) or lead.phone)
    db.session.commit()
    return count


def export_leads_to_excel() -> str:
    leads = Lead.query.all()
    rows = []
    for l in leads:
        rows.append(
            {
                "name": l.name,
                "profile url": l.profile_url,
                "role": l.role,
                "company": l.company,
                "email": l.email,
                "phone": l.phone,
                "message sent": "yes" if l.message_sent else "no",
                "reply status": l.reply_status,
                "interest level": l.interest_level,
                "follow-up taken": "yes" if l.follow_up_taken else "no",
                "last contact time": l.last_contact_time.isoformat() if l.last_contact_time else "",
            }
        )
    df = pd.DataFrame(rows)
    tmpdir = tempfile.gettempdir()
    path = os.path.join(tmpdir, f"leads_export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx")
    df.to_excel(path, index=False)
    return path


