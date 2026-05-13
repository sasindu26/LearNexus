import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration dictionary
config = {
    "neo4j": {
        "url": "bolt://localhost:7691",
        "username": "neo4j",
        "password": "Mento@2152",
        "database": "neo4j"
    },
    "api": {
        "gemini_key": os.getenv('GEMINI_API_KEY', 'AIzaSyDJnqEdIfcIeyirGe2GI5MxQJJIcfsS83U'),
        "port": 8000,
        "host": "0.0.0.0"
    }
}
