"""
Email-sending Celery task.

Every email in the app (invite, password reset) goes through this one
task rather than being sent inline during a request — this is the
"Email/SMTP operations" item from the background-task requirements.
Retries with exponential backoff handle transient SMTP failures (a
flaky mail relay, a momentary DNS blip) without the calling API request
ever waiting on them.
"""
import logging

from app.core.celery_app import celery_app
from app.services.email_service import EmailDeliveryError, send_email

logger = logging.getLogger("specimen_inventory.tasks.email")


@celery_app.task(
    name="send_email_task",
    bind=True,
    autoretry_for=(EmailDeliveryError,),
    retry_backoff=True,       # 1s, 2s, 4s, ... between attempts
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def send_email_task(self, to_email: str, subject: str, html_body: str, text_body: str | None = None) -> dict:
    """
    Returns a small result dict (not just None) so GET /tasks/{id} has
    something concrete to show on SUCCESS rather than an empty result.
    """
    logger.info("Sending email to %s (subject=%r), attempt %d", to_email, subject, self.request.retries + 1)
    send_email(to_email, subject, html_body, text_body)
    return {"to": to_email, "subject": subject, "delivered": True}
