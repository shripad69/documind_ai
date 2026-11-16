"""Local Embedding Service using BAAI/bge-m3 via sentence-transformers.

Provides thread-safe singleton model management and batch/single embedding functions.
Replaces the external Gemini gemini-embedding-001 API dependency.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Sequence

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
_model_lock = threading.Lock()


def resolve_device(configured_device: str) -> str:
    """Resolve device string to actual compute device (cuda or cpu)."""
    device_lower = (configured_device or "cpu").strip().lower()
    if device_lower in ("auto", "cuda"):
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"
    return device_lower


def get_embedding_model():
    """Lazy-load the embedding model as a thread-safe singleton."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer

                device = resolve_device(settings.embedding_device)
                logger.info(
                    "embedding_service.loading_model model=%s device=%s cache_dir=%s",
                    settings.embedding_model_name,
                    device,
                    settings.embedding_cache_dir,
                )
                start = time.perf_counter()
                _model = SentenceTransformer(
                    settings.embedding_model_name,
                    device=device,
                    cache_folder=settings.embedding_cache_dir,
                    trust_remote_code=False,
                )
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "embedding_service.model_loaded elapsed_ms=%.0f device=%s",
                    elapsed_ms,
                    device,
                )
    return _model


def embed_texts(
    texts: Sequence[str],
    *,
    batch_size: int | None = None,
    show_progress: bool = False,
) -> list[list[float]]:
    """
    Embed a sequence of text chunks and return their dense 1024-d unit vectors.

    Args:
        texts: Sequence of text strings to embed.
        batch_size: Batch size for tokenization and inference.
        show_progress: Whether to show a progress bar during inference.

    Returns:
        List of embedding vectors, each of length settings.embedding_dimensions.
    """
    if not texts:
        return []

    model = get_embedding_model()
    effective_batch_size = batch_size or settings.embedding_batch_size

    start = time.perf_counter()
    embeddings = model.encode(
        list(texts),
        batch_size=effective_batch_size,
        normalize_embeddings=True,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "embedding_service.batch_completed count=%d batch_size=%d elapsed_ms=%.1f",
        len(texts),
        effective_batch_size,
        elapsed_ms,
    )

    target_dim = settings.embedding_dimensions
    result: list[list[float]] = []
    for vec in embeddings:
        vec_list = vec[:target_dim].tolist() if hasattr(vec, "tolist") else list(vec[:target_dim])
        result.append(vec_list)

    return result


def embed_query(query: str) -> list[float]:
    """
    Embed a single search query string for RAG vector retrieval.

    bge-m3 uses symmetric representations, so no prompt prefix is required.
    """
    cleaned = (query or "").strip()
    if not cleaned:
        cleaned = " "
    vectors = embed_texts([cleaned])
    return vectors[0]


def warmup() -> bool:
    """Pre-load model weights into memory during process initialization."""
    try:
        embed_query("warmup query")
        return True
    except Exception as error:
        logger.warning("embedding_service.warmup_failed error=%s", error)
        return False
