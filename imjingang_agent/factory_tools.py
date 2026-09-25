from __future__ import annotations

import json
import os
import re
from typing import Any, Callable

import httpx

from .data_hub import ImjingangRepository


def _nullable(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


class ImjingangToolRegistry:
    def __init__(self, repository: ImjingangRepository) -> None:
        self.repository = repository
        self.platform_url = os.getenv("IMJINGANG_DATAPLATFORM_URL", "").rstrip("/")
        self.platform_key = os.getenv("IMJINGANG_DATAPLATFORM_AGENT_KEY", "")
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
        if self.platform_url and self.platform_key:
            self.handlers.update({
                "list_tags": self._list_tags,
                "get_latest": self._get_latest,
                "get_readings": self._get_readings,
                "get_ccp_excursions": self._get_ccp_excursions,
            })

    def _platform_get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        try:
            with httpx.Client(
                base_url=self.platform_url,
                headers={"x-api-key": self.platform_key},
                timeout=30,
            ) as client:
                response = client.get(path, params={k: v for k, v in (params or {}).items() if v is not None})
        except httpx.HTTPError as exc:
            raise RuntimeError(f"데이터 플랫폼 연결 실패 — {exc.__class__.__name__}") from exc
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError(f"데이터 플랫폼 연결 실패 ({response.status_code}) — JSON 응답이 아닙니다.") from exc
        if response.is_error:
            message = payload.get("error") or payload.get("message") or "알 수 없는 오류"
            raise RuntimeError(f"데이터 플랫폼 연결 실패 ({response.status_code}) — {message}")
        return payload

    def _list_tags(self) -> dict[str, Any]:
        return self._platform_get("/v1/tags")

    def _get_latest(self, equip_code: str | None) -> dict[str, Any]:
        if equip_code is None:
            return self._platform_get("/v1/equipment")
        if not re.fullmatch(r"[A-Za-z0-9-]{2,20}", equip_code):
            raise ValueError("설비 코드 형식이 올바르지 않습니다.")
        return self._platform_get(f"/v1/equipment/{equip_code}/latest")

    def _get_readings(
        self, equip_code: str, item_key: str | None, from_time: str | None,
        to_time: str | None, interval: str, limit: int,
    ) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9-]{2,20}", equip_code):
            raise ValueError("설비 코드 형식이 올바르지 않습니다.")
        if interval not in {"raw", "hour"}:
            raise ValueError("interval은 raw 또는 hour여야 합니다.")
        if not 1 <= limit <= 5000:
            raise ValueError("limit은 1~5000 범위여야 합니다.")
        return self._platform_get("/v1/readings", {
            "equip_code": equip_code, "item_key": item_key, "from": from_time,
            "to": to_time, "interval": interval, "limit": limit,
        })

    def _get_ccp_excursions(self, date: str | None) -> dict[str, Any]:
        return self._platform_get("/v1/ccp/excursions", {"date": date})

    @property
    def definitions(self) -> list[dict[str, Any]]:
        specs = [
            ("search_knowledge", "절차·기준·SOP·규칙 질문에 로컬 지식문서를 검색한다.", {"query": {"type":"string"}}),
            ("get_rules", "등록된 검토 규칙과 담당자·근거 문서를 조회한다.", {}),
            ("get_db_tables", "조회 가능한 DB 테이블과 건수를 확인한다.", {}),
            ("get_table_records", "허용된 테이블을 읽기 전용으로 조회한다.", {"table":{"type":"string"}, "limit":{"type":"integer", "minimum":1, "maximum":100}, "offset":{"type":"integer", "minimum":0}}),
            ("get_lot_trace", "원재료 입고부터 포장·출하까지 LOT 부모·자식 계보를 조회한다.", {"lot_id": {"type": "string", "description": "정확한 LOT ID"}}),
            ("get_fermentation_status", "발효 LOT의 염도·pH·온도·산도와 시제품 품질예측·완료시점·이상위험을 조회한다.", {"lot_id": _nullable("발효 LOT ID, 전체이면 null")}),
            ("get_ccp_deviations", "혼합·덤퍼와 금속검출 CCP의 주의·부적합 이력을 조회한다.", {"date": _nullable("조회일 YYYY-MM-DD, 전체이면 null")}),
            ("get_inventory_status", "원재료·완제품 재고와 안전재고 부족을 조회한다.", {"item": _nullable("품목명, 전체이면 null"), "shortage_only": {"type": "boolean", "description": "부족 품목만 조회할지"}}),
            ("get_shipment_readiness", "출하대상 LOT의 승인상태·발효위험·CCP 이슈를 검토한다.", {"lot_id": _nullable("포장 LOT ID, 전체이면 null")}),
            ("get_claim_trace", "클레임에서 출하·포장·발효·절임·원재료 LOT까지 역추적한다.", {"claim_id": {"type": "string", "description": "정확한 클레임 ID"}}),
            ("get_process_measurements", "LOT별 염도·pH·온도·산도·중량과 설비상태를 조회한다.", {"lot_id": _nullable("LOT ID, 전체이면 null")}),
        ]
        if self.platform_url and self.platform_key:
            specs.extend([
                ("list_tags", "데이터 플랫폼의 설비·측정항목·CCP 기준 목록을 조회한다.", {}),
                ("get_latest", "설비 전체 또는 지정 설비의 최신 측정값과 신선도를 조회한다.", {"equip_code": _nullable("설비 코드, 전체이면 null")}),
                ("get_readings", "설비 측정값의 KST 이력을 raw 또는 시간별로 조회한다.", {
                    "equip_code": {"type": "string"}, "item_key": _nullable("측정 항목 키, 전체이면 null"),
                    "from_time": _nullable("시작 KST, API에는 from으로 전달"), "to_time": _nullable("종료 KST, API에는 to로 전달"),
                    "interval": {"type": "string", "enum": ["raw", "hour"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 5000},
                }),
                ("get_ccp_excursions", "지정 날짜의 CCP 이탈 샘플 요약을 조회한다. 사건 수가 아니라 기준 이탈 샘플 수다.", {"date": _nullable("YYYY-MM-DD KST, 어제이면 null")}),
            ])
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
            return json.dumps({"source": "임진강김치 ERP·IoT Data Hub", "tool": name, "data": result, "result": result, "status": "ok"}, ensure_ascii=False, default=str)
        except Exception as exc:
            return json.dumps({"error": str(exc), "tool": name}, ensure_ascii=False)
