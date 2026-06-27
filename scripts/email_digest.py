"""Build today's daily digest and email it (used by the scheduled GitHub Action).

Reads SMTP settings from the environment so no secrets live in the repo:

    SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASS
    DIGEST_TO        comma-separated recipient(s)
    DIGEST_FROM      sender address (defaults to SMTP_USER)

Plus the usual app secrets (LLM_PROVIDER/GROQ_API_KEY/STORAGE_BACKEND/SUPABASE_*)
so it can read the shared vault and write an LLM summary. With no SMTP set it
just prints the digest (handy for local testing / dry runs).

    python scripts/email_digest.py
"""

import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import tools  # noqa: E402


def build_text() -> tuple[str, str]:
    d = tools.daily_digest()
    lines = [f"SecondBrain — daily digest for {d['date']}", "", d["summary"], ""]
    if d["notes"]:
        lines.append("Notes touched today:")
        for n in d["notes"]:
            lines.append(f"  • {n['title']} ({n['modified']})")
    subject = f"SecondBrain digest — {d['date']} ({len(d['notes'])} notes)"
    return subject, "\n".join(lines)


def main():
    subject, body = build_text()
    host = os.getenv("SMTP_HOST")
    to = os.getenv("DIGEST_TO")
    if not (host and to):
        print("[dry run] SMTP_HOST / DIGEST_TO not set — printing digest:\n")
        print(subject)
        print(body)
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("DIGEST_FROM") or os.getenv("SMTP_USER", "")
    msg["To"] = to
    msg.set_content(body)

    port = int(os.getenv("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        user, pw = os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")
        if user and pw:
            s.login(user, pw)
        s.send_message(msg)
    print(f"Sent digest to {to}")


if __name__ == "__main__":
    main()
