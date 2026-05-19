from flask import Blueprint, request, jsonify
import traceback
import os
import sys
import threading

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(project_root)

from config.logging_config import setup_logger

# Setup logger
logger = setup_logger('chat_bot', 'chat_bot.log')

# Create blueprint
chat_bp = Blueprint('chat_bot', __name__)

# Neo4j Configuration
neo4j_config = {
    "url": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
    "username": os.getenv("NEO4J_USER", "neo4j"),
    "password": os.getenv("NEO4J_PASSWORD", "LearNexus1212"),
    "database": ""
}

# Global Chatbot Instance — pre-warmed in background at startup
chat_agent = None
_init_lock = threading.Lock()
_initializing = False


def initialize_chatbot():
    """Initialize the chatbot with error handling."""
    global chat_agent, _initializing
    with _init_lock:
        if chat_agent is not None:
            return True
        _initializing = True
    try:
        from models.basic_iomodel import cosine_search_gemini
        agent = cosine_search_gemini.EducationalChatbot(neo4j_config)
        if not agent.connect():
            print("Failed to connect to the database")
            return False
        chat_agent = agent
        return True
    except Exception as e:
        print(f"Chatbot initialization error: {e}")
        traceback.print_exc()
        return False
    finally:
        _initializing = False


def _prewarm():
    """Load chatbot model in background so first user request is instant."""
    import time
    time.sleep(10)
    print("Pre-warming chatbot...")
    initialize_chatbot()
    print("Chatbot pre-warm complete." if chat_agent else "Chatbot pre-warm failed.")


# Pre-warm is off by default on Render free tier (SentenceTransformer + PyTorch >
# 512MB combined with the rest of the app). Set PREWARM_CHATBOT=true to enable.
if os.getenv("PREWARM_CHATBOT", "false").lower() == "true":
    threading.Thread(target=_prewarm, daemon=True).start()


@chat_bp.route('/chat', methods=['POST'])
def chat():
    """
    Main chat endpoint to process user messages
    """
    if chat_agent is None:
        if _initializing:
            return jsonify({
                "status": "initializing",
                "message": "The AI is warming up, please try again in 30 seconds."
            }), 503
        initialize_chatbot()

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
