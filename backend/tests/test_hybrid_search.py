"""
Unit tests for the hybrid search module (BM25 + Dense Vector + RRF).

Tests cover:
  - Reciprocal Rank Fusion score computation and ranking.
  - Edge cases: empty lists, single-source results, deduplication.
  - BM25 score threshold filtering.
  - HybridSearcher mode dispatch.
  - tsquery sanitization.
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services.hybrid_search import (
    BM25Searcher,
    DenseVectorSearcher,
    HybridSearcher,
    RetrievedChunk,
    RetrievalResult,
    reciprocal_rank_fusion,
    BM25_CANDIDATE_LIMIT,
    VECTOR_CANDIDATE_LIMIT,
    RRF_K,
    FINAL_TOP_K,
    BM25_SCORE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_chunk(
    chunk_id: uuid.UUID | None = None,
    bm25_score: float = 0.0,
    vector_distance: float = 0.0,
    content: str = "test content",
    file_name: str = "test.pdf",
    retrieval_source: str = "",
) -> RetrievedChunk:
    """Create a RetrievedChunk with sensible defaults for testing."""
    return RetrievedChunk(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=uuid.uuid4(),
        chunk_index=0,
        page_number=1,
        content=content,
        file_name=file_name,
        bm25_score=bm25_score,
        vector_distance=vector_distance,
        retrieval_source=retrieval_source,
    )


# ---------------------------------------------------------------------------
# Test: Reciprocal Rank Fusion
# ---------------------------------------------------------------------------

class TestReciprocalRankFusion:
    """Tests for the reciprocal_rank_fusion function."""

    def test_empty_inputs_returns_empty(self):
        """Both BM25 and vector results empty should return empty list."""
        result = reciprocal_rank_fusion([], [])
        assert result == []

    def test_bm25_only_results(self):
        """When vector results are empty, RRF should return BM25 results ranked by their RRF contribution."""
        c1 = make_chunk(bm25_score=2.5)
        c2 = make_chunk(bm25_score=1.0)
        result = reciprocal_rank_fusion([c1, c2], [])
        assert len(result) == 2
        # c1 has rank 1, c2 has rank 2 in BM25 list
        # RRF(c1) = 1/(60+1) = 0.01639...
        # RRF(c2) = 1/(60+2) = 0.01613...
        assert result[0].chunk_id == c1.chunk_id
        assert result[1].chunk_id == c2.chunk_id
        assert result[0].rrf_score > result[1].rrf_score

    def test_vector_only_results(self):
        """When BM25 results are empty, RRF should return vector results."""
        c1 = make_chunk(vector_distance=0.1)
        c2 = make_chunk(vector_distance=0.3)
        result = reciprocal_rank_fusion([], [c1, c2])
        assert len(result) == 2
        assert result[0].chunk_id == c1.chunk_id

    def test_overlapping_chunks_get_boosted(self):
        """A chunk appearing in both lists should get a higher RRF score than one in only one list."""
        shared_id = uuid.uuid4()
        bm25_chunk = make_chunk(chunk_id=shared_id, bm25_score=2.0)
        vector_chunk = make_chunk(chunk_id=shared_id, vector_distance=0.1)
        bm25_only = make_chunk(bm25_score=3.0)
        vector_only = make_chunk(vector_distance=0.05)

        result = reciprocal_rank_fusion(
            [bm25_only, bm25_chunk],  # ranks 1, 2
            [vector_only, vector_chunk],  # ranks 1, 2
        )

        # shared_id gets 1/(60+2) + 1/(60+2) = 2 * 0.01613 = 0.03226
        # bm25_only gets 1/(60+1) = 0.01639
        # vector_only gets 1/(60+1) = 0.01639
        # So shared should be ranked first
        assert result[0].chunk_id == shared_id
        assert result[0].retrieval_source == "bm25+vector"

    def test_rrf_score_calculation_exact(self):
        """Verify exact RRF score computation with known values."""
        k = 60
        c1_id = uuid.uuid4()
        c2_id = uuid.uuid4()
        bm25_list = [make_chunk(chunk_id=c1_id)]  # rank 1
        vector_list = [make_chunk(chunk_id=c2_id), make_chunk(chunk_id=c1_id)]  # ranks 1, 2

        result = reciprocal_rank_fusion(bm25_list, vector_list, k=k)

        c1_expected = 1.0 / (k + 1) + 1.0 / (k + 2)  # in both lists
        c2_expected = 1.0 / (k + 1)  # vector only

        c1_result = next(c for c in result if c.chunk_id == c1_id)
        c2_result = next(c for c in result if c.chunk_id == c2_id)

        assert abs(c1_result.rrf_score - c1_expected) < 1e-10
        assert abs(c2_result.rrf_score - c2_expected) < 1e-10

    def test_top_k_truncation(self):
        """Result list should be truncated to top_k."""
        chunks_bm25 = [make_chunk() for _ in range(15)]
        chunks_vector = [make_chunk() for _ in range(15)]
        result = reciprocal_rank_fusion(chunks_bm25, chunks_vector, top_k=5)
        assert len(result) <= 5

    def test_top_k_with_fewer_results(self):
        """When total unique chunks < top_k, return all of them."""
        c1 = make_chunk()
        c2 = make_chunk()
        result = reciprocal_rank_fusion([c1], [c2], top_k=8)
        assert len(result) == 2

    def test_results_sorted_descending_by_rrf_score(self):
        """Output must be sorted by RRF score in descending order."""
        chunks_bm25 = [make_chunk() for _ in range(10)]
        chunks_vector = [make_chunk() for _ in range(10)]
        result = reciprocal_rank_fusion(chunks_bm25, chunks_vector, top_k=20)
        for i in range(len(result) - 1):
            assert result[i].rrf_score >= result[i + 1].rrf_score


# ---------------------------------------------------------------------------
# Test: BM25Searcher tsquery sanitization
# ---------------------------------------------------------------------------

class TestBM25TsquerySanitization:
    """Tests for BM25Searcher._build_tsquery."""

    def test_normal_query_preserved(self):
        result = BM25Searcher._build_tsquery("what is the revenue growth")
        assert result == "what is the revenue growth"

    def test_special_characters_stripped(self):
        result = BM25Searcher._build_tsquery("ISO-27001 & compliance @test!")
        assert "ISO-27001" in result
        assert "compliance" in result
        assert "@" not in result
        assert "&" not in result

    def test_empty_query(self):
        result = BM25Searcher._build_tsquery("")
        assert result == ""

    def test_whitespace_normalization(self):
        result = BM25Searcher._build_tsquery("  too   many    spaces  ")
        assert result == "too many spaces"

    def test_unicode_preserved(self):
        result = BM25Searcher._build_tsquery("temperature -1.5 degrees")
        assert "-1.5" in result


# ---------------------------------------------------------------------------
# Test: HybridSearcher mode dispatch
# ---------------------------------------------------------------------------

class TestHybridSearcherModeDispatch:
    """Tests for HybridSearcher.search() mode routing."""

    def setup_method(self):
        self.searcher = HybridSearcher()
        self.mock_db = MagicMock()
        self.user_id = uuid.uuid4()
        self.workspace_id = uuid.uuid4()
        self.query = "test query"
        self.query_embedding = [0.1] * 384

    @patch.object(DenseVectorSearcher, "search")
    def test_cosine_baseline_mode(self, mock_vector_search):
        """cosine_baseline mode should only call vector searcher."""
        mock_vector_search.return_value = [make_chunk() for _ in range(3)]

        result = self.searcher.search(
            self.mock_db, self.user_id, self.workspace_id,
            self.query, self.query_embedding, mode="cosine_baseline",
        )

        assert result.mode == "cosine_baseline"
        assert len(result.chunks) == 3
        mock_vector_search.assert_called_once()

    @patch.object(BM25Searcher, "search")
    def test_bm25_only_mode(self, mock_bm25_search):
        """bm25_only mode should only call BM25 searcher."""
        mock_bm25_search.return_value = [make_chunk(bm25_score=1.5) for _ in range(2)]

        result = self.searcher.search(
            self.mock_db, self.user_id, self.workspace_id,
            self.query, self.query_embedding, mode="bm25_only",
        )

        assert result.mode == "bm25_only"
        assert len(result.chunks) == 2
        mock_bm25_search.assert_called_once()

    @patch.object(DenseVectorSearcher, "search")
    @patch.object(BM25Searcher, "search")
    def test_hybrid_rrf_mode(self, mock_bm25_search, mock_vector_search):
        """hybrid_rrf mode should call both searchers."""
        mock_bm25_search.return_value = [make_chunk(bm25_score=1.0)]
        mock_vector_search.return_value = [make_chunk(vector_distance=0.2)]

        result = self.searcher.search(
            self.mock_db, self.user_id, self.workspace_id,
            self.query, self.query_embedding, mode="hybrid_rrf",
        )

        assert result.mode == "hybrid_rrf"
        mock_bm25_search.assert_called_once()
        mock_vector_search.assert_called_once()

    @patch.object(DenseVectorSearcher, "search")
    @patch.object(BM25Searcher, "search")
    def test_unknown_mode_falls_back_to_hybrid(self, mock_bm25_search, mock_vector_search):
        """Unknown mode should fall back to hybrid_rrf."""
        mock_bm25_search.return_value = []
        mock_vector_search.return_value = [make_chunk()]

        result = self.searcher.search(
            self.mock_db, self.user_id, self.workspace_id,
            self.query, self.query_embedding, mode="invalid_mode",
        )

        assert result.mode == "hybrid_rrf"

    @patch.object(DenseVectorSearcher, "search")
    @patch.object(BM25Searcher, "search")
    def test_hybrid_with_zero_bm25_matches(self, mock_bm25_search, mock_vector_search):
        """When BM25 returns nothing, RRF should smoothly return vector-only results."""
        mock_bm25_search.return_value = []
        vector_chunks = [make_chunk(vector_distance=0.1 * i) for i in range(1, 6)]
        mock_vector_search.return_value = vector_chunks

        result = self.searcher.search(
            self.mock_db, self.user_id, self.workspace_id,
            self.query, self.query_embedding, mode="hybrid_rrf",
        )

        assert result.bm25_candidate_count == 0
        assert result.vector_candidate_count == 5
        assert len(result.chunks) == 5
        # All chunks should come from vector only
        for chunk in result.chunks:
            assert chunk.retrieval_source == "vector"

    def test_latency_is_recorded(self):
        """RetrievalResult should have a non-negative latency_ms."""
        with patch.object(BM25Searcher, "search", return_value=[]):
            with patch.object(DenseVectorSearcher, "search", return_value=[]):
                result = self.searcher.search(
                    self.mock_db, self.user_id, self.workspace_id,
                    self.query, self.query_embedding, mode="hybrid_rrf",
                )
                assert result.latency_ms >= 0


# ---------------------------------------------------------------------------
# Test: RetrievedChunk data structure
# ---------------------------------------------------------------------------

class TestRetrievedChunk:
    """Tests for the RetrievedChunk dataclass."""

    def test_default_values(self):
        chunk = RetrievedChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            chunk_index=0,
            page_number=1,
            content="test",
            file_name="test.pdf",
        )
        assert chunk.bm25_score == 0.0
        assert chunk.vector_distance == 0.0
        assert chunk.rrf_score == 0.0
        assert chunk.retrieval_source == ""


# ---------------------------------------------------------------------------
# Test: Edge case - fewer than K chunks in workspace
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Edge case tests for the hybrid search pipeline."""

    def test_rrf_with_single_chunk_in_both(self):
        """Single chunk appearing in both lists gets correct double score."""
        shared_id = uuid.uuid4()
        c_bm25 = make_chunk(chunk_id=shared_id, bm25_score=1.0)
        c_vec = make_chunk(chunk_id=shared_id, vector_distance=0.1)

        result = reciprocal_rank_fusion([c_bm25], [c_vec], k=60, top_k=8)
        assert len(result) == 1
        expected_score = 1.0 / (60 + 1) + 1.0 / (60 + 1)
        assert abs(result[0].rrf_score - expected_score) < 1e-10
        assert result[0].retrieval_source == "bm25+vector"

    def test_rrf_preserves_content_and_metadata(self):
        """RRF should preserve chunk content and metadata from the first occurrence."""
        cid = uuid.uuid4()
        doc_id = uuid.uuid4()
        c_bm25 = RetrievedChunk(
            chunk_id=cid, document_id=doc_id, chunk_index=5,
            page_number=3, content="important text", file_name="report.pdf",
            bm25_score=2.0, retrieval_source="bm25",
        )
        c_vec = RetrievedChunk(
            chunk_id=cid, document_id=doc_id, chunk_index=5,
            page_number=3, content="important text", file_name="report.pdf",
            vector_distance=0.15, retrieval_source="vector",
        )
        result = reciprocal_rank_fusion([c_bm25], [c_vec])
        assert result[0].content == "important text"
        assert result[0].file_name == "report.pdf"
        assert result[0].page_number == 3
        assert result[0].chunk_index == 5
