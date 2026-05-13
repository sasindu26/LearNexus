from flask import Flask, jsonify, request
from flask_cors import CORS
import os
import sys
from dotenv import load_dotenv
load_dotenv(override=True)
import nltk
from datetime import datetime
import platform

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

# Import config
from config.logging_config import setup_logger

# Initialize NLTK dependencies
nltk.download('averaged_perceptron_tagger_eng', quiet=True)

# Setup logger for main app
logger = setup_logger('main_app', 'main_app.log')

def create_app(config=None):
    """
    Factory function to create and configure the Flask application
    """
    app = Flask(__name__)
    
    # Configure the app
    if config:
        app.config.from_mapping(config)
    
    # Enable CORS for all routes with proper configuration
    CORS(app, resources={r"/*": {"origins": "*"}}, 
         supports_credentials=False,
         allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
         methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    
    # Import blueprints inside the function to avoid circular imports
    # This is a common pattern in Flask applications
    # Use relative imports since we're in the same package
    from api.routes.chat_bot import chat_bp
    from api.routes.topic_extracter import topic_bp
    from api.routes.module_name_fetcher import module_bp
    from api.routes.tech_updates_for_fe import tech_updates_bp
    from api.routes.tech_updates_module import tech_module_bp
    from api.routes.auth import auth_bp, courses_bp
    from api.routes.module_chat import module_chat_bp
    from api.routes.profile import profile_bp
    from api.routes.job_recommendations import job_rec_bp
    from api.routes.certificate_recommendations import cert_rec_bp
    from api.routes.career_intelligence import career_bp

    # Register blueprints
    app.register_blueprint(chat_bp)
    app.register_blueprint(topic_bp)
    app.register_blueprint(module_bp)
    app.register_blueprint(tech_updates_bp, url_prefix='/api')
    app.register_blueprint(tech_module_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(module_chat_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(job_rec_bp)
    app.register_blueprint(cert_rec_bp)
    app.register_blueprint(career_bp)

    # Start inactivity reminder scheduler
    try:
        from api.scheduler import start_scheduler
        start_scheduler()
    except Exception as _sched_err:
        logger.warning(f"Scheduler not started: {_sched_err}")

    # Health Check Endpoint
    @app.route('/', methods=['GET' ,'POST'])
    def health_check():
        """
        Enhanced health check endpoint
        """
        # Import inside the function to avoid circular imports
        from api.routes.chat_bot import chat_agent
        
        status = "Chatbot Initialized" if chat_agent is not None else "Chatbot Not Initialized"
        
        logger.info("Health check request received")
        
        return jsonify({
            "status": "Server is running",
            "chatbot_status": status,
            "server_time": datetime.now().isoformat(),
            "python_version": platform.python_version(),
            # "flask_version": Flask.__version__,
            "cors_enabled": True,
            "endpoints": {
                "health": "/",
                "chat": "/chat",
                "module_content": "/module-content/<module_name>/topics",
                "test_connection": "/test-connection"
            }
        }), 200
    
    # Add a catch-all route to help diagnose 404 errors
    @app.errorhandler(404)
    def handle_404(e):
        """
        Custom 404 handler to help diagnose URL pattern issues
        """
        # Log details about the request that caused the 404
        path = request.path
        method = request.method
        args = dict(request.args)
        headers = dict(request.headers)
        
        logger.warning(f"404 Error: {method} {path}")
        logger.info(f"Request args: {args}")
        logger.info(f"Request headers: {headers}")
        

        # Suggest possible correct endpoints
        suggestions = []
        if '/modules/' in path:
            alt_path = path.replace('/modules/', '/module-content/')
            suggestions.append(alt_path)
        elif '/module-content/' in path:
            alt_path = path.replace('/module-content/', '/modules/')
            suggestions.append(alt_path)
            
        return jsonify({
            "status": "error",
            "code": 404,
            "message": f"Endpoint not found: {method} {path}",
            "possible_alternatives": suggestions,
            "available_patterns": [
                "/module-content/<module_name>/topics",
                "/modules/<module_name>/topics",
                "/api/module-articles?module=<module_name>&limit=<limit>",
                "/tech-updates (POST with moduleName in body)"
            ]
        }), 404
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    print("Starting Flask server...")
    print("Attempting to bind to: http://0.0.0.0:8000")
    
    # Run the Flask app
    app.run(
        host='0.0.0.0', 
        port=8000, 
        debug=True,
        threaded=True  # Enable multi-threading
    )
