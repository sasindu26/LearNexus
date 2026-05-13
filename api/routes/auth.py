from flask import Blueprint, request, jsonify
import bcrypt
import jwt
import datetime
import os
import re
import random
import time
import threading
from neo4j import GraphDatabase

# Setup
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Neo4j Configuration (same as chat_bot.py)
NEO4J_URL = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "LearNexus1212"
NEO4J_DB = "neo4j"

JWT_SECRET = os.getenv("JWT_SECRET", "learnexus_mento_secret_key_2026")

driver = GraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_session():
    return driver.session(database=NEO4J_DB)


# In-memory OTP store: {key: {"otp": "123456", "expires": float}}
_otp_store: dict = {}
_OTP_TTL = 600  # 10 minutes


def _validate_password(password: str):
    """Return error string or None if password meets requirements."""
    if len(password) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>/?]', password):
        return "Password must contain at least one special character"
    return None


# ─── SIGNUP ──────────────────────────────────────────────
@auth_bp.route('/signup', methods=['POST'])
def signup():
    """Create a new Student node in Neo4j"""
    data = request.get_json() or {}
    first_name = data.get('first_name', '').strip()
    last_name  = data.get('last_name', '').strip()
    email      = data.get('email', '').strip().lower()
    password   = data.get('password', '')

    if not first_name or not email or not password:
        return jsonify({"status": "error", "message": "First name, email and password are required"}), 400

    pwd_err = _validate_password(password)
    if pwd_err:
        return jsonify({"status": "error", "message": pwd_err}), 400

    name = f"{first_name} {last_name}".strip()

    try:
        with get_session() as session:
            existing = session.run(
                "MATCH (s:Student {email: $email}) RETURN s", email=email
            ).single()
            if existing:
                return jsonify({"status": "error", "message": "Email already registered"}), 409

            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            result = session.run(
                """
                CREATE (s:Student {
                    name: $name, first_name: $first_name, last_name: $last_name,
                    email: $email, password_hash: $password_hash,
                    created_at: datetime(), last_login: datetime(), failed_attempts: 0
                })
                RETURN s.name AS name, s.email AS email, s.first_name AS first_name, id(s) AS id
                """,
                name=name, first_name=first_name, last_name=last_name,
                email=email, password_hash=password_hash
            ).single()

            token = jwt.encode({
                "id": result["id"], "email": result["email"], "name": result["name"],
                "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
            }, JWT_SECRET, algorithm="HS256")

            # Send welcome email in background
            try:
                from api.services.email_service import send_welcome
                threading.Thread(target=send_welcome, args=(email, first_name), daemon=True).start()
            except Exception:
                pass

            return jsonify({
                "status": "success",
                "message": "Account created successfully",
                "token": token,
                "user": {"name": result["name"], "email": result["email"]}
            }), 201

    except Exception as e:
        print(f"[AUTH] Signup error: {e}")
        return jsonify({"status": "error", "message": "Server error during signup"}), 500


