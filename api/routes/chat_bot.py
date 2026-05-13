from flask import Blueprint, request, jsonify
import traceback
import os
import sys

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(project_root)

from models.basic_iomodel import cosine_search_gemini
from config.logging_config import setup_logger

# Setup logger
logger = setup_logger('chat_bot', 'chat_bot.log')

# Create blueprint
chat_bp = Blueprint('chat_bot', __name__)

# Neo4j Configuration
neo4j_config = {
    "url": "bolt://localhost:7687",
    "username": "neo4j",
    "password": "LearNexus1212",
    "database": "neo4j"
}

# Global Chatbot Instance
chat_agent = None

def initialize_chatbot():
    """
    Initialize the chatbot with error handling
    """
    global chat_agent
    try:
        chat_agent = cosine_search_gemini.EducationalChatbot(neo4j_config)
        
        # Verify database connection
        if not chat_agent.connect():
            print("Failed to connect to the database")
            return False
        return True
    except Exception as e:
        print(f"Chatbot initialization error: {e}")
        traceback.print_exc()
        return False

# Initialize chatbot when module is loaded
if initialize_chatbot():
    print("Chatbot initialized successfully")
else:
    print("Failed to initialize chatbot")

@chat_bp.route('/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint to process user messages
    """
    try:
        # Validate chatbot initialization
        if chat_agent is None:
            return jsonify({
                "status": "error",
                "message": "Chatbot not initialized. Please restart the server."
            }), 500

        # Extract user message and chat history
        data = request.json
        user_message = data.get('message', '').strip()
        history = data.get('history', [])

        # Validate input
        if not user_message:
            return jsonify({
                "status": "error", 
                "message": "Empty message received"
            }), 400

        # Log incoming message
        print(f"Received message: {user_message}")
        print(f"Chat History length: {len(history)}")

        # Get chatbot response and courses
        response, courses = chat_agent.chat(user_message, history=history)
        
        # Log response and courses
        print(f"Chatbot Response: {response}")
        print(f"Courses: {courses}")

        # Return response
        return jsonify({
            "status": "success",
            "message": response,
            "courses": courses
        }), 200

    except Exception as e:
        # Comprehensive error logging
        print(f"Error in chat endpoint: {str(e)}")
        traceback.print_exc()
        
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred",
            "details": str(e)
        }), 500
