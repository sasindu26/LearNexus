"""
LinkedIn Learning certificate scraper.
Primary: HTTP request to public catalog search page.
Fallback: curated seed dataset of popular LinkedIn Learning paths.
"""
import os
import logging
import requests
from scrapers.base_scraper import BaseScraper
from services.skill_extractor import extract_skills
from services.embedding_service import embed_text
from services.neo4j_service import get_session

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# LinkedIn Learning Voyager API for public catalog (no auth required for basic search)
_LL_SEARCH_URL = (
    "https://www.linkedin.com/learning-login/share"
    "?account=0&v=2&shareType=course&courseType=COURSE"
)

_LI_SEED = [
    {
        "title": "Python Essential Training",
        "provider": "LinkedIn Learning",
        "category": "Programming",
        "description": "Master the Python programming language from beginner to advanced level.",
        "skills_taught": ["python", "programming", "oop", "data structures"],
        "difficulty": "beginner",
        "duration": "4h 58m",
        "career_relevance": "Python Developer / Data Analyst",
        "url": "https://www.linkedin.com/learning/python-essential-training-18764650",
        "image_url": "https://media.licdn.com/dms/image/D560DAQH8GKnYuHBfYw/learning-public-crop_675_1200/0/1710262672034",
    },
    {
        "title": "React.js Essential Training",
        "provider": "LinkedIn Learning",
        "category": "Web Development",
        "description": "Learn React.js fundamentals: components, state, hooks, and the React ecosystem.",
        "skills_taught": ["react", "javascript", "html", "css", "front-end development"],
        "difficulty": "intermediate",
        "duration": "2h 45m",
        "career_relevance": "Front-End Developer",
        "url": "https://www.linkedin.com/learning/react-js-essential-training",
        "image_url": "https://media.licdn.com/dms/image/C560DAQGldS7BbBa5eA/learning-public-crop_675_1200/0/1631725975049",
    },
    {
        "title": "Machine Learning with Python: Foundations",
        "provider": "LinkedIn Learning",
        "category": "Artificial Intelligence",
        "description": "Build machine learning models using scikit-learn, pandas, and NumPy.",
        "skills_taught": ["machine learning", "python", "scikit-learn", "pandas", "numpy", "data analysis"],
        "difficulty": "intermediate",
        "duration": "3h 18m",
        "career_relevance": "ML Engineer / Data Scientist",
        "url": "https://www.linkedin.com/learning/machine-learning-with-python-foundations",
        "image_url": "https://media.licdn.com/dms/image/C560DAQGotV0pqH1WUw/learning-public-crop_675_1200/0/1611002028696",
    },
    {
        "title": "SQL Essential Training",
        "provider": "LinkedIn Learning",
        "category": "Database",
        "description": "Learn SQL from the ground up: queries, joins, subqueries, and database design.",
        "skills_taught": ["sql", "database", "data analysis", "mysql", "postgresql"],
        "difficulty": "beginner",
        "duration": "3h 56m",
        "career_relevance": "Data Analyst / Backend Developer",
        "url": "https://www.linkedin.com/learning/sql-essential-training-20685933",
        "image_url": "https://media.licdn.com/dms/image/D560DAQGBd_qyiCIlXA/learning-public-crop_675_1200/0/1708096698116",
    },
    {
        "title": "Git Essential Training: The Basics",
        "provider": "LinkedIn Learning",
        "category": "Software Engineering",
        "description": "Learn Git version control from scratch with branching, merging, and remote repos.",
        "skills_taught": ["git", "version control", "software engineering", "devops"],
        "difficulty": "beginner",
        "duration": "3h 10m",
        "career_relevance": "Software Developer",
        "url": "https://www.linkedin.com/learning/git-essential-training-the-basics",
        "image_url": "https://media.licdn.com/dms/image/C560DAQGqpjQ4lMpW_A/learning-public-crop_675_1200/0/1611080895698",
    },
    {
        "title": "Learning Docker",
        "provider": "LinkedIn Learning",
        "category": "DevOps",
        "description": "Containerize applications with Docker and understand container orchestration basics.",
        "skills_taught": ["docker", "containers", "devops", "linux", "kubernetes"],
        "difficulty": "intermediate",
        "duration": "2h 49m",
        "career_relevance": "DevOps Engineer",
        "url": "https://www.linkedin.com/learning/learning-docker-17236240",
        "image_url": "https://media.licdn.com/dms/image/C560DAQF2CxFqQ2Jk5w/learning-public-crop_675_1200/0/1610667892247",
    },
    {
        "title": "JavaScript Essential Training",
        "provider": "LinkedIn Learning",
        "category": "Web Development",
        "description": "Learn modern JavaScript: ES6+, async/await, DOM manipulation, and APIs.",
        "skills_taught": ["javascript", "es6", "html", "css", "web development", "dom"],
        "difficulty": "beginner",
        "duration": "5h 45m",
        "career_relevance": "Web Developer / Full-Stack Developer",
        "url": "https://www.linkedin.com/learning/javascript-essential-training",
        "image_url": "https://media.licdn.com/dms/image/C560DAQGnkEMRiLrXFg/learning-public-crop_675_1200/0/1611013047866",
    },
    {
        "title": "AWS Essential Training for Developers",
        "provider": "LinkedIn Learning",
        "category": "Cloud Computing",
        "description": "Deploy applications on AWS using EC2, S3, Lambda, RDS, and the AWS SDK.",
        "skills_taught": ["aws", "cloud", "python", "lambda", "s3", "ec2", "devops"],
        "difficulty": "intermediate",
        "duration": "4h 10m",
        "career_relevance": "Cloud Developer / DevOps Engineer",
        "url": "https://www.linkedin.com/learning/aws-essential-training-for-developers-17237791",
        "image_url": "https://media.licdn.com/dms/image/C560DAQF95_OvFa1fSw/learning-public-crop_675_1200/0/1626272929665",
    },
    {
        "title": "Cybersecurity Foundations",
        "provider": "LinkedIn Learning",
        "category": "Cybersecurity",
        "description": "Foundational cybersecurity concepts: threats, risk, cryptography, and network security.",
        "skills_taught": ["cybersecurity", "networking", "cryptography", "risk management", "linux"],
        "difficulty": "beginner",
        "duration": "2h 54m",
        "career_relevance": "Security Analyst",
        "url": "https://www.linkedin.com/learning/cybersecurity-foundations-2019",
        "image_url": "https://media.licdn.com/dms/image/C560DAQGhWzXqjgw5CQ/learning-public-crop_675_1200/0/1610650793266",
    },
    {
        "title": "Deep Learning: Getting Started",
        "provider": "LinkedIn Learning",
        "category": "Artificial Intelligence",
        "description": "Introduction to deep learning: neural networks, backpropagation, CNNs, and RNNs.",
        "skills_taught": ["deep learning", "neural networks", "python", "tensorflow", "pytorch"],
        "difficulty": "intermediate",
        "duration": "1h 47m",
        "career_relevance": "ML Engineer / AI Researcher",
        "url": "https://www.linkedin.com/learning/deep-learning-getting-started",
        "image_url": "https://media.licdn.com/dms/image/C560DAQHaHFtyvh2E7g/learning-public-crop_675_1200/0/1611027421034",
    },
]