# ─── LOGIN ───────────────────────────────────────────────
@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate a student and return JWT"""
    data = request.get_json() or {}
    email    = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({"status": "error", "message": "Email and password are required"}), 400

    try:
        with get_session() as session:
            result = session.run("""
                MATCH (s:Student {email: $email})
                RETURN s.name AS name, s.email AS email, s.password_hash AS password_hash,
                       id(s) AS id,
                       coalesce(s.failed_attempts, 0) AS failed_attempts,
                       s.whatsapp_number AS whatsapp_number
            """, email=email).single()

            if not result:
                return jsonify({"status": "error", "message": "Invalid email or password"}), 401

            if not bcrypt.checkpw(password.encode('utf-8'), result["password_hash"].encode('utf-8')):
                new_attempts = result["failed_attempts"] + 1
                session.run("""
                    MATCH (s:Student {email: $email})
                    SET s.failed_attempts = $attempts, s.last_failed_at = datetime()
                """, email=email, attempts=new_attempts)

                if new_attempts >= 4:
                    try:
                        from api.services.email_service import send_security_alert
                        from api.services.whatsapp_service import send_whatsapp
                        name = result["name"]
                        wa   = result.get("whatsapp_number")

                        def _alert(n, e, w):
                            send_security_alert(e, n)
                            if w:
                                send_whatsapp(w,
                                    f"⚠️ *LearNexus Security Alert*\n\n"
                                    f"Hi {n.split()[0]}, we detected multiple failed login attempts "
                                    f"on your account.\n\nIf this wasn't you, please reset your password immediately."
                                )
                        threading.Thread(target=_alert, args=(name, email, wa), daemon=True).start()
                    except Exception as ex:
                        print(f"[AUTH] Alert error: {ex}")

                return jsonify({"status": "error", "message": "Invalid email or password"}), 401

            # Successful login
            session.run("""
                MATCH (s:Student {email: $email})
                SET s.failed_attempts = 0, s.last_login = datetime()
            """, email=email)

            token = jwt.encode({
                "id": result["id"], "email": result["email"], "name": result["name"],
                "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
            }, JWT_SECRET, algorithm="HS256")

            return jsonify({
                "status": "success",
                "token": token,
                "user": {"name": result["name"], "email": result["email"]}
            }), 200

    except Exception as e:
        print(f"[AUTH] Login error: {e}")
        return jsonify({"status": "error", "message": "Server error during login"}), 500


# ─── GOOGLE AUTH ─────────────────────────────────────────
@auth_bp.route('/google', methods=['POST'])
def google_auth():
    """Sign in or create account via Google OAuth"""
    import urllib.request as urlreq
    import json as jsonlib

    data = request.get_json() or {}
    credential = data.get('credential', '').strip()

    if not credential:
        return jsonify({"status": "error", "message": "Google credential is required"}), 400

    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}"
        with urlreq.urlopen(url, timeout=10) as resp:
            info = jsonlib.loads(resp.read().decode())
    except Exception as e:
        print(f"[AUTH] Google token verification failed: {e}")
        return jsonify({"status": "error", "message": "Invalid Google token"}), 401

    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if client_id and info.get('aud') != client_id:
        return jsonify({"status": "error", "message": "Token audience mismatch"}), 401

    email = (info.get('email') or '').strip().lower()
    if not email:
        return jsonify({"status": "error", "message": "No email in Google account"}), 400

    first_name = info.get('given_name', '') or ''
    last_name  = info.get('family_name', '') or ''
    name       = info.get('name', '') or f"{first_name} {last_name}".strip() or email.split('@')[0]
    picture    = info.get('picture', '') or ''

    try:
        with get_session() as session:
            existing = session.run("""
                MATCH (s:Student {email: $email})
                RETURN s.name AS name, s.email AS email, id(s) AS id
            """, email=email).single()

            if existing:
                session.run("""
                    MATCH (s:Student {email: $email})
                    SET s.last_login = datetime(), s.failed_attempts = 0
                """, email=email)

                token = jwt.encode({
                    "id": existing["id"], "email": existing["email"], "name": existing["name"],
                    "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
                }, JWT_SECRET, algorithm="HS256")

                return jsonify({
                    "status": "success",
                    "token": token,
                    "user": {"name": existing["name"], "email": existing["email"]},
                    "is_new_user": False
                }), 200

            result = session.run("""
                CREATE (s:Student {
                    name: $name, first_name: $first_name, last_name: $last_name,
                    email: $email, auth_method: 'google', picture: $picture,
                    created_at: datetime(), last_login: datetime(), failed_attempts: 0
                })
                RETURN s.name AS name, s.email AS email, id(s) AS id
            """, name=name, first_name=first_name, last_name=last_name,
                email=email, picture=picture).single()

            token = jwt.encode({
                "id": result["id"], "email": result["email"], "name": result["name"],
                "exp": datetime.datetime.utcnow() + datetime.timedelta(days=30)
            }, JWT_SECRET, algorithm="HS256")

            try:
                from api.services.email_service import send_welcome
                threading.Thread(
                    target=send_welcome,
                    args=(email, first_name or name.split()[0]),
                    daemon=True
                ).start()
            except Exception:
                pass

            return jsonify({
                "status": "success",
                "token": token,
                "user": {"name": result["name"], "email": result["email"]},
                "is_new_user": True
            }), 201

    except Exception as e:
        print(f"[AUTH] Google auth error: {e}")
        return jsonify({"status": "error", "message": "Server error during Google auth"}), 500


# ─── GET PROFILE ─────────────────────────────────────────
@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get user profile with enrolled courses"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not token:
        return jsonify({"status": "error", "message": "No token provided"}), 401

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return jsonify({"status": "error", "message": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    try:
        with get_session() as session:
            result = session.run(
                """
                MATCH (s:Student {email: $email})
                OPTIONAL MATCH (s)-[:ENROLLED_IN]->(c:Course)
                OPTIONAL MATCH (c)-[:CONTAINS]->(m:Module)
                WITH s, c, count(DISTINCT m) AS total_modules
                RETURN s.name AS name, s.email AS email,
                       s.first_name AS first_name, s.last_name AS last_name,
                       s.whatsapp_number AS whatsapp_number,
                       s.parent_number AS parent_number,
                       s.picture AS picture,
                       collect(DISTINCT {
                           name: c.name,
                           description: c.description,
                           total_modules: total_modules
                       }) AS enrolled_courses
                """,
                email=payload["email"]
            ).single()

            if not result:
                return jsonify({"status": "error", "message": "User not found"}), 404

            courses = [c for c in result["enrolled_courses"] if c["name"] is not None]

            return jsonify({
                "status": "success",
                "user": {
                    "name":             result["name"],
                    "email":            result["email"],
                    "first_name":       result["first_name"] or "",
                    "last_name":        result["last_name"] or "",
                    "whatsapp_number":  result["whatsapp_number"] or "",
                    "parent_number":    result["parent_number"] or "",
                    "picture":          result["picture"] or "",
                    "enrolled_courses": courses
                }
            }), 200

    except Exception as e:
        print(f"[AUTH] Profile error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


# ─── ENROLL IN COURSE ────────────────────────────────────
@auth_bp.route('/enroll', methods=['POST'])
def enroll():
    """Enroll a student into a course"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not token:
        return jsonify({"status": "error", "message": "No token provided"}), 401

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    data = request.get_json()
    course_name = data.get('course_name', '').strip()

    if not course_name:
        return jsonify({"status": "error", "message": "Course name is required"}), 400

    try:
        with get_session() as session:
            # Check if course exists
            course = session.run(
                "MATCH (c:Course {name: $name}) RETURN c.name AS name",
                name=course_name
            ).single()

            if not course:
                return jsonify({"status": "error", "message": f"Course '{course_name}' not found"}), 404

            # Create enrollment — MERGE on the relationship only, set enrolled_at on CREATE
            session.run(
                """
                MATCH (s:Student {email: $email}), (c:Course {name: $course_name})
                MERGE (s)-[r:ENROLLED_IN]->(c)
                ON CREATE SET r.enrolled_at = datetime()
                """,
                email=payload["email"], course_name=course_name
            )

            return jsonify({
                "status": "success",
                "message": f"Successfully enrolled in {course_name}"
            }), 200

    except Exception as e:
        print(f"[AUTH] Enroll error: {e}")
        return jsonify({"status": "error", "message": "Server error during enrollment"}), 500


