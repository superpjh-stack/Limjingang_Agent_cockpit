from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def utc_stamp() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    lot_id: str | None = Field(default=None, max_length=80)
    session_id: str | None = Field(default=None, max_length=160)


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2200)
    session_id: str = Field(min_length=16, max_length=160)
    lot_id: str | None = Field(default=None, max_length=80)
    user_context: dict[str, str] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    text: str
    sources: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    data_tools: list[str] = Field(default_factory=list)
    records: list[dict[str, Any]] = Field(default_factory=list)
    searched_documents: bool = False
    session_id: str
    mode: Literal["demo", "agentcore"]
    demo_data: bool
    region: str
    model: str
    retrieved_at: str = Field(default_factory=utc_stamp)
