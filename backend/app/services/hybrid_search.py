"""
Hybrid Search Service: BM25 + Dense Vector + Reciprocal Rank Fusion (RRF).

This module implements a three-component retrieval pipeline:
  1. BM25 lexical keyword search via PostgreSQL tsvector/tsquery and ts_rank.
  2. Dense vector semantic search via pgvector HNSW cosine distance.
  3. Reciprocal Rank Fusion (RRF) to merge and re-rank candidates from both.

Supports three retrieval modes:
  - "hybrid_rrf" (default): BM25 + Dense + RRF fusion.
  - "cosine_baseline": Pure pgvector cosine distance search (original behavior).
  - "bm25_only": Pure BM25 lexical search only.
"""

from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.entities import Document, DocumentChunk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BM25_CANDIDATE_LIMIT = 20
VECTOR_CANDIDATE_LIMIT = 20
RRF_K = 60
FINAL_TOP_K = 8
BM25_SCORE_THRESHOLD = 0.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RetrievedChunk:
    """Represents a single retrieved document chunk with scoring metadata."""
    chunk_id: UUID
    document_id: UUID
    chunk_index: int
    page_number: int | None
    content: str
    file_name: str
    bm25_score: float = 0.0
    vector_distance: float = 0.0
    rrf_score: float = 0.0
    retrieval_source: str = ""


@dataclass
class RetrievalResult:
    """Container for the final retrieval output with diagnostics."""
    chunks: list[RetrievedChunk] = field(default_factory=list)
    mode: str = "hybrid_rrf"
    bm25_candidate_count: int = 0
    vector_candidate_count: int = 0
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# BM25 Lexical Search
# ---------------------------------------------------------------------------

class BM25Searcher:
    """
    Performs lexical keyword search using PostgreSQL full-text search.

    Uses ts_rank with Okapi BM25-equivalent normalization flags.
    PostgreSQL ts_rank normalization flag 1 divides by (1 + log(doc_length)),
    and flag 4 divides by mean harmonic distance between extents.
    These together approximate Okapi BM25 behavior (k1=1.5, b=0.75).
    """

    def search(
        self,
        db: Session,
        user_id: UUID,
        workspace_id: UUID,
        query: str,
        limit: int = BM25_CANDIDATE_LIMIT,
    ) -> list[RetrievedChunk]:
        """Execute BM25 lexical search and return scored chunks."""
        sanitized_query = self._build_tsquery(query)
        if not sanitized_query:
            logger.info("BM25: empty tsquery after sanitization, returning no results")
            return []

        sql = text("""
            SELECT
                dc.id AS chunk_id,
                dc.document_id,
                dc.chunk_index,
                dc.page_number,
                dc.content,
                d.file_name,
                ts_rank(dc.tsv_content, websearch_to_tsquery('english', :query), 1|4) AS bm25_score
            FROM document_chunks dc
            INNER JOIN documents d ON d.id = dc.document_id
            WHERE dc.user_id = :user_id
              AND dc.workspace_id = :workspace_id
              AND d.user_id = :user_id
              AND d.workspace_id = :workspace_id
              AND d.status = 'indexed'
              AND dc.tsv_content @@ websearch_to_tsquery('english', :query)
            ORDER BY bm25_score DESC
            LIMIT :limit
        """)

        rows = db.execute(
            sql,
            {
                "user_id": user_id,
                "workspace_id": workspace_id,
                "query": sanitized_query,
                "limit": limit,
            },
        ).fetchall()

        results = []
        for row in rows:
            score = float(row.bm25_score)
            if score <= BM25_SCORE_THRESHOLD:
                continue
            results.append(
                RetrievedChunk(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    chunk_index=row.chunk_index,
                    page_number=row.page_number,
                    content=row.content,
                    file_name=row.file_name,
                    bm25_score=score,
                    retrieval_source="bm25",
                )
            )

        logger.info("BM25 search returned %d candidates (query: %.60s...)", len(results), query)
        return results

    @staticmethod
    def _build_tsquery(query: str) -> str:
        """
        Sanitize user query for websearch_to_tsquery.

        websearch_to_tsquery handles most user input safely, but we strip
        characters that could cause parsing errors in edge cases.
        """
        cleaned = re.sub(r"[^\w\s\-\.\,\'\"]", " ", query, flags=re.UNICODE)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned


# ---------------------------------------------------------------------------
# Dense Vector Search (pgvector HNSW Cosine)
# ---------------------------------------------------------------------------

class DenseVectorSearcher:
    """
    Performs semantic vector search using pgvector HNSW cosine distance.

    This encapsulates the existing retrieval logic from workspace_rag.py
    into a standalone searcher with a uniform interface.
    """

    def search(
        self,
        db: Session,
        user_id: UUID,
        workspace_id: UUID,
        query_embedding: list[float],
        limit: int = VECTOR_CANDIDATE_LIMIT,
    ) -> list[RetrievedChunk]:
        """Execute pgvector cosine distance search and return scored chunks."""
        dist_expr = DocumentChunk.embedding.cosine_distance(query_embedding).label("cosine_distance")
        stmt = (
            select(DocumentChunk, Document.file_name, dist_expr)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.user_id == user_id,
                DocumentChunk.workspace_id == workspace_id,
                Document.user_id == user_id,
                Document.workspace_id == workspace_id,
                Document.status == "indexed",
            )
            .order_by(dist_expr)
            .limit(limit)
        )
        rows = db.execute(stmt).all()

        results = []
        for chunk, file_name, dist in rows:
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    content=chunk.content,
                    file_name=file_name,
                    vector_distance=float(dist) if dist is not None else 0.0,
                    retrieval_source="vector",
                )
            )

        logger.info("Vector search returned %d candidates", len(results))
        return results