# ─── LIST ALL COURSES ────────────────────────────────────
@auth_bp.route('/courses', methods=['GET'])
def list_courses():
    """List all available courses with their module counts"""
    try:
        with get_session() as session:
            result = session.run(
                """
                MATCH (c:Course)
                OPTIONAL MATCH (c)-[:CONTAINS]->(m:Module)
                WITH c, count(m) AS module_count
                RETURN c.name AS name, c.description AS description,
                       c.university AS university, module_count
                ORDER BY c.name
                """
            )

            courses = []
            for record in result:
                courses.append({
                    "name": record["name"],
                    "description": record["description"] or "",
                    "university": record["university"] or "",
                    "module_count": record["module_count"]
                })

            return jsonify(courses), 200

    except Exception as e:
        print(f"[AUTH] List courses error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


# ─── WHATSAPP: SEND OTP ──────────────────────────────────
@auth_bp.route('/whatsapp/send-otp', methods=['POST'])
def whatsapp_send_otp():
    data  = request.get_json() or {}
    phone = data.get('phone', '').strip()
    if not phone:
        return jsonify({"status": "error", "message": "Phone number required"}), 400
    try:
        from api.services.whatsapp_service import send_otp
        ok = send_otp(phone)
        if ok:
            return jsonify({"status": "success", "message": "OTP sent"})
        return jsonify({"status": "error", "message": "Failed to send OTP — check Twilio credentials"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── WHATSAPP: VERIFY OTP ────────────────────────────────
@auth_bp.route('/whatsapp/verify-otp', methods=['POST'])
def whatsapp_verify_otp():
    data  = request.get_json() or {}
    phone = data.get('phone', '').strip()
    otp   = data.get('otp', '').strip()
    if not phone or not otp:
        return jsonify({"status": "error", "message": "Phone and OTP required"}), 400
    try:
        from api.services.whatsapp_service import verify_otp
        if verify_otp(phone, otp):
            return jsonify({"status": "success", "message": "OTP verified"})
        return jsonify({"status": "error", "message": "Invalid or expired OTP"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── WHATSAPP: SAVE NUMBERS ──────────────────────────────
@auth_bp.route('/whatsapp/save', methods=['POST'])
def whatsapp_save():
    """Save verified WhatsApp number (and optional parent number) for the logged-in user."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    data            = request.get_json() or {}
    whatsapp_number = (data.get('whatsapp_number') or '').strip()
    parent_raw      = data.get('parent_number')
    parent_number   = parent_raw.strip() if parent_raw else None

    if not whatsapp_number:
        return jsonify({"status": "error", "message": "WhatsApp number required"}), 400

    try:
        with get_session() as session:
            conflict = session.run("""
                MATCH (s:Student {whatsapp_number: $wa})
                WHERE s.email <> $email
                RETURN s.email AS email
            """, wa=whatsapp_number, email=payload["email"]).single()
            if conflict:
                return jsonify({"status": "error", "message": "This WhatsApp number is already linked to another account"}), 409

            session.run("""
                MATCH (s:Student {email: $email})
                SET s.whatsapp_number = $wa, s.parent_number = $parent
            """, email=payload["email"], wa=whatsapp_number, parent=parent_number)

        # Send welcome WhatsApp message in background
        try:
            from api.services.whatsapp_service import send_whatsapp
            first = (payload.get("name") or "there").split()[0]

            def _welcome_wa(phone, name):
                send_whatsapp(phone,
                    f"🎓 *Welcome to LearNexus, {name}!*\n\n"
                    f"Your account is all set! 🎉\n\n"
                    f"Start your personalised learning journey with *Mento AI* — "
                    f"explore modules, track progress, and achieve your goals.\n\n"
                    f"We're excited to have you on board! 📚\n\n"
                    f"_LearNexus — Learn Smarter_ ✨"
                )
            threading.Thread(target=_welcome_wa, args=(whatsapp_number, first), daemon=True).start()
        except Exception:
            pass

        return jsonify({"status": "success", "message": "WhatsApp numbers saved"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── FORGOT PASSWORD: REQUEST CODE ───────────────────────
@auth_bp.route('/forgot-password/request', methods=['POST'])
def forgot_password_request():
    data   = request.get_json() or {}
    email  = data.get('email', '').strip().lower()
    method = data.get('method', 'email')  # 'email' or 'whatsapp'

    if not email:
        return jsonify({"status": "error", "message": "Email required"}), 400

    try:
        with get_session() as session:
            rec = session.run("""
                MATCH (s:Student {email: $email})
                RETURN s.name AS name, s.whatsapp_number AS whatsapp_number
            """, email=email).single()

        if not rec:
            # Don't reveal whether email exists
            return jsonify({"status": "success", "message": "If that email is registered, a code was sent"})

        code = str(random.randint(100000, 999999))
        _otp_store[f"reset_{email}"] = {"otp": code, "expires": time.time() + _OTP_TTL}
        name = (rec["name"] or "there").split()[0]

        if method == 'whatsapp' and rec.get("whatsapp_number"):
            from api.services.whatsapp_service import send_whatsapp
            threading.Thread(
                target=send_whatsapp,
                args=(rec["whatsapp_number"],
                      f"🔑 *LearNexus Password Reset*\n\n"
                      f"Your verification code is: *{code}*\n\n"
                      f"This code expires in 10 minutes.\n"
                      f"Do not share this with anyone."),
                daemon=True
            ).start()
        else:
            from api.services.email_service import send_reset_code
            threading.Thread(target=send_reset_code, args=(email, name, code), daemon=True).start()

        return jsonify({"status": "success", "message": "Code sent"})

    except Exception as e:
        print(f"[AUTH] Forgot password request error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


# ─── FORGOT PASSWORD: RESET ──────────────────────────────
@auth_bp.route('/forgot-password/reset', methods=['POST'])
def forgot_password_reset():
    data         = request.get_json() or {}
    email        = data.get('email', '').strip().lower()
    code         = data.get('code', '').strip()
    new_password = data.get('new_password', '')

    if not email or not code or not new_password:
        return jsonify({"status": "error", "message": "Email, code and new password are required"}), 400

    pwd_err = _validate_password(new_password)
    if pwd_err:
        return jsonify({"status": "error", "message": pwd_err}), 400

    key   = f"reset_{email}"
    entry = _otp_store.get(key)
    if not entry:
        return jsonify({"status": "error", "message": "Invalid or expired code"}), 400
    if time.time() > entry["expires"]:
        _otp_store.pop(key, None)
        return jsonify({"status": "error", "message": "Code has expired"}), 400
    if entry["otp"] != code:
        return jsonify({"status": "error", "message": "Invalid code"}), 400

    _otp_store.pop(key, None)

    try:
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        with get_session() as session:
            session.run("""
                MATCH (s:Student {email: $email})
                SET s.password_hash = $hash, s.failed_attempts = 0
            """, email=email, hash=password_hash)
        return jsonify({"status": "success", "message": "Password reset successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── TEST: INACTIVITY MESSAGE ────────────────────────────
@auth_bp.route('/test-email', methods=['POST'])
def test_email():
    """Dev-only: send a test welcome email to the logged-in user."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    try:
        from api.services.email_service import send_welcome, FROM_EMAIL
        with get_session() as session:
            rec = session.run(
                "MATCH (s:Student {email: $e}) RETURN s.name AS name, s.email AS email",
                e=payload["email"]
            ).single()

        if not rec:
            return jsonify({"status": "error", "message": "User not found"}), 404

        first_name = (rec["name"] or "there").split()[0]
        ok = send_welcome(rec["email"], first_name)
        return jsonify({
            "status": "success" if ok else "failed",
            "from": FROM_EMAIL,
            "to": rec["email"],
            "sent": ok
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@auth_bp.route('/test-inactivity', methods=['POST'])
def test_inactivity():
    """Dev-only: send an inactivity reminder for a given number of days to the logged-in user."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    data = request.get_json() or {}
    days = int(data.get('days', 3))

    try:
        from api.scheduler import _USER_MSGS, _parent_msg
        from api.services.whatsapp_service import send_whatsapp

        with get_session() as session:
            rec = session.run("""
                MATCH (s:Student {email: $email})
                RETURN s.name AS name, s.whatsapp_number AS phone, s.parent_number AS parent
            """, email=payload["email"]).single()

        if not rec or not rec["phone"]:
            return jsonify({"status": "error", "message": "No WhatsApp number on this account"}), 400

        first_name = (rec["name"] or "there").split()[0]
        sent = []

        if days in _USER_MSGS:
            ok = send_whatsapp(rec["phone"], _USER_MSGS[days](first_name))
            sent.append(f"User message ({days}d) → {'sent' if ok else 'failed'}")

        if days == 7 and rec.get("parent"):
            ok = send_whatsapp(rec["parent"], _parent_msg(rec["name"], days))
            sent.append(f"Parent message → {'sent' if ok else 'failed'}")

        return jsonify({"status": "success", "sent": sent})

    except Exception as e:
        print(f"[TEST] Inactivity error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# Also register at /api/courses for backward compatibility
courses_bp = Blueprint('courses', __name__)

@courses_bp.route('/api/courses', methods=['GET'])
def api_courses():
    """List all courses (backward-compatible route)"""
    try:
        with get_session() as session:
            result = session.run(
                """
                MATCH (c:Course)
                OPTIONAL MATCH (c)-[:CONTAINS]->(m:Module)
                WITH c, count(m) AS module_count
                RETURN c.name AS name, c.description AS description,
                       c.university AS university, module_count
                ORDER BY c.name
                """
            )

            courses = []
            for record in result:
                courses.append({
                    "name": record["name"],
                    "description": record["description"] or "",
                    "university": record["university"] or "",
                    "module_count": record["module_count"]
                })

            return jsonify(courses), 200

    except Exception as e:
        print(f"[COURSES] Error: {e}")
        return jsonify([]), 200


# ─── GET USER PROGRESS ───────────────────────────────────
@auth_bp.route('/progress', methods=['GET'])
def get_progress():
    """Get user's enrolled course progress (completed topics / total topics)"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not token:
        return jsonify({"status": "error", "message": "No token provided"}), 401

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    try:
        with get_session() as session:
            result = session.run(
                """
                MATCH (s:Student {email: $email})-[:ENROLLED_IN]->(c:Course)
                OPTIONAL MATCH (c)-[:CONTAINS]->(m:Module)-[:HAS_TOPIC]->(t:Topic)
                WITH s, c, count(DISTINCT m) AS total_modules, count(DISTINCT t) AS total_topics
                OPTIONAL MATCH (c)-[:CONTAINS]->(:Module)-[:HAS_TOPIC]->(ct:Topic)<-[:COMPLETED]-(s)
                WITH c, total_modules, total_topics, count(DISTINCT ct) AS completed_topics
                RETURN c.name AS course_name, c.description AS description,
                       total_modules, total_topics, completed_topics,
                       CASE WHEN total_topics > 0
                            THEN round(toFloat(completed_topics) / total_topics * 100)
                            ELSE 0 END AS progress_pct
                """,
                email=payload["email"]
            )

            courses = []
            for record in result:
                courses.append({
                    "course_name": record["course_name"],
                    "description": record["description"] or "",
                    "total_modules": record["total_modules"],
                    "total_topics": record["total_topics"],
                    "completed_topics": record["completed_topics"],
                    "progress_pct": record["progress_pct"]
                })

            return jsonify({
                "status": "success",
                "courses": courses
            }), 200

    except Exception as e:
        print(f"[AUTH] Progress error: {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500


# ─── GET MODULES FOR A COURSE ────────────────────────────
@courses_bp.route('/api/modules', methods=['GET'])
def get_modules():
    """Get all modules for a course with per-student completion progress when authenticated"""
    course_name = request.args.get('course', '').strip()

    if not course_name:
        return jsonify({"status": "error", "message": "Course name is required"}), 400

    # Decode JWT to get student email for per-module progress
    student_email = None
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            student_email = payload.get("email")
        except Exception:
            pass

    try:
        with get_session() as session:
            if student_email:
                result = session.run(
                    """
                    MATCH (c:Course {name: $course_name})-[:CONTAINS]->(m:Module)
                    OPTIONAL MATCH (m)-[:HAS_TOPIC]->(t:Topic)
                    WITH m, count(t) AS topic_count
                    OPTIONAL MATCH (m)-[:HAS_TOPIC]->(ct:Topic)<-[:COMPLETED]-(s:Student {email: $email})
                    WITH m, topic_count, count(ct) AS completed_count
                    RETURN m.name AS name, m.description AS description,
                           m.level AS level, topic_count, completed_count,
                           CASE WHEN topic_count > 0
                                THEN toInteger(round(toFloat(completed_count) / topic_count * 100))
                                ELSE 0 END AS progress_pct,
                           CASE WHEN topic_count > 0 AND completed_count = topic_count
                                THEN true ELSE false END AS is_completed
                    ORDER BY m.level, m.name
                    """,
                    course_name=course_name, email=student_email
                )
            else:
                result = session.run(
                    """
                    MATCH (c:Course {name: $course_name})-[:CONTAINS]->(m:Module)
                    OPTIONAL MATCH (m)-[:HAS_TOPIC]->(t:Topic)
                    WITH m, count(t) AS topic_count
                    RETURN m.name AS name, m.description AS description,
                           m.level AS level, topic_count,
                           0 AS completed_count, 0 AS progress_pct, false AS is_completed
                    ORDER BY m.level, m.name
                    """,
                    course_name=course_name
                )

            modules = []
            for record in result:
                modules.append({
                    "name": record["name"],
                    "description": record["description"] or "",
                    "level": record["level"] if record["level"] else 1,
                    "topicCount": record["topic_count"],
                    "progress": record["progress_pct"],
                    "isCompleted": record["is_completed"]
                })

            return jsonify(modules), 200

    except Exception as e:
        print(f"[MODULES] Error: {e}")
        return jsonify([]), 200


# ─── LEARNING PATTERNS ───────────────────────────────────
@auth_bp.route('/learning-patterns', methods=['GET'])
def get_learning_patterns():
    """Calculate real learning patterns from topic completion timestamps."""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({"status": "error", "message": "No token"}), 401
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return jsonify({"status": "error", "message": "Invalid token"}), 401

    try:
        from collections import Counter, defaultdict

        with get_session() as session:
            result = session.run(
                """
                MATCH (s:Student {email: $email})-[r:COMPLETED]->(t:Topic)
                WHERE r.completed_at IS NOT NULL
                RETURN r.completed_at AS completed_at
                ORDER BY r.completed_at
                """,
                email=payload["email"]
            )
            raw = [record["completed_at"] for record in result]

        if not raw:
            return jsonify({"has_data": False}), 200

        datetimes = []
        for ts in raw:
            if hasattr(ts, 'to_native'):
                datetimes.append(ts.to_native().replace(tzinfo=None))
            elif isinstance(ts, str):
                datetimes.append(datetime.datetime.fromisoformat(ts))

        if not datetimes:
            return jsonify({"has_data": False}), 200

        # Peak Study Time
        def fmt_hour(h):
            suffix = 'AM' if h < 12 else 'PM'
            return f"{h % 12 or 12} {suffix}"

        hour_counts = Counter(d.hour for d in datetimes)
        peak_hour = hour_counts.most_common(1)[0][0]
        peak_time = f"{fmt_hour(peak_hour)} – {fmt_hour((peak_hour + 2) % 24)}"

        # Most Active Days
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_counts = Counter(day_names[d.weekday()] for d in datetimes)
        top_days = [d for d, _ in day_counts.most_common(2)]
        active_days = ", ".join(top_days) if top_days else "Not enough data"

        # Average Session Length (span from first to last completion per day)
        by_date = defaultdict(list)
        for d in datetimes:
            by_date[d.date()].append(d)

        spans = []
        for times in by_date.values():
            if len(times) > 1:
                span = (max(times) - min(times)).total_seconds() / 60
                if span > 0:
                    spans.append(span)

        if spans:
            avg_mins = round(sum(spans) / len(spans))
            if avg_mins < 60:
                avg_session = f"{avg_mins} minutes"
            else:
                hrs, mins = divmod(avg_mins, 60)
                avg_session = f"{hrs}h {mins}m" if mins else f"{hrs} hour{'s' if hrs > 1 else ''}"
        else:
            avg_session = "Not enough data yet"

        return jsonify({
            "has_data": True,
            "total_completions": len(datetimes),
            "peak_study_time": peak_time,
            "most_active_days": active_days,
            "avg_session_length": avg_session,
        }), 200

    except Exception as e:
        print(f"[AUTH] Learning patterns error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ─── TOPIC COMPLETION ────────────────────────────────────
@courses_bp.route('/topics/<topic_id>/completion', methods=['PUT'])
def toggle_topic_completion(topic_id):
    """Toggle topic completion for a student"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    data = request.get_json() or {}
    is_completed = data.get('isCompleted', False)

    # If no token, just accept silently (guest mode)
    if not token:
        return jsonify({"status": "ok"}), 200

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return jsonify({"status": "ok"}), 200

    try:
        topic_name = data.get('topicName')
        module_name = data.get('moduleName', '').strip()
        if not topic_name:
            return jsonify({"status": "error", "message": "topicName is required"}), 400

        with get_session() as session:
            if is_completed:
                if module_name:
                    # Scope to the specific module to avoid false matches on duplicate topic names
                    session.run(
                        """
                        MATCH (s:Student {email: $email})
                        MATCH (m:Module)-[:HAS_TOPIC]->(t:Topic)
                        WHERE toLower(m.name) = toLower($module_name) AND t.name = $topic_name
                        MERGE (s)-[:COMPLETED {completed_at: datetime()}]->(t)
                        """,
                        email=payload["email"], module_name=module_name, topic_name=topic_name
                    )
                else:
                    session.run(
                        """
                        MATCH (s:Student {email: $email})
                        MATCH (t:Topic {name: $topic_name})
                        MERGE (s)-[:COMPLETED {completed_at: datetime()}]->(t)
                        """,
                        email=payload["email"], topic_name=topic_name
                    )
            else:
                if module_name:
                    session.run(
                        """
                        MATCH (s:Student {email: $email})-[r:COMPLETED]->(t:Topic)<-[:HAS_TOPIC]-(m:Module)
                        WHERE toLower(m.name) = toLower($module_name) AND t.name = $topic_name
                        DELETE r
                        """,
                        email=payload["email"], module_name=module_name, topic_name=topic_name
                    )
                else:
                    session.run(
                        """
                        MATCH (s:Student {email: $email})-[r:COMPLETED]->(t:Topic {name: $topic_name})
                        DELETE r
                        """,
                        email=payload["email"], topic_name=topic_name
                    )

        return jsonify({"status": "success"}), 200

    except Exception as e:
        print(f"[TOPICS] Completion error: {e}")
        return jsonify({"status": "ok"}), 200
