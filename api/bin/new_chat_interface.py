import sys 
import os
from flask import Flask, request, jsonify
from flask_cors import CORS
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from models.basic_iomodel import  model_105_1126

import logging
# new_chat_interface.py
import os
import sys
import logging
from flask import Flask, request, jsonify
from flask_cors import CORS


# Import the existing AcademicRAGAssistant

class AcademicRAGAPI:
    def __init__(self, debug_mode=True):
        # Initialize Flask application
        self.app = Flask(__name__)
        
        # Enable CORS for mobile app connectivity
        CORS(self.app, resources={r"/*": {"origins": "*"}})
        
        # Initialize the AcademicRAGAssistant
        self.assistant = model_105_1126.AcademicRAGAssistant(debug_mode=debug_mode)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger('AcademicRAGAPI')
        
        # Register API routes
        self._register_routes()

    def _register_routes(self):
        """
        Register all API routes for mobile interaction
        """
        # Root route for connection testing
        @self.app.route('/', methods=['GET'])
        def health_check():
            return jsonify({"status": "healthy", "message": "Academic RAG API is running"}), 200

        # Define chat method with correct context
        def chat_handler():
            """
            Handle chat interactions
            """
            try:
                # Parse incoming JSON data
                data = request.get_json()
                
                # Validate input
                if not data or 'message' not in data:
                    return jsonify({
                        "status": "error", 
                        "message": "Invalid input. 'message' field is required."
                    }), 400
                
                # Prepare input dictionary for the assistant
                input_dict = {"input": data['message']}
                
                # Invoke chat with input
                response = self.assistant.invoke(input_dict)
                
                # Return response in the format expected by frontend
                return jsonify({
                    "status": "success",
                    "message": response.get('output', 'No response')
                })
            
            except Exception as e:
                self.logger.error(f"Chat handling error: {e}")
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        # Register the route with the chat handler
        self.app.add_url_rule('/chat', 'chat_handler', chat_handler, methods=['POST'])

        # Additional routes follow the same pattern
        def search_handler():
            """
            Handle knowledge graph search
            """
            try:
                data = request.get_json()
                
                if not data or 'query' not in data:
                    return jsonify({
                        "status": "error", 
                        "message": "Invalid input. 'query' field is required."
                    }), 400
                
                # Perform search
                graph_result = self.assistant.advanced_knowledge_graph_query(data['query'])
                contextual_result = self.assistant.contextual_search(data['query'])
                
                return jsonify({
                    "status": "success",
                    "graph_results": graph_result,
                    "contextual_results": contextual_result
                })
            
            except Exception as e:
                self.logger.error(f"Search handling error: {e}")
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        self.app.add_url_rule('/search', 'search_handler', search_handler, methods=['POST'])

        def learning_path_handler():
            """
            Generate learning path for a subject
            """
            try:
                data = request.get_json()
                
                if not data or 'subject' not in data:
                    return jsonify({
                        "status": "error", 
                        "message": "Invalid input. 'subject' field is required."
                    }), 400
                
                # Generate learning path
                learning_path = self.assistant.generate_learning_path(data['subject'])
                
                return jsonify({
                    "status": "success",
                    "learning_path": learning_path
                })
            
            except Exception as e:
                self.logger.error(f"Learning path generation error: {e}")
                return jsonify({
                    "status": "error",
                    "message": str(e)
                }), 500

        self.app.add_url_rule('/learning-path', 'learning_path_handler', learning_path_handler, methods=['POST'])

    def run(self, host='0.0.0.0', port=8000, debug=True):
        """
        Run the Flask application
        """
        try:
            self.logger.info(f"🚀 Starting Academic RAG API on {host}:{port}")
            self.app.run(host=host, port=port, debug=debug)
        except Exception as e:
            self.logger.error(f"API startup failed: {e}")
            sys.exit(1)

def main():
    # Create and run the API
    api = AcademicRAGAPI(debug_mode=True)
    api.run()

if __name__ == "__main__":
    main()