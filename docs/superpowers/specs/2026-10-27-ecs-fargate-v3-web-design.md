# 임진강김치 V3 ECS Fargate 웹 배포 설계

## 1. 배경과 목적

AWS App Runner는 현재 서울 리전(`ap-northeast-2`)을 지원하지 않는다. 서울 리전에 이미 배포된 AgentCore Runtime과 같은 리전에서 V3 React·FastAPI 웹 앱을 공개 테스트하기 위해 ECS Fargate와 Application Load Balancer(ALB)를 사용한다.

성공 기준:

- 공개 ALB URL에서 V3 React 화면이 열린다.
- `/api/health`가 `3.0.0`, `agentcore`, `ap-northeast-2`를 반환한다.
- FastAPI가 ECS Task Role로 `ImjingangV3Live` AgentCore Runtime을 호출한다.
- 대표 LOT 질문이 `mode=agentcore`와 근거 도구를 반환한다.
- V1/V2와 기존 AgentCore Runtime·Gateway·ECR을 보존한다.

## 2. 아키텍처

```text
Internet
   |
   v
Application Load Balancer :80
   |
   v
ECS Fargate Service (private subnet, port 8510)
   |-- React V3 static files
   |-- FastAPI V3 BFF
   |-- /tmp SQLite sample DB
   |
   | ECS Task Role
   v
AgentCore Runtime / ImjingangV3Live
   |
   v
Bedrock / global.amazon.nova-2-lite-v1:0
```

초기 테스트 URL은 ALB HTTP 주소를 사용한다. 실제 운영 전에는 ACM 인증서와 HTTPS listener, Route 53 또는 별도 인증 프록시를 추가해야 한다.

## 3. 네트워크

V3 전용 VPC를 생성한다.

- 가용영역: 2개
- Public subnet: ALB 배치
- Private subnet: Fargate Task 배치
- NAT Gateway: 비용을 줄이기 위해 1개
- ALB Security Group: 인터넷에서 TCP 80 허용
- Task Security Group: ALB Security Group에서 TCP 8510만 허용
- Task outbound: AgentCore API, ECR, CloudWatch와 패키지 실행에 필요한 HTTPS

ECS Task에는 공인 IP를 할당하지 않는다. NAT Gateway를 통해 AgentCore 공개 엔드포인트를 호출한다.

## 4. 컨테이너와 ECR

- 웹 ECR 저장소를 기존 AgentCore CloudFormation 스택에 추가한다.
- 이미지 태그: `v3-web`
- 플랫폼: `linux/amd64`
- 소스: `v3/Dockerfile`
- 포트: 8510
- 실행 사용자: 비특권 `agentv3`
- 헬스 체크: `/api/health`
- SQLite 경로: `/tmp/imjingang_v3_demo.db`

웹 이미지와 AgentCore Runtime ARM64 이미지는 저장소와 태그를 분리한다. `.env`, 로컬 DB, AWS 자격증명과 빌드 캐시는 이미지에 포함하지 않는다.

## 5. ECS 리소스

- ECS Cluster: `imjingang-agentcore-v3`
- Fargate Task Definition: 0.25 vCPU, 0.5GB 메모리
- Desired count: 1
- Deployment minimum healthy percent: 100
- Deployment maximum percent: 200
- Circuit breaker와 자동 롤백 활성화
- CloudWatch Logs: 14일 보존
- ALB health check: `/api/health`, 정상 코드 200

컨테이너 환경변수:

- `V3_AGENT_BACKEND=agentcore`
- `AWS_REGION=ap-northeast-2`
- `V3_BEDROCK_MODEL_ID=global.amazon.nova-2-lite-v1:0`
- `V3_AGENTCORE_RUNTIME_ARN`: 기존 Runtime ARN
- `V3_AGENTCORE_QUALIFIER=ImjingangV3Live`
- `V3_AGENTCORE_GATEWAY_URL`: 기존 Gateway URL
- `V3_REQUEST_TIMEOUT=120`
- `V3_SECURE_COOKIE=0` — 초기 HTTP ALB 테스트에 한정
- `V3_SQLITE_PATH=/tmp/imjingang_v3_demo.db`

HTTPS 적용 후 `V3_SECURE_COOKIE=1`로 변경한다.

## 6. IAM

### Task Execution Role

- 해당 웹 ECR 이미지 pull
- 해당 CloudWatch log group에 로그 기록

### Task Role

- `bedrock-agentcore:InvokeAgentRuntime`
- 리소스는 배포된 `ImjingangManufacturingV3` Runtime ARN으로 제한

Task Role에는 Bedrock 직접 호출, ECR 쓰기, IAM, S3, 데이터베이스 권한을 부여하지 않는다.

## 7. 공개 테스트 안전 경계

- 2026년 9월 가상 샘플 데이터만 제공한다.
- 운영 PostgreSQL, ERP, IoT와 고객 개인정보는 연결하지 않는다.
- 설비 제어, CCP 처분, 발주, 출하 승인 기능은 없다.
- URL을 아는 사용자는 AI 호출 비용을 발생시킬 수 있다.
- 테스트 완료 후 ECS desired count를 0으로 내리거나 인증·WAF·HTTPS를 추가한다.
- ALB HTTP URL은 자격증명이나 민감정보 입력에 사용하지 않는다.

## 8. IaC와 배포 순서

기존 `infra/agentcore-v3/` CDK 스택에 ECS 리소스를 추가한다.

파라미터:

- `EnableEcsWeb`: 기본 `false`
- `WebImageTag`: 기본 `v3-web`
- `ExistingAgentRuntimeArn`
- `AgentRuntimeQualifier`
- `ExistingAgentCoreGatewayUrl`

배포 순서:

1. `EnableEcsWeb=false`로 웹 ECR 생성
2. AMD64 웹 이미지 빌드 및 ECR push
3. `EnableEcsWeb=true`로 VPC·ALB·ECS 생성
4. ECS Service가 steady state가 될 때까지 대기
5. ALB URL에서 헬스·HTML·질문 검증

## 9. 오류와 롤백

- 이미지 pull 실패: Task Execution Role과 ECR digest 확인
- health check 실패: Task 로그와 `/api/health` 확인
- AgentCore 403: Task Role의 Runtime ARN과 작업 확인
- AgentCore timeout: qualifier, Runtime 상태와 120초 timeout 확인
- 배포 실패: circuit breaker 자동 롤백 후 직전 task definition 유지
- 전체 웹 중지: `EnableEcsWeb=false` 또는 desired count 0

롤백 시 기존 AgentCore Runtime, Gateway, Memory 설정과 V1/V2를 변경하지 않는다.

## 10. 검증

자동 검증:

- V3 테스트 15개 이상
- React 프로덕션 빌드
- CDK 테스트와 synth
- `linux/amd64` 이미지 빌드
- CloudFormation `UPDATE_COMPLETE`

종단 간 검증:

- ECS Service `ACTIVE`, desired/running count 1
- ALB target `healthy`
- `GET /api/health` HTTP 200
- `GET /` HTTP 200 및 V3 HTML
- `POST /api/chat` HTTP 200
- 응답 `mode=agentcore`
- 도구 `get_lot_trace`, `get_shipment_readiness`
- 데스크톱과 390px 화면

## 11. 범위 밖

- HTTPS·ACM·커스텀 도메인
- Cognito·조직 SSO·WAF
- RDS/PostgreSQL 운영 데이터
- 멀티 AZ NAT Gateway
- 오토스케일 최적화와 장기 SLA

이 항목은 공개 테스트 이후 별도 승인 대상으로 둔다.
