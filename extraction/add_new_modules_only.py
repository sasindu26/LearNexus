"""
LearNexus — Add NEW modules only (never touches existing DB data)
Reads existing module structure from DB and replicates it for new modules.
New modules found from scraped CSVs vs DB comparison:
 - "Detection & Response" (Computer Networks)
 - "Intrusion Prevention"  (Computer Networks)
Note: These are splits of the original "Intrusion Prevention, Detection & Response"
"""
import os, time, json, requests, logging
from dotenv import load_dotenv
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(_ROOT, '.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('add_new_modules')

NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "LearNexus1212"
GEMINI_KEY     = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL     = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

driver   = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
embedder = SentenceTransformer('all-MiniLM-L6-v2')

CSV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'courses_separated')

# ── Helpers ──────────────────────────────────────────────────────────────────
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
        logger.warning(f"Gemini error: {e}")
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
        logger.warning(f"dev.to error: {e}")
        return []

def get_course_max_order(session, course_name: str) -> int:
    """Get the highest existing module order in a course to append after."""
    r = session.run("""
        MATCH (c:Course {name: $course})-[:CONTAINS]->(m:Module)
        RETURN max(coalesce(m.order, 0)) AS max_order
    """, course=course_name)
    rec = r.single()
    return (rec['max_order'] or 0) if rec else 0

def save_new_module(session, course_name: str, module_name: str,
                    level: int, order: int, description: str,
                    topics: list, resources: list, emb: list):
    """Save a brand new module — never overwrites existing nodes."""

    # Module node (only creates if doesn't exist)
    session.run("""
        MERGE (m:Module {name: $name})
        ON CREATE SET
            m.level       = $level,
            m.order       = $order,
            m.description = $desc,
            m.embeddings  = $emb,
            m.embedding   = $emb
    """, name=module_name, level=level, order=order, desc=description, emb=emb)

    # Course -[:CONTAINS]-> Module
    session.run("""
        MATCH (c:Course {name: $course}), (m:Module {name: $mod})
        MERGE (c)-[:CONTAINS]->(m)
    """, course=course_name, mod=module_name)

    # Topics → HAS_TOPIC
    for topic in topics:
        topic = topic.strip()
        if not topic:
            continue
        t_emb = embed(topic)
        session.run("""
            MERGE (t:Topic {name: $name})
            ON CREATE SET t.embedding = $emb
            WITH t
            MATCH (m:Module {name: $mod})
            MERGE (m)-[:HAS_TOPIC]->(t)
        """, name=topic, emb=t_emb, mod=module_name)

    # Resources → HAS_RESOURCE
    for res in resources:
        if not res.get('url'):
            continue
        session.run("""
            MERGE (r:Resource {url: $url})
            ON CREATE SET r.title = $title, r.type = $rtype
            WITH r
            MATCH (m:Module {name: $mod})
            MERGE (m)-[:HAS_RESOURCE]->(r)
        """, url=res['url'], title=res['title'], rtype=res['type'], mod=module_name)

    logger.info(f"  ✓ Saved: '{module_name}' | level={level} | {len(topics)} topics | {len(resources)} resources")

def process_new_module(session, course_name: str, module_name: str, level: int, order: int):
    """Generate all content for a new module and save it."""
    logger.info(f"\n  Generating content for: '{module_name}' ({course_name})")

    # 1. Rich description
    desc = gemini(
        f"Write a concise 2-3 sentence academic description for the university module "
        f"'{module_name}' which is part of the '{course_name}' degree at NSBM Green University. "
        f"Focus on what students will learn and key practical skills they will gain. Plain text only, no bullet points."
    ) or f"This module covers key concepts and practical skills in {module_name}."
    time.sleep(2)

    # 2. Topics (6 specific topics)
    topics_raw = gemini(
        f"List exactly 6 specific learning topics for the university module '{module_name}' "
        f"(part of the '{course_name}' degree). "
        f"Return ONLY a JSON array of strings like [\"Topic 1\", \"Topic 2\", ...]. No other text."
    )
    time.sleep(2)
    try:
        s = topics_raw.find('[')
        e = topics_raw.rfind(']') + 1
        topics = json.loads(topics_raw[s:e]) if s >= 0 else [module_name]
    except Exception:
        topics = [module_name]

    # 3. Embedding (same format as existing modules — 384 dims via all-MiniLM-L6-v2)
    emb = embed(f"{module_name} {desc}")

    # 4. dev.to resources
    resources = devto_resources(module_name, n=3)

    # 5. Save
    save_new_module(session, course_name, module_name, level, order, desc, topics, resources, emb)
    return desc, topics

