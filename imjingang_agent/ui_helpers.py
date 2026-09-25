from __future__ import annotations

from datetime import datetime
from typing import Any


QUESTION_GROUPS = {'공정데이터': [
    '지금 데이터가 끊겼거나 신선도가 떨어진 설비를 알려줘',
    '지금 숙성 냉장고 TC-01의 현재온도와 설정온도를 알려줘',
    '냉장·냉동 설비 4대의 현재온도를 비교해줘',
    '지금 SAL-01 절임통 염도와 염수온도를 확인해줘',
    '어제 SAL-01 염도의 시간별 최소·평균·최대값을 요약해줘',
    '어제 숙성 냉장고 TC-01 온도 추이와 기준 이탈 여부를 알려줘',
    '지금 금속검출기 MD-01의 가동상태·검사수량·불합격수량을 알려줘',
    '지금 소독수 공급장치 SAN-01의 농도와 접촉시간을 확인해줘',
    '어제 CCP 이탈 샘플을 심각도와 설비별로 요약해줘',
    '데이터 플랫폼에 연결된 설비와 측정 항목을 공정별로 정리해줘',
], '일반질의': [
    '김치 제조 공정의 전체 흐름을 쉽게 설명해줘',
    '김치 발효에서 pH가 중요한 이유는 뭐야?',
    '절임 공정에서 염도와 온도를 함께 확인하는 이유를 알려줘',
    'HACCP의 CCP가 무엇인지 현장 작업자가 이해하기 쉽게 설명해줘',
    '금속검출 부적합이 발생했을 때 확인할 사항을 정리해줘',
    '원재료부터 완제품까지 LOT 추적이 필요한 이유는 뭐야?',
    '냉장 보관중인 김치의 품질을 확인할 때 보는 항목은 뭐야?',
    '출하 전 품질 검토 체크리스트를 만들어줘',
    '숙성 편차 클레임이 발생했을 때 역추적 순서를 알려줘',
    '제조 데이터의 누락과 이상치를 검토하는 방법을 알려줘',
]}

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
