"""Centralized embedding generation. Uses SentenceTransformer if available, falls back to keyword vectors."""
import logging
import math

logger = logging.getLogger(__name__)

_model = None
_USE_ST = False


def _load_model():
    global _model, _USE_ST
    if _model is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer('all-MiniLM-L6-v2')
        _USE_ST = True
        logger.info("SentenceTransformer loaded: all-MiniLM-L6-v2")
    except Exception as e:
        logger.warning(f"SentenceTransformer unavailable, using keyword fallback: {e}")
        _USE_ST = False


def embed_text(text: str) -> list:
    _load_model()
    if not text:
        return []
    if _USE_ST:
        return _model.encode(text, normalize_embeddings=True).tolist()
    return _keyword_vector(text)


def embed_batch(texts: list) -> list:
    _load_model()
    if not texts:
        return []
    if _USE_ST:
        return _model.encode(texts, normalize_embeddings=True).tolist()
    return [_keyword_vector(t) for t in texts]


def cosine_similarity(vec_a: list, vec_b: list) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ── Keyword fallback (bag-of-words TF vector, dim=256) ──────────────────
_VOCAB_SIZE = 256


def _keyword_vector(text: str) -> list:
    vec = [0.0] * _VOCAB_SIZE
    words = text.lower().split()
    for w in words:
        idx = hash(w) % _VOCAB_SIZE
        vec[idx] += 1.0
    mag = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / mag for v in vec]
