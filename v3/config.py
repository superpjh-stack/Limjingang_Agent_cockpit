from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    pass


@dataclass(frozen=True)
class V3Settings:
    backend: str = "demo"
    aws_region: str = "ap-northeast-2"
    model_id: str = ""
    runtime_arn: str = ""
    runtime_qualifier: str = "DEFAULT"
    gateway_url: str = ""
    memory_id: str = ""
    database_url: str = ""
    sqlite_path: str = "data/imjingang_v3_demo.db"
    request_timeout: float = 120.0
    memory_ttl_hours: int = 24
    voice_enabled: bool = False
    voice_runtime_arn: str = ""
    voice_runtime_qualifier: str = "ImjingangVoiceV3Live"
    voice_url_ttl_seconds: int = 60

    @classmethod
    def from_env(cls) -> "V3Settings":
        settings = cls(
            backend=os.getenv("V3_AGENT_BACKEND", "demo").strip().lower(),
            aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")).strip(),
            model_id=os.getenv("V3_BEDROCK_MODEL_ID", "").strip(),
            runtime_arn=os.getenv("V3_AGENTCORE_RUNTIME_ARN", "").strip(),
            runtime_qualifier=os.getenv("V3_AGENTCORE_QUALIFIER", "DEFAULT").strip(),
            gateway_url=os.getenv("V3_AGENTCORE_GATEWAY_URL", "").strip(),
            memory_id=os.getenv("V3_AGENTCORE_MEMORY_ID", "").strip(),
            database_url=os.getenv("DATABASE_URL", "").strip(),
            sqlite_path=os.getenv("V3_SQLITE_PATH", "data/imjingang_v3_demo.db").strip(),
            request_timeout=float(os.getenv("V3_REQUEST_TIMEOUT", "120")),
            memory_ttl_hours=int(os.getenv("V3_MEMORY_TTL_HOURS", "24")),
            voice_enabled=os.getenv("V3_VOICE_ENABLED", "0").strip().lower() in {"1", "true", "yes"},
            voice_runtime_arn=os.getenv("V3_VOICE_RUNTIME_ARN", "").strip(),
            voice_runtime_qualifier=os.getenv("V3_VOICE_RUNTIME_QUALIFIER", "ImjingangVoiceV3Live").strip(),
            voice_url_ttl_seconds=int(os.getenv("V3_VOICE_URL_TTL_SECONDS", "60")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.backend not in {"demo", "agentcore"}:
            raise ConfigurationError("V3_AGENT_BACKEND는 demo 또는 agentcore여야 합니다.")
        if not self.aws_region:
            raise ConfigurationError("AWS_REGION을 설정해야 합니다.")
        if self.request_timeout <= 0 or self.request_timeout > 300:
            raise ConfigurationError("V3_REQUEST_TIMEOUT은 0초 초과 300초 이하여야 합니다.")
        if self.memory_ttl_hours < 1 or self.memory_ttl_hours > 720:
            raise ConfigurationError("V3_MEMORY_TTL_HOURS는 1~720 범위여야 합니다.")
        if self.voice_url_ttl_seconds < 30 or self.voice_url_ttl_seconds > 300:
            raise ConfigurationError("V3_VOICE_URL_TTL_SECONDS는 30~300 범위여야 합니다.")
        if self.voice_enabled and not self.voice_runtime_arn:
            raise ConfigurationError("음성 기능에는 V3_VOICE_RUNTIME_ARN이 필요합니다.")
        if self.backend == "agentcore":
            missing = [name for name, value in {
                "V3_BEDROCK_MODEL_ID": self.model_id,
                "V3_AGENTCORE_RUNTIME_ARN": self.runtime_arn,
                "V3_AGENTCORE_QUALIFIER": self.runtime_qualifier,
                "V3_AGENTCORE_GATEWAY_URL": self.gateway_url,
            }.items() if not value]
            if missing:
                raise ConfigurationError("AgentCore 설정 누락: " + ", ".join(missing))
