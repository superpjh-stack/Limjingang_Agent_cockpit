# 임진강김치 V3 App Runner 웹 배포 설계

> 상태: 2026-10-27 폐기. AWS App Runner는 서울 리전을 지원하지 않아 [ECS Fargate 설계](2026-10-27-ecs-fargate-v3-web-design.md)로 대체한다.

## 1. 목적

배포된 Amazon Bedrock AgentCore V3 Runtime을 실제 브라우저에서 테스트할 수 있도록 React·FastAPI V3 애플리케이션을 AWS App Runner에 독립 배포한다. 기존 V1, V2와 AgentCore Runtime 배포는 유지한다.

성공 기준:

- App Runner가 관리하는 공개 HTTPS URL에서 V3 화면이 열린다.
- `/api/health`가 `3.0.0`, `agentcore`, `ap-northeast-2`를 반환한다.
- 브라우저 질문이 FastAPI를 거쳐 배포된 `ImjingangV3Live` Runtime을 호출한다.
- AWS 자격증명과 Runtime ARN 전체가 브라우저 번들 또는 API 응답에 노출되지 않는다.
- V1/V2의 이미지, 포트, URL과 트래픽을 변경하지 않는다.

## 2. 배포 구조

```text
Browser
  |
  | HTTPS
  v
AWS App Runner
  |-- React V3 정적 파일
  |-- FastAPI V3 BFF
  |-- SQLite 샘플 DB (컨테이너 로컬, 비영속)
  |
  | IAM Instance Role
  v
AgentCore Runtime / ImjingangV3Live
  |
  v
Amazon Bedrock / global.amazon.nova-2-lite-v1:0
```

App Runner는 V3 전용 ECR 이미지에서 실행한다. AgentCore Runtime용 ARM64 이미지는 재사용하지 않고 웹 앱용 이미지를 별도 ECR 저장소에 `linux/amd64`로 게시한다.

## 3. App Runner 구성

- 서비스명: `imjingang-agentcore-v3-web`
- 리전: `ap-northeast-2`
- 포트: `8510`
- 헬스 체크: `HTTP /api/health`
- CPU/메모리: App Runner가 지원하는 최소 실용 구성
- 자동 배포: 비활성화
- ECR 이미지 태그: `v3-web`
- 공개 인바운드: App Runner 기본 HTTPS URL
- 아웃바운드: 공개 AgentCore AWS API 호출

환경변수:

- `V3_AGENT_BACKEND=agentcore`
- `AWS_REGION=ap-northeast-2`
- `V3_BEDROCK_MODEL_ID=global.amazon.nova-2-lite-v1:0`
- `V3_AGENTCORE_RUNTIME_ARN`: 기존 CloudFormation 출력
- `V3_AGENTCORE_QUALIFIER=ImjingangV3Live`
- `V3_AGENTCORE_GATEWAY_URL`: 기존 CloudFormation 출력
- `V3_REQUEST_TIMEOUT=120`
- `V3_SECURE_COOKIE=1`
- `V3_SQLITE_PATH=/tmp/imjingang_v3_demo.db`

비밀값은 이미지나 소스에 넣지 않는다. 이번 공개 테스트 배포에는 외부 DB 비밀번호나 장기 AWS 액세스 키가 필요하지 않다.

## 4. IAM

두 역할을 분리한다.

### ECR Access Role

App Runner 서비스가 웹 이미지를 pull할 수 있는 역할이다. App Runner build 서비스 주체만 신뢰하고 해당 ECR 저장소의 pull 작업만 허용한다.

### Instance Role

실행 중인 FastAPI가 AgentCore Runtime을 호출하는 역할이다. 다음으로 제한한다.

- 작업: `bedrock-agentcore:InvokeAgentRuntime`
- 리소스: 배포된 `ImjingangManufacturingV3` Runtime ARN

Bedrock 직접 호출 권한은 App Runner에 주지 않는다. Bedrock 호출은 기존 AgentCore Runtime 역할에서 수행한다.

## 5. 데이터와 보안 경계

- 공개 URL에는 2026년 9월 가상 샘플 데이터만 제공한다.
- SQLite는 컨테이너 시작 시 `/tmp`에 초기화되며 운영 지속성을 보장하지 않는다.
- 실제 ERP·IoT·PostgreSQL 운영 데이터는 이번 배포에 연결하지 않는다.
- 설비 제어, 발주, CCP 처분, 출하 승인 기능은 없다.
- App Runner URL을 아는 사용자는 샘플 AI 질문을 호출할 수 있으므로 테스트 완료 후 서비스를 중지하거나 인증 계층을 추가한다.
- 질문은 비용이 발생하는 AgentCore/Bedrock 호출이므로 공개 운영 전 사용량 제한과 인증이 필요하다.
- 쿠키는 `Secure`, `HttpOnly`, `SameSite=Lax`로 설정한다.
- 오류 응답에 ARN, 토큰, 내부 스택 트레이스를 노출하지 않는다.

## 6. IaC 변경

기존 `infra/agentcore-v3/` 스택에 다음을 추가한다.

- 웹 앱 ECR 저장소
- App Runner ECR Access Role
- App Runner Instance Role
- App Runner 서비스
- 공개 Service URL 출력

AgentCore Runtime처럼 웹 서비스도 2단계로 배포한다.

1. `EnableAppRunner=false`로 웹 ECR과 역할을 생성한다.
2. `linux/amd64` 웹 이미지를 `v3-web` 태그로 push한다.
3. `EnableAppRunner=true`로 App Runner 서비스를 생성한다.

웹 ECR 저장소는 삭제 시 보존한다. App Runner 자동 배포는 끄고 CloudFormation 업데이트로만 이미지 버전을 변경한다.

## 7. 오류 처리

- App Runner 시작 실패: 서비스 이벤트와 로그를 확인하고 기존 AgentCore Runtime은 유지한다.
- AgentCore 권한 오류: 사용자에게 연결 설정 오류를 표시하고 demo 모드로 자동 전환하지 않는다.
- AgentCore 콜드 스타트: 최대 120초까지 기다린 뒤 명확한 시간 초과를 표시한다.
- SQLite 초기화 실패: 헬스 체크를 실패시켜 잘못된 서비스를 트래픽에 노출하지 않는다.
- 배포 실패: App Runner 리소스만 롤백하고 AgentCore Runtime과 Gateway는 유지한다.

## 8. 검증

### 자동 검증

- V3 Python 테스트
- React 프로덕션 빌드
- CDK 테스트 및 synth
- Docker `linux/amd64` 이미지 빌드
- 이미지에 AWS 자격증명이나 `.env`가 포함되지 않았는지 확인

### 배포 검증

- CloudFormation `UPDATE_COMPLETE`
- App Runner 서비스 `RUNNING`
- 공개 URL `/api/health` HTTP 200
- 공개 URL `/`에서 V3 HTML 로드
- `PACK-260903-001` 질문 HTTP 200
- 응답 `mode=agentcore`
- 응답 도구에 `get_lot_trace`, `get_shipment_readiness` 포함
- 모바일 390px 및 데스크톱 화면 확인

## 9. 범위 밖

- 사용자 로그인, Cognito, WAF, 조직 SSO
- 커스텀 도메인과 Route 53
- PostgreSQL/RDS 운영 데이터 연결
- App Runner VPC Connector
- 오토스케일 세부 튜닝
- 장기 공개 운영과 SLA

위 기능은 테스트 URL 검증 이후 별도 승인으로 진행한다.