class LinkedInLearningScraper(BaseScraper):

    def scrape(self) -> list:
        """Return curated seed (always) + any live results if scraping succeeds."""
        items = list(_LI_SEED)
        try:
            live = self._fetch_live_courses()
            logger.info(f"LinkedInLearningScraper: {len(live)} live courses fetched")
            items.extend(live)
        except Exception as e:
            logger.warning(f"LinkedIn Learning live fetch failed (using seed): {e}")
        return items

    def _fetch_live_courses(self) -> list:
        """
        Try LinkedIn Learning's Voyager search API (public endpoint).
        Returns [] if blocked or rate-limited — system falls back to seed.
        """
        queries = os.getenv("LI_LEARNING_QUERIES", "python,javascript,machine learning,cybersecurity").split(",")
        results = []
        seen_urls = set()

        for query in queries[:4]:
            try:
                url = "https://www.linkedin.com/learning/api/search"
                params = {
                    "keywords": query.strip(),
                    "learningContextUrn": "urn:li:learningContext:default",
                    "start": 0,
                    "count": 5,
                    "filterValues": "COURSE",
                }
                resp = requests.get(url, params=params, headers=_HEADERS, timeout=8)
                if resp.status_code != 200:
                    continue
                data = resp.json()
                for item in data.get("elements", []):
                    course = item.get("course", item)
                    title = (course.get("title") or {}).get("value", "")
                    slug = course.get("slug", "")
                    if not title or not slug:
                        continue
                    course_url = f"https://www.linkedin.com/learning/{slug}"
                    if course_url in seen_urls:
                        continue
                    seen_urls.add(course_url)
                    results.append({
                        "title": title,
                        "provider": "LinkedIn Learning",
                        "category": "General",
                        "description": (course.get("shortDescription") or {}).get("value", ""),
                        "skills_taught": [],
                        "difficulty": "intermediate",
                        "duration": "",
                        "career_relevance": "",
                        "url": course_url,
                        "image_url": course.get("primaryImageUrl", {}).get("url", ""),
                    })
            except Exception:
                continue

        return results

    def normalize(self, raw: dict) -> dict:
        return {
            "title": raw.get("title", ""),
            "provider": raw.get("provider", "LinkedIn Learning"),
            "category": raw.get("category", "General"),
            "description": raw.get("description", ""),
            "skills_taught": raw.get("skills_taught") or [],
            "difficulty": raw.get("difficulty", "intermediate"),
            "duration": raw.get("duration", ""),
            "career_relevance": raw.get("career_relevance", ""),
            "url": raw.get("url", ""),
            "image_url": raw.get("image_url", ""),
        }

    def store(self, items: list):
        if not items:
            return
        with get_session() as session:
            for cert in items:
                if not cert.get("title") or not cert.get("url"):
                    continue
                try:
                    desc_skills = extract_skills(
                        cert.get("description", ""),
                        context=f"Certificate: {cert['title']}"
                    ) if not cert.get("skills_taught") else []
                    all_skills = list(dict.fromkeys(
                        s.lower() for s in (cert.get("skills_taught") or []) + desc_skills
                    ))[:20]

                    embedding = embed_text(
                        f"{cert['title']} {cert.get('description', '')} {' '.join(all_skills)}"
                    )

                    result = session.run(
                        """
                        MERGE (c:Certificate {url: $url})
                        ON CREATE SET
                            c.title = $title,
                            c.provider = $provider,
                            c.category = $category,
                            c.description = $description,
                            c.skills_taught = $skills,
                            c.difficulty = $difficulty,
                            c.duration = $duration,
                            c.career_relevance = $career_relevance,
                            c.image_url = $image_url,
                            c.embedding = $embedding,
                            c.scraped_at = datetime()
                        ON MATCH SET
                            c.scraped_at = datetime(),
                            c.image_url = $image_url
                        RETURN elementId(c) AS eid
                        """,
                        url=cert["url"],
                        title=cert["title"],
                        provider=cert["provider"],
                        category=cert["category"],
                        description=cert["description"],
                        skills=all_skills,
                        difficulty=cert["difficulty"],
                        duration=cert["duration"],
                        career_relevance=cert["career_relevance"],
                        image_url=cert["image_url"],
                        embedding=embedding,
                    )
                    cert_eid = result.single()["eid"]

                    for skill_name in all_skills:
                        session.run(
                            """
                            MERGE (sk:Skill {name: $skill})
                            ON CREATE SET sk.category = 'general', sk.created_at = datetime()
                            WITH sk
                            MATCH (c:Certificate) WHERE elementId(c) = $eid
                            MERGE (sk)-[:REQUIRED_BY]->(c)
                            """,
                            skill=skill_name, eid=cert_eid
                        )
                except Exception as e:
                    logger.warning(f"LinkedIn store error '{cert.get('title', '?')}': {e}")
