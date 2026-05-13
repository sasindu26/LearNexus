"""Skill knowledge graph operations: extract, store, and query skills."""
import logging
from services.neo4j_service import get_session
from services.skill_extractor import extract_skills
from services.embedding_service import embed_text

logger = logging.getLogger(__name__)


def extract_and_store_skills():
    """One-time backfill: extract skills from all Module and Topic nodes."""
    logger.info("Starting skill extraction backfill...")
    with get_session() as session:
        modules = session.run(
            "MATCH (m:Module) WHERE m.description IS NOT NULL RETURN m.name AS name, m.description AS desc"
        ).data()

    for m in modules:
        skills = extract_skills(m.get("desc", ""), context=f"Module: {m['name']}")
        _store_module_skills(m["name"], skills)
        logger.info(f"Module '{m['name']}': {len(skills)} skills found")

    with get_session() as session:
        topics = session.run(
            "MATCH (t:Topic) WHERE t.name IS NOT NULL RETURN t.name AS name, coalesce(t.description, t.name) AS desc"
        ).data()

    for t in topics:
        skills = extract_skills(t.get("desc", ""), context=f"Topic: {t['name']}")
        _store_topic_skills(t["name"], skills)

    logger.info("Skill extraction backfill complete.")


def _store_module_skills(module_name: str, skills: list):
    if not skills:
        return
    with get_session() as session:
        for skill_name in skills:
            embedding = embed_text(skill_name)
            session.run(
                """
                MERGE (sk:Skill {name: $name})
                ON CREATE SET sk.category = 'general', sk.created_at = datetime(), sk.embedding = $emb
                WITH sk
                MATCH (m:Module {name: $module_name})
                MERGE (m)-[:TEACHES]->(sk)
                """,
                name=skill_name, emb=embedding, module_name=module_name
            )


def _store_topic_skills(topic_name: str, skills: list):
    if not skills:
        return
    with get_session() as session:
        for skill_name in skills:
            embedding = embed_text(skill_name)
            session.run(
                """
                MERGE (sk:Skill {name: $name})
                ON CREATE SET sk.category = 'general', sk.created_at = datetime(), sk.embedding = $emb
                WITH sk
                MATCH (t:Topic {name: $topic_name})
                MERGE (t)-[:COVERS]->(sk)
                """,
                name=skill_name, emb=embedding, topic_name=topic_name
            )


def get_completed_module_context(email: str) -> str:
    """
    Returns a single text blob of descriptions from all completed topics
    and their parent modules. Used to enrich the semantic user vector for
    job matching — goes beyond skill names to actual learning content.
    """
    with get_session() as session:
        topic_rows = session.run(
            """
            MATCH (st:Student {email: $email})-[:COMPLETED]->(t:Topic)
            WHERE t.description IS NOT NULL AND t.description <> ''
            RETURN DISTINCT t.description AS desc
            """,
            email=email
        ).data()

        module_rows = session.run(
            """
            MATCH (st:Student {email: $email})-[:COMPLETED]->(t:Topic)<-[:HAS_TOPIC]-(m:Module)
            WHERE m.description IS NOT NULL AND m.description <> ''
            RETURN DISTINCT m.description AS desc
            """,
            email=email
        ).data()

    parts = [r["desc"] for r in topic_rows if r["desc"]] + \
            [r["desc"] for r in module_rows if r["desc"]]
    return " ".join(parts)


def infer_user_skills(email: str) -> list:
    """Build user skill profile from completed topics and enrolled modules."""
    with get_session() as session:
        # Skills from completed topics
        result = session.run(
            """
            MATCH (st:Student {email: $email})-[:COMPLETED]->(t:Topic)-[:COVERS]->(sk:Skill)
            RETURN DISTINCT sk.name AS skill
            UNION
            MATCH (st:Student {email: $email})-[:COMPLETED]->(t:Topic)<-[:HAS_TOPIC]-(m:Module)-[:TEACHES]->(sk:Skill)
            RETURN DISTINCT sk.name AS skill
            """,
            email=email
        )
        return [r["skill"] for r in result if r["skill"]]


def get_skill_gaps(email: str, career_path: str = None) -> dict:
    """Compare user skills vs skills required by their enrolled course/career path."""
    user_skills = set(infer_user_skills(email))

    with get_session() as session:
        if career_path:
            result = session.run(
                "MATCH (cp:CareerPath {name: $cp})-[:REQUIRES]->(sk:Skill) RETURN sk.name AS skill",
                cp=career_path
            )
        else:
            result = session.run(
                """
                MATCH (st:Student {email: $email})-[:ENROLLED_IN]->(c:Course)-[:CONTAINS]->(m:Module)-[:TEACHES]->(sk:Skill)
                RETURN DISTINCT sk.name AS skill
                """,
                email=email
            )
        all_skills = {r["skill"] for r in result if r["skill"]}

    gap_skills = all_skills - user_skills
    return {
        "current_skills": sorted(user_skills),
        "required_skills": sorted(all_skills),
        "gap_skills": sorted(gap_skills),
        "coverage_pct": round(len(user_skills & all_skills) / max(len(all_skills), 1) * 100, 1)
    }


def get_skill_overlap(email: str, job_id: str) -> dict:
    """Return matching and missing skills for a specific job."""
    user_skills = set(infer_user_skills(email))

    with get_session() as session:
        result = session.run(
            "MATCH (j:Job) WHERE toString(elementId(j)) = $id RETURN j.skills_required AS skills",
            id=job_id
        ).single()
        if not result:
            return {"matching": [], "missing": [], "match_pct": 0}
        job_skills = set(result["skills"] or [])

    matching = user_skills & job_skills
    missing = job_skills - user_skills
    return {
        "matching": sorted(matching),
        "missing": sorted(missing),
        "match_pct": round(len(matching) / max(len(job_skills), 1) * 100, 1)
    }


def update_user_skills(email: str):
    """Called after topic completion — updates HAS_SKILL relationships."""
    skills = infer_user_skills(email)
    if not skills:
        return
    with get_session() as session:
        for skill_name in skills:
            session.run(
                """
                MATCH (st:Student {email: $email}), (sk:Skill {name: $skill})
                MERGE (st)-[r:HAS_SKILL]->(sk)
                ON CREATE SET r.proficiency = 'beginner', r.inferred_at = datetime()
                ON MATCH SET r.inferred_at = datetime()
                """,
                email=email, skill=skill_name
            )
