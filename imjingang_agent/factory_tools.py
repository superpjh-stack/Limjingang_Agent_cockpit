from __future__ import annotations

import json
from typing import Any, Callable

from .data_hub import ImjingangRepository


def _nullable(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


class ImjingangToolRegistry:
    def __init__(self, repository: ImjingangRepository) -> None:
        self.repository = repository
        self.handlers: dict[str, Callable[..., Any]] = {
            "search_knowledge": repository.search_knowledge,
            "get_rules": repository.get_rules,
            "get_db_tables": repository.table_inventory,
            "get_table_records": repository.table_records,
            "get_lot_trace": repository.lot_trace,
            "get_fermentation_status": repository.fermentation_status,
            "get_ccp_deviations": repository.ccp_deviations,
            "get_inventory_status": repository.inventory_status,
            "get_shipment_readiness": repository.shipment_readiness,
            "get_claim_trace": repository.claim_trace,
            "get_process_measurements": repository.process_measurements,
        }

    @property
    def definitions(self) -> list[dict[str, Any]]:
        specs = [
            ("search_knowledge", "절차·기준·SOP·규칙 질문에 로컬 지식문서를 검색한다.", {"query": {"type":"string"}}),
            ("get_rules", "미승인 샘플 규칙과 담당자·근거 문서를 조회한다.", {}),
            ("get_db_tables", "조회 가능한 DB 테이블과 건수를 확인한다.", {}),
            ("get_table_records", "허용된 테이블을 읽기 전용으로 조회한다.", {"table":{"type":"string"}, "limit":{"type":"integer", "minimum":1, "maximum":100}, "offset":{"type":"integer", "minimum":0}}),
            ("get_lot_trace", "원재료 입고부터 포장·출하까지 LOT 부모·자식 계보를 조회한다.", {"lot_id": {"type": "string", "description": "정확한 LOT ID"}}),
            ("get_fermentation_status", "발효 LOT의 염도·pH·온도·산도와 시제품 품질예측·완료시점·이상위험을 조회한다.", {"lot_id": _nullable("발효 LOT ID, 전체이면 null")}),
            ("get_ccp_deviations", "혼합·덤퍼와 금속검출 CCP의 주의·부적합 이력을 조회한다.", {"date": _nullable("조회일 YYYY-MM-DD, 전체이면 null")}),
            ("get_inventory_status", "원재료·완제품 샘플 재고와 안전재고 부족을 조회한다.", {"item": _nullable("품목명, 전체이면 null"), "shortage_only": {"type": "boolean", "description": "부족 품목만 조회할지"}}),
            ("get_shipment_readiness", "출하대상 LOT의 승인상태·발효위험·CCP 이슈를 검토한다.", {"lot_id": _nullable("포장 LOT ID, 전체이면 null")}),
            ("get_claim_trace", "클레임에서 출하·포장·발효·절임·원재료 LOT까지 역추적한다.", {"claim_id": {"type": "string", "description": "정확한 클레임 ID"}}),
            ("get_process_measurements", "LOT별 염도·pH·온도·산도·중량과 설비상태를 조회한다.", {"lot_id": _nullable("LOT ID, 전체이면 null")}),
        ]
        return [
            {"type": "function", "name": name, "description": description, "strict": True,
             "parameters": {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}}
            for name, description, props in specs
        ]

    def execute(self, name: str, arguments: str | dict[str, Any]) -> str:
        if name not in self.handlers:
            return json.dumps({"error": f"허용되지 않은 도구: {name}"}, ensure_ascii=False)
        try:
            values = json.loads(arguments) if isinstance(arguments, str) else arguments
            result = self.handlers[name](**values)
            return json.dumps({"source": "임진강김치 ERP·IoT Data Hub", "tool": name, "data": result, "result": result, "status": "ok", "demo_data": True}, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "tool": name}, ensure_ascii=False)
