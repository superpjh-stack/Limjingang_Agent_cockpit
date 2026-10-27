from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any


class PollyError(RuntimeError):
    pass


class PollyVoice:
    def __init__(self, region: str, client: Any | None = None, chunk_bytes: int = 12_000) -> None:
        if client is None:
            import boto3
            client = boto3.client("polly", region_name=region)
        self.client = client
        self.chunk_bytes = chunk_bytes

    def _synthesize(self, text: str) -> bytes:
        try:
            response = self.client.synthesize_speech(
                Text=text[:3000],
                OutputFormat="pcm",
                SampleRate="16000",
                VoiceId="Seoyeon",
                Engine="generative",
                LanguageCode="ko-KR",
            )
            stream = response["AudioStream"]
            return stream.read() if hasattr(stream, "read") else bytes(stream)
        except Exception as exc:
            raise PollyError("한국어 음성 답변을 만들지 못했습니다.") from exc

    async def stream(self, text: str) -> AsyncIterator[bytes]:
        audio = await asyncio.to_thread(self._synthesize, text)
        for start in range(0, len(audio), self.chunk_bytes):
            yield audio[start:start + self.chunk_bytes]
