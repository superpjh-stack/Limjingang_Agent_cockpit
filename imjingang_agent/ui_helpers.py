from __future__ import annotations

from datetime import datetime
from typing import Any


QUESTION_GROUPS = {'지식베이스': ['원재료 입고부터 출하까지 LOT 연결 절차를 알려줘', '배추·율무 입고검사에서 확인할 문서는?', '세척·절임 작업표준 확인 순서를 알려줘', '양념·혼합 배합 확인 절차는?', '발효·숙성 상태를 검토하는 절차는?', 'CCP 주의 건 발생 시 확인할 기록은?', '율무 부족 시 구매담당자가 확인할 것은?', '포장 LOT 출하검토 체크리스트를 알려줘', '숙성 편차 클레임 역추적 순서를 알려줘', '예측 정확도 90%가 달성값인지 근거로 설명해줘'], 'DB': ['샘플 데이터의 발효 위험 LOT를 브리핑해줘', 'FERM-260903-002의 pH·산도·염도·온도를 알려줘', 'PACK-260903-001을 원재료까지 역추적해줘', '2026-09-03 CCP 주의 건을 알려줘', '율무 재고와 부족량을 계산해줘', '승인대기 출하와 확인할 사항을 알려줘', 'CLM-260903-01의 관련 LOT를 추적해줘', 'SALT-260901-001의 측정기록을 알려줘', 'DB에 어떤 테이블이 있는지 알려줘', '발효 예측 테이블의 모델 상태와 예측시각을 알려줘'], '룰': ['등록된 검토 규칙과 근거 문서를 알려줘', '원료 부족 규칙과 율무 재고를 함께 확인해줘', '발효 위험 규칙으로 샘플 LOT를 검토해줘', 'CCP 주의 규칙과 담당자를 알려줘', '출하 승인대기 규칙을 적용해 검토사항을 알려줘', '클레임 분석중 규칙의 확인사항은?', '센서 상태 주의 규칙과 관련 기록을 알려줘', '계보가 누락된 LOT와 확인할 규칙은?', '등록된 규칙이 현장 승인 기준인지 확인해줘', '규칙별 담당자와 승인 필요한 조치를 요약해줘']}

WELCOME_MESSAGE = {"role": "assistant", "content": "안녕하세요. 임진강김치 제조 Agent입니다.  \n원재료부터 전처리·절임·혼합·금속검출·발효·포장·출하까지 LOT와 품질 근거를 연결합니다.", "sources": [], "evidence": [], "data_tools": [], "created_at": "시작"}


def timestamp() -> str:
    return datetime.now().strftime("%H:%M")


def user_question_history(messages: list[dict[str, Any]], limit: int = 8) -> list[dict[str, str]]:
    return [{"content": str(m.get("content", "")), "created_at": str(m.get("created_at", ""))} for m in reversed(messages) if m.get("role") == "user"][:limit]


def lot_snapshot(repository: Any, lot_id: str) -> dict[str, Any]:
    lot = next((row for row in repository.all_lots() if row["lot_id"] == lot_id), {})
    trace = repository.lot_trace(lot_id)
    related = {row["lot_id"] for row in trace}
    fermentation = [row for row in repository.fermentation_status(None) if row.get("lot_id") in related]
    ccp = [row for row in repository.ccp_deviations(None) if row.get("lot_id") in related]
    shipments = repository.shipment_readiness(lot_id) if lot_id.startswith("PACK-") else []
    return {"lot": lot, "trace": trace, "fermentation": fermentation, "ccp": ccp, "shipments": shipments}


def risk_label(snapshot: dict[str, Any]) -> tuple[str, str]:
    high = any(float(row.get("abnormal_risk") or 0) >= .7 for row in snapshot["fermentation"])
    score = int(high) * 2 + len(snapshot["ccp"]) + len([r for r in snapshot["shipments"] if r.get("approval_status") != "승인"])
    return ("높음", "🔴") if score >= 3 else (("주의", "🟠") if score else ("안정", "🟢"))
