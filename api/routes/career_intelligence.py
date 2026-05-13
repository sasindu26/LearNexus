"""Career intelligence dashboard API endpoints."""
from flask import Blueprint, request, jsonify
import jwt
import os
import logging
from services.skill_graph_service import infer_user_skills, get_skill_gaps, get_skill_overlap
from services.job_recommendation_service import get_recommendations as get_jobs
from services.certificate_recommendation_service import get_recommendations as get_certs
from services.job_role_service import get_current_eligible_roles, get_post_completion_roles
from services.neo4j_service import get_session
import services.cache_service as cache

logger = logging.getLogger(__name__)

career_bp = Blueprint('career_intelligence', __name__, url_prefix='/api/career')

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


@career_bp.route('/dashboard', methods=['GET'])
def career_dashboard():
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    cache_key = f"career_dashboard:{email}"
    cached = cache.get(cache_key)
    if cached:
        return jsonify({"status": "success", **cached})

    try:
        skills = infer_user_skills(email)
        gaps = get_skill_gaps(email)
        top_jobs = get_jobs(email, page=1, limit=5)
        top_certs = get_certs(email, page=1, limit=5)
        eligible_roles = get_current_eligible_roles(email)
        future_roles = get_post_completion_roles(email)

        # Deduplicate: remove from future any role titles already in eligible
        eligible_titles = {r["title"].lower() for r in eligible_roles}
        future_roles = [r for r in future_roles if r["title"].lower() not in eligible_titles]

        result = {
            "skill_count": len(skills),
            "current_skills": skills[:20],
            "skill_gap": {
                "gap_count": len(gaps.get("gap_skills", [])),
                "coverage_pct": gaps.get("coverage_pct", 0),
                "gap_skills": gaps.get("gap_skills", [])[:10],
            },
            "top_jobs": top_jobs.get("jobs", []),
            "top_certificates": top_certs.get("certificates", []),
            "total_jobs_available": top_jobs.get("total", 0),
            "total_certs_available": top_certs.get("total", 0),
            "eligible_roles": eligible_roles[:6],
            "future_roles": future_roles[:6],
        }
        cache.set(cache_key, result, ttl=600)
        return jsonify({"status": "success", **result})
    except Exception as e:
        logger.error(f"Career dashboard error: {e}")
        return jsonify({"status": "error", "message": "Failed to load dashboard"}), 500


@career_bp.route('/skill-profile', methods=['GET'])
def skill_profile():
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    try:
        skills = infer_user_skills(email)

        # Get skill categories from Neo4j
        skill_by_category: dict = {}
        if skills:
            with get_session() as session:
                records = session.run(
                    "MATCH (sk:Skill) WHERE sk.name IN $skills RETURN sk.name AS name, sk.category AS cat",
                    skills=skills
                ).data()
                for r in records:
                    cat = r.get("cat") or "general"
                    skill_by_category.setdefault(cat, []).append(r["name"])

        return jsonify({
            "status": "success",
            "skills": skills,
            "skill_count": len(skills),
            "by_category": skill_by_category,
        })
    except Exception as e:
        logger.error(f"Skill profile error: {e}")
        return jsonify({"status": "error", "message": "Failed to load skill profile"}), 500


@career_bp.route('/skill-gaps', methods=['GET'])
def skill_gaps():
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    career_path = request.args.get('career') or None

    try:
        gaps = get_skill_gaps(email, career_path)
        return jsonify({"status": "success", **gaps})
    except Exception as e:
        logger.error(f"Skill gaps error: {e}")
        return jsonify({"status": "error", "message": "Failed to load skill gaps"}), 500


@career_bp.route('/career-paths', methods=['GET'])
def career_paths():
    try:
        with get_session() as session:
            paths = session.run(
                """
                MATCH (c:CareerPath)
                OPTIONAL MATCH (c)-[:REQUIRES]->(sk:Skill)
                RETURN
                    toString(elementId(c)) AS id,
                    c.name AS name,
                    c.description AS description,
                    collect(sk.name) AS required_skills
                LIMIT 20
                """
            ).data()

        if not paths:
            # Return sensible defaults based on common tech career paths
            paths = _default_career_paths()

        return jsonify({"status": "success", "career_paths": paths})
    except Exception as e:
        logger.error(f"Career paths error: {e}")
        return jsonify({"status": "error", "message": "Failed to load career paths"}), 500


