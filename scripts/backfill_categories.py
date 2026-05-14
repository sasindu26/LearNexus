"""
Backfill existing articles in Neo4j with:
1. Proper category tags (auto-categorized from title/description)
2. Clean short_description (HTML stripped)
"""
import sys, os, re

# Add pipeline dir for imports
_pipeline_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models', 'pipeline'))
sys.path.insert(0, _pipeline_dir)

from py2neo import Graph  # type: ignore
from deepseel2 import categorize_article  # type: ignore

graph = Graph("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))


def strip_html(text):
    if not text:
        return ''
    clean = re.sub(r'<[^>]+>', ' ', text)
    return ' '.join(clean.split()).strip()


def main():
    # Fetch all articles
    articles = graph.run("""
        MATCH (a:Article)
        RETURN a.url as url,
               a.title as title,
               a.tags as tags,
               a.description as description,
               a.full_description as full_description,
               a.short_description as short_description
    """).data()

    print(f"Found {len(articles)} articles to backfill")
    print("=" * 60)

    updated = 0

    for i, art in enumerate(articles):
        url = art.get('url', '')
        title = art.get('title', '')
        old_tags = art.get('tags') or []
        desc = art.get('description', '') or ''
        full_desc = art.get('full_description', '') or ''
        existing_short = art.get('short_description', '') or ''

        if not url or not title:
            continue

        # 1. Auto-categorize
        new_tags = categorize_article(title, old_tags, desc)

        # 2. Create short_description if missing or if it contains HTML
        if not existing_short or ('<' in existing_short and '>' in existing_short):
            raw = full_desc or desc
            short = strip_html(raw)[:300]
        else:
            short = existing_short

        # Check if anything changed
        tags_changed = set(new_tags) != set(t.lower().strip() for t in old_tags if t)
        short_changed = short != existing_short

        if tags_changed or short_changed:
            graph.run("""
                MATCH (a:Article {url: $url})
                SET a.tags = $tags,
                    a.short_description = $short
            """, url=url, tags=new_tags, short=short)

            # Also create Tag nodes for new tags
            for tag in new_tags:
                if tag:
                    graph.run("""
                        MERGE (t:Tag {name: $tag})
                        WITH t
                        MATCH (a:Article {url: $url})
                        MERGE (a)-[:HAS_TAG]->(t)
                    """, tag=tag.lower().strip(), url=url)

            updated += 1

            if tags_changed:
                added = set(new_tags) - set(t.lower().strip() for t in old_tags if t)
                print(f"[{i+1}/{len(articles)}] {title[:60]}")
                print(f"  + tags: {', '.join(sorted(added))}")

    print()
    print("=" * 60)
    print(f"Updated {updated}/{len(articles)} articles")
    print("=" * 60)


if __name__ == '__main__':
    main()
