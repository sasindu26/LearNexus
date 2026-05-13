from neo4j import GraphDatabase
import pandas as pd, os

d = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j','LearNexus1212'))
with d.session() as s:
    # 1. See full properties of one existing module
    print("=== SAMPLE MODULE STRUCTURE ===")
    r = s.run("""
        MATCH (c:Course)-[:CONTAINS]->(m:Module)-[:HAS_TOPIC]->(t:Topic)
        WHERE c.name = 'Computer Science'
        RETURN c.name AS course, m, collect(t.name)[0..3] AS sample_topics
        LIMIT 1
    """)
    rec = r.single()
    if rec:
        print(f"Course: {rec['course']}")
        props = dict(rec['m'])
        for k,v in props.items():
            if k == 'embeddings' or k == 'embedding':
                print(f"  {k}: [vector of {len(v)} dims]")
            else:
                print(f"  {k}: {str(v)[:120]}")
        print(f"  sample_topics: {rec['sample_topics']}")

    print("\n=== EXISTING MODULE NAMES IN DB ===")
    r2 = s.run("MATCH (m:Module) RETURN m.name AS name ORDER BY m.name")
    existing = {rec['name'] for rec in r2}
    print(f"Total: {len(existing)} modules in DB")

    print("\n=== COMPARING WITH SCRAPED CSVs ===")
    csv_dir = r'C:\Users\sasin\Videos\fyp\project (1)\Learnexus\mento_repo\extraction\courses_separated'
    for f in sorted(os.listdir(csv_dir)):
        if not f.endswith('_modules.csv'): continue
        course = f.replace('_modules.csv','').replace('_',' ')
        df = pd.read_csv(os.path.join(csv_dir, f))
        scraped = set(df['Modules'].dropna().str.strip())
        new_mods = scraped - existing
        print(f"\n{course}:")
        print(f"  Scraped: {len(scraped)} | Already in DB: {len(scraped - new_mods)} | NEW: {len(new_mods)}")
        for m in sorted(new_mods):
            print(f"    + NEW: {m}")
d.close()
