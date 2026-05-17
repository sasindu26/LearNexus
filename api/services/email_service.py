import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

def _send(to: str, subject: str, html: str) -> bool:
    from_email = os.getenv("LEARNEXUS_EMAIL", "")
    from_password = os.getenv("LEARNEXUS_EMAIL_PASSWORD", "")
    if not from_email or not from_password:
        logger.warning("Email not configured — set LEARNEXUS_EMAIL and LEARNEXUS_EMAIL_PASSWORD env vars")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"LearNexus <{from_email}>"
        msg["To"] = to
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(from_email, from_password)
            s.sendmail(from_email, to, msg.as_string())
        logger.info(f"Email sent → {to} | {subject}")
        return True
    except Exception as e:
        logger.error(f"Email failed → {to}: {e}")
        return False


FROM_EMAIL = os.getenv("LEARNEXUS_EMAIL", "")


def send_welcome(to: str, name: str) -> bool:
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:linear-gradient(135deg,#1a237e,#283593);padding:32px;border-radius:14px;text-align:center;margin-bottom:24px">
    <h1 style="color:white;margin:0;font-size:26px;font-weight:900">🎓 Welcome to LearNexus!</h1>
  </div>
  <h2 style="color:#1a237e;margin-bottom:8px">Hi {name}! 👋</h2>
  <p style="color:#555;line-height:1.8;margin-bottom:12px">
    Your account has been successfully created. You're officially part of the LearNexus learning community!
  </p>
  <p style="color:#555;line-height:1.8;margin-bottom:24px">
    Chat with <strong>LearNexus AI</strong> to plan your learning path, explore your course modules,
    and track your progress — all in one place.
  </p>
  <div style="text-align:center;margin:28px 0">
    <a href="http://localhost:3000" style="background:#1565C0;color:white;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:700;font-size:15px">
      Start Learning →
    </a>
  </div>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="color:#aaa;font-size:12px;text-align:center;margin:0">LearNexus — Personalized Learning Platform</p>
</div>"""
    return _send(to, "Welcome to LearNexus! 🎓", html)


def send_security_alert(to: str, name: str) -> bool:
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:#b71c1c;padding:24px;border-radius:14px;text-align:center;margin-bottom:24px">
    <h1 style="color:white;margin:0;font-size:22px;font-weight:900">⚠️ Security Alert</h1>
  </div>
  <h2 style="color:#b71c1c;margin-bottom:8px">Hi {name},</h2>
  <p style="color:#555;line-height:1.8">
    We detected <strong>multiple failed login attempts</strong> on your LearNexus account.
  </p>
  <p style="color:#555;line-height:1.8">
    If this was you, you can ignore this message. If not, please reset your password immediately
    to protect your account.
  </p>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="color:#aaa;font-size:12px;text-align:center;margin:0">LearNexus Security Team</p>
</div>"""
    return _send(to, "⚠️ Security Alert — Multiple Failed Login Attempts", html)


def send_reset_code(to: str, name: str, code: str) -> bool:
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:linear-gradient(135deg,#1a237e,#283593);padding:28px;border-radius:14px;text-align:center;margin-bottom:24px">
    <h1 style="color:white;margin:0;font-size:24px;font-weight:900">🔑 Password Reset</h1>
  </div>
  <h2 style="color:#1a237e;margin-bottom:8px">Hi {name},</h2>
  <p style="color:#555;line-height:1.8;margin-bottom:20px">
    You requested a password reset for your LearNexus account. Use the code below:
  </p>
  <div style="background:#f5f7ff;border:2px solid #e3e8ff;border-radius:12px;padding:28px;text-align:center;margin:20px 0">
    <p style="color:#888;margin:0 0 8px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2px">Verification Code</p>
    <p style="font-size:40px;font-weight:900;color:#1a237e;margin:0;letter-spacing:12px">{code}</p>
    <p style="color:#aaa;margin:10px 0 0;font-size:12px">Expires in 10 minutes</p>
  </div>
  <p style="color:#aaa;font-size:12px;text-align:center">If you didn't request this, you can safely ignore this email.</p>
</div>"""
    return _send(to, "LearNexus — Password Reset Code 🔑", html)


def send_email_verify(to: str, name: str, code: str) -> bool:
    html = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:linear-gradient(135deg,#1a237e,#283593);padding:28px;border-radius:14px;text-align:center;margin-bottom:24px">
    <h1 style="color:white;margin:0;font-size:24px;font-weight:900">✉️ Verify New Email</h1>
  </div>
  <h2 style="color:#1a237e;margin-bottom:8px">Hi {name},</h2>
  <p style="color:#555;line-height:1.8;margin-bottom:20px">
    Use the code below to verify your new email address for LearNexus:
  </p>
  <div style="background:#f5f7ff;border:2px solid #e3e8ff;border-radius:12px;padding:28px;text-align:center;margin:20px 0">
    <p style="color:#888;margin:0 0 8px;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2px">Verification Code</p>
    <p style="font-size:40px;font-weight:900;color:#1a237e;margin:0;letter-spacing:12px">{code}</p>
    <p style="color:#aaa;margin:10px 0 0;font-size:12px">Expires in 10 minutes</p>
  </div>
  <p style="color:#aaa;font-size:12px;text-align:center">If you didn't request this, you can safely ignore this email.</p>
</div>"""
    return _send(to, "LearNexus — Verify New Email Address ✉️", html)


def send_contact(from_name: str, from_email: str, message: str) -> bool:
    """Send contact form to LearNexus inbox + confirmation copy to user."""
    learnexus_email = os.getenv("LEARNEXUS_EMAIL", "")
    html_to_us = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:#1a237e;padding:24px;border-radius:14px;text-align:center;margin-bottom:24px">
    <h1 style="color:white;margin:0;font-size:20px;font-weight:900">📩 New Contact Form Submission</h1>
  </div>
  <p><strong>Name:</strong> {from_name}</p>
  <p><strong>Email:</strong> {from_email}</p>
  <hr style="border:none;border-top:1px solid #eee;margin:16px 0">
  <p><strong>Message:</strong></p>
  <p style="background:#f9f9f9;padding:16px;border-radius:8px;color:#333;line-height:1.8">{message}</p>
</div>"""
    html_to_user = f"""
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <div style="background:linear-gradient(135deg,#1a237e,#283593);padding:28px;border-radius:14px;text-align:center;margin-bottom:24px">
    <h1 style="color:white;margin:0;font-size:22px;font-weight:900">🎓 Thanks for reaching out!</h1>
  </div>
  <h2 style="color:#1a237e">Hi {from_name},</h2>
  <p style="color:#555;line-height:1.8">We received your message and will get back to you soon.</p>
  <div style="background:#f5f7ff;border-radius:12px;padding:20px;margin:20px 0">
    <p style="color:#888;font-size:12px;margin:0 0 8px;font-weight:700;text-transform:uppercase">Your message</p>
    <p style="color:#333;margin:0;line-height:1.8">{message}</p>
  </div>
  <hr style="border:none;border-top:1px solid #eee;margin:24px 0">
  <p style="color:#aaa;font-size:12px;text-align:center">LearNexus — Personalized Learning Platform</p>
</div>"""
    ok1 = _send(learnexus_email, f"LearNexus Contact: {from_name}", html_to_us)
    ok2 = _send(from_email, "We received your message — LearNexus 🎓", html_to_user)
    return ok1 and ok2
