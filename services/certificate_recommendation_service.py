"""
Certificate recommendation engine.
- get_recommendations: certs for current skill gaps (completed modules only)
- get_post_completion_recommendations: certs for roles achievable after full course completion
- get_by_skill_gap, get_by_career: supplementary queries
"""
import logging
from services.neo4j_service import get_session
from services.skill_graph_service import infer_user_skills
from services.embedding_service import embed_text, cosine_similarity
import services.cache_service as cache

logger = logging.getLogger(__name__)

_CACHE_TTL = 900
_DIFF_ORDER = {"beginner": 0, "intermediate": 1, "advanced": 2}


def _format_cert(r: dict, user_skills: set = None) -> dict:
    cert_skills = set(r.get("skills_taught") or [])
    skills_you_know = sorted(cert_skills & user_skills) if user_skills else []
    skills_to_learn = sorted(cert_skills - user_skills) if user_skills else sorted(cert_skills)
    return {
        "id": r.get("id", ""),
        "title": r.get("title", ""),
        "provider": r.get("provider", ""),
        "category": r.get("category", ""),
        "description": r.get("description", ""),     # full description
        "skills_taught": sorted(cert_skills),
        "skills_you_know": skills_you_know,
        "skills_to_learn": skills_to_learn,
        "difficulty": r.get("difficulty", "intermediate"),
        "duration": r.get("duration", ""),
        "career_relevance": r.get("career_relevance", ""),
        "url": r.get("url", ""),
        "image_url": r.get("image_url", "") or "",
        "relevance_score": r.get("relevance_score", 0),
    }


def _infer_user_level(skills: set) -> int:
    n = len(skills)
    if n < 5:
        return 0
    if n < 15:
        return 1
    return 2


def _score_and_filter(records: list, user_skills: set, user_vec: list,
                       difficulty: str = None) -> list:
    scored = []
    for r in records:
        cert_skills = set(r.get("skills_taught") or [])
        diff = r.get("difficulty", "intermediate")

        if difficulty and diff != difficulty:
            continue

        gap_coverage = len(cert_skills - user_skills) / max(len(cert_skills), 1)
        overlap = len(cert_skills & user_skills) / max(len(cert_skills), 1)

        cert_vec = r.get("embedding") or []
        sem_sim = cosine_similarity(user_vec, cert_vec) if (user_vec and cert_vec) else 0.0

        diff_score = 1.0
        if user_skills:
            user_level = _infer_user_level(user_skills)
            cert_level = _DIFF_ORDER.get(diff, 1)
            diff_score = max(0.0, 1.0 - abs(cert_level - (user_level + 1)) * 0.3)

        career_rel = 1.0 if r.get("career_relevance") else 0.5
        score = (0.35 * gap_coverage + 0.25 * sem_sim +
                 0.2 * diff_score + 0.1 * overlap + 0.1 * career_rel)

        item = _format_cert(r, user_skills)
        item["relevance_score"] = round(score * 100)
        scored.append(item)
    return scored


