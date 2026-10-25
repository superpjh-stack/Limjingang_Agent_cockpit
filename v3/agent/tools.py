from __future__ import annotations

import json
from typing import Any

from imjingang_agent.factory_tools import ImjingangToolRegistry


ALLOWED_TOOLS = {
    "search_knowledge", "get_rules", "get_lot_trace", "get_fermentation_status",
    "get_ccp_deviations", "get_inventory_status", "get_shipment_readiness",
    "get_claim_trace", "get_process_measurements",
}


class ReadOnlyTools:
    def __init__(self, repository: Any) -> None:
        self.registry = ImjingangToolRegistry(repository)

    @property
    def definitions(self) -> list[dict[str, Any]]:
        return [item for item in self.registry.definitions if item.get("name") in ALLOWED_TOOLS]

    def execute(self, name: str, arguments: str | dict[str, Any]) -> dict[str, Any]:
        if name not in ALLOWED_TOOLS:
            return {"error": f"허용되지 않은 도구: {name}", "tool": name}
        payload = json.loads(self.registry.execute(name, arguments))
        result = payload.get("result")
        if isinstance(result, list) and len(result) > 100:
            payload["result"] = result[:100]
            payload["data"] = result[:100]
            payload["truncated"] = True
        return payload
