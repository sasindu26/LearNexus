import os
import sys
import pytest

# Make the project importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Dummy env vars so route imports don't crash trying to read real secrets
os.environ.setdefault("NEO4J_URI", "bolt://localhost:7687")
os.environ.setdefault("NEO4J_USER", "neo4j")
os.environ.setdefault("NEO4J_PASSWORD", "dummy")
os.environ.setdefault("GEMINI_API_KEY", "dummy")
os.environ.setdefault("DISABLE_EMBEDDINGS", "true")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-ci-only-32bytes")


@pytest.fixture(scope="session")
def app():
    from api.main_app import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()