def get_recommendations(email: str, page: int = 1, limit: int = 10,
                         difficulty: str = None) -> dict:
    """Certs that address current skill gaps from completed modules."""
    cache_key = f"cert_rec:{email}:{page}:{limit}:{difficulty}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    user_skills = set(infer_user_skills(email))
    user_vec = embed_text(" ".join(user_skills)) if user_skills else []

    with get_session() as session:
        records = session.run(
            """
            MATCH (c:Certificate)
            RETURN
                toString(elementId(c)) AS id,
                c.title AS title, c.provider AS provider,
                c.category AS category, c.description AS description,
                c.skills_taught AS skills_taught, c.difficulty AS difficulty,
                c.duration AS duration, c.career_relevance AS career_relevance,
                c.url AS url, c.image_url AS image_url, c.embedding AS embedding
            ORDER BY c.scraped_at DESC
            LIMIT 500
            """
        ).data()

    if not records:
        return {"certificates": [], "total": 0, "page": page, "limit": limit, "pages": 1}

    scored = _score_and_filter(records, user_skills, user_vec, difficulty)
    scored.sort(key=lambda x: x["relevance_score"], reverse=True)

    total = len(scored)
    offset = (page - 1) * limit
    result = {
        "certificates": scored[offset: offset + limit],
        "total": total, "page": page, "limit": limit,
        "pages": max(1, -(-total // limit)),
    }
    cache.set(cache_key, result, ttl=_CACHE_TTL)
    return result


def get_post_completion_recommendations(email: str, page: int = 1, limit: int = 10) -> dict:
    """
    Certificates relevant to roles achievable after completing ALL course modules.
    Targets the skill gap between current skills and the full course skill set.
    """
    cache_key = f"cert_post:{email}:{page}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    user_skills = set(infer_user_skills(email))

    # Skills from ALL modules in enrolled course (not just completed ones)
    with get_session() as session:
        full_skill_result = session.run(
            """
            MATCH (st:Student {email: $email})-[:ENROLLED_IN]->(c:Course)-[:CONTAINS]->(m:Module)-[:TEACHES]->(sk:Skill)
            RETURN DISTINCT sk.name AS skill
            """,
            email=email
        )
        full_course_skills = {r["skill"] for r in full_skill_result if r["skill"]}

    # Target: skills the student doesn't have yet but the course will teach
    target_skills = full_course_skills - user_skills
    if not target_skills:
        target_skills = full_course_skills  # fallback when everything is completed

    target_vec = embed_text(" ".join(target_skills)) if target_skills else []

    with get_session() as session:
        records = session.run(
            """
            MATCH (c:Certificate)
            RETURN
                toString(elementId(c)) AS id,
                c.title AS title, c.provider AS provider,
                c.category AS category, c.description AS description,
                c.skills_taught AS skills_taught, c.difficulty AS difficulty,
                c.duration AS duration, c.career_relevance AS career_relevance,
                c.url AS url, c.image_url AS image_url, c.embedding AS embedding
            LIMIT 500
            """
        ).data()

    if not records:
        return {"certificates": [], "total": 0, "page": page, "limit": limit, "pages": 1}

    # Score by how well the cert prepares the student for post-completion roles
    scored = []
    for r in records:
        cert_skills = set(r.get("skills_taught") or [])
        # Overlap with target (post-completion) skills
        target_overlap = len(cert_skills & target_skills) / max(len(cert_skills), 1)
        cert_vec = r.get("embedding") or []
        sem_sim = cosine_similarity(target_vec, cert_vec) if (target_vec and cert_vec) else 0.0
        career_rel = 1.0 if r.get("career_relevance") else 0.5
        score = 0.5 * target_overlap + 0.35 * sem_sim + 0.15 * career_rel

        item = _format_cert(r, user_skills)
        item["relevance_score"] = round(score * 100)
        scored.append(item)

    scored.sort(key=lambda x: x["relevance_score"], reverse=True)
    # Exclude certs the student already fully knows
    scored = [c for c in scored if c["skills_to_learn"]]

    total = len(scored)
    offset = (page - 1) * limit
    result = {
        "certificates": scored[offset: offset + limit],
        "total": total, "page": page, "limit": limit,
        "pages": max(1, -(-total // limit)),
    }
    cache.set(cache_key, result, ttl=_CACHE_TTL)
    return result


def get_by_skill_gap(email: str, page: int = 1, limit: int = 10) -> dict:
    """Certs that address explicit skill gaps (Neo4j HAS_SKILL gap query)."""
    user_skills = set(infer_user_skills(email))

    with get_session() as session:
        gap_result = session.run(
            """
            MATCH (st:Student {email: $email})-[:ENROLLED_IN]->(:Course)-[:CONTAINS]->(m:Module)-[:TEACHES]->(sk:Skill)
            WHERE NOT (st)-[:HAS_SKILL]->(sk)
            RETURN DISTINCT sk.name AS skill
            """,
            email=email
        )
        gap_skills = [r["skill"] for r in gap_result if r["skill"]]

    if not gap_skills:
        return get_recommendations(email, page, limit)

    with get_session() as session:
        records = session.run(
            """
            MATCH (sk:Skill)-[:REQUIRED_BY]->(c:Certificate)
            WHERE sk.name IN $gaps
            WITH c, collect(DISTINCT sk.name) AS covered_gaps, count(DISTINCT sk) AS gap_count
            RETURN
                toString(elementId(c)) AS id,
                c.title AS title, c.provider AS provider,
                c.category AS category, c.description AS description,
                c.skills_taught AS skills_taught, c.difficulty AS difficulty,
                c.duration AS duration, c.career_relevance AS career_relevance,
                c.url AS url, c.image_url AS image_url, covered_gaps, gap_count
            ORDER BY gap_count DESC
            SKIP $skip LIMIT $limit
            """,
            gaps=gap_skills, skip=(page - 1) * limit, limit=limit
        ).data()

    certs = []
    for r in records:
        item = _format_cert(r, user_skills)
        item["gap_coverage"] = len(r.get("covered_gaps") or [])
        certs.append(item)

    return {"certificates": certs, "total": len(certs), "page": page, "limit": limit, "pages": 1}


def get_by_career(career_path: str, page: int = 1, limit: int = 10) -> dict:
    cache_key = f"cert_career:{career_path}:{page}:{limit}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    with get_session() as session:
        records = session.run(
            """
            MATCH (c:Certificate)
            WHERE toLower(c.career_relevance) CONTAINS toLower($career)
               OR toLower(c.category) CONTAINS toLower($career)
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
            career=career_path, skip=(page - 1) * limit, limit=limit
        ).data()

    certs = [_format_cert(r) for r in records]
    result = {"certificates": certs, "total": len(certs), "page": page, "limit": limit, "pages": 1}
    cache.set(cache_key, result, ttl=_CACHE_TTL)
    return result
