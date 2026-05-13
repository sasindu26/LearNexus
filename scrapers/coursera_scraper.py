"""Coursera certificate scraper using the public catalog API."""
import logging
import requests
from scrapers.base_scraper import BaseScraper
from services.skill_extractor import extract_skills
from services.embedding_service import embed_text
from services.neo4j_service import get_session

logger = logging.getLogger(__name__)

# Coursera's public catalog API (no auth required for read-only access)
COURSERA_API = (
    "https://api.coursera.org/api/courses.v1"
    "?fields=name,description,primaryLanguages,partnerIds,photoUrl,slug,domainTypes"
    "&limit=100&start={start}"
)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; LearNexusBot/1.0)"}

_DIFFICULTY_MAP = {
    "beginner": "beginner",
    "intermediate": "intermediate",
    "advanced": "advanced",
    "mixed": "intermediate",
}

_PROVIDER_LOGOS = {
    "Google / Coursera": "https://upload.wikimedia.org/wikipedia/commons/2/2f/Coursera-Logo_600x600.svg",
    "IBM / Coursera": "https://upload.wikimedia.org/wikipedia/commons/5/51/IBM_logo.svg",
    "Meta / Coursera": "https://upload.wikimedia.org/wikipedia/commons/7/7b/Meta_Platforms_Inc._logo.svg",
    "Google Cloud": "https://upload.wikimedia.org/wikipedia/commons/0/01/Google-cloud-platform.svg",
    "Amazon Web Services": "https://upload.wikimedia.org/wikipedia/commons/9/93/Amazon_Web_Services_Logo.svg",
    "Google / TensorFlow": "https://upload.wikimedia.org/wikipedia/commons/2/2d/Tensorflow_logo.svg",
    "Cloud Native Computing Foundation": "https://www.cncf.io/wp-content/uploads/2020/08/cncf-logo.png",
    "CompTIA": "https://www.comptia.org/content/dam/comptia/images/comptia-logo.svg",
    "Microsoft": "https://upload.wikimedia.org/wikipedia/commons/4/44/Microsoft_logo.svg",
    "DeepLearning.AI / Coursera": "https://deeplearning.ai/wp-content/uploads/2021/02/Logo-White.png",
    "(ISC)²": "https://www.isc2.org/-/media/Project/ISC2/Main/images/logos/isc2-primary-logo.png",
    "Oracle": "https://upload.wikimedia.org/wikipedia/commons/5/50/Oracle_logo.svg",
    "SCRUMstudy": "https://www.scrumstudy.com/images/scrumstudy-logo.png",
    "Coursera": "https://upload.wikimedia.org/wikipedia/commons/2/2f/Coursera-Logo_600x600.svg",
}

