from flask import Blueprint, request, jsonify
from neo4j import GraphDatabase
import os
import jwt
import uuid
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(project_root)

from models.services.gemini_service import GeminiService
from config.logging_config import setup_logger

logger = setup_logger('module_chat', 'module_chat.log')

module_chat_bp = Blueprint('module_chat', __name__)

SECRET_KEY = "learnexus_ai_secret_key_2026"
URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
DB_USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "LearNexus1212")

try:
    driver = GraphDatabase.driver(URI, auth=(DB_USER, PASSWORD))
except Exception:
    driver = None

_gemini = None


def _get_gemini():
    global _gemini
    if _gemini is None:
        _gemini = GeminiService()
    return _gemini


def _user_id_from_token(auth_header: str) -> str:
    token = auth_header.replace("Bearer ", "").strip() if auth_header else ""
    if not token:
        return "anonymous"
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload.get("email") or payload.get("sub") or "anonymous"
    except Exception:
        return "anonymous"


def _get_module_topics(module_name: str) -> list:
    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (m:Module {name: $name})-[:HAS_TOPIC]->(t:Topic)
                RETURN t.name AS name, t.description AS description
                LIMIT 20
                """,
                name=module_name,
            )
            return [
                {"name": r["name"], "description": r["description"] or ""}
                for r in result
            ]
    except Exception as e:
        logger.error(f"Error fetching topics for {module_name}: {e}")
        return []


def _save_message(user_id: str, module_name: str, role: str, text: str):
    try:
        with driver.session() as session:
            session.run(
                """
                CREATE (:ModuleChatMessage {
                    id: $id,
                    user_id: $user_id,
                    module_name: $module_name,
                    role: $role,
                    text: $text,
                    timestamp: datetime()
                })
                """,
                id=str(uuid.uuid4()),
                user_id=user_id,
                module_name=module_name,
                role=role,
                text=text,
            )
    except Exception as e:
        logger.error(f"Error saving message: {e}")


@module_chat_bp.route("/api/module-chat/history", methods=["GET"])
def get_history():
    module_name = request.args.get("module", "")
    user_id = _user_id_from_token(request.headers.get("Authorization", ""))

    if not module_name:
        return jsonify({"error": "module name required"}), 400

    try:
        with driver.session() as session:
            result = session.run(
                """
                MATCH (m:ModuleChatMessage {user_id: $user_id, module_name: $module_name})
                RETURN m.id AS id, m.role AS role, m.text AS text
                ORDER BY m.timestamp ASC
                """,
                user_id=user_id,
                module_name=module_name,
            )
            messages = [
                {"id": r["id"], "role": r["role"], "text": r["text"]}
                for r in result
            ]
        return jsonify({"messages": messages})
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        return jsonify({"error": str(e)}), 500


@module_chat_bp.route("/api/module-chat/message", methods=["POST"])
def send_message():
    data = request.json or {}
    user_message = data.get("message", "").strip()
    module_name = data.get("module_name", "")
    history = data.get("history", [])  # list of {role, text}
    user_id = _user_id_from_token(request.headers.get("Authorization", ""))

    if not user_message or not module_name:
        return jsonify({"error": "message and module_name are required"}), 400

    # Fetch module topics from DB to ground the AI
    topics = _get_module_topics(module_name)
    topics_text = (
        "\n".join([f"- {t['name']}: {t['description']}" for t in topics])
        if topics
        else "Topics not yet available."
    )

    # Build conversation history string
    history_text = "\n".join(
        [
            f"{'Student' if m['role'] == 'user' else 'LearNexus AI'}: {m['text']}"
            for m in history[-6:]
        ]
    )

    prompt = f"""You are LearNexus AI, a dedicated learning assistant for the university module "{module_name}".

Module topics you teach:
{topics_text}

Your strict rules:
1. ONLY answer questions directly related to "{module_name}" and its topics above.
2. If a question is completely unrelated to this module, politely decline: "I'm your dedicated assistant for {module_name}. Please ask something related to this module!"
3. Keep answers educational, clear, and concise (under 200 words unless explaining complex concepts).
4. You can explain concepts, give examples, clarify topics, and help students understand the material.
5. Never recommend other courses or act as a general-purpose AI assistant.
6. Do NOT re-introduce yourself if there is existing chat history.

Recent conversation:
{history_text}

Student: {user_message}
LearNexus AI:"""

    # Persist user message
    _save_message(user_id, module_name, "user", user_message)

    # Generate AI response
    response = _get_gemini().generate_content(prompt)
    if not response:
        response = "I'm sorry, I couldn't generate a response right now. Please try again."

    # Persist AI response
    _save_message(user_id, module_name, "assistant", response)

    return jsonify({"message": response, "status": "success"})
