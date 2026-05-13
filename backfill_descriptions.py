"""
Backfill full_description for existing articles that have short/plain descriptions.
Run once: python backfill_descriptions.py
"""
import sys
import os
# Fix Unicode on Windows console
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'models', 'pipeline'))

from py2neo import Graph
from deepseel2 import scrape_full_description
import time

graph = Graph("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))

# Only backfill dev.to articles — news sites block scraping
articles = graph.run("""
    MATCH (a:Article)
    WHERE a.url IS NOT NULL AND a.url <> ''
      AND a.source = 'dev.to'
      AND (a.full_description IS NULL OR size(a.full_description) < 500)
    RETURN toString(elementId(a)) as id, a.url as url, a.title as title,
           coalesce(a.full_description, '') as full_description
    ORDER BY a.published_at DESC
    LIMIT 200
""").data()

print(f"Found {len(articles)} dev.to articles to backfill")

success = 0
failed = 0

for i, article in enumerate(articles):
    url = article['url']
    title = article['title'][:60] if article['title'] else '(no title)'
    print(f"[{i+1}/{len(articles)}] {title}")

    try:
        html = scrape_full_description(url)
        if html and len(html) > 200:
            graph.run("""
                MATCH (a:Article)
                WHERE toString(elementId(a)) = $id
                SET a.full_description = $html
            """, id=article['id'], html=html)
            print(f"  -> OK ({len(html)} chars)")
            success += 1
        else:
            print(f"  -> skipped (too short or empty)")
            failed += 1
    except Exception as e:
        print(f"  -> ERROR: {e}")
        failed += 1

    # Be polite to servers
    time.sleep(0.5)

print(f"\nDone. Success: {success}, Failed/skipped: {failed}")
