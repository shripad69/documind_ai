from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("Enter a valid email address.")
        return value


class UserOut(ORMModel):
    id: UUID
    email: str
    created_at: datetime


class WorkspaceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)


class WorkspaceUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)


class WorkspaceOut(ORMModel):
    id: UUID
    title: str
    description: str
    created_at: datetime


class DocumentOut(ORMModel):
    id: UUID
    workspace_id: UUID
    file_name: str
    status: str
    error_message: str | None
    created_at: datetime
    indexed_at: datetime | None


class ChatCreate(BaseModel):
    title: str = Field(default="New chat", min_length=1, max_length=180)


class ChatOut(ORMModel):
    id: UUID
    workspace_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20000)


class MessageOut(ORMModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    source_references: list[dict[str, Any]]
    created_at: datetime


class ChatAnswer(BaseModel):
    user_message: MessageOut
    assistant_message: MessageOut
