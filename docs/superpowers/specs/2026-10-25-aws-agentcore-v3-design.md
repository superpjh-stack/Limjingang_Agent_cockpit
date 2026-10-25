# 임진강김치 AWS AgentCore V3 설계

## 1. 목적

기존 Streamlit V1과 React/FastAPI V2를 변경하거나 대체하지 않고, Amazon Bedrock AgentCore를 실행 기반으로 사용하는 독립적인 V3 제조 AI Agent를 추가한다. V3는 임진강김치의 LOT, 공정, CCP, 재고, 출하, 문서 근거를 읽기 전용으로 조회하고 한국어로 답한다.

이 설계의 성공 기준은 다음과 같다.

- V1과 V2의 실행 경로, 배포 설정, 데이터 파일을 그대로 유지한다.
- V3가 별도 디렉터리, 이미지, 포트, 환경설정으로 실행된다.
- AgentCore Runtime에서 제조 Agent를 실행할 수 있다.
- AgentCore Gateway를 통해 허용된 제조 조회 도구만 노출한다.
- AWS 자격증명이 없는 개발 환경에서도 결정형 데모 조회와 자동 테스트가 동작한다.
- 실제 AWS 리소스는 Infrastructure as Code로 재현할 수 있고 최소 권한을 사용한다.
- 응답에서 근거, 조회 도구, 샘플 데이터 여부와 조회 시각을 확인할 수 있다.

## 2. 범위

### 포함

- `v3/` 독립 React 19, TypeScript, Vite 7, FastAPI 애플리케이션
- Amazon Bedrock AgentCore Runtime용 Agent 진입점과 컨테이너
- AgentCore Gateway에 등록할 읽기 전용 제조 도구
- Amazon Bedrock 모델 호출 어댑터
- AgentCore Memory 연동 경계
- AgentCore Observability용 구조화 로그와 추적 상관관계
- 서울 리전(`ap-northeast-2`)을 기본값으로 하는 IaC와 배포 안내
- V2의 저장소 및 도메인 로직 재사용
- SQLite 로컬 데모와 PostgreSQL 운영 연결
- 단위, API, 계약, 빌드, 로컬 컨테이너 검증

### 제외

- V1/V2 제거, 이동 또는 자동 마이그레이션
- 설비 제어, CCP 처분, 출하 승인, 발주 실행
- ERP·IoT 운영 시스템에 대한 쓰기 작업
- 실제 승인 기준이나 실제 생산 데이터 생성
- 기존 음성 기능의 AWS 서비스 전환
- 운영 계정에 대한 무승인 리소스 생성과 실제 배포
- Cognito, 조직 SSO 또는 다중 테넌트 권한 체계의 신규 구축
- 기존 PostgreSQL 데이터의 자동 변환 또는 삭제

## 3. 버전 격리

저장소의 기존 루트 앱은 V1, `v2/`는 V2로 유지한다. V3 관련 변경은 원칙적으로 다음 경로에 한정한다.

```text
v3/
  api.py
  agent/
  web/
  tests/
  Dockerfile
  docker-compose.yml
  requirements.lock
  .env.example
infra/agentcore-v3/
docs/aws-agentcore-v3.md
```

공유 가능한 제조 도메인 코드는 기존 `imjingang_agent/`를 import한다. 공유 모듈 변경이 반드시 필요한 경우에는 V1/V2의 기존 인터페이스를 보존하는 추가형 변경만 허용하고, V1/V2 회귀 테스트를 함께 수행한다.

V3의 기본 호스트 포트는 `8504`, 컨테이너 포트는 `8510`으로 한다. 이미지명, Compose 프로젝트명, 데이터베이스 이름, 볼륨 이름과 세션 쿠키 이름도 V1/V2와 분리한다.

## 4. 아키텍처

```text
React V3 UI
    |
    | HTTPS /api/chat
    v
V3 FastAPI BFF
    |
    | AWS SigV4 + AgentCore invoke
    v
AgentCore Gateway
    |
    v
AgentCore Runtime
    |-- Amazon Bedrock model
    |-- AgentCore Memory
    |-- AgentCore Observability
    |
    | MCP/read-only tools
    v
Manufacturing tool adapter
    |
    +-- PostgreSQL + pgvector (AWS/운영)
    +-- SQLite demo (로컬)
    +-- 등록된 문서 및 규칙
```

