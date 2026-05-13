"""Extract skills from text using Gemini API with regex fallback."""
import os
import json
import re
import logging

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Common tech skills for regex fallback
_SKILL_PATTERNS = [
    "python", "java", "javascript", "typescript", "c\\+\\+", "c#", "go", "rust", "kotlin", "swift",
    "react", "angular", "vue", "next\\.?js", "node\\.?js", "django", "flask", "fastapi", "spring",
    "sql", "mysql", "postgresql", "mongodb", "neo4j", "redis", "sqlite",
    "machine learning", "deep learning", "nlp", "computer vision", "data science", "data analysis",
    "tensorflow", "pytorch", "scikit.learn", "pandas", "numpy", "keras",
    "docker", "kubernetes", "aws", "azure", "gcp", "ci/cd", "devops", "git", "linux",
    "html", "css", "tailwind", "bootstrap", "restful api", "graphql", "microservices",
    "agile", "scrum", "oop", "data structures", "algorithms", "networking", "cybersecurity",
    "android", "ios", "flutter", "react native", "unity", "unreal engine",
    "r", "matlab", "scala", "hadoop", "spark", "kafka", "elasticsearch",
]
_SKILL_RE = re.compile(r'\b(' + '|'.join(_SKILL_PATTERNS) + r')\b', re.IGNORECASE)


def extract_skills(text: str, context: str = "") -> list:
    """Return list of skill name strings extracted from text."""
    if not text:
        return []
    skills = _extract_with_gemini(text, context)
    if not skills:
        skills = _extract_with_regex(text)
    return list(dict.fromkeys(s.strip().lower() for s in skills if s.strip()))


def _extract_with_gemini(text: str, context: str = "") -> list:
    if not GEMINI_API_KEY:
        return []
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash")
        prompt = (
            f"Extract a list of technical skills and technologies from the following text. "
            f"Return ONLY a JSON array of skill name strings, nothing else. "
            f"Context: {context}\n\nText: {text[:2000]}"
        )
        response = model.generate_content(prompt)
        raw = response.text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r'^```[a-z]*\n?', '', raw).rstrip('`').strip()
        skills = json.loads(raw)
        if isinstance(skills, list):
            return [str(s) for s in skills]
    except Exception as e:
        logger.debug(f"Gemini skill extraction failed: {e}")
    return []


def _extract_with_regex(text: str) -> list:
    matches = _SKILL_RE.findall(text)
    return list(dict.fromkeys(m.lower() for m in matches))
