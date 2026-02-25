"""Email sending and local report saving."""

import json
import smtplib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from pathlib import Path

from arxiv_recsys_llm_bot.config import (
    GMAIL_APP_PASSWORD,
    RECIPIENT_EMAIL,
    SENDER_EMAIL,
    log,
)


def send_email(html_content: str, subject: str) -> bool:
    """Send HTML email via Gmail SMTP. Returns True on success."""
    if not GMAIL_APP_PASSWORD:
        log.warning(
            "GMAIL_APP_PASSWORD not set. Cannot send email.\n"
            "To set up:\n"
            "  1. Enable 2-Step Verification on your Google account\n"
            "  2. Go to https://myaccount.google.com/apppasswords\n"
            "  3. Create an app password\n"
            "  4. Set GMAIL_APP_PASSWORD env var"
        )
        return False

    if not SENDER_EMAIL or not RECIPIENT_EMAIL:
        log.warning("SENDER_EMAIL or RECIPIENT_EMAIL not set. Cannot send email.")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL

    msg.set_content(
        "Your daily RecSys & LLM industry papers digest. "
        "View in an HTML-capable email client."
    )
    msg.add_alternative(html_content, subtype="html")

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        log.info("Email sent successfully to %s", RECIPIENT_EMAIL)
        return True
    except Exception as e:
        log.error("Failed to send email: %s", e)
        return False


def save_report(html_content: str, industry_papers: list[dict]) -> Path:
    """Save the HTML report and a JSON dump locally."""
    report_dir = Path(__file__).resolve().parent.parent / "reports"
    report_dir.mkdir(exist_ok=True)

    date_str = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%Y-%m-%d")

    html_path = report_dir / f"recsys-llm-industry-{date_str}.html"
    html_path.write_text(html_content, encoding="utf-8")

    json_path = report_dir / f"recsys-llm-industry-{date_str}.json"
    json_path.write_text(
        json.dumps(industry_papers, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    log.info("Report saved to %s", html_path)
    return html_path
