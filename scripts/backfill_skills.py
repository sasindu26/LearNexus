"""One-time script to extract skills from all modules/topics and populate the skill graph."""
import os
import sys

# Ensure project root is on path
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _root not in sys.path:
    sys.path.insert(0, _root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_root, '.env'))

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

import argparse
from services.skill_graph_service import extract_and_store_skills
from services.neo4j_service import get_session


def verify():
    with get_session() as session:
        skill_count = session.run("MATCH (sk:Skill) RETURN count(sk) AS n").single()["n"]
        teaches_count = session.run("MATCH ()-[:TEACHES]->(:Skill) RETURN count(*) AS n").single()["n"]
        covers_count = session.run("MATCH ()-[:COVERS]->(:Skill) RETURN count(*) AS n").single()["n"]
        print(f"\nVerification:")
        print(f"  Skill nodes : {skill_count}")
        print(f"  TEACHES rels: {teaches_count}")
        print(f"  COVERS  rels: {covers_count}")

        samples = session.run(
            "MATCH (m:Module)-[:TEACHES]->(s:Skill) RETURN m.name, collect(s.name) AS skills LIMIT 5"
        ).data()
        print("\nSample module → skills:")
        for row in samples:
            print(f"  {row['m.name']}: {row['skills']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Only show counts, do not write")
    args = parser.parse_args()

    if args.dry_run:
        with get_session() as session:
            m = session.run("MATCH (m:Module) WHERE m.description IS NOT NULL RETURN count(m) AS n").single()["n"]
            t = session.run("MATCH (t:Topic) RETURN count(t) AS n").single()["n"]
        print(f"Dry-run: would process {m} modules and {t} topics")
    else:
        extract_and_store_skills()
        verify()
