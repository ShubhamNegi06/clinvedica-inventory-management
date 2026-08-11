"""
Run ONCE after applying migration 0003_custom_auth against a database
that has existing users from the old Supabase-Auth system.

Those users' hashed_password was backfilled to a random, unusable
placeholder by the migration (see that migration's docstring) — they
cannot log in until they go through the password-reset flow. This
script queues a "reset your password" email (via the same Celery task
the app uses everywhere else) for every currently-active user, so they
all receive a working sign-in link in one pass rather than needing an
admin to click "Send Password Reset" individually for each one.

Requires a running Celery worker (and Redis) to actually process the
queued emails — this script only enqueues them.

Usage:
    uv run python scripts/backfill_existing_user_passwords.py
    uv run python scripts/backfill_existing_user_passwords.py --dry-run
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.password_reset_token import TokenPurpose
from app.models.user import User
from app.services import auth_service
from app.services.email_service import build_password_reset_email

settings = get_settings()


def run(dry_run: bool) -> None:
    db = SessionLocal()
    try:
        users = list(db.execute(select(User).where(User.is_active.is_(True))).scalars())
        print(f"Found {len(users)} active user(s).")

        if dry_run:
            for user in users:
                print(f"  [dry-run] would email {user.email} ({user.role})")
            return

        from app.tasks.email_tasks import send_email_task

        queued = 0
        for user in users:
            raw_token = auth_service.create_password_reset_token(db, user, TokenPurpose.RESET)
            reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/set-password?token={raw_token}&purpose=reset"
            subject, html, text = build_password_reset_email(user.full_name, reset_url)
            send_email_task.delay(user.email, subject, html, text)
            queued += 1
            print(f"  queued reset email for {user.email}")

        print(f"\nQueued {queued} password-reset email(s). Make sure a Celery worker is running to deliver them.")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="List affected users without sending anything")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
