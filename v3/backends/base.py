from __future__ import annotations

from typing import Protocol

from v3.contracts import AgentRequest, AgentResponse


class AgentBackend(Protocol):
    def ask(self, request: AgentRequest) -> AgentResponse: ...
