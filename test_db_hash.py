from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'LearNexus1212'))
res = driver.execute_query("MATCH (s:Student {email: 'amilanishantha1526@gmail.com'}) RETURN s.password_hash")[0]
for r in res: print(r)
