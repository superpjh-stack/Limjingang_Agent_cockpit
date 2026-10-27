from __future__ import annotations

from typing import Annotated, Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator


MAX_AUDIO_BASE64_CHARS = 24_000


class VoiceEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionStart(VoiceEvent):
    type: Literal["session.start"]
    session_id: str = Field(min_length=16, max_length=160)
    lot_id: str | None = Field(default=None, max_length=80)


class AudioChunk(VoiceEvent):
    type: Literal["audio.chunk"]
    utterance_id: str = Field(min_length=1, max_length=80)
    sequence: int = Field(ge=0, le=1_000_000)
    audio: str = Field(min_length=1, max_length=MAX_AUDIO_BASE64_CHARS)

    @field_validator("audio")
    @classmethod
    def base64_shape(cls, value: str) -> str:
        if len(value) % 4 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=" for char in value):
            raise ValueError("audio must be base64 PCM")
        return value


class AudioStop(VoiceEvent):
    type: Literal["audio.stop"]
    utterance_id: str = Field(min_length=1, max_length=80)


class ResponseCancel(VoiceEvent):
    type: Literal["response.cancel"]
    response_id: str = Field(min_length=1, max_length=80)


class SessionEnd(VoiceEvent):
    type: Literal["session.end"]


ClientEvent: TypeAlias = Annotated[
    SessionStart | AudioChunk | AudioStop | ResponseCancel | SessionEnd,
    Field(discriminator="type"),
]
_client_adapter = TypeAdapter(ClientEvent)


def parse_client_event(value: Any) -> ClientEvent:
    return _client_adapter.validate_python(value)


class ServerEvent(VoiceEvent):
    type: str = Field(min_length=1, max_length=60)
    session_id: str | None = Field(default=None, max_length=160)
    utterance_id: str | None = Field(default=None, max_length=80)
    response_id: str | None = Field(default=None, max_length=80)
    sequence: int | None = Field(default=None, ge=0, le=1_000_000)
    status: str | None = Field(default=None, max_length=40)
    text: str | None = Field(default=None, max_length=20_000)
    audio: str | None = Field(default=None, max_length=MAX_AUDIO_BASE64_CHARS)
    code: str | None = Field(default=None, max_length=60)
    message: str | None = Field(default=None, max_length=300)
    answer: dict[str, Any] | None = None
