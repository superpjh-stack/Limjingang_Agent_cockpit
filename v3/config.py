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
    gateway_url: str = ""
    memory_id: str = ""
    database_url: str = ""
    sqlite_path: str = "data/imjingang_v3_demo.db"
    request_timeout: float = 45.0
    memory_ttl_hours: int = 24

    @classmethod
    def from_env(cls) -> "V3Settings":
        settings = cls(
            backend=os.getenv("V3_AGENT_BACKEND", "demo").strip().lower(),
            aws_region=os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")).strip(),
            model_id=os.getenv("V3_BEDROCK_MODEL_ID", "").strip(),
            runtime_arn=os.getenv("V3_AGENTCORE_RUNTIME_ARN", "").strip(),
            gateway_url=os.getenv("V3_AGENTCORE_GATEWAY_URL", "").strip(),
            memory_id=os.getenv("V3_AGENTCORE_MEMORY_ID", "").strip(),
            database_url=os.getenv("DATABASE_URL", "").strip(),
            sqlite_path=os.getenv("V3_SQLITE_PATH", "data/imjingang_v3_demo.db").strip(),
            request_timeout=float(os.getenv("V3_REQUEST_TIMEOUT", "45")),
            memory_ttl_hours=int(os.getenv("V3_MEMORY_TTL_HOURS", "24")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if self.backend not in {"demo", "agentcore"}:
            raise ConfigurationError("V3_AGENT_BACKEND는 demo 또는 agentcore여야 합니다.")
        if not self.aws_region:
            raise ConfigurationError("AWS_REGION을 설정해야 합니다.")
        if self.request_timeout <= 0 or self.request_timeout > 120:
            raise ConfigurationError("V3_REQUEST_TIMEOUT은 0초 초과 120초 이하여야 합니다.")
        if self.memory_ttl_hours < 1 or self.memory_ttl_hours > 720:
            raise ConfigurationError("V3_MEMORY_TTL_HOURS는 1~720 범위여야 합니다.")
        if self.backend == "agentcore":
            missing = [name for name, value in {
                "V3_BEDROCK_MODEL_ID": self.model_id,
                "V3_AGENTCORE_RUNTIME_ARN": self.runtime_arn,
                "V3_AGENTCORE_GATEWAY_URL": self.gateway_url,
            }.items() if not value]
            if missing:
                raise ConfigurationError("AgentCore 설정 누락: " + ", ".join(missing))