_CERT_SEED = [
    {
        "title": "Google Data Analytics Certificate",
        "provider": "Google / Coursera",
        "category": "Data Science",
        "description": "Get the skills to succeed in an entry-level data analytics role.",
        "skills_taught": ["data analysis", "sql", "r", "tableau", "python", "data visualization"],
        "difficulty": "beginner",
        "duration": "6 months",
        "career_relevance": "Data Analyst",
        "url": "https://www.coursera.org/professional-certificates/google-data-analytics",
    },
    {
        "title": "IBM Data Science Professional Certificate",
        "provider": "IBM / Coursera",
        "category": "Data Science",
        "description": "Kickstart your career in data science with a comprehensive professional certificate.",
        "skills_taught": ["python", "machine learning", "data science", "sql", "data visualization", "pandas", "numpy"],
        "difficulty": "beginner",
        "duration": "10 months",
        "career_relevance": "Data Scientist",
        "url": "https://www.coursera.org/professional-certificates/ibm-data-science",
    },
    {
        "title": "Meta Front-End Developer Certificate",
        "provider": "Meta / Coursera",
        "category": "Web Development",
        "description": "Launch a career as a front-end developer with Meta's industry-recognized certificate.",
        "skills_taught": ["html", "css", "javascript", "react", "ui/ux", "version control"],
        "difficulty": "beginner",
        "duration": "7 months",
        "career_relevance": "Front-End Developer",
        "url": "https://www.coursera.org/professional-certificates/meta-front-end-developer",
    },
    {
        "title": "Google Cloud Professional Data Engineer",
        "provider": "Google Cloud",
        "category": "Cloud Computing",
        "description": "Demonstrate the ability to design and build data processing systems on Google Cloud.",
        "skills_taught": ["gcp", "bigquery", "dataflow", "cloud storage", "machine learning", "sql"],
        "difficulty": "advanced",
        "duration": "self-paced",
        "career_relevance": "Cloud Data Engineer",
        "url": "https://cloud.google.com/certification/data-engineer",
    },
    {
        "title": "AWS Certified Developer – Associate",
        "provider": "Amazon Web Services",
        "category": "Cloud Computing",
        "description": "Demonstrate knowledge of core AWS services and best practices for application development.",
        "skills_taught": ["aws", "cloud", "python", "docker", "lambda", "s3", "dynamodb", "api gateway"],
        "difficulty": "intermediate",
        "duration": "self-paced",
        "career_relevance": "Cloud Developer",
        "url": "https://aws.amazon.com/certification/certified-developer-associate/",
    },
    {
        "title": "TensorFlow Developer Certificate",
        "provider": "Google / TensorFlow",
        "category": "Artificial Intelligence",
        "description": "Demonstrate proficiency in using TensorFlow to solve deep learning and ML problems.",
        "skills_taught": ["tensorflow", "deep learning", "python", "neural networks", "computer vision", "nlp"],
        "difficulty": "intermediate",
        "duration": "self-paced",
        "career_relevance": "ML Engineer",
        "url": "https://www.tensorflow.org/certificate",
    },
    {
        "title": "Certified Kubernetes Administrator (CKA)",
        "provider": "Cloud Native Computing Foundation",
        "category": "DevOps",
        "description": "Validate expertise in Kubernetes administration.",
        "skills_taught": ["kubernetes", "docker", "linux", "devops", "cloud", "networking"],
        "difficulty": "advanced",
        "duration": "self-paced",
        "career_relevance": "DevOps Engineer / SRE",
        "url": "https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/",
    },
    {
        "title": "CompTIA Security+",
        "provider": "CompTIA",
        "category": "Cybersecurity",
        "description": "Validate baseline, vendor-agnostic IT security knowledge and skills.",
        "skills_taught": ["cybersecurity", "networking", "cryptography", "risk management", "linux"],
        "difficulty": "intermediate",
        "duration": "self-paced",
        "career_relevance": "Security Analyst",
        "url": "https://www.comptia.org/certifications/security",
    },
    {
        "title": "Microsoft Azure Fundamentals (AZ-900)",
        "provider": "Microsoft",
        "category": "Cloud Computing",
        "description": "Foundational knowledge of cloud concepts and Azure services.",
        "skills_taught": ["azure", "cloud", "networking", "security", "devops"],
        "difficulty": "beginner",
        "duration": "self-paced",
        "career_relevance": "Cloud Architect",
        "url": "https://learn.microsoft.com/en-us/certifications/azure-fundamentals/",
    },
    {
        "title": "Google UX Design Certificate",
        "provider": "Google / Coursera",
        "category": "UX Design",
        "description": "Gain in-demand skills in UX design and build a portfolio of work.",
        "skills_taught": ["ux design", "figma", "wireframing", "prototyping", "user research"],
        "difficulty": "beginner",
        "duration": "6 months",
        "career_relevance": "UX Designer",
        "url": "https://www.coursera.org/professional-certificates/google-ux-design",
    },
    {
        "title": "DeepLearning.AI Machine Learning Specialization",
        "provider": "DeepLearning.AI / Coursera",
        "category": "Machine Learning",
        "description": "Master fundamental AI concepts and develop practical skills in ML.",
        "skills_taught": ["machine learning", "python", "tensorflow", "neural networks", "regression", "classification"],
        "difficulty": "intermediate",
        "duration": "3 months",
        "career_relevance": "ML Engineer / Data Scientist",
        "url": "https://www.coursera.org/specializations/machine-learning-introduction",
    },
    {
        "title": "Meta Back-End Developer Certificate",
        "provider": "Meta / Coursera",
        "category": "Web Development",
        "description": "Learn back-end development with Python and Django.",
        "skills_taught": ["python", "django", "sql", "apis", "git", "linux", "restful api"],
        "difficulty": "beginner",
        "duration": "8 months",
        "career_relevance": "Back-End Developer",
        "url": "https://www.coursera.org/professional-certificates/meta-back-end-developer",
    },
    {
        "title": "Certified Information Systems Security Professional (CISSP)",
        "provider": "(ISC)²",
        "category": "Cybersecurity",
        "description": "The world's premier cybersecurity certification for experienced practitioners.",
        "skills_taught": ["cybersecurity", "risk management", "networking", "cryptography", "security architecture"],
        "difficulty": "advanced",
        "duration": "self-paced",
        "career_relevance": "Security Manager / CISO",
        "url": "https://www.isc2.org/Certifications/CISSP",
    },
    {
        "title": "Oracle Java SE 17 Developer",
        "provider": "Oracle",
        "category": "Software Development",
        "description": "Validate skills in designing and developing Java applications.",
        "skills_taught": ["java", "oop", "data structures", "algorithms", "design patterns"],
        "difficulty": "intermediate",
        "duration": "self-paced",
        "career_relevance": "Java Developer",
        "url": "https://education.oracle.com/java-se-17-developer/pexam_1Z0-829",
    },
    {
        "title": "Scrum Master Certified (SMC)",
        "provider": "SCRUMstudy",
        "category": "Project Management",
        "description": "Understand Scrum and agile principles for software project management.",
        "skills_taught": ["agile", "scrum", "project management", "software engineering"],
        "difficulty": "beginner",
        "duration": "self-paced",
        "career_relevance": "Scrum Master / Project Manager",
        "url": "https://www.scrumstudy.com/certification/scrum-master-certified",
    },
]


