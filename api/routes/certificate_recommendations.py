"""Certificate recommendation API endpoints."""
from flask import Blueprint, request, jsonify
import jwt
import os
import logging
from services.certificate_recommendation_service import (
    get_recommendations, get_post_completion_recommendations,
    get_by_skill_gap, get_by_career
)
from services.neo4j_service import get_session

logger = logging.getLogger(__name__)

cert_rec_bp = Blueprint('certificate_recommendations', __name__,
                         url_prefix='/api/recommendations/certificates')

JWT_SECRET = os.getenv("JWT_SECRET", "learnexus_ai_secret_key_2026")


def _get_email(req):
    auth = req.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload.get("email")
    except Exception:
        return None


@cert_rec_bp.route('/', methods=['GET'])
def personalized_certs():
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 10, type=int), 50)
    difficulty = request.args.get('difficulty') or None

    try:
        result = get_recommendations(email, page=page, limit=limit, difficulty=difficulty)
        return jsonify({"status": "success", **result})
    except Exception as e:
        logger.error(f"Cert recommendations error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch recommendations"}), 500


@cert_rec_bp.route('/post-completion', methods=['GET'])
def post_completion_certs():
    """Certificates recommended for roles achievable after finishing all course modules."""
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 10, type=int), 50)

    try:
        result = get_post_completion_recommendations(email, page=page, limit=limit)
        return jsonify({"status": "success", **result})
    except Exception as e:
        logger.error(f"Post-completion certs error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch certificates"}), 500


@cert_rec_bp.route('/all', methods=['GET'])
def all_certs():
    """All browsable certificates — no auth required."""
    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 10, type=int), 50)
    difficulty = request.args.get('difficulty') or None
    category = request.args.get('category') or None

    try:
        filters = ["1=1"]
        params = {"skip": (page - 1) * limit, "limit": limit}
        if difficulty:
            filters.append("c.difficulty = $difficulty")
            params["difficulty"] = difficulty
        if category:
            filters.append("toLower(c.category) CONTAINS toLower($category)")
            params["category"] = category

        where = " AND ".join(filters)
        with get_session() as session:
            total_r = session.run(
                f"MATCH (c:Certificate) WHERE {where} RETURN count(c) AS n", **params
            ).single()
            total = total_r["n"] if total_r else 0

            records = session.run(
                f"""
                MATCH (c:Certificate)
                WHERE {where}
                RETURN
                    toString(elementId(c)) AS id,
                    c.title AS title, c.provider AS provider,
                    c.category AS category, c.description AS description,
                    c.skills_taught AS skills_taught, c.difficulty AS difficulty,
                    c.duration AS duration, c.career_relevance AS career_relevance,
                    c.url AS url, c.image_url AS image_url
                ORDER BY c.scraped_at DESC
                SKIP $skip LIMIT $limit
                """,
                **params
            ).data()

        certs = [{
            "id": r["id"], "title": r["title"], "provider": r.get("provider", ""),
            "category": r.get("category", ""), "description": r.get("description", ""),
            "skills_taught": r.get("skills_taught") or [],
            "difficulty": r.get("difficulty", "intermediate"),
            "duration": r.get("duration", ""),
            "career_relevance": r.get("career_relevance", ""),
            "url": r.get("url", ""),
            "image_url": r.get("image_url", "") or "",
        } for r in records]

        return jsonify({"status": "success", "certificates": certs, "total": total,
                        "page": page, "limit": limit,
                        "pages": max(1, -(-total // limit))})
    except Exception as e:
        logger.error(f"All certs error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch certificates"}), 500


@cert_rec_bp.route('/by-skill-gap', methods=['GET'])
def certs_by_skill_gap():
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 10, type=int), 50)

    try:
        result = get_by_skill_gap(email, page=page, limit=limit)
        return jsonify({"status": "success", **result})
    except Exception as e:
        logger.error(f"Certs by skill gap error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch skill gap certs"}), 500


@cert_rec_bp.route('/by-career', methods=['GET'])
def certs_by_career():
    career = request.args.get('career', '')
    if not career:
        return jsonify({"status": "error", "message": "career parameter required"}), 400

    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 10, type=int), 50)

    try:
        result = get_by_career(career, page=page, limit=limit)
        return jsonify({"status": "success", **result})
    except Exception as e:
        logger.error(f"Certs by career error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch certs"}), 500


@cert_rec_bp.route('/detail/<cert_id>', methods=['GET'])
def cert_detail(cert_id: str):
    try:
        with get_session() as session:
            r = session.run(
                """
                MATCH (c:Certificate) WHERE toString(elementId(c)) = $id
                RETURN
                    toString(elementId(c)) AS id,
                    c.title AS title, c.provider AS provider,
                    c.category AS category, c.description AS description,
                    c.skills_taught AS skills_taught, c.difficulty AS difficulty,
                    c.duration AS duration, c.career_relevance AS career_relevance,
                    c.url AS url
                """,
                id=cert_id
            ).single()
        if not r:
            return jsonify({"status": "error", "message": "Certificate not found"}), 404

        cert = {
            "id": r["id"], "title": r["title"], "provider": r.get("provider", ""),
            "category": r.get("category", ""), "description": r.get("description", ""),
            "skills_taught": r.get("skills_taught") or [],
            "difficulty": r.get("difficulty", "intermediate"),
            "duration": r.get("duration", ""),
            "career_relevance": r.get("career_relevance", ""),
            "url": r.get("url", ""),
        }
        return jsonify({"status": "success", "certificate": cert})
    except Exception as e:
        logger.error(f"Cert detail error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch certificate"}), 500


@cert_rec_bp.route('/feedback', methods=['POST'])
def cert_feedback():
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    data = request.get_json() or {}
    cert_id = data.get('cert_id', '')
    relevant = data.get('relevant', True)

    if not cert_id:
        return jsonify({"status": "error", "message": "cert_id required"}), 400

    try:
        with get_session() as session:
            session.run(
                """
                MATCH (st:Student {email: $email}), (c:Certificate)
                WHERE toString(elementId(c)) = $cert_id
                MERGE (st)-[r:RATED_CERT]->(c)
                SET r.relevant = $relevant, r.rated_at = datetime()
                """,
                email=email, cert_id=cert_id, relevant=relevant
            )
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Cert feedback error: {e}")
        return jsonify({"status": "error", "message": "Failed to save feedback"}), 500
