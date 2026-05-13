"""
Append new courses (AI Plymouth, Computer Security) from Neo4j into the existing
multiple_courses_modules2.csv so break_modules.ipynb can see them.
"""
import pandas as pd
from neo4j import GraphDatabase

CSV_PATH = r'C:\Users\sasin\Videos\fyp\project (1)\Learnexus\mento_repo\extraction\multiple_courses_modules2.csv'

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))
NEW_COURSES = ["Artificial Intelligence (Plymouth)", "Computer Security"]

rows = []
with driver.session() as s:
    for course in NEW_COURSES:
        # Get modules grouped by level
        result = s.run("""
            MATCH (c:Course {name:$course})-[:CONTAINS]->(m:Module)
            RETURN m.name AS name, coalesce(m.level, 1) AS level
            ORDER BY m.level, m.name
        """, course=course)

        by_level = {}
        for rec in result:
            lv = int(rec['level']) if rec['level'] else 1
            by_level.setdefault(lv, []).append(rec['name'])

        # Build rows — one row per module, placed in the correct level column
        max_per_level = max(len(v) for v in by_level.values()) if by_level else 0
        max_len = max_per_level

        # Pad all levels to same length
        for lv in range(1, 5):
            by_level.setdefault(lv, [])

        # Zip across levels — one row per "slot"
        max_rows = max(len(by_level[lv]) for lv in range(1, 5))
        for i in range(max_rows):
            row = {
                'Level 1': by_level[1][i] if i < len(by_level[1]) else None,
                'Level 2': by_level[2][i] if i < len(by_level[2]) else None,
                'Level 3': by_level[3][i] if i < len(by_level[3]) else None,
                'Level 4': by_level[4][i] if i < len(by_level[4]) else None,
                'Course':  course,
            }
            rows.append(row)

        total = sum(len(v) for v in by_level.values())
        print(f"{course}: {total} modules added to CSV")

driver.close()

# Load existing CSV and append (skip if already there)
df_existing = pd.read_csv(CSV_PATH)
existing_courses = df_existing['Course'].unique().tolist()

new_rows = [r for r in rows if r['Course'] not in existing_courses]
if not new_rows:
    print("Courses already in CSV — nothing to add.")
else:
    df_new = pd.DataFrame(new_rows, columns=['Level 1','Level 2','Level 3','Level 4','Course'])
    df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    df_combined.to_csv(CSV_PATH, index=False)
    print(f"\nCSV updated: {len(df_existing)} -> {len(df_combined)} rows")
    print(f"Courses now in CSV: {df_combined['Course'].unique().tolist()}")
