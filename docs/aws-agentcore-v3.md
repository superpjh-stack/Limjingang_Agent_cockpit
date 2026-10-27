# 임진강김치 AWS AgentCore V3

V3는 기존 Streamlit V1과 React/FastAPI V2를 보존하면서 Amazon Bedrock AgentCore 실행 경계를 추가한 독립 버전이다. 로컬에서는 AWS 자격증명 없이 결정형 데모를 실행할 수 있고, 운영에서는 AgentCore Runtime 호출로 전환한다.

## 현재 구현

- 독립 React 19·TypeScript·Vite UI와 FastAPI BFF
- AgentCore Runtime 호출용 boto3 어댑터
- AgentCore Runtime 컨테이너 진입점(`/ping`, `/invocations`)
- LOT·CCP·발효·재고·출하·문서용 읽기 전용 도구 허용 목록
- PostgreSQL + pgvector 및 SQLite 데모 저장소 재사용
- 응답 근거, 실행 도구, 조회 시각, 리전과 모델 표시
- 별도 Docker/Compose와 기본 호스트 포트 8504
- AgentCore Runtime, 버전 엔드포인트, Gateway와 선택적 Memory용 AWS CDK

현재 Runtime의 모델 경로는 제한된 근거 조회 결과를 Bedrock Converse에 전달한다. Gateway 리소스는 통제 진입점으로 생성되지만 실제 제조 도구 대상 등록과 조직 인증 정책은 계정별 엔드포인트 및 인증 요구를 확인한 뒤 배포 단계에서 연결해야 한다. 이를 완료하기 전에는 Gateway 기반 MCP 도구 연결이 검증됐다고 간주하지 않는다.

## 로컬 실행

Python 3.12와 Node 22를 권장한다.

```bash
python3.12 -m venv .venv-v3
source .venv-v3/bin/activate
pip install -r v3/requirements.txt
npm ci --prefix v3/web
npm run build --prefix v3/web
V3_AGENT_BACKEND=demo uvicorn v3.api:app --host 127.0.0.1 --port 8511
```

접속 주소는 `http://127.0.0.1:8511`이다. 화면 개발은 API 서버와 함께 `npm run dev --prefix v3/web`을 실행한다.

demo 모드는 실제 LLM이나 AgentCore 호출이 아니다. 응답에는 `demo_data: true`와 `로컬 데모`가 표시된다.

## AgentCore 모드

다음 환경변수가 필요하다.

```bash
V3_AGENT_BACKEND=agentcore
AWS_REGION=ap-northeast-2
V3_BEDROCK_MODEL_ID=<서울 리전에서 호출 가능한 모델 또는 추론 프로필 ID>
V3_AGENTCORE_RUNTIME_ARN=<배포 출력 RuntimeArn>
V3_AGENTCORE_QUALIFIER=ImjingangV3Live
V3_AGENTCORE_GATEWAY_URL=<배포 출력 GatewayUrl>
DATABASE_URL=<V3 전용 PostgreSQL URL>
```

AWS 자격증명은 boto3의 기본 자격증명 체인을 사용한다. 액세스 키를 이미지, 저장소 또는 브라우저 환경변수에 넣지 않는다. AgentCore 설정이 없거나 권한이 부족할 때 demo 모드로 자동 폴백하지 않는다.

## 테스트

```bash
.venv-v3/bin/python -m pytest v3/tests -q
npm run build --prefix v3/web
.venv-v2/bin/python -m pytest v2/tests tests/test_data_hub.py tests/test_service.py tests/test_ui_helpers.py -q
python -m pytest -q
```

## Docker

```bash
cp v3/.env.example v3/.env
# v3/.env에 POSTGRES_PASSWORD를 추가한다.
docker compose --env-file v3/.env -f v3/docker-compose.yml config --quiet
docker compose --env-file v3/.env -f v3/docker-compose.yml up -d --build
```

기본 접속 포트는 8504다. V3 Compose는 `imjingang-v3` 프로젝트와 별도 PostgreSQL volume을 사용한다.

## AWS CDK

AWS 리소스 생성은 비용과 외부 상태 변경을 발생시키므로 `cdk deploy` 전 계획을 검토한다.

