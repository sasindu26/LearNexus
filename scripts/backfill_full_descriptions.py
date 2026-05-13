#!/usr/bin/env python
"""
Backfill cover_image and full_description for articles in Neo4j.
Handles articles that have placeholder Google images or missing content.

Usage (with venv activated):
    cd LearNexus_repo
    python scripts/backfill_full_descriptions.py
"""
import os
import sys
import time

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'models', 'pipeline'))

from py2neo import Graph
from deepseel2 import scrape_full_description, _is_placeholder_image  # type: ignore[import-not-found]
import requests
from bs4 import BeautifulSoup

try:
    from googlenewsdecoder import gnewsdecoder
except ImportError:
    gnewsdecoder = None
    print("[WARN] googlenewsdecoder not installed. Google News URLs won't be resolved.")

graph = Graph("bolt://localhost:7687", auth=("neo4j", "LearNexus1212"))

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def scrape_meta_from_page(html_text):
    """Extract og:image and og:description from HTML."""
    soup = BeautifulSoup(html_text, "html.parser")
    cover = ""
    desc = ""

    for meta_prop in ["og:image", "twitter:image"]:
        tag = soup.find("meta", property=meta_prop)
        if not tag:
            tag = soup.find("meta", attrs={"name": meta_prop})
        if tag and tag.get("content") and not _is_placeholder_image(tag["content"]):
            cover = tag["content"]
            break

    og_desc = soup.find("meta", property="og:description")
    if og_desc and og_desc.get("content") and len(og_desc["content"]) > 30:
        desc = og_desc["content"]
    else:
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc and meta_desc.get("content") and len(meta_desc["content"]) > 30:
            desc = meta_desc["content"]

    return cover, desc


def backfill():
    articles = graph.run("""
        MATCH (a:Article)
        WHERE a.cover_image CONTAINS 'lh3.googleusercontent.com'
           OR a.cover_image CONTAINS 'googleusercontent.com/J6_coF'
           OR a.url CONTAINS 'news.google.com'
           OR a.cover_image IS NULL
           OR trim(a.cover_image) = ''
           OR a.full_description IS NULL
           OR trim(a.full_description) = ''
           OR size(a.full_description) < 100
        RETURN a.url AS url, a.title AS title,
               coalesce(a.cover_image, '') AS cover,
               coalesce(a.full_description, '') AS full_desc
        ORDER BY a.created_date DESC
    """).data()

    print(f"\n{'='*60}")
    print(f"Found {len(articles)} articles needing fixes")
    print(f"{'='*60}")

    updated = 0
    for i, art in enumerate(articles, 1):
        url = art["url"]
        title = art["title"]
        current_cover = art["cover"]
        current_desc = art["full_desc"]
        needs_cover = _is_placeholder_image(current_cover) or not current_cover.strip()
        needs_desc = not current_desc or len(current_desc) < 100

        print(f"\n[{i}/{len(articles)}] {title[:70]}")

        updates = {}
        real_url = url

        # ── Step 1: Resolve Google News URLs ───────────────────────────
        if "news.google.com" in url and gnewsdecoder:
            try:
                result = gnewsdecoder(url)
                if result.get("status") and result.get("decoded_url"):
                    real_url = result["decoded_url"]
                    updates["url"] = real_url
                    print(f"  -> Resolved: {real_url[:100]}")
                else:
                    print(f"  x Could not decode Google News URL")
            except Exception as e:
                print(f"  x Decode error: {e}")
            time.sleep(1)

        # ── Step 2: Fetch page HTML (for cover & description) ──────────
        page_html = ""
        if needs_cover or needs_desc:
            try:
                resp = requests.get(real_url, timeout=12, headers=_HEADERS,
                                    allow_redirects=True)
                if resp.status_code == 200:
                    page_html = resp.text
                    if resp.url != real_url and "news.google.com" not in resp.url:
                        real_url = resp.url
                        updates["url"] = real_url
                else:
                    print(f"  x HTTP {resp.status_code} fetching page")
            except Exception as e:
                print(f"  x Fetch error: {e}")

        # ── Step 3: Fix cover image ────────────────────────────────────
        if needs_cover:
            if page_html:
                new_cover, _ = scrape_meta_from_page(page_html)
                if new_cover:
                    updates["cover_image"] = new_cover
                    print(f"  OK Cover image found")
                else:
                    print(f"  x No og:image found on page")
            else:
                print(f"  x No page HTML to extract cover from")

        # ── Step 4: Fix full_description ───────────────────────────────
        if needs_desc:
            desc_html = scrape_full_description(real_url)
            if desc_html and len(desc_html) > 100:
                updates["full_description"] = desc_html
                print(f"  OK Description scraped ({len(desc_html)} chars)")
            elif page_html:
                _, page_desc = scrape_meta_from_page(page_html)
                if page_desc:
                    updates["full_description"] = f"<p>{page_desc}</p>"
                    print(f"  ~ Description from meta tag")
                else:
                    print(f"  x No description found")
            else:
                print(f"  x No description found")

        # ── Apply updates ──────────────────────────────────────────────
        if updates:
            set_clauses = ", ".join(f"a.{k} = ${k}" for k in updates)
            query = f"MATCH (a:Article {{url: $old_url}}) SET {set_clauses}"
            updates["old_url"] = url
            graph.run(query, **updates)
            updated += 1
            keys = [k for k in updates if k != "old_url"]
            print(f"  OK Updated: {keys}")
        else:
            print(f"  - No updates needed")

        time.sleep(0.3)

    print(f"\n{'='*60}")
    print(f"DONE! Updated {updated}/{len(articles)} articles")
    print(f"{'='*60}")


if __name__ == "__main__":
    backfill()
