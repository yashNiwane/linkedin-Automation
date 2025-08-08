import os
from dotenv import load_dotenv


load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "sqlite:///app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

    # Selenium settings
    SELENIUM_HEADLESS = os.environ.get("SELENIUM_HEADLESS", "true").lower() == "true"
    SELENIUM_PROFILE_DIR = os.environ.get("SELENIUM_PROFILE_DIR", "selenium_profile")

    # Scheduler
    JOB_CHECK_INBOX_INTERVAL_MIN = int(os.environ.get("JOB_CHECK_INBOX_INTERVAL_MIN", "10"))
    JOB_FOLLOWUP_INTERVAL_MIN = int(os.environ.get("JOB_FOLLOWUP_INTERVAL_MIN", "30"))
    FOLLOWUP_AFTER_HOURS = int(os.environ.get("FOLLOWUP_AFTER_HOURS", "24"))


