import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

_THEME_GREEN = "#8B9E3A"
_THEME_GOLD = "#BFA15A"


def _normalize_recipients(recipients: Sequence[str] | str) -> list[str]:
    if isinstance(recipients, str):
        recipients = [recipients]
    normalized = []
    for email in recipients:
        if not email:
            continue
        clean = email.strip()
        if clean:
            normalized.append(clean)
    return list(dict.fromkeys(normalized))


def _smtp_settings() -> dict:
    return {
        "host": os.getenv("SMTP_HOST", "").strip(),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "username": os.getenv("SMTP_USERNAME", "").strip(),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes"},
        "use_ssl": os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes"},
        "from_email": os.getenv("SMTP_FROM_EMAIL", "").strip(),
        "from_name": os.getenv("SMTP_FROM_NAME", "Operations Team").strip() or "Operations Team",
    }


def send_email(
    recipients: Sequence[str] | str,
    subject: str,
    html_content: str,
    text_content: str,
) -> Tuple[bool, Optional[str]]:
    settings = _smtp_settings()
    to_addresses = _normalize_recipients(recipients)

    if not to_addresses:
        return False, "No recipient email addresses were provided"

    if not settings["host"] or not settings["from_email"]:
        return False, "SMTP is not configured (missing SMTP_HOST or SMTP_FROM_EMAIL)"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{settings['from_name']} <{settings['from_email']}>"
    msg["To"] = ", ".join(to_addresses)
    msg.set_content(text_content)
    msg.add_alternative(html_content, subtype="html")

    try:
        if settings["use_ssl"]:
            with smtplib.SMTP_SSL(settings["host"], settings["port"], timeout=20) as server:
                if settings["username"] and settings["password"]:
                    server.login(settings["username"], settings["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings["host"], settings["port"], timeout=20) as server:
                if settings["use_tls"]:
                    server.starttls()
                if settings["username"] and settings["password"]:
                    server.login(settings["username"], settings["password"])
                server.send_message(msg)

        return True, None
    except Exception as exc:
        logger.exception("Failed to send email")
        return False, str(exc)


def _shell_email_layout(title: str, greeting: str, body_html: str, footer_text: str) -> str:
    return f"""
<!doctype html>
<html>
  <body style=\"margin:0;padding:0;background:#f6f6f4;font-family:Arial,sans-serif;color:#1f1f1f;\">
    <table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f6f6f4;padding:28px 12px;\">
      <tr>
        <td align=\"center\">
          <table width=\"640\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:640px;background:#ffffff;border:1px solid #e8e8e8;border-radius:10px;\">
            <tr>
              <td style=\"padding:22px 28px 14px 28px;border-bottom:2px solid {_THEME_GREEN};\">
                <div style=\"font-size:18px;font-weight:700;color:{_THEME_GREEN};\">{title}</div>
              </td>
            </tr>
            <tr>
              <td style=\"padding:22px 28px 8px 28px;font-size:14px;line-height:1.6;\">
                <p style=\"margin:0 0 14px 0;\">{greeting}</p>
                {body_html}
              </td>
            </tr>
            <tr>
              <td style=\"padding:14px 28px 24px 28px;border-top:1px solid #efefef;font-size:12px;color:#606060;\">
                <p style=\"margin:0;color:{_THEME_GOLD};font-weight:600;\">Operations Notice</p>
                <p style=\"margin:6px 0 0 0;\">{footer_text}</p>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
""".strip()


def send_credentials_email(
    recipient_email: str,
    recipient_name: str,
    username: str,
    temporary_password: str,
    role: str,
) -> Tuple[bool, Optional[str]]:
    role_label = role.replace("_", " ").title()

    body_html = f"""
<p style=\"margin:0 0 12px 0;\">Your account has been provisioned with the details below:</p>
<table cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;margin:0 0 12px 0;font-size:14px;\">
  <tr>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;background:#fbfbfb;font-weight:600;\">Role</td>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;\">{role_label}</td>
  </tr>
  <tr>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;background:#fbfbfb;font-weight:600;\">Username</td>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;\">{username}</td>
  </tr>
  <tr>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;background:#fbfbfb;font-weight:600;\">Temporary Password</td>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;\">{temporary_password}</td>
  </tr>
</table>
<p style=\"margin:0 0 12px 0;color:#222;\"><strong>Action required:</strong> Please sign in and change your password immediately after your first login.</p>
<p style=\"margin:0;\">If you were not expecting this account setup, please contact your organization administrator.</p>
"""

    html = _shell_email_layout(
        title="Account Access Details",
        greeting=f"Dear {recipient_name},",
        body_html=body_html,
        footer_text="This is an official business communication from your operations team.",
    )

    text = (
        f"Dear {recipient_name},\n\n"
        "Your account has been provisioned.\n"
        f"Role: {role_label}\n"
        f"Username: {username}\n"
        f"Temporary Password: {temporary_password}\n\n"
        "Please sign in and change your password immediately after your first login.\n"
        "If you were not expecting this account setup, contact your organization administrator.\n"
    )

    return send_email(
        recipients=[recipient_email],
        subject="Account Access Details",
        html_content=html,
        text_content=text,
    )


def send_doctor_assignment_confirmation_email(
    recipients: Sequence[str],
    facility_name: str,
    doctor_name: str,
    doctor_email: str,
    specialty: Optional[str],
    requested_by_name: str,
    confirmation_url: str,
    expires_at_iso: str,
) -> Tuple[bool, Optional[str]]:
    specialty_label = specialty.strip() if specialty and specialty.strip() else "Not specified"

    body_html = f"""
<p style=\"margin:0 0 12px 0;\">A request has been submitted to add a doctor to your facility. Please review and confirm this action.</p>
<table cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;margin:0 0 18px 0;font-size:14px;\">
  <tr>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;background:#fbfbfb;font-weight:600;\">Facility</td>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;\">{facility_name}</td>
  </tr>
  <tr>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;background:#fbfbfb;font-weight:600;\">Doctor Name</td>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;\">{doctor_name}</td>
  </tr>
  <tr>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;background:#fbfbfb;font-weight:600;\">Doctor Email</td>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;\">{doctor_email}</td>
  </tr>
  <tr>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;background:#fbfbfb;font-weight:600;\">Specialty</td>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;\">{specialty_label}</td>
  </tr>
  <tr>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;background:#fbfbfb;font-weight:600;\">Requested By</td>
    <td style=\"padding:6px 10px;border:1px solid #e2e2e2;\">{requested_by_name}</td>
  </tr>
</table>
<p style=\"margin:0 0 16px 0;\">
  <a href=\"{confirmation_url}\" style=\"display:inline-block;padding:10px 16px;background:{_THEME_GREEN};color:#ffffff;text-decoration:none;border-radius:6px;font-weight:600;\">Confirm Doctor Assignment</a>
</p>
<p style=\"margin:0 0 8px 0;\">If the button does not open, copy and paste this URL into your browser:</p>
<p style=\"margin:0 0 10px 0;color:#444;word-break:break-all;\">{confirmation_url}</p>
<p style=\"margin:0;\">This confirmation request expires at {expires_at_iso}.</p>
"""

    html = _shell_email_layout(
        title="Confirmation Required: Doctor Assignment",
        greeting="Dear Facility Leadership,",
        body_html=body_html,
        footer_text="Please action this request only if it matches your approved staffing plan.",
    )

    text = (
        "A request has been submitted to add a doctor to your facility.\n\n"
        f"Facility: {facility_name}\n"
        f"Doctor Name: {doctor_name}\n"
        f"Doctor Email: {doctor_email}\n"
        f"Specialty: {specialty_label}\n"
        f"Requested By: {requested_by_name}\n\n"
        f"Confirm using this URL: {confirmation_url}\n"
        f"This request expires at {expires_at_iso}.\n"
    )

    return send_email(
        recipients=recipients,
        subject="Confirmation Required: Doctor Assignment",
        html_content=html,
        text_content=text,
    )
