from __future__ import annotations

import json
from typing import Any

from v3.contracts import AgentRequest


class AgentCoreError(RuntimeError):
    pass


class AgentCoreClient:
    """Thin wrapper around the evolving AgentCore Runtime boto3 API."""

    def __init__(self, runtime_arn: str, region: str, timeout: float = 45.0, client: Any | None = None) -> None:
        self.runtime_arn = runtime_arn
        self.region = region
        self.timeout = timeout
        if client is None:
            try:
                import boto3
                from botocore.config import Config
            except ImportError as exc:
                raise AgentCoreError("AgentCore 모드에는 boto3와 botocore가 필요합니다.") from exc
            client = boto3.client(
                "bedrock-agentcore",
                region_name=region,
                config=Config(connect_timeout=5, read_timeout=timeout, retries={"max_attempts": 2, "mode": "standard"}),
            )
        self.client = client

    def invoke(self, request: AgentRequest) -> dict[str, Any]:
        payload = request.model_dump_json().encode("utf-8")
        try:
            response = self.client.invoke_agent_runtime(
                agentRuntimeArn=self.runtime_arn,
                runtimeSessionId=request.session_id,
                payload=payload,
                qualifier="DEFAULT",
            )
            body = response.get("response") or response.get("body")
            if hasattr(body, "read"):
                body = body.read()
            if isinstance(body, bytes):
                body = body.decode("utf-8")
            result = json.loads(body) if isinstance(body, str) else body
            if not isinstance(result, dict):
                raise ValueError("object response required")
            return result
        except AgentCoreError:
            raise
        except Exception as exc:
            name = exc.__class__.__name__.lower()
            if "access" in name or "credential" in name or "unauthorized" in name:
                message = "AgentCore 호출 권한을 확인해 주세요."
            elif "timeout" in name:
                message = "AgentCore 응답 시간이 초과되었습니다."
            else:
                message = "AgentCore Runtime 응답을 받지 못했습니다."
            raise AgentCoreError(message) from exc
