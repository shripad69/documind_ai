import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.auth import get_current_user
from app.db import get_db
from app.models.entities import Document, DocumentChunk, DocumentMindMap, User, Workspace, utcnow
from app.models.schemas import MindMapGenerateRequest, MindMapOut
from app.services.mindmap_generator import MindMapGenerator, MindMapGenerationError

router = APIRouter(prefix="/api/workspaces", tags=["mindmap"])


def owned_document(db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID, document_id: uuid.UUID) -> Document:
    document = db.scalar(
        select(Document).where(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
            Document.user_id == user_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return document


@router.get("/{workspace_id}/documents/{document_id}/mindmap", response_model=MindMapOut)
def get_document_mindmap(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Retrieve an existing cached mind map for a document."""
    owned_document(db, user.id, workspace_id, document_id)

    mind_map = db.scalar(
        select(DocumentMindMap).where(
            DocumentMindMap.document_id == document_id,
            DocumentMindMap.workspace_id == workspace_id,
            DocumentMindMap.user_id == user.id,
        )
    )
    if mind_map is None:
        raise HTTPException(status_code=404, detail="Mind map has not been generated for this document yet.")

    tree = mind_map.tree_data if isinstance(mind_map.tree_data, dict) else {}
    children = tree.get("children")
    if not isinstance(children, list) or len(children) == 0:
        raise HTTPException(status_code=404, detail="Cached mind map is incomplete. Please regenerate.")

    return mind_map


@router.post(
    "/{workspace_id}/documents/{document_id}/mindmap",
    response_model=MindMapOut,
    status_code=status.HTTP_200_OK,
)
def generate_document_mindmap(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    refresh: bool = Query(default=False, description="Force regeneration even if cached"),
    force: bool = Query(default=False, description="Force fresh regeneration from scratch bypassing cache"),
    body: MindMapGenerateRequest | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate or retrieve a cached mind map for an indexed document."""
    document = owned_document(db, user.id, workspace_id, document_id)

    if document.status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is still being indexed. Please wait until indexing finishes before generating a mind map.",
        )
    if document.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document indexing failed ({document.error_message or 'Unknown error'}). Cannot generate a mind map.",
        )
    if document.status != "indexed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document must be fully indexed to generate a mind map.",
        )

    should_regenerate = (
        bool(refresh)
        or bool(force)
        or (body is not None and bool(body.force or body.force_regenerate or body.refresh))
    )

    # Check for existing cached mind map
    existing = db.scalar(
        select(DocumentMindMap).where(
            DocumentMindMap.document_id == document.id,
            DocumentMindMap.workspace_id == workspace_id,
            DocumentMindMap.user_id == user.id,
        )
    )

    if existing and not should_regenerate:
        tree = existing.tree_data if isinstance(existing.tree_data, dict) else {}
        children = tree.get("children")
        if isinstance(children, list) and len(children) > 0:
            return existing
        # Stale single-node record detected; bypass cache and regenerate to repair

    # Retrieve all document chunks in original order
    chunks = list(
        db.scalars(
            select(DocumentChunk.content)
            .where(
                DocumentChunk.document_id == document.id,
                DocumentChunk.workspace_id == workspace_id,
                DocumentChunk.user_id == user.id,
            )
            .order_by(DocumentChunk.chunk_index.asc())
        )
    )

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No text chunks found for this document.",
        )

    try:
        generator = MindMapGenerator()
        tree_data = generator.generate(chunks, document.file_name, document.id)
    except MindMapGenerationError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail="Failed to generate mind map.") from error

    if not tree_data or not tree_data.get("children"):
        raise HTTPException(status_code=502, detail="Generated mind map tree contains no child branches.")

    if existing:
        existing.tree_data = tree_data
        flag_modified(existing, "tree_data")
        existing.updated_at = utcnow()
        db.commit()
        db.refresh(existing)
        return existing

    mind_map = DocumentMindMap(
        document_id=document.id,
        user_id=user.id,
        workspace_id=workspace_id,
        tree_data=tree_data,
    )
    db.add(mind_map)
    db.commit()
    db.refresh(mind_map)
    return mind_map
