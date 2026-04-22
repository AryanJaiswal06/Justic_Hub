# services/notification_service.py — email + in-app notifications
import os
from datetime import datetime
from flask import current_app
from flask_mail import Message as MailMessage
from extensions import db, mail
from models.document_model import Notification


# ── In-app notifications ───────────────────────────────────────────────────────

def create_notification(
    user_id:  int,
    title:    str,
    body:     str  = "",
    notif_type: str = "system",
    link:     str  = "",
) -> Notification:
    notif = Notification(
        user_id=user_id,
        type=notif_type,
        title=title,
        body=body,
        link=link,
    )
    db.session.add(notif)
    db.session.commit()
    return notif


def notify_case_update(client_id: int, lawyer_id: int, case_title: str, update_text: str) -> None:
    """Notify both parties of a case update. Either side may be None (e.g. unassigned case)."""
    if client_id:
        create_notification(client_id, f"Case Update: {case_title}", update_text, "case_update")
    if lawyer_id:
        create_notification(lawyer_id, f"Case Update: {case_title}", update_text, "case_update")


def notify_new_message(recipient_id: int, sender_name: str) -> None:
    create_notification(recipient_id, f"New message from {sender_name}", notif_type="new_message")


def notify_payment(client_id: int, amount: float, status: str) -> None:
    create_notification(
        client_id,
        f"Payment {status}: ₹{amount:,.2f}",
        notif_type="payment",
    )


def notify_lawyer_verified(lawyer_id: int, approved: bool) -> None:
    msg = "Your profile has been verified!" if approved else "Your verification was not approved. Please contact support."
    create_notification(lawyer_id, msg, notif_type="system")


# ── Email helpers ──────────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, html_body: str) -> bool:
    """Send an email. Returns True on success, False on failure."""
    try:
        msg = MailMessage(
            subject=subject,
            recipients=[to],
            html=html_body,
            sender=current_app.config.get("MAIL_DEFAULT_SENDER", "noreply@lexbridge.in"),
        )
        mail.send(msg)
        return True
    except Exception as exc:
        current_app.logger.error(f"Email send failed to {to}: {exc}")
        return False


def send_verification_email(to: str, full_name: str, token: str) -> bool:
    base_url = current_app.config.get("BASE_URL", "http://localhost:5000")
    link     = f"{base_url}/api/auth/verify-email/{token}"
    html     = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto">
      <h2 style="color:#c9a84c">Welcome to LexBridge, {full_name}!</h2>
      <p>Please verify your email address to activate your account.</p>
      <a href="{link}" style="display:inline-block;background:#c9a84c;color:#000;
         padding:0.7rem 1.5rem;border-radius:8px;text-decoration:none;font-weight:600">
        Verify Email
      </a>
      <p style="color:#888;font-size:0.8rem;margin-top:1.5rem">
        Link expires in 24 hours. If you did not sign up, ignore this email.
      </p>
    </div>"""
    return _send_email(to, "Verify your LexBridge account", html)


def send_password_reset_email(to: str, full_name: str, token: str) -> bool:
    base_url = current_app.config.get("BASE_URL", "http://localhost:5000")
    link     = f"{base_url}/api/auth/reset-password?token={token}"
    html     = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto">
      <h2 style="color:#c9a84c">Reset your password</h2>
      <p>Hi {full_name}, click the button below to reset your LexBridge password.</p>
      <a href="{link}" style="display:inline-block;background:#c9a84c;color:#000;
         padding:0.7rem 1.5rem;border-radius:8px;text-decoration:none;font-weight:600">
        Reset Password
      </a>
      <p style="color:#888;font-size:0.8rem;margin-top:1.5rem">
        This link expires in 1 hour. If you did not request this, ignore this email.
      </p>
    </div>"""
    return _send_email(to, "Reset your LexBridge password", html)


def send_case_accepted_email(to: str, client_name: str, case_title: str, lawyer_name: str) -> bool:
    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto">
      <h2 style="color:#c9a84c">Your case has been accepted</h2>
      <p>Hi {client_name},</p>
      <p><strong>{lawyer_name}</strong> has accepted your case: <em>{case_title}</em>.</p>
      <p>Log in to your dashboard to view updates and communicate with your lawyer.</p>
    </div>"""
    return _send_email(to, f"Case accepted: {case_title}", html)


def send_lawyer_verified_email(to: str, lawyer_name: str, approved: bool) -> bool:
    status = "Approved" if approved else "Not Approved"
    html   = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto">
      <h2 style="color:#c9a84c">Verification {status}</h2>
      <p>Hi {lawyer_name},</p>
      {"<p>Your LexBridge lawyer profile has been <strong>verified</strong>. You can now receive case requests.</p>"
       if approved else
       "<p>Unfortunately your profile verification was not approved. Please contact support@lexbridge.in.</p>"}
    </div>"""
    return _send_email(to, f"LexBridge Verification: {status}", html)
