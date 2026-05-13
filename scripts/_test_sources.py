"""Test all 3 sources produce full_description."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'models', 'pipeline'))

from deepseel2 import fetch_devto_articles, fetch_dailydev_articles, fetch_google_news_tech  # type: ignore

print("=" * 60)
print("Testing full_description for all 3 sources")
print("=" * 60)

# 1. Dev.to
print("\n--- DEV.TO ---")
devto = fetch_devto_articles(tag="python", max_articles=2)
for a in devto[:2]:
    fd = a.get("full_description", "")
    has_html = "<" in fd and ">" in fd
    print(f"  {a['title'][:55]}")
    print(f"    full_description: {len(fd)} chars, has HTML: {has_html}")
    # Show first 150 chars cleaned
    import re
    clean = re.sub(r'<[^>]+>', '', fd[:300]).strip()[:150]
    print(f"    Preview: {clean}...")
    print()

# 2. Medium (daily.dev)
print("\n--- MEDIUM (daily.dev) ---")
medium = fetch_dailydev_articles(tag="technology", max_articles=2)
for a in medium[:2]:
    fd = a.get("full_description", "")
    has_html = "<" in fd and ">" in fd
    print(f"  {a['title'][:55]}")
    print(f"    full_description: {len(fd)} chars, has HTML: {has_html}")
    clean = re.sub(r'<[^>]+>', '', fd[:300]).strip()[:150]
    print(f"    Preview: {clean}...")
    print()

# 3. Google News
print("\n--- GOOGLE NEWS ---")
google = fetch_google_news_tech(max_articles=2)
for a in google[:2]:
    fd = a.get("full_description", "")
    has_html = "<" in fd and ">" in fd
    print(f"  {a['title'][:55]}")
    print(f"    full_description: {len(fd)} chars, has HTML: {has_html}")
    clean = re.sub(r'<[^>]+>', '', fd[:300]).strip()[:150]
    print(f"    Preview: {clean}...")
    print()

print("=" * 60)
print("SUMMARY")
for name, arts in [("Dev.to", devto), ("Medium", medium), ("Google", google)]:
    avg = sum(len(a.get("full_description","")) for a in arts) / max(len(arts),1)
    print(f"  {name:12s}: {len(arts)} articles, avg desc: {avg:.0f} chars")
print("=" * 60)
