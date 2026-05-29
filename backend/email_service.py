from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from html import escape

from backend.core.config import settings


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def app_base_url() -> str:
    return _env("APP_BASE_URL", getattr(settings, "APP_URL", "http://localhost:8000")).rstrip("/")


def _email_shell(title: str, preheader: str, body_html: str, button_text: str, button_url: str) -> str:
    safe_title = escape(title)
    safe_preheader = escape(preheader)
    safe_button_text = escape(button_text)
    safe_button_url = escape(button_url, quote=True)
    return f"""<!doctype html>
<html lang=\"en\">
<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"></head>
<body style=\"margin:0;background:#0b0d11;padding:32px 16px;font-family:Inter,Segoe UI,Arial,sans-serif;color:#e5e7eb;\">
  <div style=\"display:none;max-height:0;overflow:hidden;color:transparent;\">{safe_preheader}</div>
  <table role=\"presentation\" width=\"100%\" cellspacing=\"0\" cellpadding=\"0\" style=\"max-width:640px;margin:0 auto;background:#12151c;border:1px solid #242b3a;border-radius:20px;overflow:hidden;box-shadow:0 24px 80px rgba(0,0,0,.35);\">
    <tr><td style=\"padding:28px 32px;border-bottom:1px solid #242b3a;\">
      <div style=\"font-size:14px;letter-spacing:.08em;text-transform:uppercase;color:#60a5fa;font-weight:800;\">Meta Tool</div>
      <h1 style=\"margin:10px 0 0;color:#fff;font-size:26px;line-height:1.2;\">{safe_title}</h1>
    </td></tr>
    <tr><td style=\"padding:30px 32px;color:#cbd5e1;font-size:15px;line-height:1.7;\">
      {body_html}
      <p style=\"margin:28px 0;\"><a href=\"{safe_button_url}\" style=\"display:inline-block;background:#3b82f6;color:#fff;text-decoration:none;font-weight:800;padding:13px 22px;border-radius:12px;\">{safe_button_text}</a></p>
      <p style=\"font-size:13px;color:#94a3b8;margin-top:24px;\">If the button does not work, copy and paste this URL into your browser:</p>
      <p style=\"word-break:break-all;font-size:12px;color:#60a5fa;\">{safe_button_url}</p>
    </td></tr>
    <tr><td style=\"padding:20px 32px;background:#0f1218;color:#64748b;font-size:12px;line-height:1.5;\">
      This email was sent by Meta Tool. If you did not request this, you can safely ignore it.
    </td></tr>
  </table>
</body></html>"""


def _send(to_email: str, subject: str, html: str) -> bool:
    host = _env("SMTP_HOST")
    if not host:
        print(f"[email-dev] To: {to_email}\nSubject: {subject}\n{html[:1000]}", flush=True)
        return False

    port = int(_env("SMTP_PORT", "587"))
    username = _env("SMTP_USERNAME")
    password = _env("SMTP_PASSWORD")
    from_email = _env("SMTP_FROM_EMAIL", username or "no-reply@example.com")
    from_name = _env("SMTP_FROM_NAME", "Meta Tool")
    use_tls = _env("SMTP_USE_TLS", "true").lower() not in {"0", "false", "no"}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg.set_content("Please open this email in an HTML-compatible email client.")
    msg.add_alternative(html, subtype="html")

    with smtplib.SMTP(host, port, timeout=30) as smtp:
        if use_tls:
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(msg)
    return True


def send_activation_email(to_email: str, name: str, activation_url: str) -> bool:
    safe_name = escape(name or "there")
    html = _email_shell(
        "Activate your account",
        "Confirm your email address to activate your Meta Tool account.",
        f"""
        <p style=\"margin-top:0;\">Hi {safe_name},</p>
        <p>Welcome to Meta Tool. Please confirm your email address to activate your account and access your metrics dashboard.</p>
        <p>This activation link expires in 24 hours.</p>
        """,
        "Activate account",
        activation_url,
    )
    return _send(to_email, "Activate your Meta Tool account", html)


def send_password_reset_email(to_email: str, name: str, reset_url: str) -> bool:
    safe_name = escape(name or "there")
    html = _email_shell(
        "Reset your password",
        "Use this secure link to choose a new password.",
        f"""
        <p style=\"margin-top:0;\">Hi {safe_name},</p>
        <p>We received a request to reset your Meta Tool password. Click the button below to choose a new password.</p>
        <p>This password reset link expires in 1 hour.</p>
        """,
        "Reset password",
        reset_url,
    )
    return _send(to_email, "Reset your Meta Tool password", html)
