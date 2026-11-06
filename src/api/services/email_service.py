"""
Email service for FORGE-Vision.

Supports SMTP (local/relay) and SendGrid.
Configuration via environment variables — no credentials in source.

Usage:
    from src.api.services.email_service import send_password_reset_email
    await send_password_reset_email(to_email="user@example.com", token="abc123")
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)

_APP_URL = os.getenv("APP_URL", "http://localhost:8501")
_FROM_EMAIL = os.getenv("EMAIL_FROM", "noreply@forgevision.local")
_SMTP_HOST = os.getenv("SMTP_HOST", "")
_SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
_SMTP_USER = os.getenv("SMTP_USER", "")
_SMTP_PASS = os.getenv("SMTP_PASS", "")
_SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")


def _build_reset_email(to_email: str, token: str) -> tuple[str, str]:
    """Return (subject, html_body) for a password reset email."""
    reset_url = f"{_APP_URL}/reset-password?token={token}"
    subject = "FORGE-Vision — Password Reset Request"
    html = f"""
    <p>Hello,</p>
    <p>A password reset was requested for your FORGE-Vision account (<strong>{to_email}</strong>).</p>
    <p>Click the link below to set a new password. This link expires in <strong>30 minutes</strong>.</p>
    <p><a href="{reset_url}">{reset_url}</a></p>
    <p>If you did not request this, please ignore this email.</p>
    <p>— FORGE-Vision System</p>
    """
    return subject, html


async def send_password_reset_email(to_email: str, token: str) -> None:
    """
    Send a password reset email via SendGrid (if configured) or SMTP.
    Falls back to stdout logging in development (SMTP_HOST not set).
    """
    subject, html_body = _build_reset_email(to_email, token)

    if _SENDGRID_API_KEY:
        await _send_via_sendgrid(to_email, subject, html_body)
    elif _SMTP_HOST:
        await _send_via_smtp(to_email, subject, html_body)
    else:
        # Development fallback — token visible in logs only
        reset_url = f"{_APP_URL}/reset-password?token={token}"
        log.warning(
            "[DEV] Password reset token for %s: %s  |  URL: %s",
            to_email, token, reset_url,
        )


async def _send_via_sendgrid(to_email: str, subject: str, html_body: str) -> None:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                "https://api.sendgrid.com/v3/mail/send",
                headers={"Authorization": f"Bearer {_SENDGRID_API_KEY}"},
                json={
                    "personalizations": [{"to": [{"email": to_email}]}],
                    "from": {"email": _FROM_EMAIL},
                    "subject": subject,
                    "content": [{"type": "text/html", "value": html_body}],
                },
            )
            if resp.status_code not in (200, 202):
                log.error("SendGrid returned %s: %s", resp.status_code, resp.text)
            else:
                log.info("Password reset email sent via SendGrid to %s", to_email)
    except Exception as exc:
        log.error("SendGrid send failed: %s", exc)


async def _send_via_smtp(to_email: str, subject: str, html_body: str) -> None:
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _smtp_send_sync, to_email, subject, html_body)
        log.info("Password reset email sent via SMTP to %s", to_email)
    except Exception as exc:
        log.error("SMTP send failed: %s", exc)


def _smtp_send_sync(to_email: str, subject: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"] = _FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as server:
        server.ehlo()
        if _SMTP_PORT == 587:
            server.starttls()
        if _SMTP_USER and _SMTP_PASS:
            server.login(_SMTP_USER, _SMTP_PASS)
        server.sendmail(_FROM_EMAIL, to_email, msg.as_string())