# ---------------------------------------------------------------------------
# Reciprocal Rank Fusion (RRF)
# ---------------------------------------------------------------------------

def reciprocal_rank_fusion(
    bm25_results: list[RetrievedChunk],
    vector_results: list[RetrievedChunk],
    k: int = RRF_K,
    top_k: int = FINAL_TOP_K,
) -> list[RetrievedChunk]:
    """
    Merge BM25 and vector results using Reciprocal Rank Fusion.

    RRF_Score(d) = 1/(k + rank_bm25(d)) + 1/(k + rank_vector(d))

    where k=60, rank is 1-based, and missing ranks contribute 0.

    Args:
        bm25_results: Ranked BM25 candidates (already filtered by score > 0).
        vector_results: Ranked vector candidates (ordered by ascending distance).
        k: RRF smoothing constant (default 60).
        top_k: Number of final results to return (default 8).

    Returns:
        Merged and re-ranked list of top_k RetrievedChunk objects.
    """
    # Build lookup by chunk_id
    chunk_map: dict[UUID, RetrievedChunk] = {}
    rrf_scores: dict[UUID, float] = {}

    # Score BM25 contributions (1-based ranking)
    for rank_idx, chunk in enumerate(bm25_results, start=1):
        cid = chunk.chunk_id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank_idx)
        if cid not in chunk_map:
            chunk_map[cid] = chunk

    # Score vector contributions (1-based ranking)
    for rank_idx, chunk in enumerate(vector_results, start=1):
        cid = chunk.chunk_id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (k + rank_idx)
        if cid not in chunk_map:
            chunk_map[cid] = chunk
        else:
            # Merge scores from both sources into the existing chunk record
            chunk_map[cid].vector_distance = chunk.vector_distance

    # Assign RRF scores and mark retrieval sources
    for cid, score in rrf_scores.items():
        chunk = chunk_map[cid]
        chunk.rrf_score = score
        # Determine composite source label
        in_bm25 = any(c.chunk_id == cid for c in bm25_results)
        in_vector = any(c.chunk_id == cid for c in vector_results)
        if in_bm25 and in_vector:
            chunk.retrieval_source = "bm25+vector"
        elif in_bm25:
            chunk.retrieval_source = "bm25"
        else:
            chunk.retrieval_source = "vector"

    # Sort by RRF score descending and return top_k
    sorted_chunks = sorted(chunk_map.values(), key=lambda c: c.rrf_score, reverse=True)
    return sorted_chunks[:top_k]


# ---------------------------------------------------------------------------
# Hybrid Search Orchestrator
# ---------------------------------------------------------------------------

class HybridSearcher:
    """
    Top-level orchestrator that dispatches to the appropriate retrieval
    strategy based on the configured RETRIEVAL_MODE.

    Supports:
      - "hybrid_rrf": BM25 + Dense Vector + RRF fusion (default).
      - "cosine_baseline": Pure pgvector cosine distance search.
      - "bm25_only": Pure BM25 lexical search only.
    """

    def __init__(self) -> None:
        self.bm25_searcher = BM25Searcher()
        self.vector_searcher = DenseVectorSearcher()

    def search(
        self,
        db: Session,
        user_id: UUID,
        workspace_id: UUID,
        query: str,
        query_embedding: list[float],
        mode: str = "hybrid_rrf",
        top_k: int = FINAL_TOP_K,
    ) -> RetrievalResult:
        """
        Execute retrieval using the specified mode and return results.

        Args:
            db: Active SQLAlchemy database session.
            user_id: Authenticated user UUID for tenant isolation.
            workspace_id: Target workspace UUID for tenant isolation.
            query: Raw user query text (used for BM25).
            query_embedding: 384-d embedding vector (used for dense search).
            mode: Retrieval strategy - "hybrid_rrf", "cosine_baseline", or "bm25_only".
            top_k: Number of final chunks to return.

        Returns:
            RetrievalResult with ranked chunks and diagnostics.
        """
        start_time = time.perf_counter()
        result = RetrievalResult(mode=mode)

        if mode == "cosine_baseline":
            vector_results = self.vector_searcher.search(
                db, user_id, workspace_id, query_embedding, limit=top_k
            )
            result.chunks = vector_results[:top_k]
            result.vector_candidate_count = len(vector_results)

        elif mode == "bm25_only":
            bm25_results = self.bm25_searcher.search(
                db, user_id, workspace_id, query, limit=top_k
            )
            result.chunks = bm25_results[:top_k]
            result.bm25_candidate_count = len(bm25_results)

        elif mode == "hybrid_rrf":
            # Run both searches
            bm25_results = self.bm25_searcher.search(
                db, user_id, workspace_id, query, limit=BM25_CANDIDATE_LIMIT
            )
            vector_results = self.vector_searcher.search(
                db, user_id, workspace_id, query_embedding, limit=VECTOR_CANDIDATE_LIMIT
            )
            result.bm25_candidate_count = len(bm25_results)
            result.vector_candidate_count = len(vector_results)

            # Fuse using RRF
            result.chunks = reciprocal_rank_fusion(
                bm25_results, vector_results, k=RRF_K, top_k=top_k
            )

            logger.info(
                "Hybrid RRF: %d BM25 + %d vector -> %d fused results",
                len(bm25_results),
                len(vector_results),
                len(result.chunks),
            )
        else:
            logger.warning("Unknown retrieval mode '%s', falling back to hybrid_rrf", mode)
            return self.search(
                db, user_id, workspace_id, query, query_embedding,
                mode="hybrid_rrf", top_k=top_k,
            )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        result.latency_ms = round(elapsed_ms, 2)
        logger.info(
            "Retrieval completed in %.2f ms (mode=%s, results=%d)",
            elapsed_ms, mode, len(result.chunks)
        )
        return result
