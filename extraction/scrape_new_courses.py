"""
LearNexus — Scrape NEW Faculty of Computing courses & add to Neo4j
New courses found from NSBM website (not in existing 5):
 1. Cyber Security (BIT Major in Cyber Security)
 2. Technology Management (BSc Hons)
 3. Computer Security (BSc Hons - Plymouth)
 4. Artificial Intelligence (BSc Hons - Plymouth)

Uses same scraper.py logic (data-id selectors) + same module structure as old 5 courses.
NEVER touches existing data.
"""
import os, time, json, requests, logging
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(_ROOT, '.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('new_courses')

NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "LearNexus1212"
GEMINI_KEY     = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

driver   = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# ── NEW courses discovered from NSBM Faculty of Computing ────────────────────
NEW_COURSES = {
    "Cyber Security": "https://www.nsbm.ac.lk/course/bachelor-of-information-technology-major-in-cyber-security/",
    "Technology Management": "https://www.nsbm.ac.lk/course/bsc-honours-in-technology-management/",
    "Computer Security": "https://www.nsbm.ac.lk/course/bsc-hons-in-computer-security/",
    "Artificial Intelligence": "https://www.nsbm.ac.lk/course/bsc-hons-artificial-intelligence-plymouth-university-uk/",
}

# Same year div IDs as scraper.py
YEAR_IDS = {
    1: "1a46983",
    2: "08e7c80",
    3: "64138a9",
    4: "f6b6454",
}

# ── Helpers ──────────────────────────────────────────────────────────────────
def scrape_modules(course_name: str, url: str) -> dict:
    """Returns {level: [module_names]} — exact same logic as scraper.py"""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            logger.warning(f"HTTP {resp.status_code} for {url}")
            return {}
        soup = BeautifulSoup(resp.content, 'html.parser')
        result = {}
        for level, year_id in YEAR_IDS.items():
            div = soup.find('div', {'data-id': year_id})
            if not div:
                logger.info(f"  Level {level} div not found")
                continue
            spans = div.find_all('span', {'data-text': True})
            names = [s['data-text'].strip() for s in spans if s['data-text'].strip()]
            if names:
                result[level] = names
                logger.info(f"  Level {level}: {names}")
        return result
    except Exception as e:
        logger.error(f"Scrape error {course_name}: {e}")
        return {}

def gemini(prompt: str) -> str:
    try:
        r = requests.post(
            f"{GEMINI_URL}?key={GEMINI_KEY}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        logger.warning(f"Gemini: {e}")
        return ""

def embed(text: str) -> list:
    return embedder.encode(text[:512]).tolist()

def devto_resources(module_name: str, n=3) -> list:
    try:
        r = requests.get("https://dev.to/api/articles",
                         params={"q": module_name, "per_page": n}, timeout=8)
        return [{"title": a.get("title",""), "url": a.get("url",""), "type": "article"}
                for a in r.json() if a.get("url")]
    except Exception as e:
        logger.warning(f"dev.to: {e}")
        return []

def save_course(session, name: str):
    session.run("""
        MERGE (c:Course {name: $name})
        ON CREATE SET c.university = 'NSBM Green University'
    """, name=name)

def save_module(session, course: str, name: str, level: int,
                desc: str, topics: list, resources: list, emb: list):
    # Module — ON CREATE only (never overwrites existing)
    session.run("""
        MERGE (m:Module {name: $name})
        ON CREATE SET
            m.level       = $level,
            m.description = $desc,
            m.embeddings  = $emb,
            m.embedding   = $emb
    """, name=name, level=level, desc=desc, emb=emb)

    # Course contains Module
    session.run("""
        MATCH (c:Course {name: $course}), (m:Module {name: $mod})
        MERGE (c)-[:CONTAINS]->(m)
    """, course=course, mod=name)

    # Topics
    for topic in topics:
        topic = topic.strip()
        if not topic: continue
        session.run("""
            MERGE (t:Topic {name: $name})
            ON CREATE SET t.embedding = $emb
            WITH t
            MATCH (m:Module {name: $mod})
            MERGE (m)-[:HAS_TOPIC]->(t)
        """, name=topic, emb=embed(topic), mod=name)

    # Resources
    for res in resources:
        if not res.get('url'): continue
        session.run("""
            MERGE (r:Resource {url: $url})
            ON CREATE SET r.title = $title, r.type = $rtype
            WITH r
            MATCH (m:Module {name: $mod})
            MERGE (m)-[:HAS_RESOURCE]->(r)
        """, url=res['url'], title=res['title'], rtype=res['type'], mod=name)

    logger.info(f"    ✓ {name} | level={level} | {len(topics)} topics | {len(resources)} resources")

def process_module(session, course: str, name: str, level: int):
    logger.info(f"  Processing: {name}")

    # Description
    desc = gemini(
        f"Write a concise 2-3 sentence academic description for the university module "
        f"'{name}' which is part of the '{course}' degree at NSBM Green University. "
        f"Focus on what students learn and practical skills gained. Plain text only."
    ) or f"This module covers key concepts and practical skills in {name}."
    time.sleep(2)

    # Topics (6)
    topics_raw = gemini(
        f"List exactly 6 specific learning topics for the university module '{name}' "
        f"(part of '{course}' degree). "
        f"Return ONLY a JSON array of strings like [\"Topic 1\", \"Topic 2\", ...]. No other text."
    )
    time.sleep(2)
    try:
        s = topics_raw.find('['); e = topics_raw.rfind(']') + 1
        topics = json.loads(topics_raw[s:e]) if s >= 0 else [name]
    except Exception:
        topics = [name]

    emb       = embed(f"{name} {desc}")
    resources = devto_resources(name, n=3)

    save_module(session, course, name, level, desc, topics, resources, emb)

# ── Main ─────────────────────────────────────────────────────────────────────
def run():
    logger.info("=== LearNexus — Scraping NEW Computing Courses ===")

    with driver.session() as session:
        # All existing module names — will NOT touch these
        existing_modules = {rec['name'] for rec in
                            session.run("MATCH (m:Module) RETURN m.name AS name")}
        existing_courses = {rec['name'] for rec in
                            session.run("MATCH (c:Course) RETURN c.name AS name")}
        logger.info(f"Existing: {len(existing_courses)} courses, {len(existing_modules)} modules")

        for course_name, url in NEW_COURSES.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"COURSE: {course_name}")
            logger.info(f"URL: {url}")

            # Scrape modules from NSBM (same scraper.py logic)
            modules_by_level = scrape_modules(course_name, url)
            if not modules_by_level:
                logger.warning(f"No modules found — skipping {course_name}")
                continue

            total = sum(len(v) for v in modules_by_level.values())
            logger.info(f"Scraped {total} modules across {len(modules_by_level)} levels")

            # Create course if new
            if course_name not in existing_courses:
                save_course(session, course_name)
                logger.info(f"Created new course: {course_name}")
            else:
                logger.info(f"Course already exists: {course_name}")

            # Process each module
            for level, module_names in sorted(modules_by_level.items()):
                for module_name in module_names:
                    if module_name in existing_modules:
                        # Still link to new course even if module exists
                        session.run("""
                            MATCH (c:Course {name: $course}), (m:Module {name: $mod})
                            MERGE (c)-[:CONTAINS]->(m)
                        """, course=course_name, mod=module_name)
                        logger.info(f"  LINKED (existing module): {module_name}")
                    else:
                        try:
                            process_module(session, course_name, module_name, level)
                            existing_modules.add(module_name)
                        except Exception as e:
                            logger.error(f"  ERROR: {module_name} — {e}")

    driver.close()

    # Final summary
    d2 = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with d2.session() as s:
        logger.info("\n=== FINAL DB STATE ===")
        r = s.run("MATCH (c:Course) OPTIONAL MATCH (c)-[:CONTAINS]->(m) RETURN c.name AS course, count(m) AS mcount ORDER BY c.name")
        for rec in r:
            logger.info(f"  {rec['course']}: {rec['mcount']} modules")
        tm = s.run("MATCH (m:Module) RETURN count(m) AS t").single()['t']
        tt = s.run("MATCH (t:Topic) RETURN count(t) AS t").single()['t']
        tr = s.run("MATCH (r:Resource) RETURN count(r) AS t").single()['t']
        logger.info(f"Total modules: {tm} | topics: {tt} | resources: {tr}")
    d2.close()

if __name__ == "__main__":
    run()
