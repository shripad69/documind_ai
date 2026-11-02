"""Requeue indexed workspace documents after chunking or embedding changes.

From the backend directory, run:
    python -m app.reindex_documents --all
or:
    python -m app.reindex_documents --document-id <document UUID>
"""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import select

from app.db import SessionLocal
from app.models.entities import Document
from app.tasks import ingest_document


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-index workspace documents with the current sentence chunker.")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true", help="re-index every currently indexed document")
    selection.add_argument("--document-id", type=uuid.UUID, help="re-index one document by UUID")
    args = parser.parse_args()

    with SessionLocal() as db:
        query = select(Document).where(Document.status == "indexed")
        if args.document_id:
            query = select(Document).where(Document.id == args.document_id)
        documents = list(db.scalars(query.order_by(Document.created_at.asc())))
        queued = 0
        for document in documents:
            ingest_document.delay(str(document.id))
            print(f"Queued {document.file_name} ({document.id})")
            queued += 1

    print(f"Queued {queued} document(s). The Celery worker will replace their chunks after successful extraction and embedding.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

