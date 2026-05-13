"""RemoteOK job scraper using their public JSON API."""
import logging
import re
import requests
import time
from scrapers.base_scraper import BaseScraper
from services.skill_extractor import extract_skills
from services.embedding_service import embed_text
from services.neo4j_service import get_session

logger = logging.getLogger(__name__)

REMOTEOK_API = "https://remoteok.com/api"
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LearNexusBot/1.0; +https://learnexus.app)"}

_HTML_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&nbsp;": " ",
    "&#39;": "'", "&quot;": '"', "&apos;": "'", "&#x27;": "'",
}


def _strip_html(html: str) -> str:
    """Strip HTML tags and decode common entities — RemoteOK descriptions are raw HTML."""
    text = re.sub(r'<[^>]+>', ' ', html or '')
    for entity, char in _HTML_ENTITIES.items():
        text = text.replace(entity, char)
    return re.sub(r'\s+', ' ', text).strip()


def _infer_level(text: str) -> str:
    text = text.lower()
    if any(w in text for w in ["intern", "internship", "trainee", "placement year"]):
        return "intern"
    if any(w in text for w in ["senior", "sr.", "lead", "staff", "principal", "architect"]):
        return "senior"
    if any(w in text for w in ["junior", "jr.", "entry", "graduate", "entry-level"]):
        return "junior"
    return "mid"


class RemoteOKScraper(BaseScraper):

    def scrape(self) -> list:
        try:
            resp = requests.get(REMOTEOK_API, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            # First element is a legal notice dict, skip it
            jobs = [item for item in data if isinstance(item, dict) and item.get("id")]
            logger.info(f"RemoteOK returned {len(jobs)} jobs")
            return jobs[:100]  # cap at 100
        except Exception as e:
            logger.error(f"RemoteOK scrape failed: {e}")
            return []

    def normalize(self, raw: dict) -> dict:
        try:
            title = raw.get("position", "") or raw.get("title", "")
            company = raw.get("company", "Unknown")
            description = _strip_html(raw.get("description", "") or "")
            tags = raw.get("tags", []) or []
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(",") if t.strip()]
            salary = raw.get("salary", "") or ""
            location = raw.get("location", "Remote") or "Remote"
            url = raw.get("url", "") or raw.get("apply_url", "")
            date_posted = raw.get("date", "") or raw.get("epoch", "")
            # RemoteOK returns company_logo as a URL
            image_url = raw.get("company_logo", "") or ""

            return {
                "title": title,
                "company": company,
                "skills_required": tags[:20],
                "experience_level": _infer_level(title + " " + description),
                "location": location,
                "salary": salary,
                "tags": tags[:20],
                "job_type": "remote",
                "description": description,          # full description — no truncation
                "source_url": url,
                "source": "remoteok",
                "date_posted": str(date_posted),
                "image_url": image_url,
            }
        except Exception as e:
            logger.warning(f"RemoteOK normalize error: {e}")
            return {}

    def store(self, items: list):
        if not items:
            return
        with get_session() as session:
            for job in items:
                try:
                    # Extract additional skills from description
                    desc_skills = extract_skills(
                        job.get("description", ""),
                        context=f"Job: {job.get('title', '')}"
                    )
                    all_skills = list(dict.fromkeys(
                        [s.lower() for s in (job.get("skills_required", []) + desc_skills)]
                    ))[:25]

                    embedding = embed_text(
                        f"{job['title']} {job.get('description', '')} {' '.join(all_skills)}"
                    )

                    result = session.run(
                        """
                        MERGE (j:Job {source_url: $source_url})
                        ON CREATE SET
                            j.title = $title,
                            j.company = $company,
                            j.skills_required = $skills,
                            j.experience_level = $level,
                            j.location = $location,
                            j.salary = $salary,
                            j.tags = $tags,
                            j.job_type = $job_type,
                            j.description = $description,
                            j.source = $source,
                            j.image_url = $image_url,
                            j.embedding = $embedding,
                            j.scraped_at = datetime(),
                            j.is_active = true
                        ON MATCH SET
                            j.scraped_at = datetime(),
                            j.is_active = true,
                            j.image_url = $image_url,
                            j.description = $description,
                            j.embedding = $embedding
                        RETURN elementId(j) AS eid
                        """,
                        source_url=job["source_url"],
                        title=job["title"],
                        company=job["company"],
                        skills=all_skills,
                        level=job["experience_level"],
                        location=job["location"],
                        salary=job["salary"],
                        tags=job["tags"],
                        job_type=job["job_type"],
                        description=job["description"],
                        source=job["source"],
                        image_url=job.get("image_url", ""),
                        embedding=embedding,
                    )
                    job_eid = result.single()["eid"]

                    # Create Skill nodes and MATCHES relationships
                    for skill_name in all_skills:
                        session.run(
                            """
                            MERGE (sk:Skill {name: $skill})
                            ON CREATE SET sk.category = 'general', sk.created_at = datetime()
                            WITH sk
                            MATCH (j:Job) WHERE elementId(j) = $eid
                            MERGE (sk)-[:MATCHES]->(j)
                            """,
                            skill=skill_name, eid=job_eid
                        )
                except Exception as e:
                    logger.warning(f"Job store error for '{job.get('title', '?')}': {e}")
