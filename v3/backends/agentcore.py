from __future__ import annotations

from typing import Any

from v3.contracts import AgentRequest, AgentResponse


class AgentCoreBackend:
    def __init__(self, client: Any, region: str, model_id: str) -> None:
        self.client = client
        self.region = region
        self.model_id = model_id

    def ask(self, request: AgentRequest) -> AgentResponse:
        payload = self.client.invoke(request)
        payload.update({
            "session_id": request.session_id,
            "mode": "agentcore",
            "demo_data": bool(payload.get("demo_data", False)),
            "region": self.region,
            "model": self.model_id,
        })
        return AgentResponse.model_validate(payload)
