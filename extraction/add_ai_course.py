"""
Add BSc (Hons) Artificial Intelligence (Plymouth) — 3 years
Modules taken directly from NSBM course page screenshot.
Never touches existing data.
"""
import os, time, json, requests, logging
from dotenv import load_dotenv
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(_ROOT, '.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('ai_course')

driver   = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))
embedder = SentenceTransformer('all-MiniLM-L6-v2')

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

COURSE_NAME = "Artificial Intelligence (Plymouth)"

# Exact modules from the NSBM page screenshot
MODULES = {
    1: [
        "Introduction to Computer Science",
        "Mathematics for Computing",
        "Fundamentals of Artificial Intelligence",
        "Programming Fundamentals",
        "Personal Development and Communication Skills",
        "Database Management Systems",
        "Algorithms and Data Structures",
        "IT Solutions Architecture",
        "Web and Mobile Development",
        "Fundamentals of Data Communication and Security",
        "Object-Oriented Programming with C#",
    ],
    2: [
        "Advanced Mathematics for AI",
        "Information Management and Retrieval",
        "Algorithms for Machine Learning",
        "Computing Group Project",
        "Evolutionary Computing",
        "Computer Vision & Image Processing",
    ],
    3: [
        "AI and Machine Learning",
        "Full Stack Development",
        "Computing Individual Project",
        "Natural Language Processing",
        "Big Data Analytics",
    ],
}

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

def run():
    with driver.session() as session:
        existing = {r['name'] for r in session.run("MATCH (m:Module) RETURN m.name AS name")}
        logger.info(f"Existing modules: {len(existing)}")

        # Create course
        session.run("""
            MERGE (c:Course {name: $name})
            ON CREATE SET c.university = 'Plymouth University', c.duration = '3 Years'
        """, name=COURSE_NAME)
        logger.info(f"Course: {COURSE_NAME}")

        for level, module_names in MODULES.items():
            logger.info(f"\n--- Year {level} ---")
            for name in module_names:
                if name in existing:
                    # Just link to this course
                    session.run("""
                        MATCH (c:Course {name:$c}), (m:Module {name:$m})
                        MERGE (c)-[:CONTAINS]->(m)
                    """, c=COURSE_NAME, m=name)
                    logger.info(f"  LINKED (exists): {name}")
                    continue

                logger.info(f"  NEW: {name}")
                desc = gemini(
                    f"Write a concise 2-3 sentence academic description for the university module "
                    f"'{name}' which is part of the 'BSc (Hons) Artificial Intelligence' degree "
                    f"at Plymouth University / NSBM Green University. "
                    f"Focus on what students learn and practical skills. Plain text only."
                ) or f"This module covers key concepts and practical skills in {name}."
                time.sleep(2)

                topics_raw = gemini(
                    f"List exactly 6 specific learning topics for the university module '{name}' "
                    f"(BSc Artificial Intelligence degree). "
                    f"Return ONLY a JSON array of strings. No other text."
                )
                time.sleep(2)
                try:
                    s = topics_raw.find('['); e = topics_raw.rfind(']') + 1
                    topics = json.loads(topics_raw[s:e]) if s >= 0 else [name]
                except:
                    topics = [name]

                emb = embed(f"{name} {desc}")
                resources = devto_resources(name, n=3)

                # Save module
                session.run("""
                    MERGE (m:Module {name: $name})
                    ON CREATE SET m.level=$lv, m.description=$desc,
                                  m.embeddings=$emb, m.embedding=$emb
                """, name=name, lv=level, desc=desc, emb=emb)

                session.run("""
                    MATCH (c:Course {name:$c}), (m:Module {name:$m})
                    MERGE (c)-[:CONTAINS]->(m)
                """, c=COURSE_NAME, m=name)

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

                existing.add(name)
                logger.info(f"    ✓ {name} | L{level} | {len(topics)} topics | {len(resources)} res")

    driver.close()

    # Final summary
    d2 = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))
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
