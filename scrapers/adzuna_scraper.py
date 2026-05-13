"""
Adzuna API job scraper (free tier: 250 req/day).
Requires env vars: ADZUNA_APP_ID, ADZUNA_API_KEY.
Optional: ADZUNA_COUNTRY (default: gb), ADZUNA_QUERY (default: developer)
"""
import os
import logging
import requests
from scrapers.base_scraper import BaseScraper
from services.skill_extractor import extract_skills
from services.embedding_service import embed_text
from services.neo4j_service import get_session

logger = logging.getLogger(__name__)

ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_API_KEY = os.getenv("ADZUNA_API_KEY", "")
ADZUNA_COUNTRY = os.getenv("ADZUNA_COUNTRY", "gb")
ADZUNA_QUERY = os.getenv("ADZUNA_QUERY", "software developer")
ADZUNA_MAX_RESULTS = int(os.getenv("ADZUNA_MAX_RESULTS", "50"))

_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
_HEADERS = {"Accept": "application/json"}

_SENIORITY_KEYWORDS = {
    "intern": ["intern", "internship", "trainee", "placement", "graduate trainee"],
    "junior": ["junior", "jr.", "entry", "entry-level", "entry level", "associate", "graduate"],
    "senior": ["senior", "sr.", "lead", "principal", "staff", "head of", "architect"],
}


def _infer_seniority(title: str, description: str) -> str:
    combined = (title + " " + description).lower()
    for level, kws in _SENIORITY_KEYWORDS.items():
        if any(kw in combined for kw in kws):
            return level
    return "mid"


class AdzunaScraper(BaseScraper):

    def scrape(self) -> list:
        if not ADZUNA_APP_ID or not ADZUNA_API_KEY:
            logger.warning("AdzunaScraper: ADZUNA_APP_ID or ADZUNA_API_KEY not set — skipping")
            return []

        results = []
        page = 1
        per_page = min(50, ADZUNA_MAX_RESULTS)

        while len(results) < ADZUNA_MAX_RESULTS:
            url = _BASE_URL.format(country=ADZUNA_COUNTRY, page=page)
            params = {
                "app_id": ADZUNA_APP_ID,
                "app_key": ADZUNA_API_KEY,
                "what": ADZUNA_QUERY,
                "category": "it-jobs",
                "results_per_page": per_page,
                "content-type": "application/json",
            }
            try:
                resp = requests.get(url, params=params, headers=_HEADERS, timeout=15)
                resp.raise_for_status()
                data = resp.json()
                jobs = data.get("results", [])
                if not jobs:
                    break
                results.extend(jobs)
                if len(jobs) < per_page:
                    break
                page += 1
            except Exception as e:
                logger.error(f"AdzunaScraper page {page} failed: {e}")
                break

        logger.info(f"AdzunaScraper scraped {len(results)} jobs")
        return results[:ADZUNA_MAX_RESULTS]

    def normalize(self, raw: dict) -> dict:
        title = raw.get("title", "")
        company = (raw.get("company") or {}).get("display_name", "Unknown")
        description = raw.get("description", "")
        location = (raw.get("location") or {}).get("display_name", "Remote")
        salary_min = raw.get("salary_min")
        salary_max = raw.get("salary_max")
        salary = ""
        if salary_min and salary_max:
            salary = f"£{int(salary_min):,} – £{int(salary_max):,}"
        elif salary_min:
            salary = f"from £{int(salary_min):,}"

        source_url = raw.get("redirect_url", "")
        image_url = (raw.get("company") or {}).get("logo_url", "")
        if not image_url:
            # Adzuna doesn't always have logos — construct a Clearbit-style fallback
            domain = raw.get("company", {}).get("canonical_name", "").replace(" ", "").lower()
            if domain:
                image_url = f"https://logo.clearbit.com/{domain}.com"

        return {
            "title": title,
            "company": company,
            "description": description,
            "location": location,
            "salary": salary,
            "source_url": source_url,
            "source": "adzuna",
            "job_type": "remote" if "remote" in (location + description).lower() else "onsite",
            "image_url": image_url,
            "seniority": _infer_seniority(title, description),
        }

    def store(self, items: list):
        if not items:
            return
        with get_session() as session:
            for job in items:
                if not job.get("title") or not job.get("source_url"):
                    continue
                try:
                    skills = extract_skills(job["description"], context=f"Job: {job['title']}")
                    all_skills = list(dict.fromkeys(s.lower() for s in skills))[:25]
                    embedding = embed_text(
                        f"{job['title']} {job['description']} {' '.join(all_skills)}"
                    )

                    result = session.run(
                        """
                        MERGE (j:Job {source_url: $source_url})
                        ON CREATE SET
                            j.title = $title,
                            j.company = $company,
                            j.skills_required = $skills,
                            j.experience_level = $seniority,
                            j.location = $location,
                            j.salary = $salary,
                            j.tags = $skills,
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
                        seniority=job["seniority"],
                        location=job["location"],
                        salary=job["salary"],
                        job_type=job["job_type"],
                        description=job["description"],
                        source=job["source"],
                        image_url=job["image_url"],
                        embedding=embedding,
                    )
                    job_eid = result.single()["eid"]

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
                    logger.warning(f"AdzunaScraper store error '{job.get('title', '?')}': {e}")
