from __future__ import annotations

import asyncio
from typing import Any

from v3.aws import AgentCoreClient
from v3.contracts import AgentRequest


class VoiceAgent:
    def __init__(self, client: AgentCoreClient) -> None:
        self.client = client

    async def ask(self, question: str, session_id: str, lot_id: str | None) -> dict[str, Any]:
        request = AgentRequest(
            question=question,
            session_id=session_id,
            lot_id=lot_id,
            user_context={"role": "operator", "channel": "voice"},
        )
        return await asyncio.to_thread(self.client.invoke, request)