# ── Main ─────────────────────────────────────────────────────────────────────
def run():
    logger.info("=== LearNexus — Add NEW modules only (safe, no existing data touched) ===")

    import pandas as pd

    with driver.session() as session:
        # Get all existing module names from DB
        existing = {rec['name'] for rec in session.run(
            "MATCH (m:Module) RETURN m.name AS name"
        )}
        logger.info(f"Existing modules in DB: {len(existing)}")

        # Get existing courses
        existing_courses = {rec['name'] for rec in session.run(
            "MATCH (c:Course) RETURN c.name AS name"
        )}

        # Read each scraped CSV
        for fname in sorted(os.listdir(CSV_DIR)):
            if not fname.endswith('_modules.csv'):
                continue

            course_name = fname.replace('_modules.csv', '').replace('_', ' ')
            df = pd.read_csv(os.path.join(CSV_DIR, fname))
            scraped_modules = [m.strip() for m in df['Modules'].dropna() if m.strip()]

            new_modules = [m for m in scraped_modules if m not in existing]

            if not new_modules:
                logger.info(f"\n{course_name}: no new modules — skipping")
                continue

            logger.info(f"\n{course_name}: {len(new_modules)} new module(s) to add")

            # Ensure course exists
            if course_name not in existing_courses:
                session.run("""
                    MERGE (c:Course {name: $name})
                    ON CREATE SET c.university = 'NSBM Green University'
                """, name=course_name)
                logger.info(f"  Created new course: {course_name}")

            # Infer level from position in scraped list
            # scraper.py uses Level 1 → Level 4 divs
            # We'll read level from the original CSV
            main_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    'multiple_courses_modules2.csv')
            level_map = {}
            try:
                main_df = pd.read_csv(main_csv)
                course_df = main_df[main_df['Course'] == course_name]
                for _, row in course_df.iterrows():
                    for lv in range(1, 5):
                        col = f"Level {lv}"
                        if col in main_df.columns and pd.notna(row.get(col)):
                            level_map[str(row[col]).strip()] = lv
            except Exception as e:
                logger.warning(f"  Could not read level map: {e}")

            base_order = get_course_max_order(session, course_name)

            for i, module_name in enumerate(new_modules):
                level = level_map.get(module_name, 3)  # default level 3 if unknown
                order = base_order + i + 1
                try:
                    desc, topics = process_new_module(
                        session, course_name, module_name, level, order
                    )
                    existing.add(module_name)
                except Exception as e:
                    logger.error(f"  ERROR processing '{module_name}': {e}")

    driver.close()

    # Final summary
    d2 = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with d2.session() as s:
        total_m = s.run("MATCH (m:Module) RETURN count(m) AS t").single()['t']
        total_t = s.run("MATCH (t:Topic) RETURN count(t) AS t").single()['t']
        total_r = s.run("MATCH (r:Resource) RETURN count(r) AS t").single()['t']
        logger.info(f"\n=== DONE ===")
        logger.info(f"Total modules:   {total_m}")
        logger.info(f"Total topics:    {total_t}")
        logger.info(f"Total resources: {total_r}")
    d2.close()

if __name__ == "__main__":
    run()
