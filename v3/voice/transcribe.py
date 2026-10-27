from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


TranscriptCallback = Callable[[str, bool], Awaitable[None]]


class TranscribeError(RuntimeError):
    pass


class KoreanTranscriber:
    def __init__(self, region: str, client: Any | None = None) -> None:
        if client is None:
            try:
                from amazon_transcribe.client import TranscribeStreamingClient
            except ImportError as exc:
                raise TranscribeError("실시간 음성 인식 SDK가 설치되지 않았습니다.") from exc
            client = TranscribeStreamingClient(region=region)
        self.client = client

    async def run(self, audio: asyncio.Queue[bytes | None], callback: TranscriptCallback) -> None:
        try:
            stream = await self.client.start_stream_transcription(
                language_code="ko-KR",
                media_sample_rate_hz=16000,
                media_encoding="pcm",
            )
        except Exception as exc:
            raise TranscribeError("한국어 음성 인식을 시작하지 못했습니다.") from exc

        async def write_audio() -> None:
            while True:
                chunk = await audio.get()
                if chunk is None:
                    await stream.input_stream.end_stream()
                    return
                await stream.input_stream.send_audio_event(audio_chunk=chunk)

        async def read_transcripts() -> None:
            try:
                async for event in stream.output_stream:
                    transcript = getattr(event, "transcript", None)
                    for result in getattr(transcript, "results", []) if transcript else []:
                        alternatives = getattr(result, "alternatives", [])
                        text = getattr(alternatives[0], "transcript", "").strip() if alternatives else ""
                        if text:
                            await callback(text, not bool(getattr(result, "is_partial", False)))
            except Exception as exc:
                raise TranscribeError("한국어 음성 인식 연결이 끊겼습니다.") from exc

        await asyncio.gather(write_audio(), read_transcripts())
