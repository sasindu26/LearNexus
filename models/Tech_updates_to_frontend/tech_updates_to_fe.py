from flask import Flask, jsonify, request
from flask_cors import CORS
from neo4j import GraphDatabase
from datetime import datetime
import random

app = Flask(__name__)
CORS(app)

# Neo4j connection setup
URI = "neo4j://localhost:7687"  # Update with your Neo4j URI
USERNAME = "neo4j"              # Update with your username
PASSWORD = "LearNexus1212"

driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

def get_articles_from_neo4j():
    with driver.session() as session:
        result = session.run("""
            MATCH (a:Article)
            RETURN a.elementId as id,
                   a.title as title,
                   a.full_description as description,
                   a.tags as tags,
                   a.url as url,
                   a.cover_image as image,
                   a.source as source,
                   a.published_at as created_at
        """)
        return [dict(record) for record in result]

# Store user ratings
user_ratings = {}

@app.route('/api/tech-recommendations', methods=['GET'])
def get_tech_recommendations():
    """Retrieve all tech recommendations"""
    limit = request.args.get('limit', default=10, type=int)
    articles = get_articles_from_neo4j()
    return jsonify(articles[:limit])

@app.route('/api/tech-recommendations/<recommendation_id>', methods=['GET'])
def get_tech_recommendation(recommendation_id):
    """Retrieve a specific tech recommendation by ID"""
    with driver.session() as session:
        result = session.run("""
            MATCH (a:Article {elementId: $id})
            RETURN a.elementId as id,
                   a.title as title,
                   a.full_description as description,
                   a.tags as tags,
                   a.url as url,
                   a.cover_image as image,
                   a.source as source,
                   a.published_at as created_at
        """, id=recommendation_id)
        article = result.single()
        if article:
            return jsonify(dict(article))
        return jsonify({"error": "Recommendation not found"}), 404

@app.route('/api/tech-recommendations/rating', methods=['POST'])
def rate_recommendation():
    """Store user ratings for recommendations"""
    data = request.json
    if not data or 'id' not in data or 'isEffective' not in data:
        return jsonify({"error": "Missing required fields"}), 400
    
    module_id = data['id']
    is_effective = data['isEffective']
    
    if module_id not in user_ratings:
        user_ratings[module_id] = {"effective": 0, "not_effective": 0}
    
    if is_effective:
        user_ratings[module_id]["effective"] += 1
    else:
        user_ratings[module_id]["not_effective"] += 1
    
    return jsonify({"success": True, "current_ratings": user_ratings[module_id]})

@app.route('/api/tech-recommendations/personalized', methods=['GET'])
def get_personalized_recommendations():
    """Get personalized recommendations based on user preferences"""
    user_id = request.args.get('userId', default=None)
    if not user_id:
        # If no user ID, return random recommendations
        random_recs = random.sample(tech_recommendations, min(3, len(tech_recommendations)))
        return jsonify(random_recs)
    
    # Here you would typically query a database based on user preferences
    # For now, we'll just return the highest popularity items
    sorted_recs = sorted(tech_recommendations, key=lambda x: x["popularity"], reverse=True)
    return jsonify(sorted_recs[:3])

@app.route('/api/tech-recommendations/trending', methods=['GET'])
def get_trending_recommendations():
    """Get trending tech recommendations"""
    with driver.session() as session:
        result = session.run("""
            MATCH (a:Article)
            RETURN a.elementId as id,
                   a.title as title,
                   a.full_description as description,
                   a.tags as tags,
                   a.url as url,
                   a.cover_image as image,
                   a.source as source,
                   a.published_at as created_at
            ORDER BY a.published_at DESC
            LIMIT $limit
        """, limit=request.args.get('limit', default=3, type=int))
        trending = [dict(record) for record in result]
        return jsonify(trending)

if __name__ == '__main__':
    app.run(debug=True, port=5000)