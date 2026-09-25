# 임진강김치 Agent v2.0 진행 기록

기준 문서: `docs/v2.0-product-plan.md`, `docs/v2.0-delivery-spec.md` (티켓 표 2절). 구현은 `v2/`.

## 지금까지 끝난 것

- 2026-09-25 화면 단순화 재설계: 7개 메뉴 중심 Cockpit을 왼쪽 `지식베이스·데이터허브`, 중앙 `챗`, 오른쪽 `질의이력·추천질의 10선`의 3열 워크스페이스로 재구성. 임진강김치에 맞춘 배추잎 녹색·고춧가루 적색·밝은 한지 톤, 모바일 좌우 서랍, 세션 질의이력, 실제 문서·테이블·추천질의 API 연결을 구현. 프런트 빌드 및 V2 테스트 19개 통과·1개 스킵(PostgreSQL).

- 2.0-A 티켓 CX-01·CX-02·CTX-01·VO-01·VO-02·VO-03·PC-01·EV-01 구현 (직접 녹음 `useVoice.ts`, 문맥 유지, 구조화 답변).
- 2.0-B 티켓 AU-01·WK-01·EV-02·HO-01·SY-01 구현 (`v2/work.py`, `WorkBoard.tsx`, `manage_users.py`).
- PC-02 출하·클레임 검토 초안 (`WorkBoard.tsx` 내부/고객 초안, 외부 발송 없음).
- 2026-09-23 ME-01 여정 계측: `v2/metrics.py`(`/api/events`, 관리자 `/api/metrics`), 화면 `track()`(`types.ts`), 관리자 지표 패널 `PilotMetrics.tsx`, 테스트 `v2/tests/test_metrics.py`. 전체 테스트 25 통과·1 스킵(PostgreSQL), 빌드 정상, 데스크톱 브라우저에서 이벤트 적재·지표 표시 확인. README 갱신.
- 2026-09-23 음성 복구 보완: 변환 실패 시 녹음 Blob을 유지해 재시도, `stopping`에서 마지막 `dataavailable` 처리, 지원 MIME·빈 파일·20MB 제한, 자동 재생 차단 시 `ready`→사용자 재생 버튼, 새 녹음·화면 전환 시 기존 재생 정리. Docker 런타임에 `v2/metrics.py` 복사 누락도 수정. 프런트 빌드 정상, V2 테스트 17 통과·1 스킵.
- 2026-09-23 실시간 음성 대화 전환: 모바일 브라우저 WebRTC와 Realtime API를 직접 연결해 녹음 파일·수동 변환 단계를 제거. 의미 기반 발화 종료 감지, 즉시 음성 응답, 답변 중 끼어들기, 음소거·종료, 세션 자막, 선택 LOT의 서버 검증 문맥을 구현. 공급자 키는 서버에만 유지.

## 지금 해야 할 것

1. 실기기 검증: iPhone Safari·Android Chrome에서 HTTPS로 수용 시나리오 A01~A03·A06·A08·A11 (마이크 권한·배경 전환·재생 정지). 시뮬레이션만으로 음성 완료라고 하지 않는다.
2. 모바일↔PC 교차 시나리오 B01·B03을 실제 두 기기로 확인하고 지표의 "저장 후 이어보기"가 연결되는지 본다.
3. PostgreSQL 통합 테스트: `TEST_POSTGRES_ADMIN_URL=... .venv-v2/bin/python -m pytest v2/tests -q` (v2_journey_events 포함).
4. Docker 이미지 실제 빌드(`docker build -f v2/Dockerfile ...`) — 로컬에서 미검증.
5. 파일럿 전 확정 항목(명세 7절)은 사용자·현장 결정 사항. 현행 흐름 기준값 측정 필요.

## 알아둘 것

- 여정 이벤트 journey_id: 일반 이벤트는 탭별 임시 UUID, 업무 이벤트(task_saved·task_resumed·handoff·review_completed)는 업무 ID. 그래야 기기 간 이어보기가 집계된다.
- `/api/events`는 extra 필드를 422로 거절한다. 문장·음성을 실수로 보내지 않게 하는 장치이므로 느슨하게 바꾸지 말 것.
- `task_opened`는 페이지 로드부터 첫 업무 열기까지 한 번만 기록한다. 저장 직후 자동으로 열리는 것은 task_resumed로 세지 않는다.
- `V2_REQUIRE_LOGIN=1`이면 `/api/events`도 로그인이 필요하다 (비로그인 데모 이벤트는 수집되지 않음).