V3 FastAPI는 브라우저 인증, 입력 검증, V3 세션 식별, 응답 정규화와 정적 UI 제공을 담당한다. AgentCore Runtime은 모델 오케스트레이션과 도구 선택을 담당한다. 제조 데이터 접근은 Runtime 내부에서 직접 임의 SQL을 실행하지 않고, 명시적 허용 목록을 가진 도구 어댑터를 통해서만 이루어진다.

Gateway는 Runtime의 단일 통제 진입점으로 사용한다. Gateway 또는 관련 기능의 서울 리전 가용성이 배포 시점에 확인되지 않으면 리전을 자동으로 바꾸지 않는다. 배포를 중단하고 지원 리전과 데이터 거버넌스를 검토한다.

## 5. 주요 구성요소

### 5.1 V3 Web

V2의 정보 구조와 접근성 패턴을 재사용하되 소스는 `v3/web/`에 독립적으로 둔다. 화면에는 다음을 명시한다.

- `AWS AgentCore V3` 버전 배지
- 현재 실행 모드: `AgentCore`, `로컬 데모`, `연결 오류`
- 사용 모델과 AWS 리전
- 응답 근거, 실행된 도구, 조회 시각, 샘플 데이터 표시
- 선택된 LOT와 질문에 포함된 LOT가 충돌할 때의 입력 오류

V3는 초기 범위에서 V2의 업무 저장, 인계, 파일럿 지표와 실시간 음성을 복제하지 않는다. 이 기능들은 제조 질의의 AgentCore 전환을 검증한 이후 별도 버전에서 판단한다.

### 5.2 V3 FastAPI BFF

FastAPI는 다음 API를 제공한다.

- `GET /api/health`: 앱, 데이터 저장소, AgentCore 설정 상태와 `3.0.0` 버전
- `GET /api/workspace`: 기존 제조 개요와 V3 실행 메타데이터
- `POST /api/chat`: 입력 검증 후 AgentCore Runtime 호출
- `POST /api/chat/reset`: 브라우저 세션과 AgentCore 대화 연결 초기화
- 기존 LOT, 문서, 테이블 읽기 API 중 V3 UI에 필요한 항목

브라우저에는 AWS 자격증명, Bedrock 자격증명 또는 데이터베이스 비밀번호를 전달하지 않는다. AWS 호출은 서버의 IAM 역할 또는 로컬 AWS 프로파일을 사용한다.

### 5.3 AgentCore Runtime

Runtime은 다음 계약을 갖는다.

입력:

```json
{
  "question": "PACK-260904-001의 출하 확인사항을 알려줘",
  "session_id": "opaque-session-id",
  "lot_id": "PACK-260904-001",
  "user_context": {"role": "operator"}
}
```

출력:

```json
{
  "text": "...",
  "evidence": [],
  "data_tools": ["get_lot_trace", "get_shipment_readiness"],
  "records": [],
  "session_id": "opaque-session-id",
  "mode": "agentcore",
  "demo_data": true,
  "region": "ap-northeast-2",
  "model": "configured-model-id",
  "retrieved_at": "ISO-8601"
}
```

모델 ID는 코드에 고정하지 않고 `V3_BEDROCK_MODEL_ID`로 설정한다. IaC 배포 전 서울 리전에서 해당 모델에 대한 접근 권한과 가용성을 확인한다. 모델 접근 실패를 로컬 데모 응답으로 위장하지 않고 명확한 연결 오류로 반환한다.

### 5.4 제조 도구

V3의 1차 도구 집합은 기존 `ImjingangToolRegistry`의 읽기 전용 기능 중 다음 범위로 제한한다.

- LOT 목록 및 계보 조회
- 공정 측정 조회
- 발효 상태 조회
- CCP 이탈 조회
- 재고 상태 조회
- 출하 준비 상태 조회
- 클레임 역추적 조회
- 등록 문서 및 규칙 검색

도구 인자는 Pydantic 또는 동등한 JSON Schema로 검증한다. 테이블명, 정렬, 페이지 크기 같은 값은 허용 목록과 상한을 적용한다. 도구 결과 안의 텍스트는 명령이 아니라 비신뢰 데이터로 취급하도록 Agent 지침에 명시한다.

### 5.5 Memory

AgentCore Memory에는 대화 연결에 필요한 최소 정보만 저장한다.

- 세션 ID
- 사용자 질문과 Agent 답변의 요약
- 사용자가 명시적으로 선택한 LOT
- 마지막 사용 도구와 문서 식별자

API 키, 비밀번호, 원본 음성, 전체 제조 테이블 덤프, 고객 개인정보는 저장하지 않는다. 제조 원본 기록과 업무 저장 데이터는 기존 PostgreSQL에 남기고 Memory를 원본 저장소로 사용하지 않는다. 보존 기간은 환경설정으로 관리하며 초기 기본값은 24시간의 단기 대화 문맥으로 한다.

