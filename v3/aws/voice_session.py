from __future__ import annotations

from typing import Any


class VoiceSessionError(RuntimeError):
    pass


class VoiceSessionSigner:
    def __init__(self, runtime_arn: str, region: str, expires: int = 60, client: Any | None = None) -> None:
        if expires < 30 or expires > 300:
            raise ValueError("voice URL expiry must be between 30 and 300 seconds")
        self.runtime_arn = runtime_arn
        self.region = region
        self.expires = expires
        if client is None:
            try:
                from bedrock_agentcore.runtime import AgentCoreRuntimeClient
            except ImportError as exc:
                raise VoiceSessionError("음성 세션 SDK가 설치되지 않았습니다.") from exc
            client = AgentCoreRuntimeClient(region=region)
        self.client = client

    def create_url(self, session_id: str | None = None) -> str:
        try:
            arguments = {"runtime_arn": self.runtime_arn, "expires": self.expires}
            if session_id:
                arguments["session_id"] = session_id
            url = self.client.generate_presigned_url(**arguments)
        except Exception as exc:
            raise VoiceSessionError("실시간 음성 세션을 준비하지 못했습니다.") from exc
        if not isinstance(url, str) or not url.startswith("wss://") or "X-Amz-Signature=" not in url:
            raise VoiceSessionError("음성 연결 주소를 검증하지 못했습니다.")
        return url
