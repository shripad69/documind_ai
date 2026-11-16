import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
from docx import Document as DocxDocument
from sqlalchemy import delete

from app.config import settings
from app.db import SessionLocal
from app.models.entities import Document, DocumentChunk, DocumentMindMap
from app.queue import celery_app
from app.services.citation_pipeline import chunk_pages as sentence_chunk_pages
from app.services.embedding_service import embed_texts

logger = logging.getLogger(__name__)


def parse_pages(file_path: Path) -> list[tuple[int, str]]:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        with pymupdf.open(file_path) as pdf:
            pages = []
            for index, page in enumerate(pdf):
                blocks = page.get_text("blocks", sort=True)
                text = "\n\n".join(
                    block[4].strip()
                    for block in blocks
                    if len(block) > 4 and isinstance(block[4], str) and block[4].strip()
                )
                if text:
                    pages.append((index + 1, text))
            return pages
    if suffix == ".docx":
        document = DocxDocument(file_path)
        text = "\n\n".join(paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip())
        return [(1, text)] if text else []
    raise ValueError("Unsupported document format.")


def chunk_pages(pages: list[tuple[int, str]], size: int = 800, overlap: int = 2) -> list[tuple[int, str]]:
    """Compatibility wrapper for the old ingestion API; overlap is sentence based."""
    del overlap
    return sentence_chunk_pages(pages, size=min(size, 900), overlap_sentences=2)


@celery_app.task(name="app.tasks.ingest_document", bind=True, max_retries=2, default_retry_delay=10)
def ingest_document(self, document_id: str) -> dict:
    document_uuid = uuid.UUID(document_id)
    db = SessionLocal()
    try:
        document = db.get(Document, document_uuid)
        if document is None:
            return {"status": "missing", "document_id": document_id}
        document.status = "processing"
        document.error_message = None
        db.commit()

        pages = parse_pages(Path(document.file_path))
        chunks = chunk_pages(pages)
        if not chunks:
            raise ValueError("No readable text was found in this document.")

        texts = [content for _, content in chunks]
        total_chunks = len(chunks)
        batch_size = max(1, settings.embedding_batch_size)
        replacement_chunks: list[DocumentChunk] = []

        logger.info(
            "ingestion.embedding_started document_id=%s total_chunks=%d batch_size=%d",
            document_id,
            total_chunks,
            batch_size,
        )

        for offset in range(0, total_chunks, batch_size):
            batch_texts = texts[offset:offset + batch_size]
            batch_embeddings = embed_texts(batch_texts)

            if len(batch_embeddings) != len(batch_texts):
                raise RuntimeError(
                    f"Embedding service returned {len(batch_embeddings)} vectors for {len(batch_texts)} texts."
                )

            for index, embedding in enumerate(batch_embeddings):
                page_number, content = chunks[offset + index]
                replacement_chunks.append(DocumentChunk(
                    user_id=document.user_id,
                    workspace_id=document.workspace_id,
                    document_id=document.id,
                    chunk_index=offset + index,
                    page_number=page_number,
                    content=content,
                    embedding=embedding,
                ))

        # Atomically replace old chunks and cached mind maps with newly generated ones.
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.execute(delete(DocumentMindMap).where(DocumentMindMap.document_id == document.id))
        db.add_all(replacement_chunks)
        document.status = "indexed"
        document.indexed_at = datetime.now(timezone.utc)
        document.error_message = None
        db.commit()
        logger.info("ingestion.completed document_id=%s chunks=%d", document_id, len(chunks))
        return {"status": "indexed", "document_id": document_id, "chunks": len(chunks)}
    except Exception as error:
        db.rollback()
        document = db.get(Document, document_uuid)
        if document:
            document.status = "failed"
            document.error_message = f"{type(error).__name__}: {str(error)[:300]}"
            db.commit()
        logger.exception("ingestion.failed document_id=%s error_type=%s", document_id, type(error).__name__)
        if self.request.retries < self.max_retries and not isinstance(error, (ValueError, FileNotFoundError)):
            logger.info("ingestion.retrying document_id=%s attempt %d/%d", document_id, self.request.retries + 1, self.max_retries)
            raise self.retry(exc=error, countdown=10)
        return {"status": "failed", "document_id": document_id}
    finally:
        db.close()
