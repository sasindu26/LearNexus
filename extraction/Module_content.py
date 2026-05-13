"""
Find modules in NEW courses that have 0 topics, then generate topics + resources.
NEW courses = Artificial Intelligence (Plymouth), Computer Security
OLD courses (untouched) = Computer Networks, Computer Science, Data Science,
                          Management Information Systems, Software Engineering
"""
import os, time, json, requests, logging
from dotenv import load_dotenv
from neo4j import GraphDatabase
from sentence_transformers import SentenceTransformer

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
load_dotenv(dotenv_path=os.path.join(_ROOT, '.env'))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger('fix_new_modules')

driver   = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))
embedder = SentenceTransformer('all-MiniLM-L6-v2')

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

NEW_COURSES = ["Artificial Intelligence (Plymouth)", "Computer Security"]

def gemini(prompt: str) -> str:
    for attempt in range(3):
        try:
            r = requests.post(f"{GEMINI_URL}?key={GEMINI_KEY}",
                              json={"contents": [{"parts": [{"text": prompt}]}]},
                              timeout=30)
            r.raise_for_status()
            return r.json()['candidates'][0]['content']['parts'][0]['text'].strip()
        except Exception as e:
            logger.warning(f"Gemini attempt {attempt+1}: {e}")
            time.sleep(5 * (attempt + 1))  # 5s, 10s, 15s backoff
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
    with driver.session() as s:
        # Find modules in new courses with FEWER than 4 topics (includes rate-limited ones)
        result = s.run("""
            MATCH (c:Course)-[:CONTAINS]->(m:Module)
            WHERE c.name IN $courses
            WITH c, m, size([(m)-[:HAS_TOPIC]->() | 1]) AS topic_count
            WHERE topic_count < 4
            RETURN m.name AS name, m.level AS level, c.name AS course, topic_count
            ORDER BY c.name, m.level, m.name
        """, courses=NEW_COURSES)

        modules = [dict(r) for r in result]
        logger.info(f"Modules with < 4 topics in new courses: {len(modules)}")
        for m in modules:
            logger.info(f"  [{m['course']}] Level {m['level']}: {m['name']}")

        if not modules:
            logger.info("All new course modules already have topics!")
            return

        for mod in modules:
            name   = mod['name']
            course = mod['course']
            level  = mod.get('level') or 1
            logger.info(f"\n  Processing: '{name}' ({course})")

            # 1. Rich description
            desc = gemini(
                f"Write a concise 2-3 sentence academic description for the university module "
                f"'{name}' which is part of the '{course}' degree at NSBM Green University. "
                f"Focus on what students learn and key practical skills gained. Plain text only."
            ) or f"This module covers key concepts and practical skills in {name}."
            time.sleep(2)

            # 2. Update description + embedding
            emb = embed(f"{name} {desc}")
            s.run("""
                MATCH (m:Module {name: $name})
                SET m.description = $desc, m.embeddings = $emb, m.embedding = $emb
            """, name=name, desc=desc, emb=emb)

            # 3. Generate 6 topics
            topics_raw = gemini(
                f"List exactly 6 specific learning topics for the university module '{name}' "
                f"(part of '{course}' degree). "
                f"Return ONLY a JSON array of strings like [\"Topic 1\", \"Topic 2\", ...]. No other text."
            )
            time.sleep(2)
            try:
                st = topics_raw.find('['); en = topics_raw.rfind(']') + 1
                topics = json.loads(topics_raw[st:en]) if st >= 0 else [name]
            except:
                topics = [name]

            # 4. Save topics → HAS_TOPIC
            for topic in topics:
                topic = topic.strip()
                if not topic: continue
                t_emb = embed(topic)
                s.run("""
                    MERGE (t:Topic {name: $n})
                    ON CREATE SET t.embedding = $e
                    WITH t
                    MATCH (m:Module {name: $mod})
                    MERGE (m)-[:HAS_TOPIC]->(t)
                """, n=topic, e=t_emb, mod=name)

            # 5. dev.to resources → HAS_RESOURCE
            resources = devto_resources(name, n=3)
            for res in resources:
                if not res.get('url'): continue
                s.run("""
                    MERGE (r:Resource {url: $u})
                    ON CREATE SET r.title = $t, r.type = $rt
                    WITH r
                    MATCH (m:Module {name: $mod})
                    MERGE (m)-[:HAS_RESOURCE]->(r)
                """, u=res['url'], t=res['title'], rt=res['type'], mod=name)

            logger.info(f"    ✓ '{name}' | desc updated | {len(topics)} topics | {len(resources)} resources")

    driver.close()

    # Final verification — show topic counts for new courses only
    d2 = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))
    with d2.session() as s:
        logger.info("\n=== NEW COURSE MODULE STATS ===")
        r = s.run("""
            MATCH (c:Course)-[:CONTAINS]->(m:Module)
            WHERE c.name IN $courses
            OPTIONAL MATCH (m)-[:HAS_TOPIC]->(t)
            OPTIONAL MATCH (m)-[:HAS_RESOURCE]->(res)
            RETURN c.name AS course, m.name AS module, m.level AS level,
                   count(DISTINCT t) AS topics, count(DISTINCT res) AS resources
            ORDER BY c.name, m.level, m.name
        """, courses=NEW_COURSES)
        cur_course = None
        for rec in r:
            if rec['course'] != cur_course:
                cur_course = rec['course']
                logger.info(f"\n  {cur_course}:")
            logger.info(f"    L{rec['level']} {rec['module']}: {rec['topics']} topics | {rec['resources']} res")
    d2.close()
    logger.info("\n=== Done ===")

if __name__ == "__main__":
    run()
