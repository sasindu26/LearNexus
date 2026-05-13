"""Diagnose why the backfill isn't updating articles."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'models', 'pipeline'))

from py2neo import Graph
from deepseel2 import _is_placeholder_image  # type: ignore

graph = Graph("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))

articles = graph.run("""
    MATCH (a:Article)
    WHERE a.cover_image CONTAINS 'lh3.googleusercontent.com'
       OR a.url CONTAINS 'news.google.com'
       OR a.cover_image IS NULL
       OR trim(a.cover_image) = ''
       OR a.full_description IS NULL
       OR trim(a.full_description) = ''
       OR size(a.full_description) < 100
    RETURN a.url AS url, a.title AS title, a.source AS source,
           coalesce(a.cover_image, 'NULL') AS cover,
           size(coalesce(a.full_description, '')) AS desc_len,
           size(coalesce(a.description, '')) AS short_desc_len
    ORDER BY a.created_date DESC
""").data()

print(f"Found {len(articles)} articles matching query\n")
for i, a in enumerate(articles, 1):
    url = a["url"]
    is_gnews = "news.google.com" in url
    is_placeholder = _is_placeholder_image(a["cover"])
    cover_short = a["cover"][:60] if a["cover"] else "NULL"
    
    print(f"[{i}] {a['title'][:65]}")
    print(f"    Source: {a['source']}")
    print(f"    URL has google: {is_gnews}")
    print(f"    Cover: {cover_short}")
    print(f"    Cover is placeholder: {is_placeholder}")
    print(f"    Desc length: {a['desc_len']} chars")
    
    # Why matched the query?
    reasons = []
    if "lh3.googleusercontent.com" in a["cover"]:
        reasons.append("cover has lh3.googleusercontent")
    if "news.google.com" in url:
        reasons.append("URL has news.google.com")
    if a["cover"] == "NULL" or a["cover"].strip() == "":
        reasons.append("cover is NULL/empty")
    if a["desc_len"] < 100:
        reasons.append(f"desc too short ({a['desc_len']})")
    
    # Why NOT updated?
    blocks = []
    if not is_gnews:
        blocks.append("URL not google (step 1 skipped)")
    if not is_placeholder and a["cover"].strip() and a["cover"] != "NULL":
        blocks.append("cover not flagged as placeholder (step 3 skipped)")
    if a["desc_len"] >= 100:
        blocks.append(f"desc already {a['desc_len']} chars (step 4 skipped)")
    
    print(f"    MATCHED because: {', '.join(reasons)}")
    print(f"    NOT UPDATED because: {', '.join(blocks)}")
    print()
