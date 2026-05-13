from neo4j import GraphDatabase
d = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j','LearNexus1212'))
new_courses = ["Artificial Intelligence (Plymouth)", "Computer Security"]
with d.session() as s:
    r = s.run("""
        MATCH (c:Course)-[:CONTAINS]->(m:Module)
        WHERE c.name IN $courses
        OPTIONAL MATCH (m)-[:HAS_TOPIC]->(t)
        OPTIONAL MATCH (m)-[:HAS_RESOURCE]->(res)
        RETURN c.name AS course, m.name AS module, m.level AS level,
               count(DISTINCT t) AS topics, count(DISTINCT res) AS resources
        ORDER BY c.name, m.level, m.name
    """, courses=new_courses)
    cur = None
    for rec in r:
        if rec['course'] != cur:
            cur = rec['course']
            print(f'\n=== {cur} ===')
        status = "OK" if rec['topics'] > 0 else "MISSING"
        print(f"  L{rec['level']} | {rec['topics']} topics | {rec['resources']} res {status} | {rec['module']}")
d.close()
