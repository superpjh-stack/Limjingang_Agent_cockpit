from __future__ import annotations

import re
from typing import Any

from v3.contracts import AgentRequest, AgentResponse


LOT_PATTERN = re.compile(r"(?:RAW|SORT|SALT|MIX|FERM|PACK)-\d{6}-\d{3}")


class DemoBackend:
    def __init__(self, repository: Any, region: str = "ap-northeast-2") -> None:
        self.repository = repository
        self.region = region

    def ask(self, request: AgentRequest) -> AgentResponse:
        question = request.question
        selected = request.lot_id
        match = LOT_PATTERN.search(question.upper())
        selected = match.group() if match else selected
        evidence = self.repository.search_knowledge(question)[:3]
        tools: list[str] = []
        records: list[dict[str, Any]] = []

        if selected:
            trace = self.repository.lot_trace(selected)
            shipment = self.repository.shipment_readiness(selected)
            tools = ["get_lot_trace", "get_shipment_readiness"]
            records = [*trace, *shipment]
            if not trace:
                text = f"{selected}는 샘플 DB에서 확인되지 않습니다."
            else:
                text = f"{selected}의 공정 계보 {len(trace)}건과 출하 준비 기록 {len(shipment)}건을 확인했습니다."
        elif "재고" in question or "부족" in question:
            records = self.repository.inventory_status(None, "부족" in question)
            tools = ["get_inventory_status"]
            text = f"조건에 맞는 재고 기록 {len(records)}건을 확인했습니다."
        elif "CCP" in question.upper():
            records = self.repository.ccp_deviations(None)
            tools = ["get_ccp_deviations"]
            text = f"CCP 기록 {len(records)}건을 확인했습니다. 처분이나 출하 승인을 대신하지 않습니다."
        elif "발효" in question:
            records = self.repository.fermentation_status(None)
            tools = ["get_fermentation_status"]
            text = f"발효 상태 {len(records)}건을 확인했습니다."
        else:
            tools = ["search_knowledge"]
            text = f"관련 등록 문서 {len(evidence)}건을 찾았습니다. 확인되지 않은 기준은 미확인으로 남깁니다."

        sources = list(dict.fromkeys(str(item.get("filename", "")) for item in evidence if item.get("filename")))
        return AgentResponse(
            text=text + "\n근거: " + (", ".join([*tools, *sources]) or "일치하는 기록·문서 없음"),
            sources=sources,
            evidence=evidence,
            data_tools=tools,
            records=records[:100],
            searched_documents=True,
            session_id=request.session_id,
            mode="demo",
            demo_data=True,
            region=self.region,
            model="deterministic-demo",
        )
