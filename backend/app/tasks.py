import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
from docx import Document as DocxDocument
from google import genai
from google.genai import types
from sqlalchemy import delete

from app.config import settings
from app.db import SessionLocal
from app.models.entities import Document, DocumentChunk
from app.queue import celery_app
from app.services.citation_pipeline import chunk_pages as sentence_chunk_pages

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


@celery_app.task(name="app.tasks.ingest_document", bind=True, max_retries=1, default_retry_delay=10)
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
        if not settings.gemini_api_key:
            raise RuntimeError("GOOGLE_API_KEY is not configured for document embedding.")

        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(
                timeout=45_000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        replacement_chunks = []
        for offset in range(0, len(chunks), 32):
            batch = chunks[offset:offset + 32]
            response = client.models.embed_content(
                model="gemini-embedding-001",
                contents=[content for _, content in batch],
                config=types.EmbedContentConfig(
                    output_dimensionality=384,
                    task_type="RETRIEVAL_DOCUMENT",
                ),
            )
            if not response.embeddings or len(response.embeddings) != len(batch):
                raise RuntimeError("Embedding service returned an incomplete batch.")
            for index, ((page_number, content), embedding) in enumerate(zip(batch, response.embeddings)):
                replacement_chunks.append(DocumentChunk(
                    user_id=document.user_id,
                    workspace_id=document.workspace_id,
                    document_id=document.id,
                    chunk_index=offset + index,
                    page_number=page_number,
                    content=content,
                    embedding=embedding.values,
                ))

        # Keep the old index intact until every new chunk has been extracted and
        # embedded successfully, then replace it in one database transaction.
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
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
            # Keep details operationally useful without copying request data or credentials.
            document.error_message = f"{type(error).__name__}: document processing failed. Check server logs."
            db.commit()
        logger.exception("ingestion.failed document_id=%s error_type=%s", document_id, type(error).__name__)
        if self.request.retries < self.max_retries and not isinstance(error, (ValueError, FileNotFoundError)):
            raise self.retry(exc=error)
        return {"status": "failed", "document_id": document_id}
    finally:
        db.close()
