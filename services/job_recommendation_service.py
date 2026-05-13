"""
Job recommendation engine.
Matches ONLY completed-module skills to scraped jobs; includes image, full description,
seniority filter (intern/junior/mid/senior).
"""
import logging
from services.neo4j_service import get_session
from services.skill_graph_service import infer_user_skills, get_completed_module_context
from services.embedding_service import embed_text, cosine_similarity
import services.cache_service as cache

logger = logging.getLogger(__name__)

_CACHE_TTL = 900  # 15 minutes


def _format_job(r: dict, user_skills: set = None) -> dict:
    job_skills = set(r.get("skills_required") or [])
    matching = sorted(user_skills & job_skills) if user_skills else []
    missing = sorted(job_skills - user_skills) if user_skills else []
    return {
        "id": r.get("id", ""),
        "title": r.get("title", ""),
        "company": r.get("company", ""),
        "image_url": r.get("image_url", "") or "",
        "skills_required": sorted(job_skills),
        "experience_level": r.get("experience_level", "mid"),
        "location": r.get("location", "Remote"),
        "salary": r.get("salary", ""),
        "tags": r.get("tags") or [],
        "job_type": r.get("job_type", "remote"),
        "description": r.get("description", ""),      # full description
        "source_url": r.get("source_url", ""),
        "source": r.get("source", ""),
        "matching_skills": matching,
        "missing_skills": missing[:10],
        "match_score": r.get("match_score", 0),
    }


