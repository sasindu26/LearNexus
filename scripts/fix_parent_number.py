from neo4j import GraphDatabase

d = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))
with d.session() as s:
    r = s.run('MATCH (s:Student) WHERE s.parent_number IS NULL SET s.parent_number = "" RETURN count(s) as fixed')
    print(f"Fixed {r.single()['fixed']} students")
d.close()
