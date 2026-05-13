from flask import Blueprint, request, jsonify, current_app
import traceback
import os
import sys
from urllib.parse import unquote
import json
import urllib.request
import urllib.parse
import jwt
from neo4j import GraphDatabase

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(project_root)

import os
from models.module_content.module_content import ModuleContentExtractor
from config.logging_config import setup_logger

JWT_SECRET = os.getenv("JWT_SECRET", "learnexus_mento_secret_key_2026")

# Setup logger
logger = setup_logger('topic_extracter', 'topic_extracter.log')

# Create blueprint
topic_bp = Blueprint('topic_extracter', __name__)

# Neo4j connection setup
URI = "bolt://localhost:7687"
USERNAME = "neo4j"
PASSWORD = "LearNexus1212"
try:
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD), max_connection_lifetime=3600)
except Exception as e:
    logger.error(f"Failed to connect to Neo4j database: {e}")
    driver = None

def generate_topic_resources(topic_name):
    """Fallback: Search Wikipedia to auto-generate basic resources for a topic"""
    try:
        url = f'https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(topic_name)}&limit=3&namespace=0&format=json'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read())
            titles = data[1]
            urls = data[3]
            return [{'title': t, 'url': u, 'type': 'Article'} for t, u in zip(titles, urls)]
    except Exception as e:
        logger.error(f"Failed to fetch resources from Wikipedia: {e}")
        return []

@topic_bp.route('/api/topics/<path:topic_name>/resources', methods=['GET'])
def get_topic_resources(topic_name):
    """
    Get resources for a topic. If none exist in the DB, auto-generate them, save, and return.
    """
    if driver is None:
        return jsonify({"error": "Database connection error"}), 500

    topic_name = unquote(topic_name)
    logger.info(f"Fetching resources for topic: {topic_name}")

    try:
        with driver.session() as session:
            # 1. Check if resources exist in Neo4j
            result = session.run("""
                MATCH (t:Topic)-[:HAS_RESOURCE]->(r:Resource)
                WHERE toLower(t.name) = toLower($topic_name) OR t.name CONTAINS $topic_name
                RETURN r.title AS title, r.url AS url, r.type AS type
            """, topic_name=topic_name).data()

            # 2. Return if found
            if result:
                logger.info(f"Found {len(result)} resources for topic {topic_name}")
                return jsonify(result), 200

            # 3. Auto-generate if not found
            logger.info(f"No resources found for {topic_name}. Auto-generating...")
            new_resources = generate_topic_resources(topic_name)
            
            # 4. Add generic YouTube search link as fallback/bonus
            youtube_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(topic_name + ' tutorial')}"
            new_resources.append({'title': f"{topic_name} Video Tutorials", 'url': youtube_url, 'type': 'Video'})

            # 5. Save to Neo4j
            for res in new_resources:
                session.run("""
                    MATCH (t:Topic)
                    WHERE toLower(t.name) = toLower($topic_name) OR t.name CONTAINS $topic_name
                    MERGE (r:Resource {url: $url})
                    ON CREATE SET r.title = $title, r.type = $type
                    MERGE (t)-[:HAS_RESOURCE]->(r)
                """, topic_name=topic_name, url=res['url'], title=res['title'], type=res['type'])

            return jsonify(new_resources), 200

    except Exception as e:
        logger.error(f"Error fetching/generating resources: {str(e)}")
        return jsonify([]), 500

@topic_bp.route('/module-content/<module_name>/topics', methods=['GET', 'POST'])
@topic_bp.route('/modules/<module_name>/topics', methods=['GET', 'POST'])
def get_module_content(module_name):
    """
    Endpoint to get module topics by module name
    Supports both GET and POST methods
    """
    content_extractor = None
    try:
        # Log request details
        logger.info(f"Received {request.method} request for module content")
        logger.info(f"URL module_name parameter: {module_name}")
        logger.info(f"Request headers: {dict(request.headers)}")

        # Extract module name from different sources
        if request.method == 'POST':
            if request.is_json:
                data = request.get_json()
                logger.info(f"Received POST JSON data: {data}")
                # Try to get module name from POST data
                module_name = data.get('moduleName') or data.get('module_name') or module_name
            else:
                form_data = request.form
                logger.info(f"Received POST form data: {form_data}")
                # Try to get module name from form data
                module_name = form_data.get('moduleName') or form_data.get('module_name') or module_name

        # Decode module name
        decoded_module_name = unquote(module_name)
        logger.info(f"Final module name to process: '{decoded_module_name}'")

        # Initialize content extractor and get topics
        content_extractor = ModuleContentExtractor()
        raw_topics = content_extractor.get_module_content(decoded_module_name)
        
        logger.info(f"Retrieved {len(raw_topics)} raw topics")
        logger.debug(f"Raw topics: {raw_topics}")

        # Check for completed topics scoped to this module (exact case match)
        completed_topics = set()
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token and driver is not None:
            try:
                payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
                email = payload.get("email")
                with driver.session() as session:
                    result = session.run("""
                        MATCH (s:Student {email: $email})-[:COMPLETED]->(t:Topic)<-[:HAS_TOPIC]-(m:Module)
                        WHERE toLower(m.name) = toLower($module_name)
                        RETURN t.name AS name
                    """, email=email, module_name=decoded_module_name).data()
                    completed_topics = {r['name'] for r in result if r['name']}
            except Exception as e:
                logger.error(f"Failed to fetch completed topics: {e}")

        # Transform topics to match frontend expectations
        formatted_topics = []
        for idx, topic in enumerate(raw_topics):
            topic_name = topic.get("topic", "Unnamed Topic")
            is_completed = topic_name in completed_topics
            
            formatted_topic = {
                "id": f"topic-{idx}",
                "name": topic_name,
                "title": topic_name,
                "description": topic.get("description", "No description available"),
                "isCompleted": is_completed,
                "subtopics": [],
                "difficulty": "beginner",
                "timeEstimate": "15 mins",
                "progress": 100 if is_completed else 0,
                "icon": "📚"
            }
            formatted_topics.append(formatted_topic)

        # Prepare response
        response_data = formatted_topics if formatted_topics else []
        logger.info(f"Sending response with {len(response_data)} topics")
        
        # Create response
        response = jsonify(response_data)
        return response, 200

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        logger.error(traceback.format_exc())
        error_response = jsonify([])  # Return empty array on error
        return error_response, 500

    finally:
        if content_extractor:
            content_extractor.close()

