# V3 App Runner 웹 배포 구현 계획

## 목표

승인된 [App Runner 설계](../specs/2026-10-26-apprunner-v3-web-design.md)에 따라 V3 React·FastAPI 앱을 서울 리전 App Runner에 배포하고 공개 HTTPS URL에서 AgentCore Runtime 호출을 검증한다.

## 1. 웹 컨테이너 계약 보강

수정 대상:

- `v3/Dockerfile`
- `v3/config.py`
- `v3/tests/test_config.py`

작업:

1. App Runner용 `linux/amd64` 이미지가 포트 8510에서 실행되는지 확인한다.
2. SQLite 경로를 `/tmp/imjingang_v3_demo.db`로 설정 가능하게 유지한다.
3. Secure cookie, Runtime ARN, qualifier와 120초 timeout 설정을 검증한다.
4. 이미지에 `.env`, 로컬 DB, 빌드 캐시가 들어가지 않는지 확인한다.

검증:

```bash
.venv-v2/bin/python -m pytest v3/tests -q
npm run build --prefix v3/web
docker buildx build --platform linux/amd64 -f v3/Dockerfile --load -t imjingang-agentcore-v3-web:test .
```

## 2. App Runner IaC 추가

수정 대상:

- `infra/agentcore-v3/stacks/agentcore_stack.py`
- `infra/agentcore-v3/tests/test_stack.py`

추가 리소스:

- 웹 ECR 저장소
- App Runner ECR Access Role
- App Runner Instance Role
- `AWS::AppRunner::Service`
- `AppRunnerServiceUrl` 출력

파라미터:

- `EnableAppRunner`: 기본 `false`
- `WebImageTag`: 기본 `v3-web`
- `AgentRuntimeArn`: 기존 Runtime ARN
- `AgentRuntimeQualifier`: 기본 `ImjingangV3Live`
- `AgentCoreGatewayUrl`: 기존 Gateway URL

IAM 검증:

- ECR Access Role은 웹 ECR pull만 허용한다.
- Instance Role은 지정 AgentCore Runtime의 `bedrock-agentcore:InvokeAgentRuntime`만 허용한다.
- App Runner에는 Bedrock 직접 호출 권한을 주지 않는다.

## 3. 1단계 스택 업데이트

1. CDK 테스트와 synth를 실행한다.
2. `EnableAppRunner=false`로 CloudFormation 스택을 업데이트한다.
3. 웹 ECR URI 출력을 조회한다.
4. 기존 Runtime, Gateway와 엔드포인트가 유지되는지 확인한다.

실패 시 CloudFormation 이벤트를 확인하고 새 웹 리소스만 롤백한다.

## 4. 웹 이미지 빌드와 업로드

1. 서울 리전 ECR에 Docker 인증한다.
2. `linux/amd64` 웹 이미지를 빌드한다.
3. `v3-web` 태그로 웹 ECR에 push한다.
4. ECR digest와 push 시각을 기록한다.

Runtime ARM64 이미지 저장소와 웹 AMD64 저장소를 혼합하지 않는다.

## 5. App Runner 활성화

1. `EnableAppRunner=true`로 스택을 업데이트한다.
2. App Runner 서비스가 `RUNNING`이 될 때까지 기다린다.
3. CloudFormation 출력에서 공개 URL을 조회한다.
4. App Runner 이벤트와 배포 상태를 확인한다.

환경변수는 승인 명세와 일치시킨다. 실제 비밀값이나 액세스 키는 전달하지 않는다.

## 6. 종단 간 검증

공개 URL에서 다음을 확인한다.

```text
GET /api/health
GET /
POST /api/chat
```

대표 질문:

```text
PACK-260903-001의 공정 계보와 출하 확인사항을 알려줘
```

수용 기준:

- `/api/health` HTTP 200, `version=3.0.0`, `backend=agentcore`
- `/` HTTP 200, V3 HTML 반환
- 질문 HTTP 200, `mode=agentcore`
- `get_lot_trace`, `get_shipment_readiness` 포함
- 모델 `global.amazon.nova-2-lite-v1:0`
- 오류에 자격증명, ARN 전체와 스택 트레이스가 없음

## 7. UI 확인

- 데스크톱 화면
- 390px 모바일 화면
- 추천 질문 실행
- LOT 선택 후 질문
- 근거 펼치기
- 새 대화
- 연결 오류 표시

브라우저 자동화가 제공되지 않으면 HTTP/HTML 검증 결과와 미실행 시각 검증을 구분해 보고한다.

## 8. 문서와 커밋

수정 대상:

- `docs/aws-agentcore-v3.md`
- 필요하면 `README.md`

기록 항목:

- App Runner 서비스명과 공개 URL
- 이미지 digest
- 배포 시각과 검증 결과
- 공개 테스트 비용·보안 주의
- 중지 및 삭제 방법

커밋:

1. `feat: add App Runner deployment for V3 web`
2. `deploy: publish V3 web on App Runner`

## 9. 롤백

- 새 이미지 실패: App Runner를 직전 이미지 digest로 되돌린다.
- 서비스 생성 실패: `EnableAppRunner=false`로 업데이트한다.
- AgentCore 호출 실패: App Runner Instance Role과 환경변수를 수정한다.
- 비용 또는 공개 노출 중단: App Runner 서비스를 삭제하거나 CloudFormation 조건을 끈다.

롤백 과정에서 기존 AgentCore Runtime, Gateway, ECR Runtime 이미지와 V1/V2를 삭제하지 않는다.
