from flask import Blueprint, request, jsonify
import bcrypt
import jwt
import os
import re
import random
import time
import threading
from neo4j import GraphDatabase

profile_bp = Blueprint('profile', __name__, url_prefix='/api/auth/profile')

NEO4J_URL      = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "LearNexus1212")
JWT_SECRET     = os.getenv("JWT_SECRET", "learnexus_ai_secret_key_2026")

try:
    driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))
except Exception as _e:
    driver = None

def get_session():
    if driver is None:
        raise RuntimeError("No database connection")
    return driver.session()

# In-memory pending-change store: keyed by user email
# value: {"otp": "123456", "expires": float, "pending": <new value>}
_pending: dict = {}
_OTP_TTL = 600


def _decode_token(req):
    token = req.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return None, ('Unauthorized', 401)
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"]), None
    except Exception:
        return None, ('Invalid token', 401)


def _gen_otp():
    return str(random.randint(100000, 999999))


def _validate_password(password: str):
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', password):
        return "Password must contain at least one special character"
    return None


# ─── UPDATE PERSONAL DETAILS ─────────────────────────────
@profile_bp.route('/personal', methods=['PUT'])
def update_personal():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data = request.get_json() or {}
    first_name   = data.get('first_name', '').strip()
    last_name    = data.get('last_name', '').strip()
    parent_number = data.get('parent_number', None)
    if parent_number:
        parent_number = parent_number.strip() or None

    if not first_name or not last_name:
        return jsonify({"status": "error", "message": "First and last name are required"}), 400

    full_name = f"{first_name} {last_name}"
    try:
        with get_session() as session:
            session.run("""
                MATCH (s:Student {email: $email})
                SET s.first_name = $fn, s.last_name = $ln,
                    s.name = $name, s.parent_number = $pn
            """, email=payload["email"], fn=first_name, ln=last_name,
                 name=full_name, pn=parent_number)
        return jsonify({"status": "success", "message": "Personal details updated"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── UPDATE PROFILE PICTURE ──────────────────────────────
@profile_bp.route('/picture', methods=['POST'])
def update_picture():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data = request.get_json() or {}
    picture = data.get('picture', '').strip()
    if not picture:
        return jsonify({"status": "error", "message": "No picture provided"}), 400

    try:
        with get_session() as session:
            session.run("""
                MATCH (s:Student {email: $email})
                SET s.picture = $pic
            """, email=payload["email"], pic=picture)
        return jsonify({"status": "success", "message": "Profile picture updated"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── CHANGE EMAIL — REQUEST ──────────────────────────────
@profile_bp.route('/change-email/request', methods=['POST'])
def change_email_request():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data = request.get_json() or {}
    new_email = data.get('new_email', '').strip().lower()
    if not new_email or '@' not in new_email:
        return jsonify({"status": "error", "message": "Valid email required"}), 400

    # Check not already taken
    with get_session() as session:
        existing = session.run(
            "MATCH (s:Student {email: $e}) RETURN s LIMIT 1", e=new_email
        ).single()
        if existing:
            return jsonify({"status": "error", "message": "Email already in use"}), 409

        rec = session.run(
            "MATCH (s:Student {email: $e}) RETURN s.name AS name",
            e=payload["email"]
        ).single()

    name = (rec["name"] or "there").split()[0] if rec else "there"
    otp = _gen_otp()
    _pending[f"email:{payload['email']}"] = {
        "otp": otp, "expires": time.time() + _OTP_TTL, "pending": new_email
    }

    from api.services.email_service import send_email_verify
    threading.Thread(target=send_email_verify, args=(new_email, name, otp), daemon=True).start()
    return jsonify({"status": "success", "message": f"Verification code sent to {new_email}"})


# ─── CHANGE EMAIL — VERIFY ───────────────────────────────
@profile_bp.route('/change-email/verify', methods=['POST'])
def change_email_verify():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data = request.get_json() or {}
    otp  = data.get('otp', '').strip()
    key  = f"email:{payload['email']}"
    entry = _pending.get(key)

    if not entry or time.time() > entry["expires"]:
        _pending.pop(key, None)
        return jsonify({"status": "error", "message": "Code expired. Request a new one"}), 400
    if entry["otp"] != otp:
        return jsonify({"status": "error", "message": "Invalid code"}), 400

    new_email = entry["pending"]
    _pending.pop(key, None)

    try:
        with get_session() as session:
            session.run("""
                MATCH (s:Student {email: $old})
                SET s.email = $new
            """, old=payload["email"], new=new_email)
        return jsonify({"status": "success", "message": "Email updated successfully", "new_email": new_email})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── CHANGE WHATSAPP — REQUEST ───────────────────────────
@profile_bp.route('/change-whatsapp/request', methods=['POST'])
def change_whatsapp_request():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data = request.get_json() or {}
    new_phone = data.get('new_phone', '').strip()
    if not new_phone:
        return jsonify({"status": "error", "message": "Phone number required"}), 400

    otp = _gen_otp()
    _pending[f"wa:{payload['email']}"] = {
        "otp": otp, "expires": time.time() + _OTP_TTL, "pending": new_phone
    }

    from api.services.whatsapp_service import send_whatsapp
    body = (
        f"🎓 *LearNexus Verification*\n\n"
        f"Your verification code is: *{otp}*\n\n"
        f"This code expires in 10 minutes.\nDo not share this with anyone."
    )
    threading.Thread(target=send_whatsapp, args=(new_phone, body), daemon=True).start()
    return jsonify({"status": "success", "message": f"Verification code sent to {new_phone}"})


# ─── CHANGE PARENT NUMBER — REQUEST ─────────────────────
@profile_bp.route('/change-parent/request', methods=['POST'])
def change_parent_request():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data = request.get_json() or {}
    new_phone = data.get('new_phone', '').strip()
    if not new_phone:
        return jsonify({"status": "error", "message": "Phone number required"}), 400

    otp = _gen_otp()
    _pending[f"parent:{payload['email']}"] = {
        "otp": otp, "expires": time.time() + _OTP_TTL, "pending": new_phone
    }

    from api.services.whatsapp_service import send_whatsapp
    body = (
        f"🎓 *LearNexus Verification*\n\n"
        f"You have been added as a parent/guardian on a LearNexus account.\n\n"
        f"Your verification code is: *{otp}*\n\n"
        f"This code expires in 10 minutes.\nDo not share this with anyone."
    )
    threading.Thread(target=send_whatsapp, args=(new_phone, body), daemon=True).start()
    return jsonify({"status": "success", "message": f"Verification code sent to {new_phone}"})


# ─── CHANGE PARENT NUMBER — VERIFY ───────────────────────
@profile_bp.route('/change-parent/verify', methods=['POST'])
def change_parent_verify():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data  = request.get_json() or {}
    otp   = data.get('otp', '').strip()
    key   = f"parent:{payload['email']}"
    entry = _pending.get(key)

    if not entry or time.time() > entry["expires"]:
        _pending.pop(key, None)
        return jsonify({"status": "error", "message": "Code expired. Request a new one"}), 400
    if entry["otp"] != otp:
        return jsonify({"status": "error", "message": "Invalid code"}), 400

    new_phone = entry["pending"]
    _pending.pop(key, None)

    try:
        with get_session() as session:
            session.run("""
                MATCH (s:Student {email: $email})
                SET s.parent_number = $phone
            """, email=payload["email"], phone=new_phone)
        return jsonify({"status": "success", "message": "Parent number updated", "new_phone": new_phone})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── CHANGE WHATSAPP — VERIFY ────────────────────────────
@profile_bp.route('/change-whatsapp/verify', methods=['POST'])
def change_whatsapp_verify():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data = request.get_json() or {}
    otp  = data.get('otp', '').strip()
    key  = f"wa:{payload['email']}"
    entry = _pending.get(key)

    if not entry or time.time() > entry["expires"]:
        _pending.pop(key, None)
        return jsonify({"status": "error", "message": "Code expired. Request a new one"}), 400
    if entry["otp"] != otp:
        return jsonify({"status": "error", "message": "Invalid code"}), 400

    new_phone = entry["pending"]
    _pending.pop(key, None)

    try:
        with get_session() as session:
            session.run("""
                MATCH (s:Student {email: $email})
                SET s.whatsapp_number = $phone
            """, email=payload["email"], phone=new_phone)
        return jsonify({"status": "success", "message": "WhatsApp number updated", "new_phone": new_phone})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── CHANGE PASSWORD — REQUEST ───────────────────────────
@profile_bp.route('/change-password/request', methods=['POST'])
def change_password_request():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data = request.get_json() or {}
    old_password = data.get('old_password', '')
    new_password = data.get('new_password', '')
    method       = data.get('method', 'email')  # 'email' or 'whatsapp'

    err_msg = _validate_password(new_password)
    if err_msg:
        return jsonify({"status": "error", "message": err_msg}), 400

    try:
        with get_session() as session:
            rec = session.run("""
                MATCH (s:Student {email: $e})
                RETURN s.password_hash AS pw_hash, s.name AS name,
                       s.whatsapp_number AS wa, s.email AS email
            """, e=payload["email"]).single()

        if not rec:
            return jsonify({"status": "error", "message": "User not found"}), 404

        if not rec["pw_hash"]:
            return jsonify({"status": "error", "message": "Account has no password (e.g. Google Login)"}), 400

        if not bcrypt.checkpw(old_password.encode(), rec["pw_hash"].encode()):
            return jsonify({"status": "error", "message": "Current password is incorrect"}), 400

        otp = _gen_otp()
        new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        _pending[f"pw:{payload['email']}"] = {
            "otp": otp, "expires": time.time() + _OTP_TTL, "pending": new_hash
        }

        name = (rec["name"] or "there").split()[0]

        if method == 'whatsapp' and rec.get("wa"):
            from api.services.whatsapp_service import send_whatsapp
            body = (
                f"🔑 *LearNexus Password Change*\n\n"
                f"Your verification code is: *{otp}*\n\n"
                f"Expires in 10 minutes. Do not share."
            )
            threading.Thread(target=send_whatsapp, args=(rec["wa"], body), daemon=True).start()
            return jsonify({"status": "success", "method": "whatsapp"})
        else:
            from api.services.email_service import send_reset_code
            threading.Thread(target=send_reset_code, args=(rec["email"], name, otp), daemon=True).start()
            return jsonify({"status": "success", "method": "email"})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── CHANGE PASSWORD — VERIFY ────────────────────────────
@profile_bp.route('/change-password/verify', methods=['POST'])
def change_password_verify():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data  = request.get_json() or {}
    otp   = data.get('otp', '').strip()
    key   = f"pw:{payload['email']}"
    entry = _pending.get(key)

    if not entry or time.time() > entry["expires"]:
        _pending.pop(key, None)
        return jsonify({"status": "error", "message": "Code expired. Start again"}), 400
    if entry["otp"] != otp:
        return jsonify({"status": "error", "message": "Invalid code"}), 400

    new_hash = entry["pending"]
    _pending.pop(key, None)

    try:
        with get_session() as session:
            session.run("""
                MATCH (s:Student {email: $email})
                SET s.password_hash = $pw
            """, email=payload["email"], pw=new_hash)
        return jsonify({"status": "success", "message": "Password changed successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── DELETE ACCOUNT ──────────────────────────────────────
@profile_bp.route('/delete', methods=['DELETE'])
def delete_account():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data     = request.get_json() or {}
    password = data.get('password', '')

    with get_session() as session:
        rec = session.run(
            "MATCH (s:Student {email: $e}) RETURN s.password_hash AS pw_hash",
            e=payload["email"]
        ).single()

    if not rec:
        return jsonify({"status": "error", "message": "User not found"}), 404
    if not bcrypt.checkpw(password.encode(), rec["pw_hash"].encode()):
        return jsonify({"status": "error", "message": "Incorrect password"}), 400

    try:
        with get_session() as session:
            session.run("MATCH (s:Student {email: $e}) DETACH DELETE s", e=payload["email"])
        return jsonify({"status": "success", "message": "Account deleted"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── CONTACT US ──────────────────────────────────────────
@profile_bp.route('/contact', methods=['POST'])
def contact_us():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data    = request.get_json() or {}
    name    = data.get('name', '').strip()
    email   = data.get('email', '').strip()
    message = data.get('message', '').strip()

    if not name or not email or not message:
        return jsonify({"status": "error", "message": "All fields are required"}), 400

    from api.services.email_service import send_contact
    threading.Thread(target=send_contact, args=(name, email, message), daemon=True).start()
    return jsonify({"status": "success", "message": "Message sent"})


# ─── FEEDBACK ────────────────────────────────────────────
@profile_bp.route('/feedback', methods=['POST'])
def submit_feedback():
    payload, err = _decode_token(request)
    if err:
        return jsonify({"status": "error", "message": err[0]}), err[1]

    data     = request.get_json() or {}
    category = data.get('category', '').strip()
    message  = data.get('message', '').strip()
    rating   = data.get('rating', None)

    if not message:
        return jsonify({"status": "error", "message": "Feedback message is required"}), 400

    try:
        from datetime import datetime
        with get_session() as session:
            session.run("""
                MATCH (s:Student {email: $email})
                CREATE (f:Feedback {
                    category: $cat, message: $msg,
                    rating: $rating, created_at: $ts
                })
                CREATE (s)-[:SUBMITTED]->(f)
            """, email=payload["email"], cat=category,
                 msg=message, rating=rating,
                 ts=datetime.utcnow().isoformat())
        return jsonify({"status": "success", "message": "Feedback submitted. Thank you!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