@career_bp.route('/career-paths/<path_id>', methods=['GET'])
def career_path_detail(path_id: str):
    try:
        with get_session() as session:
            r = session.run(
                """
                MATCH (cp:CareerPath) WHERE toString(elementId(cp)) = $id
                OPTIONAL MATCH (cp)-[:REQUIRES]->(sk:Skill)
                RETURN
                    toString(elementId(cp)) AS id,
                    cp.name AS name,
                    cp.description AS description,
                    cp.entry_level AS entry_level,
                    cp.mid_level AS mid_level,
                    cp.senior_level AS senior_level,
                    collect(sk.name) AS required_skills
                """,
                id=path_id
            ).single()

        if not r:
            return jsonify({"status": "error", "message": "Career path not found"}), 404

        return jsonify({"status": "success", "career_path": dict(r)})
    except Exception as e:
        logger.error(f"Career path detail error: {e}")
        return jsonify({"status": "error", "message": "Failed to load career path"}), 500


@career_bp.route('/explanation/<item_type>/<item_id>', methods=['GET'])
def recommendation_explanation(item_type: str, item_id: str):
    email = _get_email(request)
    if not email:
        return jsonify({"status": "error", "message": "Authentication required"}), 401

    if item_type not in ("job", "certificate"):
        return jsonify({"status": "error", "message": "item_type must be 'job' or 'certificate'"}), 400

    try:
        if item_type == "job":
            overlap = get_skill_overlap(email, item_id)
            with get_session() as session:
                r = session.run(
                    "MATCH (j:Job) WHERE toString(elementId(j)) = $id RETURN j.title AS title, j.company AS company",
                    id=item_id
                ).single()
            title = r["title"] if r else "This job"
            company = r["company"] if r else ""
            matching = overlap.get("matching", [])
            missing = overlap.get("missing", [])
            match_pct = overlap.get("match_pct", 0)
            explanation = (
                f"'{title}' at {company} matches {match_pct}% of required skills. "
                f"You already know: {', '.join(matching[:5]) or 'none yet'}. "
                f"Skills to develop: {', '.join(missing[:5]) or 'none'}."
            )
        else:
            user_skills = set(infer_user_skills(email))
            with get_session() as session:
                r = session.run(
                    "MATCH (c:Certificate) WHERE toString(elementId(c)) = $id RETURN c.title AS title, c.skills_taught AS skills",
                    id=item_id
                ).single()
            title = r["title"] if r else "This certificate"
            cert_skills = set(r["skills"] or []) if r else set()
            you_know = cert_skills & user_skills
            to_learn = cert_skills - user_skills
            explanation = (
                f"'{title}' will teach you {len(to_learn)} new skills. "
                f"Skills you'll learn: {', '.join(list(to_learn)[:5]) or 'various skills'}. "
                f"Skills you already have: {', '.join(list(you_know)[:3]) or 'none'}."
            )

        return jsonify({"status": "success", "explanation": explanation})
    except Exception as e:
        logger.error(f"Explanation error: {e}")
        return jsonify({"status": "error", "message": "Failed to generate explanation"}), 500


def _default_career_paths() -> list:
    return [
        {"id": "cp1", "name": "Data Scientist", "description": "Analyze data and build ML models",
         "required_skills": ["python", "machine learning", "sql", "statistics", "pandas", "numpy"]},
        {"id": "cp2", "name": "Full-Stack Developer", "description": "Build web apps front to back",
         "required_skills": ["javascript", "react", "node.js", "sql", "html", "css", "git"]},
        {"id": "cp3", "name": "Cloud Engineer", "description": "Design and manage cloud infrastructure",
         "required_skills": ["aws", "docker", "kubernetes", "linux", "networking", "python"]},
        {"id": "cp4", "name": "ML Engineer", "description": "Deploy and scale machine learning systems",
         "required_skills": ["python", "tensorflow", "pytorch", "docker", "mlops", "sql"]},
        {"id": "cp5", "name": "DevOps Engineer", "description": "Bridge development and operations",
         "required_skills": ["linux", "docker", "kubernetes", "ci/cd", "python", "git"]},
        {"id": "cp6", "name": "Cybersecurity Analyst", "description": "Protect systems and data",
         "required_skills": ["networking", "linux", "cybersecurity", "python", "cryptography"]},
    ]