### 5.6 Observability

각 요청에 `request_id`, `session_id`, `agent_runtime_id`를 연결한다. 로그에는 질문 전문과 도구 원본 레코드를 기본적으로 남기지 않고 다음 메타데이터를 기록한다.

- 처리 단계와 소요시간
- 모델 ID와 리전
- 실행된 도구 이름, 성공 여부, 반환 건수
- 오류 분류와 재시도 여부
- 응답 근거 개수

비밀정보 마스킹 후 구조화 JSON 로그를 사용한다. 모델 내부 추론 전문은 저장하거나 화면에 노출하지 않는다.

## 6. 요청 흐름

1. 사용자가 V3 UI에서 질문하고 선택 LOT를 함께 전송한다.
2. FastAPI가 길이, LOT 형식, 선택 LOT 충돌, 인증 상태를 검증한다.
3. FastAPI가 불투명 세션 ID를 만들거나 기존 세션을 사용한다.
4. FastAPI가 IAM 역할로 AgentCore Gateway를 호출한다.
5. Runtime이 Agent 지침, Memory 문맥과 질문을 조합한다.
6. 모델이 필요한 읽기 전용 제조 도구를 선택한다.
7. 도구 어댑터가 PostgreSQL 또는 SQLite에서 허용된 조회를 수행한다.
8. Runtime이 기록과 문서 근거를 함께 묶어 한국어 답변을 생성한다.
9. FastAPI가 출력을 공통 응답 스키마로 검증하고 UI에 전달한다.
10. UI가 답변, 근거, 도구, 샘플 여부와 조회 시각을 분리해 표시한다.

질문 처리 중 LOT가 바뀌거나 대화가 초기화되면 이전 요청은 새 화면 상태에 합쳐지지 않아야 한다.

## 7. 로컬 및 AWS 실행 모드

### 로컬 데모

`V3_AGENT_BACKEND=demo`에서는 AWS 호출 없이 기존 결정형 조회를 사용한다. 화면과 응답에 `로컬 데모` 및 `demo_data: true`를 표시한다. 이 모드는 AgentCore 동작 검증이나 모델 품질 검증으로 간주하지 않는다.

### AgentCore

`V3_AGENT_BACKEND=agentcore`에서는 다음 값이 필수다.

- `AWS_REGION=ap-northeast-2`
- `V3_AGENTCORE_RUNTIME_ARN` 또는 배포 결과가 제공하는 호출 식별자
- `V3_AGENTCORE_GATEWAY_URL`
- `V3_BEDROCK_MODEL_ID`
- `DATABASE_URL`

필수 설정 누락 시 앱은 시작 단계 또는 헬스 체크에서 명확한 설정 오류를 보고한다. AgentCore 장애 시 결정형 데모로 자동 전환하지 않는다.

## 8. IaC와 AWS 리소스

`infra/agentcore-v3/`는 한 가지 IaC 도구로 다음을 정의한다.

- AgentCore Runtime과 버전/엔드포인트
- AgentCore Gateway와 Runtime 또는 도구 대상
- AgentCore Memory 리소스
- 실행 역할과 최소 IAM 정책
- 컨테이너 이미지 저장소
- 로그 그룹, 보존 기간과 기본 경보
- 배포 출력값

IaC는 실제 비밀값을 포함하지 않는다. 데이터베이스 자격증명은 AWS Secrets Manager 참조로 전달하고, 로컬 `.env`는 커밋하지 않는다. 파괴 작업과 데이터 저장소 삭제 보호를 기본값으로 금지한다.

최소 IAM 권한은 리소스 ARN과 리전을 제한한다. 개발자 장기 액세스 키를 컨테이너에 포함하지 않으며 AWS 런타임에서는 역할 기반 자격증명을 사용한다.

## 9. 오류 처리

오류는 사용자 오류, 설정 오류, 외부 서비스 오류, 데이터 오류로 구분한다.

- 잘못된 LOT 또는 충돌: 4xx와 수정 가능한 한국어 안내
- 모델 또는 AgentCore 권한 부족: 503과 관리자 설정 안내
- Gateway 또는 Runtime 시간 초과: 제한된 횟수만 재시도한 뒤 504
- 도구 입력 검증 실패: 도구를 실행하지 않고 안전한 오류 반환
- 데이터 없음: 정상 응답으로 `미확인` 표시
- 응답 스키마 불일치: 원문을 그대로 전달하지 않고 502 처리

