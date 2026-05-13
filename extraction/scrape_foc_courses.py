"""
LearNexus — Scrape ALL new FOC courses found at https://www.nsbm.ac.lk/foc-degree/
Handles BOTH layout types:
  1. Accordion (data-id divs) — used by original 5 courses
  2. Table/grid (Year 1/2/3 columns) — used by AI, Plymouth courses

Never touches existing 5 courses or their modules.
"""
import os, re, time, json, requests, logging
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(_ROOT, '.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('foc_scraper')

NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "LearNexus1212"
GEMINI_KEY     = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

driver   = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
embedder = SentenceTransformer('all-MiniLM-L6-v2')

# ── Original 5 — DO NOT TOUCH ────────────────────────────────────────────────
OLD_COURSES = {
    "Computer Networks", "Computer Science", "Data Science",
    "Management Information Systems", "Software Engineering",
}

# ── All FOC courses found at /foc-degree/ ────────────────────────────────────
ALL_FOC_COURSES = {
    "Artificial Intelligence (Plymouth)":
        "https://www.nsbm.ac.lk/course/bsc-hons-artificial-intelligence-plymouth-university-uk/",
    "Technology Management":
        "https://www.nsbm.ac.lk/course/bsc-honours-in-technology-management/",
    "Computer Security":
        "https://www.nsbm.ac.lk/course/bsc-hons-in-computer-security/",
    "Cyber Security (BIT)":
        "https://www.nsbm.ac.lk/course/bachelor-of-information-technology-major-in-cyber-security-vu/",
    "Software Engineering (Plymouth)":
        "https://www.nsbm.ac.lk/course/bsc-hons-software-engineering/",
    "Computer Science (Plymouth)":
        "https://www.nsbm.ac.lk/course/bsc-hons-computer-science/",
    "Computer Networks (Plymouth)":
        "https://www.nsbm.ac.lk/course/bsc-honours-in-computer-networks/",
    "Data Science (Plymouth)":
        "https://www.nsbm.ac.lk/course/bsc-hons-data-science-plymouth/",
}

# Old accordion year IDs (original scraper.py)
YEAR_IDS = {1: "1a46983", 2: "08e7c80", 3: "64138a9", 4: "f6b6454"}
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# ── Scraper — handles BOTH layouts ──────────────────────────────────────────
def scrape_modules(course_name: str, url: str) -> dict:
    """Returns {level(int): [module_names]}. Handles accordion AND Elementor year layout."""
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        soup = BeautifulSoup(resp.content, 'html.parser')

        result = {}

        # Method 1: Original accordion (data-id divs) — used by original 5 courses
        for level, year_id in YEAR_IDS.items():
            div = soup.find('div', {'data-id': year_id})
            if div:
                spans = div.find_all('span', {'data-text': True})
                names = [s['data-text'].strip() for s in spans if s['data-text'].strip()]
                if names:
                    result[level] = names

        if result:
            total = sum(len(v) for v in result.values())
            logger.info(f"  [Accordion] Found {total} modules")
            return result

        # Method 2: Elementor Year 1/2/3 h2 headings + icon-list items
        # Find all Year h2 headings
        year_h2s = []
        for h2 in soup.find_all('h2', class_='elementor-heading-title'):
            txt = h2.get_text(strip=True)
            m = re.match(r'year\s*(\d)', txt, re.I)
            if m:
                year_h2s.append((int(m.group(1)), h2))

        if year_h2s:
            # For each year, find the parent Elementor section and get its icon-list items
            # The page has 3 separate sections for Year 1, Year 2, Year 3
            # Each section has a heading widget + list widget side by side
            for level, h2 in year_h2s:
                # Get the containing elementor-section
                section = h2.find_parent('section') or \
                          h2.find_parent('div', class_=re.compile(r'elementor-top-section|elementor-inner-section'))
                if not section:
                    continue

                # Find all icon-list items in THIS section only
                # Filter out duplicates from nested sections
                items = section.find_all('span', class_='elementor-icon-list-text')
                names = []
                seen = set()
                for item in items:
                    name = item.get_text(strip=True).lstrip('> ').strip()
                    if name and name not in seen and len(name) > 3:
                        # Skip if it's a concatenated string (contains '>')
                        if '>' not in name:
                            seen.add(name)
                            names.append(name)

                if names:
                    result[level] = names
                    logger.info(f"  Year {level}: {names}")

        if result:
            total = sum(len(v) for v in result.values())
            logger.info(f"  [Elementor] Found {total} modules")
            return result

        logger.warning(f"  No modules found for {course_name}")
        return {}

    except Exception as e:
        logger.error(f"Scrape error {course_name}: {e}")
        return {}

# ── AI helpers ────────────────────────────────────────────────────────────────
def gemini(prompt: str) -> str:
    try:
        r = requests.post(f"{GEMINI_URL}?key={GEMINI_KEY}",
                          json={"contents": [{"parts": [{"text": prompt}]}]},
                          timeout=30)
        r.raise_for_status()
        return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
    except Exception as e:
        logger.warning(f"Gemini: {e}")
        return ""

def embed(text: str) -> list:
    return embedder.encode(text[:512]).tolist()

def devto_resources(name: str, n=3) -> list:
    try:
        r = requests.get("https://dev.to/api/articles",
                         params={"q": name, "per_page": n}, timeout=8)
        return [{"title": a.get("title",""), "url": a.get("url",""), "type": "article"}
                for a in r.json() if a.get("url")]
    except:
        return []

# ── DB save ───────────────────────────────────────────────────────────────────
def save_course(session, name: str):
    session.run("""
        MERGE (c:Course {name: $name})
        ON CREATE SET c.university = 'NSBM Green University'
    """, name=name)

def save_module(session, course: str, name: str, level: int,
                desc: str, topics: list, resources: list, emb: list):
    session.run("""
        MERGE (m:Module {name: $name})
        ON CREATE SET m.level=$lv, m.description=$desc,
                      m.embeddings=$emb, m.embedding=$emb
    """, name=name, lv=level, desc=desc, emb=emb)

    session.run("""
        MATCH (c:Course {name:$c}), (m:Module {name:$m})
        MERGE (c)-[:CONTAINS]->(m)
    """, c=course, m=name)

    for topic in topics:
        topic = topic.strip()
        if not topic: continue
        session.run("""
            MERGE (t:Topic {name:$n}) ON CREATE SET t.embedding=$e
            WITH t MATCH (m:Module {name:$m}) MERGE (m)-[:HAS_TOPIC]->(t)
        """, n=topic, e=embed(topic), m=name)

    for res in resources:
        if not res.get('url'): continue
        session.run("""
            MERGE (r:Resource {url:$u}) ON CREATE SET r.title=$t, r.type=$rt
            WITH r MATCH (m:Module {name:$m}) MERGE (m)-[:HAS_RESOURCE]->(r)
        """, u=res['url'], t=res['title'], rt=res['type'], m=name)

    logger.info(f"    ✓ {name} | L{level} | {len(topics)} topics | {len(resources)} res")

def process_module(session, course: str, name: str, level: int):
    desc = gemini(
        f"Write a concise 2-3 sentence academic description for the university module "
        f"'{name}' which is part of the '{course}' degree at NSBM Green University. "
        f"Focus on what students learn and practical skills gained. Plain text only."
    ) or f"This module covers key concepts and practical skills in {name}."
    time.sleep(2)

    topics_raw = gemini(
        f"List exactly 6 specific learning topics for the university module '{name}' "
        f"(part of '{course}' degree). "
        f"Return ONLY a JSON array of strings. No other text."
    )
    time.sleep(2)
    try:
        s = topics_raw.find('['); e = topics_raw.rfind(']') + 1
        topics = json.loads(topics_raw[s:e]) if s >= 0 else [name]
    except:
        topics = [name]

    emb       = embed(f"{name} {desc}")
    resources = devto_resources(name, n=3)
    save_module(session, course, name, level, desc, topics, resources, emb)

# ── Main ──────────────────────────────────────────────────────────────────────
def run():
    logger.info("=== LearNexus — FOC New Courses Pipeline ===")

    with driver.session() as session:
        existing_modules = {r['name'] for r in session.run(
            "MATCH (m:Module) RETURN m.name AS name")}
        existing_courses = {r['name'] for r in session.run(
            "MATCH (c:Course) RETURN c.name AS name")}
        logger.info(f"DB: {len(existing_courses)} courses, {len(existing_modules)} modules")

        for course_name, url in ALL_FOC_COURSES.items():
            logger.info(f"\n{'='*60}")
            logger.info(f"COURSE: {course_name}")

            mods_by_level = scrape_modules(course_name, url)
            if not mods_by_level:
                logger.warning(f"  No modules scraped — skipping")
                continue

            total = sum(len(v) for v in mods_by_level.values())
            logger.info(f"  Total scraped: {total} modules")

            if course_name not in existing_courses:
                save_course(session, course_name)
                logger.info(f"  Created course: {course_name}")

            for level, names in sorted(mods_by_level.items()):
                for name in names:
                    if name in existing_modules:
                        # Just link to new course — don't regenerate content
                        session.run("""
                            MATCH (c:Course {name:$c}), (m:Module {name:$m})
                            MERGE (c)-[:CONTAINS]->(m)
                        """, c=course_name, m=name)
                        logger.info(f"  LINKED (exists): {name}")
                    else:
                        try:
                            process_module(session, course_name, name, level)
                            existing_modules.add(name)
                        except Exception as e:
                            logger.error(f"  ERROR: {name} — {e}")

    driver.close()

    # Summary
    d2 = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with d2.session() as s:
        logger.info("\n=== FINAL DB ===")
        for r in s.run("MATCH (c:Course) OPTIONAL MATCH (c)-[:CONTAINS]->(m) RETURN c.name AS c, count(m) AS n ORDER BY c.name"):
            logger.info(f"  {r['c']}: {r['n']} modules")
        tm = s.run("MATCH (m:Module) RETURN count(m) AS t").single()['t']
        tt = s.run("MATCH (t:Topic) RETURN count(t) AS t").single()['t']
        logger.info(f"Total: {tm} modules | {tt} topics")
    d2.close()

if __name__ == "__main__":
    run()
