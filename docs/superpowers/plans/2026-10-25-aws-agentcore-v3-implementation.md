# AWS AgentCore V3 구현 계획

## 목표

승인된 [AWS AgentCore V3 설계](../specs/2026-10-25-aws-agentcore-v3-design.md)에 따라 기존 V1/V2를 보존하면서 `v3/` 독립 애플리케이션과 `infra/agentcore-v3/` 배포 정의를 추가한다.

## 구현 원칙

- 각 단계는 실패하는 테스트 또는 검증 기준을 먼저 추가한 뒤 최소 구현으로 통과시킨다.
- V1/V2의 기존 실행 경로와 설정은 수정하지 않는다.
- 공유 모듈 변경이 필요하면 기존 공개 인터페이스를 유지하고 회귀 테스트를 실행한다.
- AWS가 없어도 전체 로컬 테스트와 UI 빌드가 가능해야 한다.
- 실제 AWS 배포는 코드와 IaC 검증 이후 사용자 승인과 사용 가능한 AWS 자격증명이 있을 때만 수행한다.
- AWS 기능과 SDK는 구현 시점의 공식 AgentCore 문서와 설치된 SDK API를 기준으로 확인한다.

## 1. V3 골격과 독립 실행 경계

### 생성 파일

- `v3/__init__.py`
- `v3/api.py`
- `v3/config.py`
- `v3/contracts.py`
- `v3/requirements.txt`
- `v3/requirements.lock`
- `v3/.env.example`
- `v3/Dockerfile`
- `v3/docker-compose.yml`
- `v3/tests/conftest.py`
- `v3/tests/test_config.py`
- `v3/tests/test_api.py`

### 작업

1. `V3Settings`에 실행 모드, 리전, 모델 ID, Runtime/Gateway 식별자, DB 경로를 정의한다.
2. `demo` 모드는 AWS 설정 없이 허용하고 `agentcore` 모드는 필수 설정을 검증한다.
3. 공통 요청·응답 Pydantic 계약을 정의한다.
4. `/api/health`가 `3.0.0`, 실행 모드, 리전, DB 종류를 반환하도록 한다.
5. SQLite 기본 경로, Compose 프로젝트, 쿠키 이름과 포트를 V2와 분리한다.

### 검증

```bash
.venv-v3/bin/python -m pytest v3/tests/test_config.py v3/tests/test_api.py -q
```

수용 기준:

- demo 모드는 빈 AWS 환경에서 시작된다.
- agentcore 모드는 설정 누락을 시작 단계에서 설명한다.
- 응답이나 로그에 자격증명과 DB 비밀번호가 나타나지 않는다.

## 2. 결정형 데모 백엔드와 제조 API

### 생성·수정 파일

- `v3/backends/base.py`
- `v3/backends/demo.py`
- `v3/routes/manufacturing.py`
- `v3/routes/chat.py`
- `v3/tests/test_demo_backend.py`
- `v3/tests/test_manufacturing_routes.py`
- 필요할 경우 `imjingang_agent/`에 하위 호환 추가형 변경

### 작업

1. `AgentBackend` 프로토콜을 정의한다.
2. 기존 V2의 결정형 `demo_answer`를 V3 전용 백엔드로 분리하되 기존 V2 코드는 변경하지 않는다.
3. LOT 형식, 명시 LOT와 선택 LOT 충돌, 존재하지 않는 LOT를 검증한다.
4. V3 UI가 필요한 workspace, LOT, 문서, 테이블 조회 라우트를 추가한다.
5. 모든 응답에 근거, 도구, 조회 시각, `demo_data`를 포함한다.

### 검증

```bash
.venv-v3/bin/python -m pytest v3/tests/test_demo_backend.py v3/tests/test_manufacturing_routes.py -q
```

수용 기준:

- 대표 LOT 질문이 실제 SQLite 기록과 문서 근거를 반환한다.
- 데이터 없음은 오류가 아니라 `미확인`으로 반환된다.
- 임의 테이블명과 과도한 페이지 크기는 거절된다.

## 3. AgentCore 클라이언트와 오류 경계

### 생성 파일

- `v3/aws/agentcore_client.py`
- `v3/aws/signing.py`
- `v3/backends/agentcore.py`
- `v3/tests/test_agentcore_client.py`
- `v3/tests/test_agentcore_backend.py`

### 작업

1. AgentCore 호출을 감싼 작은 클라이언트 인터페이스를 만든다.
2. boto3/botocore의 기본 자격증명 체인과 SigV4를 사용한다.
3. 요청 ID, 세션 ID, 시간 제한과 제한된 재시도를 적용한다.
4. AgentCore 결과를 V3 공통 응답 계약으로 검증한다.
5. 권한 부족, 시간 초과, 5xx, 잘못된 응답을 사용자 안전 오류로 매핑한다.
6. AgentCore 장애 시 demo 모드로 자동 전환하지 않는다.

### 검증

```bash
.venv-v3/bin/python -m pytest v3/tests/test_agentcore_client.py v3/tests/test_agentcore_backend.py -q
```

