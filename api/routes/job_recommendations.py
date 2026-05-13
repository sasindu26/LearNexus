"""Job recommendation API endpoints."""
from flask import Blueprint, request, jsonify
import jwt
import os
import logging
from services.job_recommendation_service import get_recommendations, get_trending
from services.job_role_service import get_current_eligible_roles, get_post_completion_roles
from services.neo4j_service import get_session

logger = logging.getLogger(__name__)

job_rec_bp = Blueprint('job_recommendations', __name__, url_prefix='/api/recommendations/jobs')

JWT_SECRET = os.getenv("JWT_SECRET", "learnexus_mento_secret_key_2026")


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


@job_rec_bp.route('/', methods=['GET'])
def personalized_jobs():
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 10, type=int), 50)
    seniority = request.args.get('seniority') or request.args.get('experience') or None
    job_type = request.args.get('type') or None

    try:
        result = get_recommendations(email, page=page, limit=limit,
                                     seniority=seniority, job_type=job_type)
        return jsonify({"status": "success", **result})
    except Exception as e:
        logger.error(f"Job recommendations error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch recommendations"}), 500


@job_rec_bp.route('/trending', methods=['GET'])
def trending_jobs():
    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 10, type=int), 50)
    seniority = request.args.get('seniority') or request.args.get('experience') or None
    job_type = request.args.get('type') or None

    try:
        result = get_trending(page=page, limit=limit, seniority=seniority, job_type=job_type)
        return jsonify({"status": "success", **result})
    except Exception as e:
        logger.error(f"Trending jobs error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch trending jobs"}), 500


@job_rec_bp.route('/eligible-roles', methods=['GET'])
def eligible_roles():
    """Job ROLES the student can apply for right now (Gemini inference, not scraped postings)."""
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401
    try:
        roles = get_current_eligible_roles(email)
        return jsonify({"status": "success", "roles": roles, "count": len(roles)})
    except Exception as e:
        logger.error(f"Eligible roles error: {e}")
        return jsonify({"status": "error", "message": "Failed to infer eligible roles"}), 500


@job_rec_bp.route('/future-roles', methods=['GET'])
def future_roles():
    """Job ROLES achievable after completing ALL course modules."""
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401
    try:
        roles = get_post_completion_roles(email)
        return jsonify({"status": "success", "roles": roles, "count": len(roles)})
    except Exception as e:
        logger.error(f"Future roles error: {e}")
        return jsonify({"status": "error", "message": "Failed to infer future roles"}), 500


@job_rec_bp.route('/by-skills', methods=['GET'])
def jobs_by_skills():
    skills_param = request.args.get('skills', '')
    skills = [s.strip().lower() for s in skills_param.split(',') if s.strip()]
    if not skills:
        return jsonify({"status": "error", "message": "skills parameter required"}), 400

    page = request.args.get('page', 1, type=int)
    limit = min(request.args.get('limit', 10, type=int), 50)

    try:
        with get_session() as session:
            total_r = session.run(
                "MATCH (sk:Skill)-[:MATCHES]->(j:Job) WHERE sk.name IN $skills AND j.is_active = true RETURN count(DISTINCT j) AS n",
                skills=skills
            ).single()
            total = total_r["n"] if total_r else 0

            records = session.run(
                """
                MATCH (sk:Skill)-[:MATCHES]->(j:Job)
                WHERE sk.name IN $skills AND j.is_active = true
                WITH j, collect(DISTINCT sk.name) AS matched
                RETURN
                    toString(elementId(j)) AS id,
                    j.title AS title, j.company AS company,
                    j.skills_required AS skills_required,
                    j.experience_level AS experience_level,
                    j.location AS location, j.salary AS salary,
                    j.tags AS tags, j.job_type AS job_type,
                    j.description AS description,
                    j.source_url AS source_url, j.source AS source,
                    j.image_url AS image_url, matched
                ORDER BY size(matched) DESC
                SKIP $skip LIMIT $limit
                """,
                skills=skills, skip=(page - 1) * limit, limit=limit
            ).data()

        jobs = [{
            "id": r["id"], "title": r["title"], "company": r["company"],
            "image_url": r.get("image_url", "") or "",
            "skills_required": r.get("skills_required") or [],
            "experience_level": r.get("experience_level", "mid"),
            "location": r.get("location", "Remote"),
            "salary": r.get("salary", ""),
            "tags": r.get("tags") or [],
            "job_type": r.get("job_type", "remote"),
            "description": r.get("description", ""),
            "source_url": r.get("source_url", ""),
            "source": r.get("source", ""),
            "matching_skills": r.get("matched") or [],
            "missing_skills": [],
            "match_score": round(len(r.get("matched") or []) / max(len(skills), 1) * 100),
        } for r in records]

        return jsonify({"status": "success", "jobs": jobs, "total": total,
                        "page": page, "limit": limit,
                        "pages": max(1, -(-total // limit))})
    except Exception as e:
        logger.error(f"Jobs by skills error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch jobs"}), 500


@job_rec_bp.route('/detail/<job_id>', methods=['GET'])
def job_detail(job_id: str):
    email = _get_email(request)
    try:
        with get_session() as session:
            r = session.run(
                """
                MATCH (j:Job) WHERE toString(elementId(j)) = $id
                RETURN
                    toString(elementId(j)) AS id,
                    j.title AS title, j.company AS company,
                    j.skills_required AS skills_required,
                    j.experience_level AS experience_level,
                    j.location AS location, j.salary AS salary,
                    j.tags AS tags, j.job_type AS job_type,
                    j.description AS description,
                    j.source_url AS source_url, j.source AS source,
                    j.image_url AS image_url
                """,
                id=job_id
            ).single()
        if not r:
            return jsonify({"status": "error", "message": "Job not found"}), 404

        job = {
            "id": r["id"], "title": r["title"], "company": r["company"],
            "image_url": r.get("image_url", "") or "",
            "skills_required": r.get("skills_required") or [],
            "experience_level": r.get("experience_level", "mid"),
            "location": r.get("location", "Remote"),
            "salary": r.get("salary", ""),
            "tags": r.get("tags") or [],
            "job_type": r.get("job_type", "remote"),
            "description": r.get("description", ""),
            "source_url": r.get("source_url", ""),
            "source": r.get("source", ""),
        }

        if email:
            from services.skill_graph_service import get_skill_overlap
            overlap = get_skill_overlap(email, job_id)
            job.update(overlap)

        return jsonify({"status": "success", "job": job})
    except Exception as e:
        logger.error(f"Job detail error: {e}")
        return jsonify({"status": "error", "message": "Failed to fetch job"}), 500


@job_rec_bp.route('/feedback', methods=['POST'])
def job_feedback():
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    data = request.get_json() or {}
    job_id = data.get('job_id', '')
    relevant = data.get('relevant', True)

    if not job_id:
        return jsonify({"status": "error", "message": "job_id required"}), 400

    try:
        with get_session() as session:
            session.run(
                """
                MATCH (st:Student {email: $email}), (j:Job)
                WHERE toString(elementId(j)) = $job_id
                MERGE (st)-[r:RATED_JOB]->(j)
                SET r.relevant = $relevant, r.rated_at = datetime()
                """,
                email=email, job_id=job_id, relevant=relevant
            )
        return jsonify({"status": "success"})
    except Exception as e:
        logger.error(f"Job feedback error: {e}")
        return jsonify({"status": "error", "message": "Failed to save feedback"}), 500