def get_recommendations(email: str, page: int = 1, limit: int = 10,
                         experience: str = None, job_type: str = None,
                         seniority: str = None) -> dict:
    """
    Personalised recommendations driven strictly by completed-module skills.
    `seniority` accepts: intern | junior | mid | senior (maps to experience_level in Neo4j).
    """
    cache_key = f"job_rec:{email}:{page}:{limit}:{experience}:{job_type}:{seniority}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    # Only skills inferred from COMPLETED modules/topics
    user_skills = set(infer_user_skills(email))
    if not user_skills:
        result = _get_trending_jobs(page, limit, experience, job_type, seniority)
        result["note"] = "Complete some modules to unlock personalised recommendations."
        return result

    # Resolve seniority filter (prefer explicit seniority param, then experience param)
    level_filter = seniority or experience or None

    # Build Cypher WHERE additions so the DB enforces the filter — don't rely on Python post-filter
    level_cond = "AND j.experience_level = $level " if level_filter else ""
    type_cond = "AND j.job_type = $job_type " if job_type else ""
    cypher_params = {"email": email}
    if level_filter:
        cypher_params["level"] = level_filter
    if job_type:
        cypher_params["job_type"] = job_type

    with get_session() as session:
        # Graph traversal: completed topic → skill → job
        records = session.run(
            f"""
            MATCH (st:Student {{email: $email}})-[:COMPLETED]->(t:Topic)-[:COVERS]->(sk:Skill)-[:MATCHES]->(j:Job)
            WHERE j.is_active = true {level_cond}{type_cond}
            WITH j, collect(DISTINCT sk.name) AS matching_skills, count(DISTINCT sk) AS match_count
            RETURN
                toString(elementId(j)) AS id,
                j.title AS title, j.company AS company,
                j.skills_required AS skills_required,
                j.experience_level AS experience_level,
                j.location AS location, j.salary AS salary,
                j.tags AS tags, j.job_type AS job_type,
                j.description AS description, j.source_url AS source_url,
                j.source AS source, j.image_url AS image_url,
                j.embedding AS embedding,
                matching_skills, match_count
            ORDER BY match_count DESC
            LIMIT 300
            """,
            **cypher_params
        ).data()

        # Also traverse via module-level TEACHES edges for broader coverage
        if len(records) < 20:
            extra = session.run(
                f"""
                MATCH (st:Student {{email: $email}})-[:COMPLETED]->(t:Topic)<-[:HAS_TOPIC]-(m:Module)-[:TEACHES]->(sk:Skill)-[:MATCHES]->(j:Job)
                WHERE j.is_active = true {level_cond}{type_cond}
                WITH j, collect(DISTINCT sk.name) AS matching_skills, count(DISTINCT sk) AS match_count
                RETURN
                    toString(elementId(j)) AS id,
                    j.title AS title, j.company AS company,
                    j.skills_required AS skills_required,
                    j.experience_level AS experience_level,
                    j.location AS location, j.salary AS salary,
                    j.tags AS tags, j.job_type AS job_type,
                    j.description AS description, j.source_url AS source_url,
                    j.source AS source, j.image_url AS image_url,
                    j.embedding AS embedding,
                    matching_skills, match_count
                ORDER BY match_count DESC
                LIMIT 300
                """,
                **cypher_params
            ).data()
            seen = {r["id"] for r in records}
            records += [r for r in extra if r["id"] not in seen]

    if not records:
        return _get_trending_jobs(page, limit, experience, job_type, seniority)

    # Richer semantic vector: skill names + actual completed module/topic descriptions
    # so cosine_similarity checks "did I study content related to this job?" not just skill names
    module_context = get_completed_module_context(email)
    context_text = " ".join(user_skills)
    if module_context:
        context_text = context_text + " " + module_context
    user_vec = embed_text(context_text)
    scored = []

    for r in records:
        job_skills = set(r.get("skills_required") or [])
        skill_match = len(user_skills & job_skills) / max(len(job_skills), 1)
        job_vec = r.get("embedding") or []
        sem_sim = cosine_similarity(user_vec, job_vec) if job_vec else 0.0
        score = 0.5 * skill_match + 0.4 * sem_sim + 0.1

        exp_level = r.get("experience_level") or "mid"
        matching = sorted(user_skills & job_skills)
        missing = sorted(job_skills - user_skills)

        scored.append({
            "id": r["id"],
            "title": r["title"],
            "company": r["company"],
            "image_url": r.get("image_url", "") or "",
            "skills_required": sorted(job_skills),
            "experience_level": exp_level,
            "location": r.get("location", "Remote"),
            "salary": r.get("salary", ""),
            "tags": r.get("tags") or [],
            "job_type": r.get("job_type", "remote"),
            "description": r.get("description", ""),
            "source_url": r.get("source_url", ""),
            "source": r.get("source", ""),
            "matching_skills": matching,
            "missing_skills": missing[:10],
            "match_score": round(score * 100),
        })

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    total = len(scored)
    offset = (page - 1) * limit
    result = {
        "jobs": scored[offset: offset + limit],
        "total": total,
        "page": page,
        "limit": limit,
        "pages": max(1, -(-total // limit)),
    }
    cache.set(cache_key, result, ttl=_CACHE_TTL)
    return result


def get_trending(page: int = 1, limit: int = 10,
                  experience: str = None, job_type: str = None,
                  seniority: str = None) -> dict:
    return _get_trending_jobs(page, limit, experience, job_type, seniority)


def _get_trending_jobs(page: int, limit: int,
                        experience: str = None, job_type: str = None,
                        seniority: str = None) -> dict:
    level_filter = seniority or experience or None
    cache_key = f"job_trending:{page}:{limit}:{level_filter}:{job_type}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    filters = ["j.is_active = true"]
    params: dict = {"skip": (page - 1) * limit, "limit": limit}
    if level_filter:
        filters.append("j.experience_level = $level")
        params["level"] = level_filter
    if job_type:
        filters.append("j.job_type = $job_type")
        params["job_type"] = job_type

    where = " AND ".join(filters)
    with get_session() as session:
        count_r = session.run(
            f"MATCH (j:Job) WHERE {where} RETURN count(j) AS n", **params
        ).single()
        total = count_r["n"] if count_r else 0

        records = session.run(
            f"""
            MATCH (j:Job)
            WHERE {where}
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
            ORDER BY j.scraped_at DESC
            SKIP $skip LIMIT $limit
            """,
            **params
        ).data()

    jobs = [_format_job(r) for r in records]
    result = {
        "jobs": jobs, "total": total, "page": page,
        "limit": limit, "pages": max(1, -(-total // limit)),
    }
    cache.set(cache_key, result, ttl=_CACHE_TTL)
    return result