수용 기준:

- 네트워크 없이 모의 AgentCore 성공·실패 계약을 모두 검증한다.
- 오류 본문에 ARN 전체, 토큰, DB URL과 스택 트레이스가 노출되지 않는다.

## 4. AgentCore Runtime 제조 Agent

### 생성 파일

- `v3/agent/runtime.py`
- `v3/agent/prompts.py`
- `v3/agent/tools.py`
- `v3/agent/response.py`
- `v3/agent/Dockerfile`
- `v3/tests/test_runtime.py`
- `v3/tests/test_tools.py`
- `v3/tests/test_prompts.py`

### 작업

1. AgentCore Runtime의 HTTP 또는 SDK 계약에 맞는 진입점을 구현한다.
2. 모델 ID를 `V3_BEDROCK_MODEL_ID`에서 받고 Bedrock 호출 어댑터를 구성한다.
3. 기존 `ImjingangToolRegistry`에서 승인된 읽기 전용 도구만 V3 스키마로 노출한다.
4. 도구 결과를 비신뢰 데이터로 취급하고 임의 명령을 따르지 않는 시스템 지침을 추가한다.
5. 도구 실행 횟수, 반환 레코드 수와 답변 크기에 상한을 둔다.
6. 모델 출력과 도구 결과를 근거형 공통 응답으로 정규화한다.

### 검증

```bash
.venv-v3/bin/python -m pytest v3/tests/test_runtime.py v3/tests/test_tools.py v3/tests/test_prompts.py -q
```

수용 기준:

- 허용되지 않은 도구와 임의 SQL이 실행되지 않는다.
- 최소 한 대표 질문이 LOT 계보와 출하 준비 도구를 함께 사용한다.
- 답변에 설비 제어 또는 출하 승인을 수행했다는 표현이 생성되지 않는다.

## 5. Gateway, Memory와 Observability 어댑터

### 생성 파일

- `v3/agent/gateway.py`
- `v3/agent/memory.py`
- `v3/observability.py`
- `v3/tests/test_gateway.py`
- `v3/tests/test_memory.py`
- `v3/tests/test_observability.py`

### 작업

1. AgentCore Gateway를 Runtime과 제조 도구의 통제 진입점으로 연결한다.
2. Gateway 요청과 도구 호출에 동일한 상관관계 ID를 전달한다.
3. Memory에 세션 요약, 선택 LOT와 근거 식별자만 저장한다.
4. 앱 세션은 24시간으로 정의한다. AgentCore Memory는 서비스 최소 보존기간 3일이 앱 정책보다 길기 때문에 IaC에서 기본 비활성화하고 별도 운영 승인 후 활성화한다.
5. 질문 전문, 전체 도구 결과와 비밀정보를 제외한 구조화 로그를 만든다.

### 검증

```bash
.venv-v3/bin/python -m pytest v3/tests/test_gateway.py v3/tests/test_memory.py v3/tests/test_observability.py -q
```

수용 기준:

- 세션 초기화 후 이전 LOT 문맥이 다시 사용되지 않는다.
- Memory 저장 페이로드에 API 키, 비밀번호, 전체 레코드가 없다.
- 로그에서 요청, Runtime과 도구 호출을 연결할 수 있다.

## 6. 독립 React V3 UI

### 생성 파일

- `v3/web/package.json`
- `v3/web/package-lock.json`
- `v3/web/tsconfig.json`
- `v3/web/vite.config.ts`
- `v3/web/index.html`
- `v3/web/src/main.tsx`
- `v3/web/src/App.tsx`
- `v3/web/src/api.ts`
- `v3/web/src/types.ts`
- `v3/web/src/components/AgentPanel.tsx`
- `v3/web/src/components/EvidencePanel.tsx`
- `v3/web/src/styles.css`

### 작업

1. V2의 사용자 흐름과 스타일 토큰을 참고하되 V3 소스를 독립 구성한다.
2. 버전, 실행 모드, 모델, 리전과 연결 상태를 표시한다.
3. 직접 질문, 추천질문, LOT 선택과 대화 초기화를 같은 처리 경로로 연결한다.
4. 응답 본문과 근거, 실행 도구, 조회 시각, 샘플 데이터 표시를 분리한다.
5. 이전 요청 취소와 LOT 변경 시 오래된 응답 폐기를 구현한다.
6. 데스크톱과 390px에서 사용할 수 있는 반응형 구성을 적용한다.

### 검증

```bash
npm ci --prefix v3/web
npm run build --prefix v3/web
```

수용 기준:

- TypeScript와 프로덕션 빌드가 통과한다.
- 키보드 조작, 포커스 표시와 오류 안내가 제공된다.
- AWS 설정값이나 자격증명이 브라우저 번들에 포함되지 않는다.

## 7. 컨테이너와 로컬 Compose

### 수정 파일

- `v3/Dockerfile`
- `v3/agent/Dockerfile`
- `v3/docker-compose.yml`
- `v3/.dockerignore`
- `v3/tests/test_container_contract.py`

