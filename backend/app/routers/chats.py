import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.logging_config import logger
from app.models.entities import ChatMessage, ChatSession, User
from app.models.schemas import ChatAnswer, MessageCreate, MessageOut
from app.services.openrouter import OpenRouterGenerationError
from app.services.workspace_rag import WorkspaceRAG

router = APIRouter(prefix="/api/chats", tags=["chats"])


def owned_chat(db: Session, user_id: uuid.UUID, chat_id: uuid.UUID) -> ChatSession:
    chat = db.scalar(select(ChatSession).where(ChatSession.id == chat_id, ChatSession.user_id == user_id))
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return chat


@router.get("/{chat_id}/messages", response_model=list[MessageOut])
def list_messages(chat_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    owned_chat(db, user.id, chat_id)
    return list(db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == chat_id).order_by(ChatMessage.created_at.asc())
    ))


@router.post("/{chat_id}/messages", response_model=ChatAnswer, status_code=201)
def send_message(
    chat_id: uuid.UUID,
    payload: MessageCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    chat = owned_chat(db, user.id, chat_id)
    question = payload.content.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    user_message = ChatMessage(session_id=chat.id, role="user", content=question, source_references=[])
    db.add(user_message)
    if chat.title == "New chat":
        chat.title = question[:72] + ("…" if len(question) > 72 else "")
    db.commit()
    db.refresh(user_message)

    history = list(db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat.id, ChatMessage.id != user_message.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    ))
    history.reverse()
    try:
        answer, references = WorkspaceRAG().answer(
            db,
            user_id=user.id,
            workspace_id=chat.workspace_id,
            question=question,
            history=history,
        )
    except Exception as error:
        db.rollback()
        if isinstance(error, OpenRouterGenerationError):
            status_code = error.status_code or 502
            logger.warning(
                "chat.answer_provider_failed chat_id=%s status_code=%s error_type=%s retry_after=%s",
                chat.id,
                status_code,
                type(error).__name__,
                error.retry_after,
            )
            headers = {"Retry-After": str(error.retry_after)} if error.retry_after else None
            raise HTTPException(status_code=status_code, detail=str(error), headers=headers)
        logger.exception("chat.answer_failed chat_id=%s error_type=%s", chat.id, type(error).__name__)
        raise HTTPException(status_code=502, detail="The answer service is temporarily unavailable. Please retry shortly.")

    assistant_message = ChatMessage(
        session_id=chat.id,
        role="assistant",
        content=answer,
        source_references=references,
    )
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)
    db.refresh(chat)
    return ChatAnswer(user_message=user_message, assistant_message=assistant_message)
