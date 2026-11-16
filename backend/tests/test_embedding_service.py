from unittest.mock import MagicMock, patch
import numpy as np
import pytest

from app.config import settings
from app.services.embedding_service import (
    embed_query,
    embed_texts,
    get_embedding_model,
    resolve_device,
)


def test_resolve_device():
    assert resolve_device("cpu") == "cpu"
    # When CUDA is not available, auto and cuda fall back safely to cpu
    with patch("torch.cuda.is_available", return_value=False):
        assert resolve_device("auto") == "cpu"
        assert resolve_device("cuda") == "cpu"

    with patch("torch.cuda.is_available", return_value=True):
        assert resolve_device("auto") == "cuda"
        assert resolve_device("cuda") == "cuda"


def test_embed_texts_empty():
    assert embed_texts([]) == []


def test_embed_texts_mocked():
    dummy_vec1 = np.ones(1024, dtype=np.float32)
    dummy_vec2 = np.zeros(1024, dtype=np.float32)
    dummy_vec2[0] = 1.0

    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([dummy_vec1, dummy_vec2])

    with patch("app.services.embedding_service.get_embedding_model", return_value=mock_model):
        results = embed_texts(["first", "second"], batch_size=2)
        assert len(results) == 2
        assert len(results[0]) == settings.embedding_dimensions
        assert len(results[1]) == settings.embedding_dimensions
        assert results[0][0] == 1.0
        assert results[1][0] == 1.0


def test_embed_query_mocked():
    dummy_vec = np.ones(1024, dtype=np.float32)
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([dummy_vec])

    with patch("app.services.embedding_service.get_embedding_model", return_value=mock_model):
        query_vec = embed_query("What is revenue?")
        assert len(query_vec) == settings.embedding_dimensions
        assert isinstance(query_vec, list)
        assert isinstance(query_vec[0], float)


def test_embed_query_empty_string():
    dummy_vec = np.ones(1024, dtype=np.float32)
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([dummy_vec])

    with patch("app.services.embedding_service.get_embedding_model", return_value=mock_model):
        # Empty string should not raise error and should embed a fallback space
        query_vec = embed_query("")
        assert len(query_vec) == settings.embedding_dimensions


def test_document_chunk_omits_tsv_content_on_insert():
    import uuid
    import sqlalchemy as sa
    from sqlalchemy.dialects import postgresql
    from app.models.entities import DocumentChunk

    ins = sa.insert(DocumentChunk).values(
        user_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        page_number=1,
        content="test content",
        embedding=[0.1] * 1024,
    )
    compiled = str(ins.compile(dialect=postgresql.dialect()))
    assert "tsv_content" not in compiled
