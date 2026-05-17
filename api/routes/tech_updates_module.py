from flask import Blueprint, jsonify, request
from neo4j import GraphDatabase
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

tech_module_bp = Blueprint('tech_module', __name__)

# Neo4j connection setup - update to use the same URI format as in tech_updates_to_module.py
# Change from neo4j:// protocol to bolt:// protocol as that seems to work in your other file
URI = "bolt://localhost:7687"  # Using bolt protocol instead of neo4j protocol
USERNAME = "neo4j"
PASSWORD = "LearNexus1212"

# Create driver with max retry time to handle connection issues
try:
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD), max_connection_lifetime=3600)
    # Verify connection is working
    with driver.session() as session:
        session.run("RETURN 1")
        logger.info("Successfully connected to Neo4j database")
except Exception as e:
    logger.error(f"Failed to connect to Neo4j database: {e}")
    driver = None

def get_articles_for_module(module_name):
    """
    Query Neo4j for articles related to the given module name using RELATED_TO relationship
    where Article -RELATED_TO-> Module (not Module -RELATED_TO-> Article)
    """
    if driver is None:
        logger.error("No active Neo4j connection")
        return []

    try:
        with driver.session() as session:
            # First try to find articles directly related to the module via RELATED_TO relationship
            # Note the direction: (a:Article)-[:RELATED_TO]->(m:Module)
            result = session.run("""
                MATCH (a:Article)-[:RELATED_TO]->(m:Module)
                WHERE toLower(m.name) = toLower($module_name) OR
                      toLower(m.name) CONTAINS toLower($module_name)
                RETURN a.elementId as id,
                       a.title as title,
                       coalesce(a.short_description, a.full_description) as description,
                       a.tags as tags,
                       a.url as url,
                       a.published_at as created_at
                UNION
                // If no direct relationships, fall back to content matching
                MATCH (a:Article)
                WHERE NOT EXISTS {
                    MATCH (a)-[:RELATED_TO]->(m:Module)
                    WHERE toLower(m.name) = toLower($module_name) OR
                          toLower(m.name) CONTAINS toLower($module_name)
                }
                AND (
                    any(tag IN coalesce(a.tags, []) WHERE toLower(tag) CONTAINS toLower($module_name)) OR
                    toLower(a.title) CONTAINS toLower($module_name) OR
                    toLower(a.full_description) CONTAINS toLower($module_name)
                )
                RETURN a.elementId as id,
                       a.title as title,
                       coalesce(a.short_description, a.full_description) as description,
                       a.tags as tags,
                       a.url as url,
                       a.published_at as created_at
            """, module_name=module_name)

            articles = [dict(record) for record in result]

            # If no articles found through relationships or content matching,
            # try to match by related topics
            if not articles:
                logger.info(f"No direct article matches for module '{module_name}', trying topic-based matching")
                result = session.run("""
                    MATCH (m:Module)-[:HAS_TOPIC]->(t:Topic)
                    WHERE toLower(m.name) = toLower($module_name) OR
                          toLower(m.name) CONTAINS toLower($module_name)
                    MATCH (a:Article)
                    WHERE any(tag IN coalesce(a.tags, []) WHERE toLower(tag) CONTAINS toLower(t.name))
                    RETURN DISTINCT a.elementId as id,
                           a.title as title,
                           coalesce(a.short_description, a.full_description) as description,
                           a.tags as tags,
                           a.url as url,
                           a.published_at as created_at
                """, module_name=module_name)
                articles = [dict(record) for record in result]

            # Strip HTML from descriptions for clean sidebar display
            for article in articles:
                raw = article.get('description') or ''
                if '<' in raw and '>' in raw:
                    clean = re.sub(r'<[^>]+>', ' ', raw)
                    article['description'] = ' '.join(clean.split()).strip()[:300]

            logger.info(f"Found {len(articles)} articles for module '{module_name}'")
            return articles
    except Exception as e:
        logger.error(f"Error fetching articles for module {module_name}: {e}")
        return []

def calculate_relevance_score(article, module_name):
    """
    Calculate a relevance score for an article based on how well it matches the module name
    """
    score = 0
    module_name_lower = module_name.lower()

    # Check title (highest weight)
    if module_name_lower in article.get('title', '').lower():
        score += 10

    # Check tags
    for tag in (article.get('tags') or []):
        if module_name_lower in tag.lower():
            score += 5

    # Check description
    description = article.get('description', '')
    if description and module_name_lower in description.lower():
        score += 3
        # Bonus for multiple occurrences
        occurrences = len(re.findall(r'\b' + re.escape(module_name_lower) + r'\b', description.lower()))
        score += min(occurrences, 5)  # Cap bonus at 5 points

    return score

