from py2neo import Graph

g = Graph("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))

results = g.run("""
    MATCH (a:Article)
    WHERE a.source = 'google_news'
    RETURN a.title AS title, a.cover_image AS cover, a.url AS url
    LIMIT 10
""").data()

print(f"Found {len(results)} google_news articles\n")
for r in results:
    cover = r["cover"] or "NONE"
    print(f"TITLE: {r['title'][:70]}")
    print(f"COVER: {cover[:200]}")
    print(f"URL:   {r['url'][:120]}")
    print()

# Also check ALL sources for cover image patterns
print("\n--- Cover image domain breakdown ---")
all_covers = g.run("""
    MATCH (a:Article)
    WHERE a.cover_image IS NOT NULL
    RETURN a.source AS source, a.cover_image AS cover
""").data()

from urllib.parse import urlparse
domains = {}
for r in all_covers:
    try:
        domain = urlparse(r["cover"]).netloc
        key = f"{r['source']}|{domain}"
        domains[key] = domains.get(key, 0) + 1
    except:
        pass

for key, count in sorted(domains.items(), key=lambda x: -x[1]):
    print(f"  {key}: {count}")
