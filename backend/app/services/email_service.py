"""
SMTP email sending.

Deliberately kept as plain synchronous smtplib (stdlib, no extra async
SMTP dependency needed) — this module is only ever called from INSIDE a
Celery worker task (see app/tasks/email_tasks.py), never from a FastAPI
request handler, so "synchronous" here doesn't block any web request.
Separating "how to build/send an email" (this file) from "how it's
scheduled" (the Celery task) means the send logic can be unit-tested
without Celery/Redis running at all.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger("specimen_inventory.email")
settings = get_settings()


class EmailDeliveryError(Exception):
    """Raised on any SMTP failure — the Celery task catches this to drive retries."""


def send_email(to_email: str, subject: str, html_body: str, text_body: str | None = None) -> None:
    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    message["To"] = to_email

    if text_body:
        message.attach(MIMEText(text_body, "plain"))
    message.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], message.as_string())
    except (smtplib.SMTPException, OSError, TimeoutError) as exc:
        logger.error("SMTP delivery failed for %s: %s", to_email, exc)
        raise EmailDeliveryError(str(exc)) from exc


def build_invite_email(full_name: str, set_password_url: str) -> tuple[str, str, str]:
    subject = "You've been invited to Clinvedica Specimen Inventory"
    html = f"""
    <p>Hi {full_name},</p>
    <p>An administrator has created an account for you on the Clinvedica Specimen Inventory platform.</p>
    <p><a href="{set_password_url}">Click here to set your password</a> and get started.</p>
    <p>This link expires in {settings.INVITE_TOKEN_EXPIRE_HOURS} hours.</p>
    <p>If you weren't expecting this, you can safely ignore this email.</p>
    """
    text = (
        f"Hi {full_name},\n\n"
        f"An administrator has created an account for you on the Clinvedica Specimen Inventory platform.\n"
        f"Set your password here: {set_password_url}\n"
        f"This link expires in {settings.INVITE_TOKEN_EXPIRE_HOURS} hours.\n"
    )
    return subject, html, text


def build_password_reset_email(full_name: str, reset_url: str) -> tuple[str, str, str]:
    subject = "Reset your Clinvedica Specimen Inventory password"
    html = f"""
    <p>Hi {full_name},</p>
    <p>We received a request to reset your password.</p>
    <p><a href="{reset_url}">Click here to choose a new password</a>.</p>
    <p>This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.</p>
    <p>If you didn't request this, you can safely ignore this email — your password won't change.</p>
    """
    text = (
        f"Hi {full_name},\n\n"
        f"We received a request to reset your password.\n"
        f"Reset it here: {reset_url}\n"
        f"This link expires in {settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes.\n"
    )
    return subject, html, text
