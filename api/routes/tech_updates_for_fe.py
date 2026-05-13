from flask import Blueprint, jsonify, request
from neo4j import GraphDatabase
import os
import logging
import threading
import sys
import requests as http_requests
import time

logger = logging.getLogger(__name__)

# Add pipeline dir to path for scraper import
_pipeline_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'pipeline'))
if _pipeline_dir not in sys.path:
    sys.path.insert(0, _pipeline_dir)

try:
    from deepseel2 import scrape_full_description as _scrape_full
except ImportError:
    _scrape_full = None
    logger.warning("deepseel2 not importable — on-demand scraping disabled")

tech_updates_bp = Blueprint('tech_updates', __name__)

URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
USERNAME = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "LearNexus1212")

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
user_ratings = {}
_world_trending_cache = {"data": [], "updated_at": 0}
_CACHE_TTL = 3600  # refresh from dev.to once per hour


ARTICLE_FIELDS = """
    toString(elementId(a)) as id,
    a.title as title,
    coalesce(a.short_description, a.description, '') as description,
    a.full_description as full_description,
    a.tags as tags,
    a.url as url,
    a.cover_image as image,
    a.source as source,
    a.published_at as created_at
"""


def _strip_html(text):
    """Strip HTML tags and collapse whitespace for clean previews."""
    if not text:
        return ''
    import re
    clean = re.sub(r'<[^>]+>', ' ', text)
    return ' '.join(clean.split()).strip()


def to_article(record):
    d = dict(record)
    if not isinstance(d.get('tags'), list):
        d['tags'] = [d['tags']] if d.get('tags') else []
    # Strip HTML from description for card/sidebar display
    raw = d.get('description') or ''
    d['description'] = _strip_html(raw)[:300]
    # Remove full_description from list responses (only needed on detail page)
    d.pop('full_description', None)
    return d


@tech_updates_bp.route('/tech-recommendations/trending', methods=['GET'])
def get_trending():
    try:
        limit = request.args.get('limit', default=100, type=int)
        skip = request.args.get('skip', default=0, type=int)
        with driver.session() as session:
            result = session.run(f"""
                MATCH (a:Article)
                WHERE a.cover_image IS NOT NULL AND trim(a.cover_image) <> ''
                RETURN {ARTICLE_FIELDS}
                ORDER BY a.published_at DESC
                SKIP $skip
                LIMIT $limit
            """, limit=limit, skip=skip)
            return jsonify([to_article(r) for r in result])
    except Exception as e:
        logger.error(f"Trending error: {e}")
        return jsonify([]), 500


@tech_updates_bp.route('/tech-recommendations', methods=['GET'])
def get_all():
    try:
        limit = request.args.get('limit', default=100, type=int)
        skip = request.args.get('skip', default=0, type=int)
        with driver.session() as session:
            result = session.run(f"""
                MATCH (a:Article)
                RETURN {ARTICLE_FIELDS}
                ORDER BY a.published_at DESC
                SKIP $skip
                LIMIT $limit
            """, limit=limit, skip=skip)
            return jsonify([to_article(r) for r in result])
    except Exception as e:
        logger.error(f"All articles error: {e}")
        return jsonify([]), 500


@tech_updates_bp.route('/tech-recommendations/by-tags', methods=['GET'])
def get_by_tags():
    try:
        tags_param = request.args.get('tags', '')
        limit = request.args.get('limit', default=100, type=int)
        query_tags = [t.strip().lower() for t in tags_param.split(',') if t.strip()]
        if not query_tags:
            return jsonify([])
        with driver.session() as session:
            result = session.run(f"""
                MATCH (a:Article)
                WHERE a.cover_image IS NOT NULL AND trim(a.cover_image) <> ''
                  AND any(tag IN a.tags WHERE any(qt IN $query_tags WHERE toLower(tag) CONTAINS qt))
                RETURN {ARTICLE_FIELDS}
                ORDER BY a.published_at DESC
                LIMIT $limit
            """, query_tags=query_tags, limit=limit)
            articles = [to_article(r) for r in result]
            # Fallback: if no tag matches, return all trending with images
            if not articles:
                result2 = session.run(f"""
                    MATCH (a:Article)
                    WHERE a.cover_image IS NOT NULL AND trim(a.cover_image) <> ''
                    RETURN {ARTICLE_FIELDS}
                    ORDER BY a.published_at DESC
                    LIMIT $limit
                """, limit=limit)
                articles = [to_article(r) for r in result2]
            return jsonify(articles)
    except Exception as e:
        logger.error(f"By-tags error: {e}")
        return jsonify([]), 500


