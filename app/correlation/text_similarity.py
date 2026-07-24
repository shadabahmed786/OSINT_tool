import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# Small resident sentence embedding model for bio/alias text similarity (§7)
_model = None

def get_embedding_model():
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer
            # Small resident embedding model (~100MB RAM)
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("SentenceTransformer model loaded residently.")
        except Exception as e:
            logger.warning("sentence-transformers not installed; falling back to token Jaccard similarity: %s", e)
            _model = "fallback"
    return _model

def compute_text_similarity(text1: str, text2: str) -> float:
    """
    Computes text similarity score (0.0 to 1.0) between two bio or display name strings (§7).
    """
    t1 = (text1 or "").strip().lower()
    t2 = (text2 or "").strip().lower()

    if not t1 or not t2:
        return 0.0

    if t1 == t2:
        return 1.0

    model = get_embedding_model()
    if model != "fallback" and model is not None:
        try:
            embeddings = model.encode([t1, t2], normalize_embeddings=True)
            similarity = float((embeddings[0] * embeddings[1]).sum())
            return max(0.0, min(1.0, similarity))
        except Exception as e:
            logger.warning("Error in sentence transformer encoding: %s", e)

    # Token Jaccard Fallback
    tokens1 = set(t1.split())
    tokens2 = set(t2.split())
    intersection = tokens1.intersection(tokens2)
    union = tokens1.union(tokens2)
    return len(intersection) / len(union) if union else 0.0
