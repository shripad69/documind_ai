import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.db import get_db
from app.models.entities import ChatSession, Document, User, Workspace
from app.models.schemas import ChatCreate, ChatOut, DocumentOut, WorkspaceCreate, WorkspaceOut, WorkspaceUpdate
from app.tasks import ingest_document

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILES_PER_UPLOAD = 20


def owned_workspace(db: Session, user_id: uuid.UUID, workspace_id: uuid.UUID) -> Workspace:
    workspace = db.scalar(
        select(Workspace).where(Workspace.id == workspace_id, Workspace.user_id == user_id)
    )
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found.")
    return workspace


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return list(db.scalars(select(Workspace).where(Workspace.user_id == user.id).order_by(Workspace.created_at.desc())))


@router.post("", response_model=WorkspaceOut, status_code=status.HTTP_201_CREATED)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace = Workspace(user_id=user.id, title=payload.title.strip(), description=payload.description.strip())
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(workspace_id: uuid.UUID, payload: WorkspaceUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace = owned_workspace(db, user.id, workspace_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(workspace, field, value.strip())
    db.commit()
    db.refresh(workspace)
    return workspace


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace(workspace_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace = owned_workspace(db, user.id, workspace_id)
    paths = list(db.scalars(select(Document.file_path).where(Document.workspace_id == workspace.id, Document.user_id == user.id)))
    db.delete(workspace)
    db.commit()
    for path in paths:
        Path(path).unlink(missing_ok=True)


@router.post("/{workspace_id}/documents", response_model=list[DocumentOut], status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    workspace_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    workspace = owned_workspace(db, user.id, workspace_id)
    if not files or len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(status_code=400, detail=f"Upload between 1 and {MAX_FILES_PER_UPLOAD} files at a time.")

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    stored: list[Document] = []
    try:
        for upload in files:
            original_name = Path(upload.filename or "document").name
            extension = Path(original_name).suffix.lower()
            if extension not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")
            content = await upload.read(settings.max_upload_bytes + 1)
            if len(content) > settings.max_upload_bytes:
                raise HTTPException(status_code=413, detail=f"{original_name} exceeds the 25 MB per-file limit.")
            document_id = uuid.uuid4()
            directory = settings.upload_dir / str(user.id) / str(workspace.id)
            directory.mkdir(parents=True, exist_ok=True)
            file_path = directory / f"{document_id}{extension}"
            file_path.write_bytes(content)
            document = Document(
                id=document_id,
                workspace_id=workspace.id,
                user_id=user.id,
                file_name=original_name,
                file_path=str(file_path),
                content_type=upload.content_type or "application/octet-stream",
                status="processing",
            )
            db.add(document)
            stored.append(document)
    except Exception:
        for document in stored:
            Path(document.file_path).unlink(missing_ok=True)
        raise

    db.commit()
    for document in stored:
        try:
            ingest_document.delay(str(document.id))
        except Exception as error:
            document.status = "failed"
            document.error_message = "Could not queue document processing. Please retry the upload."
            db.commit()
            # Keep the durable file and record so the user can see and remove the failure.
            from app.logging_config import logger
            logger.exception("documents.queue_failed document_id=%s error_type=%s", document.id, type(error).__name__)
    for document in stored:
        db.refresh(document)
    return stored


@router.get("/{workspace_id}/documents", response_model=list[DocumentOut])
def list_documents(workspace_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned_workspace(db, user.id, workspace_id)
    return list(db.scalars(
        select(Document)
        .where(Document.workspace_id == workspace_id, Document.user_id == user.id)
        .order_by(Document.created_at.desc())
    ))


@router.delete("/{workspace_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(workspace_id: uuid.UUID, document_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned_workspace(db, user.id, workspace_id)
    document = db.scalar(select(Document).where(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
        Document.user_id == user.id,
    ))
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    file_path = document.file_path
    db.delete(document)
    db.commit()
    Path(file_path).unlink(missing_ok=True)


@router.get("/{workspace_id}/chats", response_model=list[ChatOut])
def list_chats(workspace_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned_workspace(db, user.id, workspace_id)
    return list(db.scalars(
        select(ChatSession)
        .where(ChatSession.workspace_id == workspace_id, ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc())
    ))


@router.post("/{workspace_id}/chats", response_model=ChatOut, status_code=status.HTTP_201_CREATED)
def create_chat(workspace_id: uuid.UUID, payload: ChatCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    workspace = owned_workspace(db, user.id, workspace_id)
    chat = ChatSession(workspace_id=workspace.id, user_id=user.id, title=payload.title.strip())
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat
