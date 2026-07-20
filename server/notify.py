"""
Sends the "someone reported a post" notification.

Runs in SIMULATED mode by default (logs to stdout, no credentials needed).
Set SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASSWORD/REPORT_EMAIL_TO to send a
real email — every report is stored in the `reports` table regardless, so
nothing is lost if email isn't configured or a send fails.
"""

import os
import smtplib
from email.mime.text import MIMEText

REPORT_EMAIL_TO = os.environ.get("REPORT_EMAIL_TO")
SMTP_HOST = os.environ.get("SMTP_HOST")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")


def notify_report(post_id: int, reporter_email: str, reason: str) -> dict:
    subject = f"[EatRate] Post #{post_id} reported"
    body = (
        f"Post #{post_id} was reported by {reporter_email}.\n\n"
        f"Reason: {reason or '(no reason given)'}\n\n"
        f"Review it in the admin panel (/admin.html)."
    )

    if not (REPORT_EMAIL_TO and SMTP_HOST and SMTP_USER and SMTP_PASSWORD):
        print(f"[SIMULATED REPORT EMAIL] {subject}\n{body}", flush=True)
        return {"mode": "simulated"}

    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = REPORT_EMAIL_TO
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [REPORT_EMAIL_TO], msg.as_string())
        return {"mode": "sent"}
    except Exception as e:
        print(f"[REPORT EMAIL FAILED] {subject}: {e}", flush=True)
        return {"mode": "error", "error": str(e)}