@tech_updates_bp.route('/tech-recommendations/for-course', methods=['GET'])
def get_for_course():
    """Articles relevant to a course — used for navbar notifications."""
    try:
        course = request.args.get('course', '').lower()
        limit = request.args.get('limit', default=5, type=int)

        tag_map = [
            ('data science',             ['datascience', 'machinelearning', 'python', 'ai', 'analytics']),
            ('artificial intelligence',  ['ai', 'machinelearning', 'deeplearning', 'llm', 'agents']),
            ('machine learning',         ['machinelearning', 'deeplearning', 'python', 'mlops']),
            ('software engineering',     ['softwareengineering', 'devops', 'programming', 'testing']),
            ('computer science',         ['computerscience', 'algorithms', 'programming', 'python']),
            ('web',                      ['webdev', 'javascript', 'frontend', 'css', 'react']),
            ('network',                  ['networking', 'security', 'distributedsystems']),
            ('database',                 ['database', 'sql', 'neo4j', 'postgres']),
            ('security',                 ['security', 'cybersecurity', 'hacking']),
            ('cloud',                    ['cloud', 'devops', 'kubernetes', 'docker']),
        ]

        matched = next((tags for key, tags in tag_map if key in course),
                       ['programming', 'ai', 'technology', 'python'])

        with driver.session() as session:
            result = session.run("""
                MATCH (a:Article)
                WHERE any(tag IN a.tags WHERE any(mt IN $matched WHERE toLower(tag) CONTAINS mt))
                RETURN toString(elementId(a)) as id,
                       a.title as title,
                       coalesce(a.full_description, a.description, '') as description,
                       a.tags as tags,
                       a.url as url,
                       a.cover_image as image,
                       a.source as source,
                       a.published_at as created_at
                ORDER BY a.published_at DESC
                LIMIT $limit
            """, matched=matched, limit=limit)
            articles = [to_article(r) for r in result]

            if not articles:
                result2 = session.run("""
                    MATCH (a:Article)
                    RETURN toString(elementId(a)) as id,
                           a.title as title,
                           coalesce(a.full_description, a.description, '') as description,
                           a.tags as tags,
                           a.url as url,
                           a.cover_image as image,
                           a.source as source,
                           a.published_at as created_at
                    ORDER BY a.published_at DESC
                    LIMIT $limit
                """, limit=limit)
                articles = [to_article(r) for r in result2]

            return jsonify(articles)
    except Exception as e:
        logger.error(f"For-course error: {e}")
        return jsonify([]), 500


@tech_updates_bp.route('/tech-recommendations/rating', methods=['POST'])
def rate_recommendation():
    try:
        data = request.json or {}
        article_id = data.get('recommendation_id') or data.get('id')
        rating = data.get('rating')
        is_effective = (rating == 'effective') if rating else data.get('isEffective', True)

        if not article_id:
            return jsonify({"error": "Missing article id"}), 400

        if article_id not in user_ratings:
            user_ratings[article_id] = {"effective": 0, "not_effective": 0}

        if is_effective:
            user_ratings[article_id]["effective"] += 1
        else:
            user_ratings[article_id]["not_effective"] += 1

        return jsonify({"success": True, "current_ratings": user_ratings[article_id]})
    except Exception as e:
        logger.error(f"Rating error: {e}")
        return jsonify({"error": str(e)}), 500


@tech_updates_bp.route('/world-trending', methods=['GET'])
def get_world_trending():
    """Fetch truly trending tech articles from dev.to (top by reactions this week)."""
    now = time.time()
    if _world_trending_cache["data"] and (now - _world_trending_cache["updated_at"]) < _CACHE_TTL:
        return jsonify(_world_trending_cache["data"])

    try:
        limit = request.args.get('limit', default=5, type=int)
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LearNexusBot/1.0)"}
        resp = http_requests.get(
            "https://dev.to/api/articles",
            params={"top": 7, "per_page": 10},
            headers=headers,
            timeout=10
        )
        if resp.status_code != 200:
            return jsonify(_world_trending_cache["data"] or []), 502

        articles = []
        for a in resp.json()[:limit]:
            articles.append({
                "id": str(a.get("id", "")),
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "tags": a.get("tag_list", []),
                "source": "dev.to",
                "reactions": a.get("positive_reactions_count", 0),
                "image": a.get("cover_image") or a.get("social_image") or "",
                "created_at": a.get("published_at", ""),
            })

        _world_trending_cache["data"] = articles
        _world_trending_cache["updated_at"] = now
        return jsonify(articles)
    except Exception as e:
        logger.error(f"World trending error: {e}")
        return jsonify(_world_trending_cache["data"] or []), 500


def _scrape_and_cache(article_id, url):
    """Background thread: scrape full description and store in Neo4j."""
    if not _scrape_full:
        return
    try:
        html = _scrape_full(url)
        if html and len(html) > 300:
            with driver.session() as s:
                s.run("""
                    MATCH (a:Article)
                    WHERE toString(elementId(a)) = $id
                    SET a.full_description = $html
                """, id=article_id, html=html)
            logger.info(f"Cached full description for {article_id}")
    except Exception as e:
        logger.warning(f"Background scrape failed for {article_id}: {e}")


@tech_updates_bp.route('/tech-recommendations/<recommendation_id>', methods=['GET'])
def get_one(recommendation_id):
    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (a:Article)
                WHERE toString(elementId(a)) = $id
                RETURN toString(elementId(a)) as id,
                       a.title as title,
                       coalesce(a.full_description, a.description, '') as description,
                       a.tags as tags,
                       a.url as url,
                       a.cover_image as image,
                       a.source as source,
                       a.published_at as created_at
            """, id=recommendation_id)
            article = result.single()
            if not article:
                return jsonify({"error": "Not found"}), 404

            art = to_article(article)

            # If description is short, scrape full content synchronously (dev.to API is fast)
            if _scrape_full and len(art.get('description', '')) < 500 and art.get('url'):
                try:
                    html = _scrape_full(art['url'])
                    if html and len(html) > 300:
                        art['description'] = html
                        # Cache in Neo4j in background so next visit is instant
                        t = threading.Thread(
                            target=_scrape_and_cache,
                            args=(recommendation_id, art['url']),
                            daemon=True
                        )
                        t.start()
                except Exception as e:
                    logger.warning(f"On-demand scrape failed: {e}")

            return jsonify(art)
    except Exception as e:
        logger.error(f"Get-one error: {e}")
        return jsonify({"error": str(e)}), 500