재시도는 읽기 전용이고 멱등인 호출에만 적용한다. 오류 응답에 ARN 전체, 토큰, 데이터베이스 URL, 스택 트레이스를 포함하지 않는다.

## 10. 보안 및 안전 경계

- 모든 제조 도구는 읽기 전용이다.
- 임의 SQL, 셸, 파일 쓰기, 외부 URL 가져오기 도구를 제공하지 않는다.
- 서버가 AWS 자격증명과 데이터베이스 비밀을 보유한다.
- 외부 제공 시 HTTPS와 조직 인증을 필수 운영 조건으로 둔다.
- 프롬프트 인젝션을 고려해 문서와 DB 텍스트를 비신뢰 데이터로 처리한다.
- 모델 답변은 승인이나 자동 제어가 아니라 의사결정 지원임을 표시한다.
- 샘플 기준과 수치를 실제 승인 기준으로 표현하지 않는다.
- 감사 로그는 비밀정보 및 질문 전문을 기본적으로 수집하지 않는다.

## 11. 테스트 전략

### 자동 테스트

- 제조 도구의 허용 목록과 인자 검증
- V3 Agent 입력/출력 계약
- AgentCore 클라이언트의 서명, 시간 초과, 오류 매핑을 모의 객체로 검증
- demo/agentcore 모드 분리와 자동 폴백 금지
- LOT 충돌, 존재하지 않는 LOT, 데이터 없음 처리
- 키, 토큰, ARN과 DB URL 비노출
- `/api/health`와 `/api/workspace` 버전 메타데이터
- React 프로덕션 빌드
- V1/V2 기존 테스트 회귀

### 수동 검증

- 데스크톱 및 390px 화면
- 추천질문, 직접 질문, LOT 선택, 대화 초기화
- 근거 열기와 도구/조회 시각 표시
- AgentCore 세션 유지와 초기화
- 권한 부족, 잘못된 모델 ID, Gateway 장애 화면
- 실제 서울 리전 Runtime 호출과 Observability 추적 연결

실제 AWS 호출을 실행하지 않은 경우 결과에 `로컬/모의 검증만 완료`라고 명시한다.

## 12. 배포와 롤백

V3는 V1/V2와 별도 이미지와 엔드포인트로 배포한다. 초기 배포는 내부 테스트용 별도 URL에서 수행하고 기존 트래픽을 전환하지 않는다.

배포 순서는 다음과 같다.

1. 테스트 및 이미지 빌드
2. IaC 변경 계획 검토
3. AWS 리소스 생성 또는 업데이트
4. AgentCore Runtime 새 버전 게시
5. V3 엔드포인트가 새 버전을 가리키도록 갱신
6. 헬스 체크와 대표 제조 질문 검증

롤백은 V3 엔드포인트를 직전 Runtime 버전으로 되돌리는 방식으로 수행한다. V1/V2에는 라우팅 변경을 하지 않으므로 V3 장애가 기존 버전의 롤백을 요구하지 않는다. 데이터베이스 스키마 변경이 필요한 경우에는 먼저 하위 호환 마이그레이션과 백업을 별도 승인받는다.

## 13. 수용 기준

- 저장소에서 V1, V2, V3의 실행 안내가 명확히 구분된다.
- 기존 V1/V2 파일과 배포 구성이 보존된다.
- `v3/` 앱이 AWS 없이 로컬 데모 모드로 실행된다.
- AgentCore 모드가 구성 누락과 권한 오류를 명확히 보고한다.
- AgentCore Runtime용 이미지와 IaC가 재현 가능하게 생성된다.
- 최소 한 개의 LOT 질문이 두 개 이상의 읽기 도구를 사용하고 근거와 함께 반환된다.
- 사용자에게 설비 제어 또는 출하 승인을 완료했다고 잘못 알리지 않는다.
- V3와 관련 테스트 및 기존 회귀 테스트가 통과한다.
- 실제 AWS 배포 여부와 실제 모델 호출 검증 여부가 최종 보고서에 구분된다.

## 14. 구현 순서

1. V3 패키지와 공통 계약 정의
2. 로컬 데모 BFF와 독립 UI 구성
3. 제조 도구 어댑터 및 계약 테스트
4. AgentCore Runtime과 Bedrock 모델 어댑터
5. Gateway, Memory, Observability 연동
6. IaC와 배포 문서
7. 전체 자동 테스트, 빌드 및 수동 UI 검증
8. 사용자가 제공한 AWS 계정 권한 범위에서 별도 승인 후 실제 배포 검증

