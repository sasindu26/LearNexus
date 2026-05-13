import os
import random
import time
import logging
import requests

logger = logging.getLogger(__name__)

GREEN_API_URL   = os.getenv("GREEN_API_URL", "https://7107.api.greenapi.com")
GREEN_API_ID    = os.getenv("GREEN_API_ID", "")
GREEN_API_TOKEN = os.getenv("GREEN_API_TOKEN", "")

# In-memory OTP store: {phone: {"otp": "123456", "expires": float}}
_otp_store: dict = {}
_OTP_TTL = 600  # 10 minutes


def _to_chat_id(phone: str) -> str:
    """Convert phone number to Green API chatId format: 94XXXXXXXXX@c.us"""
    # Strip whatsapp: prefix if present
    phone = phone.replace("whatsapp:", "").strip()
    # Remove leading +
    phone = phone.lstrip("+")
    return f"{phone}@c.us"


def send_whatsapp(to: str, body: str) -> bool:
    """Send a WhatsApp message via Green API. Returns True on success."""
    if not GREEN_API_ID or not GREEN_API_TOKEN:
        logger.warning("Green API credentials not set (GREEN_API_ID / GREEN_API_TOKEN)")
        return False
    try:
        url = f"{GREEN_API_URL}/waInstance{GREEN_API_ID}/sendMessage/{GREEN_API_TOKEN}"
        payload = {
            "chatId": _to_chat_id(to),
            "message": body
        }
        resp = requests.post(url, json=payload, timeout=15)
        if resp.status_code == 200:
            logger.info(f"WhatsApp sent → {to}")
            return True
        else:
            logger.error(f"Green API error {resp.status_code}: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"WhatsApp failed → {to}: {e}")
        return False


def send_otp(phone: str) -> bool:
    """Generate a 6-digit OTP, cache it, and send via WhatsApp."""
    otp = str(random.randint(100000, 999999))
    _otp_store[phone] = {"otp": otp, "expires": time.time() + _OTP_TTL}
    body = (
        f"🎓 *LearNexus Verification*\n\n"
        f"Your verification code is: *{otp}*\n\n"
        f"This code expires in 10 minutes.\n"
        f"Do not share this with anyone."
    )
    return send_whatsapp(phone, body)


def verify_otp(phone: str, otp: str) -> bool:
    """Verify OTP — consumes it on success (one-time use)."""
    entry = _otp_store.get(phone)
    if not entry or time.time() > entry["expires"]:
        _otp_store.pop(phone, None)
        return False
    if entry["otp"] != otp:
        return False
    del _otp_store[phone]
    return True
