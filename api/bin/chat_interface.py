from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.basic_iomodel import  cosine_search

app = Flask(__name__)
CORS(app)

# Configuration
neo4j_config = {
    "url": "bolt://localhost:7691",
    "username": "neo4j",
    "password": "Mento@2152",
    "database": "neo4j"
}


# Initialize chat agent
print("Initializing chat agent...")
chat_agent = cosine_search.EducationalChatbot()

@app.route('/', methods=['GET'])
def health_check():
    return jsonify({"status": "Server is running"}), 200

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message', '')
        print(f"Received message: {user_message}")
        
        response = chat_agent.invoke(
            {"input": user_message},
            {"configurable": {"session_id": chat_agent.SESSION_ID}}
        )
        
        print(f"Response: {response}")
        return jsonify({
            "status": "success",
            "message": response.get("output", "No response")
        })
        
    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    print("Starting Flask server...")
    print("Attempting to bind to: http://0.0.0.0:8000")
    app.run(host='0.0.0.0', port=8000, debug=True)