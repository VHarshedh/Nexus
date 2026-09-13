"""
NEXUS -- Transactional Email Service.

Sends transactional emails (account verification, secure password reset)
via Gmail SMTP (aiosmtplib) using asynchronous event-loop safe dispatch.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from app.config import get_settings

logger = logging.getLogger(__name__)


def _build_html_template(
    title: str,
    greeting: str,
    body_text: str,
    action_url: str,
    action_text: str,
    notice_text: str,
) -> str:
    """Render a responsive, dark-mode email template matching NEXUS aesthetics."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #090d16; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #e2e8f0;">
  <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #090d16; padding: 40px 10px;">
    <tr>
      <td align="center">
        <!-- Card Container -->
        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="max-width: 540px; background-color: #111726; border: 1px solid #1f293d; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
          <!-- Header -->
          <tr>
            <td style="padding: 32px 32px 20px 32px; text-align: center; border-bottom: 1px solid #1a2234;">
              <div style="display: inline-block; width: 44px; height: 44px; line-height: 44px; background: linear-gradient(135deg, #7c3aed, #4f46e5); border-radius: 12px; font-weight: bold; font-size: 20px; color: #ffffff;">
                ⚡
              </div>
              <h1 style="margin: 12px 0 0 0; font-size: 22px; font-weight: 700; color: #ffffff; letter-spacing: 0.5px;">
                NEXUS
              </h1>
              <p style="margin: 4px 0 0 0; font-size: 13px; color: #94a3b8;">Autonomous Career Intelligence</p>
            </td>
          </tr>
          <!-- Body -->
          <tr>
            <td style="padding: 32px;">
              <h2 style="margin: 0 0 16px 0; font-size: 18px; font-weight: 600; color: #f8fafc;">
                {greeting}
              </h2>
              <p style="margin: 0 0 24px 0; font-size: 14px; line-height: 1.6; color: #cbd5e1;">
                {body_text}
              </p>
              <!-- Action Button -->
              <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin: 28px 0;">
                <tr>
                  <td align="center" style="border-radius: 10px; background: linear-gradient(135deg, #7c3aed, #6366f1);">
                    <a href="{action_url}" target="_blank" style="display: inline-block; padding: 14px 28px; font-size: 14px; font-weight: 600; color: #ffffff; text-decoration: none; border-radius: 10px;">
                      {action_text} &rarr;
                    </a>
                  </td>
                </tr>
              </table>
              <!-- Direct Link Fallback -->
              <p style="margin: 20px 0 0 0; font-size: 12px; line-height: 1.5; color: #64748b;">
                If the button above does not work, copy and paste this link into your browser:<br>
                <a href="{action_url}" style="color: #a78bfa; word-break: break-all;">{action_url}</a>
              </p>
            </td>
          </tr>
          <!-- Security Notice & Footer -->
          <tr>
            <td style="padding: 24px 32px; background-color: #0b1120; border-top: 1px solid #1a2234; text-align: center;">
              <p style="margin: 0; font-size: 12px; line-height: 1.5; color: #64748b;">
                🔒 <strong>Security Note:</strong> {notice_text}
              </p>
              <p style="margin: 12px 0 0 0; font-size: 11px; color: #475569;">
                &copy; NEXUS AI. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""


async def send_email(
    to_email: str,
    subject: str,
    text_content: str,
    html_content: str,
) -> bool:
    """Send an email using Gmail SMTP via aiosmtplib.

    Falls back to logger output if Gmail credentials are not configured.
    """
    settings = get_settings()
    gmail_user = settings.gmail_user.strip()
    gmail_password = settings.gmail_app_password.strip().replace(" ", "")

    if not gmail_user or not gmail_password:
        logger.warning(
            "[email-fallback] Gmail credentials not set. Simulated email to %s:\nSubject: %s\n%s",
            to_email,
            subject,
            text_content,
        )
        return True

    msg = EmailMessage()
    msg["From"] = f"NEXUS Career Intelligence <{gmail_user}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    try:
        await aiosmtplib.send(
            msg,
            hostname="smtp.gmail.com",
            port=465,
            use_tls=True,
            username=gmail_user,
            password=gmail_password,
            timeout=15,
        )
        logger.info("[email] Successfully sent '%s' to %s", subject, to_email)
        return True
    except Exception as exc:
        logger.error("[email] Failed to send email to %s: %s", to_email, exc)
        logger.warning(
            "[email-fallback] Dev link delivery for %s (fallback active):\n%s",
            to_email,
            text_content,
        )
        return False


async def send_verification_email(to_email: str, verify_url: str) -> bool:
    """Send account verification link to newly registered user."""
    subject = "Verify your NEXUS account"
    text = (
        f"Welcome to NEXUS!\n\n"
        f"Please verify your email address by visiting the link below:\n"
        f"{verify_url}\n\n"
        f"This link will expire in 24 hours.\n"
        f"If you did not create a NEXUS account, you can safely ignore this email."
    )
    html = _build_html_template(
        title=subject,
        greeting="Confirm your email address",
        body_text=(
            "Welcome to NEXUS! To activate your autonomous career intelligence account "
            "and safeguard your profile, please confirm your email address."
        ),
        action_url=verify_url,
        action_text="Verify My Account",
        notice_text="This link is valid for 24 hours. If you did not create this account, no action is needed.",
    )
    return await send_email(to_email, subject, text, html)


async def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """Send single-use password reset link to verified user (10 min expiry)."""
    subject = "Reset your NEXUS password"
    text = (
        f"NEXUS Password Reset Request\n\n"
        f"We received a request to reset your NEXUS password. "
        f"Click the link below to choose a new password:\n"
        f"{reset_url}\n\n"
        f"IMPORTANT: This reset link expires in 10 minutes.\n"
        f"If you did not request a password reset, your account is secure and you can ignore this email."
    )
    html = _build_html_template(
        title=subject,
        greeting="Password Reset Request",
        body_text=(
            "We received a request to reset the password for your NEXUS account. "
            "Click the button below to set a new password. "
            "For security reasons, this link will expire in <strong>10 minutes</strong>."
        ),
        action_url=reset_url,
        action_text="Reset Password",
        notice_text="This link expires in 10 minutes and can only be used once. If you did not request this, your password remains unchanged.",
    )
    return await send_email(to_email, subject, text, html)
