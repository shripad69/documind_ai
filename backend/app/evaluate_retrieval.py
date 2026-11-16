"""
Retrieval Evaluation Benchmark Script.

Compares Hybrid Search (BM25 + Dense + RRF), Baseline Cosine Similarity,
and BM25-Only retrieval modes using standard IR metrics:
  - Recall@K: Fraction of relevant chunks retrieved in top K.
  - MRR (Mean Reciprocal Rank): Average reciprocal rank of first relevant result.
  - NDCG@K (Normalized Discounted Cumulative Gain): Graded relevance quality.
  - Latency: Average retrieval time in milliseconds.
  - Citation Verification Pass Rate: Fraction of queries where cited chunks
    contain the expected keywords from the query.

Usage:
    PYTHONPATH=backend python -m app.evaluate_retrieval \
        --user-email user@example.com \
        --workspace-title "My Workspace"

Requirements:
    - Active PostgreSQL database with indexed documents.
    - Valid GOOGLE_API_KEY for query embedding.
    - At least one workspace with indexed documents.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models.entities import User, Workspace, Document, DocumentChunk
from app.services.embedding_service import embed_query
from app.services.hybrid_search import HybridSearcher, RetrievalResult

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RETRIEVAL_MODES = ["hybrid_rrf", "cosine_baseline", "bm25_only"]
TOP_K = 8


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

@dataclass
class QueryEvaluation:
    """Evaluation results for a single query across one mode."""
    query: str
    mode: str
    recall_at_k: float = 0.0
    mrr: float = 0.0
    ndcg_at_k: float = 0.0
    latency_ms: float = 0.0
    citation_pass: bool = False
    num_results: int = 0


@dataclass
class ModeAggregateMetrics:
    """Aggregated metrics for a retrieval mode across all queries."""
    mode: str
    avg_recall_at_k: float = 0.0
    avg_mrr: float = 0.0
    avg_ndcg_at_k: float = 0.0
    avg_latency_ms: float = 0.0
    citation_pass_rate: float = 0.0
    num_queries: int = 0


def compute_recall_at_k(
    retrieved_contents: list[str],
    relevant_keywords: list[str],
) -> float:
    """
    Compute Recall@K as the fraction of relevant keywords found in any retrieved chunk.

    A keyword is considered "found" if it appears (case-insensitive) in any
    of the retrieved chunk contents.
    """
    if not relevant_keywords:
        return 1.0
    found = 0
    combined_text = " ".join(retrieved_contents).lower()
    for kw in relevant_keywords:
        if kw.lower() in combined_text:
            found += 1
    return found / len(relevant_keywords)


def compute_mrr(
    retrieved_contents: list[str],
    relevant_keywords: list[str],
) -> float:
    """
    Compute Mean Reciprocal Rank.

    Returns 1/rank of the first retrieved chunk that contains any relevant keyword.
    Returns 0.0 if no relevant chunk is found.
    """
    if not relevant_keywords:
        return 1.0
    for rank, content in enumerate(retrieved_contents, start=1):
        content_lower = content.lower()
        for kw in relevant_keywords:
            if kw.lower() in content_lower:
                return 1.0 / rank
    return 0.0


def compute_ndcg_at_k(
    retrieved_contents: list[str],
    relevant_keywords: list[str],
    k: int = TOP_K,
) -> float:
    """
    Compute NDCG@K with binary relevance.

    A retrieved chunk is relevant (1) if it contains any of the keywords,
    otherwise irrelevant (0).
    """
    if not relevant_keywords:
        return 1.0

    def relevance(content: str) -> float:
        content_lower = content.lower()
        return 1.0 if any(kw.lower() in content_lower for kw in relevant_keywords) else 0.0

    # DCG
    dcg = 0.0
    for i, content in enumerate(retrieved_contents[:k]):
        rel = relevance(content)
        dcg += rel / math.log2(i + 2)  # i+2 because log2(1) = 0

    # Ideal DCG (all relevant first)
    all_rels = sorted([relevance(c) for c in retrieved_contents[:k]], reverse=True)
    num_relevant = sum(1 for c in retrieved_contents[:k] if relevance(c) > 0)
    ideal_rels = [1.0] * min(num_relevant, k) + [0.0] * (k - min(num_relevant, k))

    idcg = 0.0
    for i, rel in enumerate(ideal_rels[:k]):
        idcg += rel / math.log2(i + 2)

    return dcg / idcg if idcg > 0 else 0.0


def check_citation_pass(
    retrieved_contents: list[str],
    relevant_keywords: list[str],
) -> bool:
    """
    Check if at least one retrieved chunk contains all of the relevant keywords.

    This simulates whether the citation pipeline would be able to verify
    claims against the retrieved context.
    """
    if not relevant_keywords:
        return True
    for content in retrieved_contents:
        content_lower = content.lower()
        if all(kw.lower() in content_lower for kw in relevant_keywords):
            return True
    return False


# ---------------------------------------------------------------------------
# Query embedding is provided by app.services.embedding_service.embed_query


# ---------------------------------------------------------------------------
# Evaluation Runner
# ---------------------------------------------------------------------------

def build_evaluation_queries(db, user_id: UUID, workspace_id: UUID) -> list[dict]:
    """
    Build evaluation queries by sampling actual chunk content from the workspace.

    Extracts distinctive phrases and keywords from existing chunks to create
    queries that have known-relevant content for measuring recall.
    """
    chunks = db.execute(
        select(DocumentChunk.content, Document.file_name)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(
            DocumentChunk.user_id == user_id,
            DocumentChunk.workspace_id == workspace_id,
            Document.status == "indexed",
        )
        .limit(50)
    ).fetchall()

    if not chunks:
        logger.error("No indexed chunks found in workspace. Cannot build evaluation queries.")
        return []

    queries = []
    for i, (content, file_name) in enumerate(chunks[:10]):
        # Extract the first 2-3 meaningful words as a query
        words = [w for w in content.split() if len(w) > 3][:6]
        if len(words) < 2:
            continue
        query_text = " ".join(words)
        # Keywords that should be retrievable
        relevant_keywords = words[:3]
        queries.append({
            "query": query_text,
            "relevant_keywords": relevant_keywords,
            "source_file": file_name,
        })

    logger.info("Built %d evaluation queries from workspace chunks", len(queries))
    return queries


def run_evaluation(
    user_email: str,
    workspace_title: str,
) -> dict:
    """
    Run the full evaluation benchmark comparing all retrieval modes.

    Returns a dictionary containing per-query and aggregate results.
    """
    db = SessionLocal()
    try:
        # Resolve user and workspace
        user = db.execute(
            select(User).where(User.email == user_email.lower().strip())
        ).scalar_one_or_none()
        if not user:
            logger.error("User not found: %s", user_email)
            sys.exit(1)

        workspace = db.execute(
            select(Workspace).where(
                Workspace.user_id == user.id,
                Workspace.title == workspace_title,
            )
        ).scalar_one_or_none()
        if not workspace:
            logger.error("Workspace not found: '%s' for user %s", workspace_title, user_email)
            sys.exit(1)

        logger.info("Evaluating workspace '%s' (user: %s)", workspace.title, user.email)

        # Build evaluation queries from actual workspace content
        eval_queries = build_evaluation_queries(db, user.id, workspace.id)
        if not eval_queries:
            logger.error("No evaluation queries could be generated.")
            sys.exit(1)

        searcher = HybridSearcher()
        all_evaluations: list[QueryEvaluation] = []
        mode_evals: dict[str, list[QueryEvaluation]] = {m: [] for m in RETRIEVAL_MODES}

        for eq in eval_queries:
            query = eq["query"]
            keywords = eq["relevant_keywords"]

            logger.info("Evaluating query: '%.60s...'", query)

            # Embed the query once for all modes
            query_embedding = embed_query(query)

            for mode in RETRIEVAL_MODES:
                result = searcher.search(
                    db=db,
                    user_id=user.id,
                    workspace_id=workspace.id,
                    query=query,
                    query_embedding=query_embedding,
                    mode=mode,
                    top_k=TOP_K,
                )

                contents = [c.content for c in result.chunks]

                evaluation = QueryEvaluation(
                    query=query,
                    mode=mode,
                    recall_at_k=compute_recall_at_k(contents, keywords),
                    mrr=compute_mrr(contents, keywords),
                    ndcg_at_k=compute_ndcg_at_k(contents, keywords),
                    latency_ms=result.latency_ms,
                    citation_pass=check_citation_pass(contents, keywords),
                    num_results=len(result.chunks),
                )

                all_evaluations.append(evaluation)
                mode_evals[mode].append(evaluation)

        # Aggregate metrics per mode
        aggregates: dict[str, ModeAggregateMetrics] = {}
        for mode, evals in mode_evals.items():
            n = len(evals)
            if n == 0:
                continue
            aggregates[mode] = ModeAggregateMetrics(
                mode=mode,
                avg_recall_at_k=sum(e.recall_at_k for e in evals) / n,
                avg_mrr=sum(e.mrr for e in evals) / n,
                avg_ndcg_at_k=sum(e.ndcg_at_k for e in evals) / n,
                avg_latency_ms=sum(e.latency_ms for e in evals) / n,
                citation_pass_rate=sum(1 for e in evals if e.citation_pass) / n,
                num_queries=n,
            )

        # Print results table
        print("\n" + "=" * 90)
        print("RETRIEVAL BENCHMARK RESULTS")
        print("=" * 90)
        print(f"{'Mode':<20} {'Recall@{}'.format(TOP_K):<12} {'MRR':<10} {'NDCG@{}'.format(TOP_K):<12} {'Latency(ms)':<14} {'Citation%':<10}")
        print("-" * 90)
        for mode in RETRIEVAL_MODES:
            if mode in aggregates:
                a = aggregates[mode]
                print(
                    f"{a.mode:<20} {a.avg_recall_at_k:<12.4f} {a.avg_mrr:<10.4f} "
                    f"{a.avg_ndcg_at_k:<12.4f} {a.avg_latency_ms:<14.2f} "
                    f"{a.citation_pass_rate:<10.2%}"
                )
        print("=" * 90)

        return {
            "aggregates": {m: vars(a) for m, a in aggregates.items()},
            "num_queries": len(eval_queries),
        }

    finally:
        db.close()


# ---------------------------------------------------------------------------
# CLI Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Evaluate and compare retrieval modes (Hybrid RRF vs Cosine Baseline vs BM25)"
    )
    parser.add_argument(
        "--user-email", required=True,
        help="Email of the user who owns the workspace"
    )
    parser.add_argument(
        "--workspace-title", required=True,
        help="Title of the workspace to evaluate"
    )
    parser.add_argument(
        "--output-json", default=None,
        help="Optional path to write results as JSON"
    )
    args = parser.parse_args()

    results = run_evaluation(args.user_email, args.workspace_title)

    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info("Results written to %s", args.output_json)


if __name__ == "__main__":
    main()
