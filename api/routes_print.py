# This file is being replaced by a modular structure with blueprints.
# Please refer to the new main_app.py and the routes directory.
# This file can be deprecated once the transition is complete.

# Import necessary modules and create a backward compatibility layer
# to keep existing code working during transition
from flask import Flask, request, jsonify
from flask_cors import CORS
import sys
import os
import traceback
from datetime import datetime

# Add project root to path for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

# Create and configure the app - avoid circular imports
def get_app():
    # Import locally to avoid circular imports
    from api.main_app import create_app
    return create_app()

# Create app on demand
app = get_app()

# Add backward compatibility for direct invocation
if __name__ == '__main__':
    print("Starting Flask server using legacy entry point...")
    print("Consider using main_app.py instead")
    print("Attempting to bind to: http://0.0.0.0:8081")
    
    # Run the Flask app
    app.run(
        host='0.0.0.0', 
        port=8000, 
        debug=True,
        threaded=True  # Enable multi-threading
    )