class CourseraScraper(BaseScraper):

    def scrape(self) -> list:
        # Use curated seed dataset + try to fetch more from Coursera catalog API
        items = list(_CERT_SEED)
        try:
            fetched = self._fetch_coursera_catalog(start=0, limit=50)
            items.extend(fetched)
            logger.info(f"CourseraScraper: fetched {len(fetched)} additional certs from API")
        except Exception as e:
            logger.warning(f"CourseraScraper catalog API failed (using seed only): {e}")
        return items

    def _fetch_coursera_catalog(self, start: int = 0, limit: int = 50) -> list:
        url = COURSERA_API.format(start=start)
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        elements = data.get("elements", [])
        results = []
        for el in elements[:limit]:
            name = el.get("name", "")
            desc = el.get("description", "")
            slug = el.get("slug", "")
            if not name or not slug:
                continue
            results.append({
                "title": name,
                "provider": "Coursera",
                "category": "General",
                "description": desc,
                "skills_taught": [],
                "difficulty": "intermediate",
                "duration": "self-paced",
                "career_relevance": "",
                "url": f"https://www.coursera.org/learn/{slug}",
                "_from_api": True,
            })
        return results

    def normalize(self, raw: dict) -> dict:
        provider = raw.get("provider", "Unknown")
        image_url = raw.get("image_url", "") or _PROVIDER_LOGOS.get(provider, "")
        return {
            "title": raw.get("title", ""),
            "provider": provider,
            "category": raw.get("category", "General"),
            "description": raw.get("description", ""),   # full description
            "skills_taught": raw.get("skills_taught", []),
            "difficulty": raw.get("difficulty", "intermediate"),
            "duration": raw.get("duration", "self-paced"),
            "career_relevance": raw.get("career_relevance", ""),
            "url": raw.get("url", ""),
            "image_url": image_url,
        }

    def store(self, items: list):
        if not items:
            return
        with get_session() as session:
            for cert in items:
                try:
                    title = cert.get("title", "")
                    if not title:
                        continue

                    # Extract extra skills from description if needed
                    desc_skills = []
                    if not cert.get("skills_taught"):
                        desc_skills = extract_skills(
                            cert.get("description", ""),
                            context=f"Certificate: {title}"
                        )
                    all_skills = list(dict.fromkeys(
                        [s.lower() for s in (cert.get("skills_taught", []) + desc_skills)]
                    ))[:20]

                    embedding = embed_text(
                        f"{title} {cert.get('description', '')} {' '.join(all_skills)}"
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
                        url=cert["url"] or f"manual:{title}",
                        title=title,
                        provider=cert["provider"],
                        category=cert["category"],
                        description=cert["description"],
                        skills=all_skills,
                        difficulty=cert["difficulty"],
                        duration=cert["duration"],
                        career_relevance=cert["career_relevance"],
                        image_url=cert.get("image_url", ""),
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
                    logger.warning(f"Cert store error for '{cert.get('title', '?')}': {e}")
