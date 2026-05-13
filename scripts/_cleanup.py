"""Delete articles with placeholder Google images that can't be fixed."""
from py2neo import Graph
g = Graph("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))

# Count first
count = g.run("""
    MATCH (a:Article)
    WHERE a.cover_image CONTAINS 'lh3.googleusercontent.com'
    RETURN count(a) AS c
""").data()[0]["c"]
print(f"Found {count} articles with Google placeholder images")

# Delete them (and their relationships)
result = g.run("""
    MATCH (a:Article)
    WHERE a.cover_image CONTAINS 'lh3.googleusercontent.com'
    DETACH DELETE a
    RETURN count(a) AS deleted
""").data()
print(f"Deleted {result[0]['deleted']} articles")
print("These will be replaced by properly-scraped articles on next pipeline run.")