@tech_module_bp.route('/api/module-articles', methods=['GET'])
def get_module_articles():
    """Get articles related to a specific module"""
    module_name = request.args.get('module', '')
    if not module_name:
        return jsonify({"error": "Module name is required"}), 400

    if driver is None:
        return jsonify({
            "error": "Database connection error",
            "message": "Unable to connect to the articles database"
        }), 500

    try:
        articles = get_articles_for_module(module_name)

        # Calculate relevance score for each article
        for article in articles:
            article['relevance_score'] = calculate_relevance_score(article, module_name)

        # Sort by relevance score (highest first)
        sorted_articles = sorted(articles, key=lambda x: x['relevance_score'], reverse=True)

        # Limit to top N results
        limit = request.args.get('limit', default=10, type=int)
        return jsonify(sorted_articles[:limit])
    except Exception as e:
        logger.error(f"Error processing module articles request: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

@tech_module_bp.route('/api/module-articles/<article_id>', methods=['GET'])
def get_module_article(article_id):
    """Retrieve a specific article by ID"""
    if driver is None:
        return jsonify({
            "error": "Database connection error",
            "message": "Unable to connect to the articles database"
        }), 500

    try:
        with driver.session() as session:
            result = session.run("""
                MATCH (a:Article {elementId: $id})
                RETURN a.elementId as id,
                       a.title as title,
                       a.full_description as description,
                       a.tags as tags,
                       a.url as url,
                       a.published_at as created_at
            """, id=article_id)
            article = result.single()
            if article:
                return jsonify(dict(article))
            return jsonify({"error": "Article not found"}), 404
    except Exception as e:
        logger.error(f"Error fetching article by ID {article_id}: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e)
        }), 500

@tech_module_bp.route('/tech-updates', methods=['POST'])
def get_tech_updates():
    """Get articles related to a specific module"""
    data = request.json
    if not data or 'moduleName' not in data:
        return jsonify({"error": "moduleName is required in request body", "success": False}), 400

    if driver is None:
        return jsonify({
            "error": "Database connection error",
            "message": "Unable to connect to the articles database",
            "success": False
        }), 500

    try:
        module_name = data['moduleName']
        articles = get_articles_for_module(module_name)

        # Calculate relevance score for each article
        for article in articles:
            article['relevance_score'] = calculate_relevance_score(article, module_name)

        # Sort by relevance score (highest first)
        sorted_articles = sorted(articles, key=lambda x: x['relevance_score'], reverse=True)

        # Limit to top N results
        limit = data.get('limit', 10)

        return jsonify({
            "success": True,
            "articles": sorted_articles[:limit]
        })
    except Exception as e:
        logger.error(f"Error processing tech updates request: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e),
            "success": False
        }), 500

# Add a health check endpoint to verify database connectivity
@tech_module_bp.route('/api/module-articles/health', methods=['GET'])
def check_module_articles_health():
    """Check the health of the module articles service"""
    if driver is None:
        return jsonify({
            "status": "error",
            "message": "No database connection"
        }), 500

    try:
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            test_value = result.single()["test"]
            if test_value == 1:
                return jsonify({
                    "status": "ok",
                    "message": "Database connection established",
                    "neo4j_uri": URI
                })
            else:
                return jsonify({
                    "status": "warning",
                    "message": "Database connection test returned unexpected value"
                }), 500
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Database connection test failed: {str(e)}"
        }), 500

# Add a new endpoint to create RELATED_TO relationships between modules and articles
@tech_module_bp.route('/api/module-articles/relate', methods=['POST'])
def relate_module_to_article():
    """Create a RELATED_TO relationship from an article to a module"""
    if driver is None:
        return jsonify({
            "error": "Database connection error",
            "message": "Unable to connect to the articles database",
            "success": False
        }), 500

    data = request.json
    if not data or 'moduleTitle' not in data or 'articleId' not in data:
        return jsonify({
            "error": "Missing required fields",
            "message": "moduleTitle and articleId are required",
            "success": False
        }), 400

    module_title = data['moduleTitle']
    article_id = data['articleId']

    try:
        with driver.session() as session:
            # Check if the module exists
            module_result = session.run("""
                MATCH (m:Module)
                WHERE toLower(m.title) = toLower($module_title)
                RETURN m
            """, module_title=module_title)

            module = module_result.single()
            if not module:
                return jsonify({
                    "error": "Module not found",
                    "success": False
                }), 404

            # Check if the article exists
            article_result = session.run("""
                MATCH (a:Article {elementId: $article_id})
                RETURN a
            """, article_id=article_id)

            article = article_result.single()
            if not article:
                return jsonify({
                    "error": "Article not found",
                    "success": False
                }), 404

            # Create the relationship with the correct direction: Article -RELATED_TO-> Module
            result = session.run("""
                MATCH (m:Module), (a:Article)
                WHERE toLower(m.title) = toLower($module_title) AND a.elementId = $article_id
                MERGE (a)-[r:RELATED_TO]->(m)
                RETURN m.title as module_title, a.elementId as article_id
            """, module_title=module_title, article_id=article_id)

            relationship = result.single()
            if relationship:
                return jsonify({
                    "success": True,
                    "message": f"Relationship created from article '{relationship['article_id']}' to module '{relationship['module_title']}'",
                    "module_title": relationship['module_title'],
                    "article_id": relationship['article_id']
                })
            else:
                return jsonify({
                    "error": "Failed to create relationship",
                    "success": False
                }), 500
    except Exception as e:
        logger.error(f"Error relating article to module: {e}")
        return jsonify({
            "error": "Internal server error",
            "message": str(e),
            "success": False
        }), 500
