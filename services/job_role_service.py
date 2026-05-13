"""
Infer job roles a student can apply for, based solely on completed modules and skills.
No scraped job postings — pure Gemini-based role inference from course content.
"""
import os
import json
import re
import logging
from services.neo4j_service import get_session
import services.cache_service as cache

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_CACHE_TTL = 1800  # 30 minutes — role inference is expensive


# ── Neo4j helpers ─────────────────────────────────────────────────────────────

def _get_completed_module_data(email: str) -> list:
    """Return list of {name, description, skills} for modules with at least one completed topic."""
    with get_session() as session:
        records = session.run(
            """
            MATCH (st:Student {email: $email})-[:COMPLETED]->(t:Topic)<-[:HAS_TOPIC]-(m:Module)
            WITH m, collect(DISTINCT t.name) AS completed_topics
            OPTIONAL MATCH (m)-[:TEACHES]->(sk:Skill)
            RETURN
                m.name AS name,
                coalesce(m.description, '') AS description,
                completed_topics,
                collect(DISTINCT sk.name) AS skills
            """,
            email=email
        ).data()
    return records


def _get_all_course_module_data(email: str) -> list:
    """Return all modules in the student's enrolled course (regardless of completion)."""
    with get_session() as session:
        records = session.run(
            """
            MATCH (st:Student {email: $email})-[:ENROLLED_IN]->(c:Course)-[:CONTAINS]->(m:Module)
            OPTIONAL MATCH (m)-[:TEACHES]->(sk:Skill)
            OPTIONAL MATCH (m)-[:HAS_TOPIC]->(t:Topic)
            RETURN
                m.name AS name,
                coalesce(m.description, '') AS description,
                collect(DISTINCT t.name) AS all_topics,
                collect(DISTINCT sk.name) AS skills
            """,
            email=email
        ).data()
    return records


def _get_user_skills(email: str) -> list:
    with get_session() as session:
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


# ── Gemini inference ──────────────────────────────────────────────────────────

def _build_role_prompt(module_data: list, skills: list, context_label: str) -> str:
    modules_text = "\n".join(
        f"- {m['name']}: {m['description'][:300]}" for m in module_data if m.get("name")
    )
    skills_text = ", ".join(skills[:30]) if skills else "general computing"

    return (
        f"You are a career counsellor for university students studying computing.\n\n"
        f"Based on the following {context_label}, infer realistic job roles the student "
        f"can apply for. Return ONLY a JSON array. Each element must be an object with keys:\n"
        f"  - title (string): job role title (e.g. 'Junior Web Developer')\n"
        f"  - seniority (string): one of 'Intern', 'Junior', 'Mid-Level', 'Senior'\n"
        f"  - matched_skills (array of strings): skills from the list that match this role (max 6)\n"
        f"  - confidence (integer 0-100): how confident you are\n"
        f"  - reason (string): one sentence explaining why\n\n"
        f"Return 5-8 roles. No markdown, no explanation outside the JSON array.\n\n"
        f"Modules / Content:\n{modules_text}\n\n"
        f"Inferred Skills: {skills_text}"
    )


def _call_gemini_for_roles(prompt: str) -> list:
    if not GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — skipping role inference")
        return []
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        raw = response.text.strip()
        raw = re.sub(r'^```[a-z]*\n?', '', raw).rstrip('`').strip()
        roles = json.loads(raw)
        if isinstance(roles, list):
            return [r for r in roles if isinstance(r, dict) and r.get("title")]
    except Exception as e:
        logger.error(f"Gemini role inference failed: {e}")
    return []


def _fallback_roles(skills: list, completed: bool) -> list:
    """Keyword-based fallback when Gemini is unavailable."""
    s = set(s.lower() for s in skills)
    mapping = [
        ({"python", "machine learning", "pandas", "numpy"}, "Data Analyst", "Junior"),
        ({"python", "tensorflow", "deep learning", "pytorch"}, "ML Engineer", "Junior"),
        ({"javascript", "react", "html", "css"}, "Front-End Developer", "Junior"),
        ({"node.js", "django", "flask", "sql", "restful api"}, "Back-End Developer", "Junior"),
        ({"docker", "kubernetes", "aws", "devops", "linux"}, "DevOps Engineer", "Junior"),
        ({"cybersecurity", "networking", "linux"}, "Security Analyst", "Junior"),
        ({"java", "oop", "algorithms", "data structures"}, "Software Developer", "Junior"),
        ({"sql", "data analysis", "tableau"}, "Data Analyst Intern", "Intern"),
        ({"python"}, "Python Developer Intern", "Intern"),
    ]
    roles = []
    for required, title, seniority in mapping:
        matched = sorted(required & s)
        if len(matched) >= max(1, len(required) // 2):
            if not completed and seniority == "Junior":
                seniority = "Intern"
            roles.append({
                "title": title,
                "seniority": seniority,
                "matched_skills": matched[:6],
                "confidence": min(50 + len(matched) * 10, 90),
                "reason": f"Matched {len(matched)} key skills from your progress.",
            })
    return roles[:6]


# ── Public API ────────────────────────────────────────────────────────────────

def get_current_eligible_roles(email: str) -> list:
    """
    Roles the student can apply for RIGHT NOW based on completed modules only.
    """
    cache_key = f"eligible_roles:{email}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    modules = _get_completed_module_data(email)
    skills = _get_user_skills(email)

    if not modules and not skills:
        return []

    prompt = _build_role_prompt(modules, skills, "completed modules and inferred skills")
    roles = _call_gemini_for_roles(prompt)

    if not roles:
        roles = _fallback_roles(skills, completed=True)

    # Normalise
    for r in roles:
        r.setdefault("matched_modules", [m["name"] for m in modules[:4]])
        r.setdefault("confidence", 70)
        r.setdefault("reason", "Based on your completed coursework.")

    cache.set(cache_key, roles, ttl=_CACHE_TTL)
    return roles


def get_post_completion_roles(email: str) -> list:
    """
    Roles achievable after completing ALL modules in the enrolled course.
    """
    cache_key = f"future_roles:{email}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    modules = _get_all_course_module_data(email)
    all_skills = list({sk for m in modules for sk in (m.get("skills") or [])})

    if not modules:
        return []

    prompt = _build_role_prompt(modules, all_skills, "all modules in the enrolled course (full curriculum)")
    roles = _call_gemini_for_roles(prompt)

    if not roles:
        roles = _fallback_roles(all_skills, completed=False)

    for r in roles:
        r.setdefault("matched_modules", [m["name"] for m in modules[:6]])
        r.setdefault("confidence", 80)
        r.setdefault("reason", "Achievable upon completing the full course.")

    cache.set(cache_key, roles, ttl=_CACHE_TTL)
    return roles
