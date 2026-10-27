from __future__ import annotations

import asyncio
import base64
import contextlib
import secrets
from collections.abc import Awaitable, Callable
from typing import Any

from v3.voice.contracts import AudioChunk, AudioStop, ResponseCancel, ServerEvent, SessionEnd, SessionStart, parse_client_event


SendEvent = Callable[[dict[str, Any]], Awaitable[None]]


class VoiceSession:
    def __init__(self, transcriber: Any, agent: Any, speaker: Any, send: SendEvent) -> None:
        self.transcriber = transcriber
        self.agent = agent
        self.speaker = speaker
        self.send = send
        self.session_id = ""
        self.lot_id: str | None = None
        self.audio: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=80)
        self.last_sequence: dict[str, int] = {}
        self.final_utterances: set[str] = set()
        self.active_response_id: str | None = None
        self.transcribe_task: asyncio.Task | None = None
        self.response_task: asyncio.Task | None = None
        self.closed = False
        self.current_utterance = ""

    async def emit(self, event_type: str, **values: Any) -> None:
        payload = ServerEvent(type=event_type, session_id=self.session_id or None, **values)
        await self.send(payload.model_dump(exclude_none=True))

    async def handle(self, value: Any) -> bool:
        event = parse_client_event(value)
        if isinstance(event, SessionStart):
            if self.session_id:
                await self.emit("error", code="SESSION_ALREADY_STARTED", message="음성 세션이 이미 시작되었습니다.")
                return True
            self.session_id, self.lot_id = event.session_id, event.lot_id
            self.transcribe_task = asyncio.create_task(self.transcriber.run(self.audio, self.on_transcript))
            await self.emit("session.ready", status="listening")
        elif not self.session_id:
            await self.emit("error", code="SESSION_REQUIRED", message="음성 세션을 먼저 시작해 주세요.")
        elif isinstance(event, AudioChunk):
            previous = self.last_sequence.get(event.utterance_id, -1)
            if event.sequence <= previous:
                await self.emit("error", utterance_id=event.utterance_id, code="AUDIO_SEQUENCE", message="오디오 순서가 올바르지 않습니다.")
                return True
            self.last_sequence[event.utterance_id] = event.sequence
            self.current_utterance = event.utterance_id
            await self.audio.put(base64.b64decode(event.audio, validate=True))
        elif isinstance(event, AudioStop):
            self.current_utterance = event.utterance_id
        elif isinstance(event, ResponseCancel):
            if event.response_id == self.active_response_id:
                await self.cancel_response(event.response_id)
        elif isinstance(event, SessionEnd):
            await self.close()
            return False
        return True

    async def on_transcript(self, text: str, final: bool) -> None:
        utterance_id = self.current_utterance or "u-unknown"
        await self.emit("transcript.final" if final else "transcript.partial", utterance_id=utterance_id, text=text)
        if not final or utterance_id in self.final_utterances:
            return
        self.final_utterances.add(utterance_id)
        if self.response_task and not self.response_task.done():
            await self.cancel_response(self.active_response_id or "")
        self.response_task = asyncio.create_task(self.respond(text, utterance_id))

    async def respond(self, text: str, utterance_id: str) -> None:
        response_id = "r-" + secrets.token_hex(8)
        self.active_response_id = response_id
        try:
            await self.emit("agent.status", utterance_id=utterance_id, response_id=response_id, status="retrieving")
            answer = await self.agent.ask(text, self.session_id, self.lot_id)
            if self.active_response_id != response_id:
                return
            answer_text = str(answer.get("text", "")).strip()
            await self.emit("answer.text", utterance_id=utterance_id, response_id=response_id, text=answer_text, answer=answer)
            sequence = 0
            try:
                async for chunk in self.speaker.stream(answer_text):
                    if self.active_response_id != response_id:
                        return
                    await self.emit("audio.chunk", response_id=response_id, sequence=sequence, audio=base64.b64encode(chunk).decode())
                    sequence += 1
            except Exception:
                await self.emit("error", response_id=response_id, code="TTS_UNAVAILABLE", message="답변 텍스트는 확인했지만 음성을 재생하지 못했습니다.")
            if self.active_response_id == response_id:
                await self.emit("answer.complete", response_id=response_id, answer=answer)
        except asyncio.CancelledError:
            raise
        except Exception:
            await self.emit("error", response_id=response_id, code="AGENT_UNAVAILABLE", message="제조 근거 답변을 받지 못했습니다.")

    async def cancel_response(self, response_id: str) -> None:
        self.active_response_id = None
        if self.response_task and self.response_task is not asyncio.current_task() and not self.response_task.done():
            self.response_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.response_task
        await self.emit("response.cancelled", response_id=response_id)

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.active_response_id:
            await self.cancel_response(self.active_response_id)
        await self.audio.put(None)
        if self.transcribe_task:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await asyncio.wait_for(self.transcribe_task, timeout=3)
