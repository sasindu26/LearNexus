from flask import Flask, jsonify, request
from flask_cors import CORS
from neo4j import GraphDatabase
import re

app = Flask(__name__)
CORS(app)

# Neo4j connection setup
URI = "bolt://localhost:7691"  # Keep using bolt:// protocol
USERNAME = "neo4j"
PASSWORD = "Mento@2152"

# Create driver with better error handling
try:
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD), max_connection_lifetime=3600)
    # Verify connection on startup
    with driver.session() as session:
        session.run("RETURN 1")
        print("Successfully connected to Neo4j database")
except Exception as e:
    print(f"Failed to connect to Neo4j database: {e}")
    driver = None

def get_articles_for_module(module_name):
    """
    Query Neo4j for articles related to the given module name using RELATED_TO relationship
    where Article -RELATED_TO-> Module
    """
    if driver is None:
        print("No active Neo4j connection")
        return []
        
    try:
        with driver.session() as session:
            # First try to find articles directly related to the module via RELATED_TO relationship
            # Note the direction: (a:Article)-[:RELATED_TO]->(m:Module)
            result = session.run("""
                MATCH (a:Article)-[:RELATED_TO]->(m:Module)
                WHERE toLower(m.title) = toLower($module_name) OR 
                      toLower(m.title) CONTAINS toLower($module_name)
                RETURN a.elementId as id, 
                       a.title as title, 
                       a.full_description as description,
                       a.tags as tags,
                       a.url as url,
                       a.published_at as created_at
                UNION
                // If no direct relationships, fall back to content matching
                MATCH (a:Article)
                WHERE NOT EXISTS {
                    MATCH (a)-[:RELATED_TO]->(m:Module)
                    WHERE toLower(m.title) = toLower($module_name) OR 
                          toLower(m.title) CONTAINS toLower($module_name)
                }
                AND (
                    any(tag IN a.tags WHERE toLower(tag) CONTAINS toLower($module_name)) OR
                    toLower(a.title) CONTAINS toLower($module_name) OR 
                    toLower(a.full_description) CONTAINS toLower($module_name)
                )
                RETURN a.elementId as id, 
                       a.title as title, 
                       a.full_description as description,
                       a.tags as tags,
                       a.url as url,
                       a.published_at as created_at
            """, module_name=module_name)
            
            articles = [dict(record) for record in result]
            
            # If no articles found through relationships or content matching,
            # try to match by related topics
            if not articles:
                result = session.run("""
                    MATCH (m:Module)-[:HAS_TOPIC]->(t:Topic)
                    WHERE toLower(m.title) = toLower($module_name) OR 
                          toLower(m.title) CONTAINS toLower($module_name)
                    MATCH (a:Article)
                    WHERE any(tag IN a.tags WHERE toLower(tag) CONTAINS toLower(t.title))
                    RETURN DISTINCT a.elementId as id, 
                           a.title as title, 
                           a.full_description as description,
                           a.tags as tags,
                           a.url as url,
                           a.published_at as created_at
                """, module_name=module_name)
                articles = [dict(record) for record in result]
            
            return articles
    except Exception as e:
        print(f"Error fetching articles for module {module_name}: {e}")
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
    for tag in article.get('tags', []):
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

@app.route('/api/module-articles', methods=['GET'])
def get_module_articles():
    """Get articles related to a specific module"""
    module_name = request.args.get('module', '')
    if not module_name:
        return jsonify({"error": "Module name is required"}), 400
    
    articles = get_articles_for_module(module_name)
    
    # Calculate relevance score for each article
    for article in articles:
        article['relevance_score'] = calculate_relevance_score(article, module_name)
    
    # Sort by relevance score (highest first)
    sorted_articles = sorted(articles, key=lambda x: x['relevance_score'], reverse=True)
    
    # Limit to top N results
    limit = request.args.get('limit', default=10, type=int)
    return jsonify(sorted_articles[:limit])

@app.route('/api/module-articles/<article_id>', methods=['GET'])
def get_module_article(article_id):
    """Retrieve a specific article by ID"""
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

if __name__ == '__main__':
    if driver is None:
        print("WARNING: No active Neo4j connection. The application may not function correctly.")
    app.run(debug=True, port=8000)
