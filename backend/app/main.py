from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app import logging_config  # Configure structured application logs at startup.
from app.routers import auth, chats, workspaces

app = FastAPI(title="Document Chatbot Workspace API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(auth.router)
app.include_router(workspaces.router)
app.include_router(chats.router)


@app.get("/api/health")
def health():
    return {"status": "healthy"}


@app.get("/")
def root():
    return {"message": "Document Chatbot Workspace API", "docs": "/docs"}
