"""Remove unwanted duplicate Plymouth courses + Technology Management from DB.
Keeps: original 5 + Computer Security + Artificial Intelligence (Plymouth)
Removes course nodes + exclusive modules + orphaned topics/resources.
"""
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))

REMOVE_COURSES = [
    "Computer Networks (Plymouth)",
    "Computer Science (Plymouth)",
    "Data Science (Plymouth)",
    "Software Engineering (Plymouth)",
    "Technology Management",
]

KEEP_COURSES = [
    "Computer Networks", "Computer Science", "Data Science",
    "Management Information Systems", "Software Engineering",
    "Computer Security", "Artificial Intelligence (Plymouth)",
    "Cyber Security (BIT)",
]

with driver.session() as s:
    for course in REMOVE_COURSES:
        # Delete modules ONLY linked to this course (not shared with kept courses)
        s.run("""
            MATCH (c:Course {name: $name})-[:CONTAINS]->(m:Module)
            WHERE NOT EXISTS {
                MATCH (other:Course)-[:CONTAINS]->(m)
                WHERE other.name <> $name
            }
            DETACH DELETE m
        """, name=course)

        # Delete the course itself
        s.run("MATCH (c:Course {name: $name}) DETACH DELETE c", name=course)
        print(f"Removed: {course}")

    # Clean orphaned topics
    r = s.run("MATCH (t:Topic) WHERE NOT (()-[:HAS_TOPIC]->(t)) DELETE t RETURN count(*) AS n")
    print(f"Orphaned topics removed: {r.single()['n']}")

    # Clean orphaned resources
    r = s.run("MATCH (r:Resource) WHERE NOT (()-[:HAS_RESOURCE]->(r)) DELETE r RETURN count(*) AS n")
    print(f"Orphaned resources removed: {r.single()['n']}")

    # Final state
    print("\n=== REMAINING COURSES ===")
    for rec in s.run("MATCH (c:Course) OPTIONAL MATCH (c)-[:CONTAINS]->(m) RETURN c.name AS c, count(m) AS n ORDER BY c.name"):
        print(f"  {rec['c']}: {rec['n']} modules")

    tm = s.run("MATCH (m:Module) RETURN count(m) AS t").single()['t']
    tt = s.run("MATCH (t:Topic) RETURN count(t) AS t").single()['t']
    print(f"\nTotal: {tm} modules | {tt} topics")

driver.close()