### 작업

1. UI 빌드 후 비특권 Python 사용자로 실행하는 다단계 이미지를 구성한다.
2. V3 앱, PostgreSQL과 선택적 Runtime 모의 서비스를 독립 Compose에 정의한다.
3. DB는 V3 전용 named volume을 사용하고 외부 포트를 기본 공개하지 않는다.
4. 앱 포트는 기본 `8504:8510`으로 설정한다.
5. 앱과 Runtime 이미지에 헬스 체크를 추가한다.

### 검증

```bash
docker compose --env-file v3/.env -f v3/docker-compose.yml config --quiet
docker build -f v3/Dockerfile -t imjingang-agentcore-v3:local .
```

Docker를 사용할 수 없는 환경에서는 Compose 정적 검증 결과와 미실행 사유를 보고한다.

## 8. AWS IaC

### 생성 파일

- `infra/agentcore-v3/README.md`
- `infra/agentcore-v3/pyproject.toml`
- `infra/agentcore-v3/app.py`
- `infra/agentcore-v3/stacks/agentcore_stack.py`
- `infra/agentcore-v3/tests/test_stack.py`
- `infra/agentcore-v3/cdk.json`

### 작업

1. AWS CDK Python으로 ECR, AgentCore Runtime, Gateway, Memory, 로그와 IAM을 정의한다.
2. 서울 리전을 기본 컨텍스트로 사용하되 실제 지원 여부를 synth/deploy 전 확인한다.
3. 리소스 ARN과 허용 작업을 제한한 IAM 정책을 작성한다.
4. Secrets Manager 참조만 정의하고 비밀값은 생성 코드나 출력에 넣지 않는다.
5. 데이터 및 로그 리소스에 명시적 보존 정책을 적용한다.
6. Runtime ARN, Gateway URL과 리전만 배포 출력으로 제공한다.

### 검증

```bash
cd infra/agentcore-v3
python -m pytest tests -q
cdk synth
cdk diff
```

수용 기준:

- synth 결과에 와일드카드 관리자 권한이 없다.
- 실제 비밀값과 개발자 장기 키가 템플릿에 없다.
- 저장 리소스 삭제 보호와 로그 보존 정책이 명시된다.

## 9. 문서와 저장소 통합

### 생성·수정 파일

- `docs/aws-agentcore-v3.md`
- `README.md`
- `.gitignore` 또는 기존 무시 설정

### 작업

1. 루트 README의 버전 표에 V3를 추가하되 V1/V2 안내를 보존한다.
2. 로컬 demo 모드, AgentCore 모드, 환경변수와 검증 명령을 문서화한다.
3. AWS 생성 비용, 모델 접근, 서울 리전 가용성 확인과 삭제 절차를 안내한다.
4. 실제 AWS 검증과 모의 검증을 구분하는 체크리스트를 추가한다.
5. `.env`, CDK 출력, 빌드 산출물과 로컬 DB가 커밋되지 않게 확인한다.

## 10. 전체 검증과 완료 판정

### 자동 검증

```bash
.venv-v3/bin/python -m pytest v3/tests -q
npm run build --prefix v3/web
.venv-v2/bin/python -m pytest v2/tests tests/test_data_hub.py tests/test_service.py tests/test_ui_helpers.py -q
python -m pytest -q
git diff --check
```

환경에 따라 V1과 V2가 서로 다른 가상환경을 요구하면 각각의 잠금 파일에 맞는 환경에서 실행하고 결과를 분리해 기록한다.

### 수동 검증

- V3 데스크톱과 390px 화면
- demo 모드 질문, 근거, LOT 전환과 초기화
- AgentCore 설정 오류와 장애 화면
- 브라우저 콘솔 오류와 네트워크 실패 처리
- 실제 자격증명이 제공된 경우에만 서울 리전 Runtime, Gateway, Memory와 추적 확인

### 완료 보고

최종 보고에는 다음을 구분한다.

- 구현한 파일과 실행 경로
- 통과한 자동 테스트와 빌드
- 수행한 수동 UI 검증
- 실제 AWS 리소스 생성 여부
- 실제 Bedrock 모델 호출 여부
- 서울 리전에서 확인한 AgentCore 기능
- 배포 전 남은 계정, 권한, 비용 및 데이터 연결 작업

## 커밋 전략

구현은 검토 가능한 단위로 나눈다.

1. `feat: scaffold isolated AgentCore V3 app`
2. `feat: add V3 manufacturing demo backend`
3. `feat: integrate AgentCore runtime client`
4. `feat: add AgentCore manufacturing runtime`
5. `feat: connect AgentCore gateway memory and telemetry`
6. `feat: add independent V3 React cockpit`
7. `build: add V3 containers and AWS infrastructure`
8. `docs: document AWS AgentCore V3 operations`

각 커밋 전에 해당 단계 테스트를 실행하고, 마지막에 전체 회귀 검증을 수행한다.
