"""
EmailService — sends transactional email over SMTP.

Configuration: SMTP_HOST (and SMTP_PORT/USERNAME/PASSWORD/FROM_EMAIL/
USE_TLS) in settings. While SMTP_HOST is empty, email is off and every
call is a no-op, so the rest of the app works the same without a mail
provider configured.

Delivery runs on a background thread so a slow or failing SMTP call never
holds up the request that triggered it (e.g. a society self-registering).
"""
import logging
import smtplib
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    # Tests set this to False to deliver inline.
    run_in_background = True

    @classmethod
    def enabled(cls) -> bool:
        return bool(settings.SMTP_HOST.strip())

    @classmethod
    def send(cls, to: str, subject: str, body_text: str) -> bool:
        """Send a plain-text email to `to`. Never raises."""
        if not cls.enabled():
            logger.info(f"[email] SMTP not configured, skipping email to {to}: {subject}")
            return False

        message = MIMEMultipart()
        message["From"] = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
        message["To"] = to
        message["Subject"] = subject
        message.attach(MIMEText(body_text, "plain"))

        if cls.run_in_background:
            threading.Thread(target=cls._deliver, args=(to, message), daemon=True).start()
            return True
        return cls._deliver(to, message)

    @classmethod
    def _deliver(cls, to: str, message: MIMEMultipart) -> bool:
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                if settings.SMTP_USERNAME:
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(message["From"], [to], message.as_string())
            return True
        except Exception as e:
            logger.error(f"[email] delivery to {to} failed: {e}")
            return False
