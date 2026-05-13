from flask import Blueprint, request, jsonify
import traceback
import os
import sys

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(project_root)

from config.logging_config import setup_logger

# Setup logger
logger = setup_logger('module_name_fetcher', 'module_name_fetcher.log')

# Create blueprint
module_bp = Blueprint('module_name_fetcher', __name__)

# Add a new route for connection testing
@module_bp.route('/test-connection', methods=['GET', 'OPTIONS'])
def test_connection():
    """
    Simple endpoint for testing API connection
    """
    from datetime import datetime
    
    logger.info("Received test connection request")
    return jsonify({
        "status": "success",
        "message": "Connection successful",
        "server": "Flask API Server",
        "timestamp": datetime.now().isoformat()
    }), 200
