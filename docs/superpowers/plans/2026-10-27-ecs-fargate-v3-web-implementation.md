# V3 ECS Fargate 웹 배포 구현 계획

## 목표

승인된 [ECS Fargate 설계](../specs/2026-10-27-ecs-fargate-v3-web-design.md)에 따라 V3 React·FastAPI 앱을 서울 리전 ECS Fargate에 배포하고 ALB 공개 URL에서 AgentCore 질의를 검증한다.

## 1. 웹 컨테이너 확인

- `v3/Dockerfile`을 `linux/amd64`로 빌드한다.
- 포트 8510과 `/api/health`를 검증한다.
- `/tmp/imjingang_v3_demo.db`로 SQLite 초기화를 확인한다.
- `.env`, AWS 자격증명, 로컬 DB가 이미지에 없는지 확인한다.

검증:

```bash
.venv-v2/bin/python -m pytest v3/tests -q
npm run build --prefix v3/web
docker buildx build --platform linux/amd64 -f v3/Dockerfile --load -t imjingang-agentcore-v3-web:test .
```

## 2. CDK 리소스 추가

수정:

- `infra/agentcore-v3/stacks/agentcore_stack.py`
- `infra/agentcore-v3/tests/test_stack.py`

추가:

- 웹 ECR 저장소
- V3 전용 VPC, public/private subnet, NAT Gateway 1개
- ALB와 listener
- ECS Cluster
- Fargate Task Definition과 Service
- Task Execution Role, Task Role
- CloudWatch log group 14일 보존
- `EnableEcsWeb`, `WebImageTag`, Runtime ARN·qualifier·Gateway URL 파라미터
- `EcsWebUrl`, `WebRepositoryUri` 출력

테스트는 조건부 생성, IAM 최소권한, 비공개 Task, health path, 환경변수와 포트를 확인한다.

## 3. 1단계 CloudFormation 업데이트

- `EnableEcsWeb=false`로 synth와 deploy를 실행한다.
- 웹 ECR만 먼저 생성한다.
- 기존 AgentCore Runtime, Gateway와 endpoint 출력이 유지되는지 확인한다.
- CloudFormation 상태가 `UPDATE_COMPLETE`인지 확인한다.

## 4. AMD64 웹 이미지 게시

- 서울 리전 ECR 로그인
- `linux/amd64` 이미지 빌드
- `v3-web` 태그 push
- digest, 크기와 push 시각 기록

## 5. ECS 활성화

- `EnableEcsWeb=true`로 스택 업데이트
- Fargate Service steady state 대기
- ALB target health 확인
- Task count `desired=1`, `running=1` 확인
- 실패 시 서비스 이벤트, stopped task reason, CloudWatch 로그 확인

## 6. 공개 URL 종단 간 테스트

- `GET /api/health` → HTTP 200, V3·AgentCore·서울 리전
- `GET /` → HTTP 200, V3 HTML
- `POST /api/chat` → 대표 PACK LOT 질문
- 응답 `mode=agentcore`
- `get_lot_trace`, `get_shipment_readiness`
- 모델 `global.amazon.nova-2-lite-v1:0`

## 7. UI와 보안 확인

- 데스크톱·390px 레이아웃
- 추천 질문·LOT 선택·근거 펼치기·새 대화
- 쿠키 및 오류 메시지
- 번들에 ARN·자격증명 비노출
- 샘플 데이터와 자동 승인 금지 표시

브라우저 자동화가 없으면 HTTP/HTML 검증과 미실행 시각 검증을 구분한다.

## 8. 문서와 커밋

- `docs/aws-agentcore-v3.md`에 ECS URL·이미지 digest·배포 결과 추가
- App Runner 계획은 폐기 상태로 표시
- 구현 커밋과 배포 검증 커밋 분리

## 9. 롤백

- 배포 실패: ECS circuit breaker 자동 롤백
- 웹 중지: desired count 0 또는 `EnableEcsWeb=false`
- 이미지 문제: 직전 digest task definition으로 복구
- AgentCore Runtime·Gateway·V1/V2는 유지

## 완료 조건

- 자동 테스트와 CDK synth 통과
- CloudFormation `UPDATE_COMPLETE`
- Fargate task 1개 정상
- ALB target healthy
- 공개 URL에서 HTML과 실제 AgentCore 질문 성공
- 실행 URL과 비용·보안 주의사항 전달
