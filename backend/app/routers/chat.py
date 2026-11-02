from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool
import logging
import time
import uuid

from app.models.schemas import ChatRequest, ChatResponse
from app.services.rag_service import rag_service

router = APIRouter()
logger = logging.getLogger(__name__)

# Simple in-memory conversation storage (use a proper DB in production)
conversations = {}


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle chat messages with RAG"""
    request_id = uuid.uuid4().hex[:12]
    started_at = time.perf_counter()
    logger.info(
        "chat.request_started request_id=%s document_attached=%s message_chars=%d",
        request_id,
        bool(request.document_id),
        len(request.message),
    )
    try:
        # Get or create conversation ID
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        if conversation_id not in conversations:
            conversations[conversation_id] = []
        
        # Add user message BEFORE querying to include it in history (optional, or pass current separately)
        # Here we pass the history UP TO this point (excluding current if we want, or including)
        # Let's include current message in history so RAG sees it as "latest"
        current_history = conversations[conversation_id] + [{"role": "user", "content": request.message}]
        
        # Get RAG response with History and Document ID
        response, sources = await run_in_threadpool(
            rag_service.query,
            request.message,
            current_history,
            request.document_id,
            request_id=request_id,
        )
        
        # Now Append to storage
        conversations[conversation_id].append({
            "role": "user",
            "content": request.message
        })
        conversations[conversation_id].append({
            "role": "assistant",
            "content": response
        })
        
        logger.info(
            "chat.request_completed request_id=%s duration_ms=%d source_count=%d response_chars=%d",
            request_id,
            round((time.perf_counter() - started_at) * 1000),
            len(sources),
            len(response),
        )
        return ChatResponse(
            response=response,
            conversation_id=conversation_id,
            sources=sources
        )
    except Exception as e:
        logger.exception(
            "chat.request_failed request_id=%s duration_ms=%d",
            request_id,
            round((time.perf_counter() - started_at) * 1000),
        )
        raise HTTPException(status_code=500, detail=f"Error processing chat: {str(e)}")


@router.get("/conversation/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    if conversation_id not in conversations:
        return {"messages": []}
    return {"messages": conversations[conversation_id]}