```bash
python3.12 -m venv .venv-agentcore-infra
source .venv-agentcore-infra/bin/activate
pip install -r infra/agentcore-v3/requirements.txt
cd infra/agentcore-v3
CDK_DEFAULT_REGION=ap-northeast-2 cdk synth -c account=<AWS_ACCOUNT_ID>
cdk diff --parameters BedrockModelId=<MODEL_ID> --parameters RuntimeImageTag=v3 --parameters EnableAgentCoreRuntime=false
```

첫 배포는 `EnableAgentCoreRuntime=false`로 ECR과 Gateway를 만든다. ARM64 Runtime 이미지를 해당 ECR 저장소에 올린 다음 `EnableAgentCoreRuntime=true`로 스택을 업데이트한다. `EnableAgentCoreMemory`의 기본값은 `false`다. AgentCore Memory의 공식 최소 이벤트 보존기간이 3일이므로, 앱의 24시간 세션 정책과 동일하지 않다. 데이터 보존 승인을 받은 경우에만 `true`로 배포한다.

서울 리전에서 선택한 AgentCore 기능과 모델이 실제 계정에 제공되는지 `cdk diff`와 AWS 콘솔에서 확인한다. 지원되지 않는 경우 다른 리전으로 자동 전환하지 않는다.

## 안전 경계

- 제조 도구는 읽기 전용이다.
- 임의 SQL, 셸, 파일 쓰기, 설비 제어와 출하 승인 도구는 없다.
- 샘플 데이터는 2026년 9월 가상 데모이며 승인 기준이 아니다.
- AgentCore/Bedrock 장애를 정상 데모 답변으로 숨기지 않는다.
- 브라우저에는 AWS 자격증명과 데이터베이스 비밀번호를 전달하지 않는다.

## 실제 AWS 검증 전 남은 항목

- AWS 계정에서 AgentCore 및 선택 Bedrock 모델 접근 확인
- Runtime 이미지 ECR push
- Gateway의 Runtime/도구 대상과 조직 인증 정책 연결
- V3 전용 PostgreSQL 또는 VPC 데이터 경로 연결
- 실제 Runtime, Gateway, 선택적 Memory와 Observability 추적 검증
- 비용·로그·데이터 보존 정책 운영 승인

이 항목을 수행하지 않은 로컬 결과는 AWS 배포 완료로 표현하지 않는다.

## 2026-10-26 배포 검증

- CloudFormation 스택 `imjingang-agentcore-v3`: `UPDATE_COMPLETE`
- 리전: `ap-northeast-2`
- Runtime 엔드포인트: `ImjingangV3Live`
- 모델: `global.amazon.nova-2-lite-v1:0`
- ECR 이미지: `v3`, ARM64, digest `sha256:b3f9cc11693183848d71033d542d4311df0c2e2d7a76f287405c026e75b0c62b`
- 실제 `InvokeAgentRuntime`: HTTP 200
- 검증 질문: `PACK-260903-001` 계보·출하 확인
- 사용 도구: `get_lot_trace`, `get_shipment_readiness`
- AgentCore Memory: 데이터 보존 승인 전이므로 비활성화
- Gateway: AWS IAM 인증으로 생성됐지만 제조 도구 대상 등록은 아직 하지 않음

## 2026-10-27 ECS 웹 배포 검증

- CloudFormation 스택 `imjingang-ecs-web-v3`: `CREATE_COMPLETE`
- 공개 URL: `http://imjing-WebSe-ee3yHxBjsjKN-1271617388.ap-northeast-2.elb.amazonaws.com`
- 구성: 공개 ALB → private subnet의 ECS Fargate 태스크 1개
- 웹 ECR 이미지: `v3-web`, AMD64, digest `sha256:deaf054bd54fd77aa451f1ca00b965cb8f2d48764a3584ba3322c5c4f1c04587`
- ECS 상태: desired 1, running 1, rollout `COMPLETED`
- `/`, `/api/health`: HTTP 200
- 실제 `/api/chat`: HTTP 200, AgentCore 모드, 모델 `global.amazon.nova-2-lite-v1:0`
- 검증 질문: `PACK-260903-001` 출하 가능 여부와 확인사항
- 사용 도구: `get_lot_trace`, `get_shipment_readiness`
- 현재 URL은 테스트용 HTTP 공개 엔드포인트다. 실제 운영 전 HTTPS, 접근 인증, WAF, 영속 PostgreSQL을 추가한다.
