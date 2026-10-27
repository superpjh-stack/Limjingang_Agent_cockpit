# 임진강김치 V3 AgentCore 실시간 한국어 음성 구현 계획

## 목표

승인된 [실시간 한국어 음성 설계](../specs/2026-10-28-agentcore-realtime-korean-voice-design.md)에 따라 V3에 AgentCore WebSocket 기반 양방향 음성 질의·답변을 추가한다. 기존 텍스트 AgentCore, V1/V2, 제조 안전 경계는 유지한다.

## 구현 원칙

- 실패하는 테스트와 계약 검증을 먼저 추가하고 최소 구현으로 통과시킨다.
- 실제 SDK 이름과 AgentCore WebSocket CDK 속성은 구현 시점의 AWS 공식 문서와 설치된 SDK 모델로 확인한다.
- 브라우저에 AWS 자격증명, Runtime 실행 역할, 음성 서비스 권한을 전달하지 않는다.
- 원본 입력·출력 오디오와 서명된 WebSocket URL을 저장하거나 로그에 남기지 않는다.
- 음성 오류 시 텍스트 채팅으로 자동 위장하지 않고 음성 오류를 명시한다.
- 실제 AWS 리소스 생성·업데이트는 로컬 테스트와 CDK synth 통과 후 수행한다.
- 각 AWS 배포 단계에서 기존 Text Runtime과 ECS 서비스 상태를 확인한다.

## 1. SDK와 AWS 계정 사전 검증

확인:

- 설치할 AgentCore Runtime SDK의 WebSocket server 계약
- Python Transcribe Streaming SDK의 `ko-KR`, PCM 16kHz 계약
- boto3 Polly `Seoyeon` generative engine과 PCM 응답 계약
- AgentCore control plane의 WebSocket Runtime·Endpoint 속성
- `InvokeAgentRuntimeWithWebSocketStream` 서명 URL 형식과 IAM 리소스 계층
- 서울 리전 서비스 quota와 모델·음성 접근

AWS 읽기 전용 검증:

- 기존 Text Runtime·Endpoint가 `READY`
- `Seoyeon` generative voice 호출 가능
- Transcribe Streaming 서울 리전 사용 가능
- CloudFront 배포 가능

검증 결과는 계획과 다른 API 제약이 발견될 때만 설계 명세에 반영하고 재승인을 받는다.

## 2. 음성 이벤트 계약

추가:

- `v3/voice/__init__.py`
- `v3/voice/contracts.py`
- `v3/tests/test_voice_contracts.py`

작업:

1. client/server 이벤트를 discriminated union Pydantic 모델로 정의한다.
2. `session_id`, `utterance_id`, `response_id`, sequence와 상태 enum을 정의한다.
3. base64 PCM 청크 크기, 이벤트 크기, 문자열 길이와 허용 type을 제한한다.
4. 알 수 없는 필드와 이벤트를 거부한다.
5. 사용자용 오류 코드와 내부 예외의 매핑 테이블을 정의한다.

수용 기준:

- 승인된 JSON 예제가 모두 파싱된다.
- 과대 청크, 역순 sequence, 중복 final, 알 수 없는 type을 거절한다.
- 오류 응답에 ARN, 토큰, 서명 파라미터와 stack trace가 없다.

## 3. Voice Runtime 상태 머신

추가:

- `v3/voice/session.py`
- `v3/voice/runtime.py`
- `v3/tests/test_voice_session.py`
- `v3/tests/test_voice_runtime.py`

작업:

1. WebSocket `/ws` 진입점과 session start/end 수명을 구현한다.
2. `connecting → listening → transcribing → retrieving → speaking` 상태 전이를 구현한다.
3. 세션 15분, 무음 60초, 최대 오디오 바이트와 메시지 빈도 제한을 적용한다.
4. 발화 ID별 final 중복 제거와 한 번에 하나의 Agent 질의를 보장한다.
5. `response.cancel`에서 현재 Agent/TTS 작업을 취소하고 늦은 청크를 폐기한다.
6. disconnect에서 Transcribe, Agent, Polly task를 모두 정리한다.

수용 기준:

- mock WebSocket에서 양방향 이벤트 순서가 계약과 일치한다.
- 취소·timeout·disconnect 뒤 background task가 남지 않는다.
- 부분 전사만으로 Text Runtime을 호출하지 않는다.

## 4. Amazon Transcribe Streaming 어댑터

추가:

- `v3/voice/transcribe.py`
- `v3/tests/test_voice_transcribe.py`

작업:

1. region `ap-northeast-2`, language `ko-KR`, PCM 16kHz mono로 스트림을 시작한다.
2. 브라우저 PCM 청크를 입력 스트림으로 전달한다.
3. partial과 final 결과를 내부 이벤트로 정규화한다.
4. 빈 결과, 중복 final과 out-of-order sequence를 처리한다.
5. 연결, quota, timeout, service 오류를 제한된 공개 오류 코드로 변환한다.

수용 기준:

- mock SDK에서 partial/final 이벤트가 순서대로 나온다.
- 질문 전문과 PCM 데이터가 로그에 기록되지 않는다.
- 서비스 오류 뒤 스트림과 task가 정리된다.

## 5. 기존 Text Runtime 연결

추가·수정:

- `v3/voice/agent.py`
- `v3/contracts.py`
- `v3/tests/test_voice_agent.py`

작업:

1. final 전사와 선택 LOT를 기존 `AgentRequest`로 변환한다.
2. Voice Runtime 실행 역할로 기존 `ImjingangV3Live`를 호출한다.
3. `contentType`과 `accept`를 `application/json`으로 고정한다.
4. 기존 `AgentResponse`를 검증하고 voice answer 이벤트로 변환한다.
5. LOT 충돌, 404, Runtime timeout과 권한 오류를 음성 계약 오류로 매핑한다.
6. 새 발화가 확정되면 이전 결과의 전송을 중단한다.

수용 기준:

- 대표 PACK 질문이 기존 응답 계약과 출처·도구를 유지한다.
- 음성 계층에 제조 데이터 쓰기나 새로운 도구가 추가되지 않는다.
- Text Runtime 장애를 정상 음성으로 대체하지 않는다.

## 6. Amazon Polly 스트리밍 어댑터

추가:

- `v3/voice/polly.py`
- `v3/tests/test_voice_polly.py`

작업:

1. `Seoyeon`, `ko-KR`, generative engine, raw PCM 출력으로 호출한다.
2. 긴 답변은 문장 경계의 제한된 크기로 나눠 순차 합성한다.
3. PCM을 sequence가 있는 `audio.chunk` 이벤트로 내보낸다.
4. 취소 시 응답 stream을 닫고 추가 청크를 전송하지 않는다.
5. Polly 실패 시 텍스트 답변을 유지하고 `TTS_UNAVAILABLE`을 전송한다.

수용 기준:

- mock PCM 청크 순서가 보존된다.
- cancel 이후 오디오 이벤트가 없다.
- 응답 오디오가 디스크나 객체 저장소에 기록되지 않는다.

## 7. Voice Runtime 컨테이너

추가·수정:

- `v3/voice/Dockerfile`
- `v3/voice/requirements.txt`
- `.dockerignore`
- `v3/tests/test_voice_container_contract.py`

작업:

1. Linux ARM64, port 8080, `/ws` 계약의 비특권 컨테이너를 만든다.
2. `/ping` health endpoint를 제공한다.
3. 필요한 음성·AgentCore SDK만 별도 requirements에 고정한다.
4. 개발 자격증명, `.env`, 로컬 DB와 음성 파일을 이미지에서 제외한다.
5. 로컬 mock 모드에서 외부 AWS 호출 없이 WebSocket 계약을 검증한다.

검증:

```bash
docker buildx build --platform linux/arm64 -f v3/voice/Dockerfile --load -t imjingang-agentcore-v3-voice:test .
```

## 8. 서명 세션 API

추가·수정:

- `v3/aws/voice_session.py`
- `v3/config.py`
- `v3/api.py`
- `v3/contracts.py`
- `v3/tests/test_voice_session_api.py`
- `v3/.env.example`

작업:

1. `V3_VOICE_ENABLED`, Voice Runtime ARN·qualifier와 60초 만료 설정을 추가한다.
2. `POST /api/voice/session`에서 서버 생성 session ID와 pre-signed WSS URL을 반환한다.
3. 기능 플래그가 꺼지면 404, 설정 오류는 시작 단계에서 명시한다.
4. Origin, content type, payload, LOT와 발급 빈도를 검증한다.
5. 응답에 AWS 자격증명이나 불필요한 내부 식별자를 넣지 않는다.
6. audit 로그에서 URL query와 토큰을 완전히 제외한다.

수용 기준:

- 테스트가 60초 만료와 지정 Runtime·Endpoint 서명을 확인한다.
- 다른 Runtime ARN, 과도한 요청과 잘못된 Origin을 거절한다.
- 테스트 로그에 `X-Amz-Signature`가 없다.

## 9. React 음성 기반 모듈

추가:

- `v3/web/src/voice/types.ts`
- `v3/web/src/voice/reducer.ts`
- `v3/web/src/voice/VoiceClient.ts`
- `v3/web/src/voice/MicrophoneCapture.ts`
- `v3/web/src/voice/PcmPlayer.ts`
- `v3/web/src/voice/pcm-processor.ts`
- `v3/web/src/voice/VoicePanel.tsx`

수정:

- `v3/web/src/App.tsx`
- `v3/web/src/types.ts`
- `v3/web/src/styles.css`
- `v3/web/vite.config.ts`

작업:

1. AudioWorklet에서 마이크를 16kHz mono PCM16으로 변환한다.
2. WebSocket client와 이벤트 parser를 구현한다.
3. partial/final transcript, Agent 상태와 오류를 reducer로 관리한다.
4. PCM 재생 큐와 sequence ordering을 구현한다.
5. 새 발화 감지 시 로컬 재생 큐를 즉시 비우고 `response.cancel`을 보낸다.
6. 확정 질문과 답변을 기존 메시지 목록에 합친다.
7. LOT 변경·새 대화·unmount에서 음성 세션과 미디어 트랙을 종료한다.
8. 마이크 권한 거부와 AudioWorklet 미지원 상태를 안내한다.

수용 기준:

- 음성 상태와 제어가 키보드·스크린리더에서 식별된다.
- 마이크·AudioContext·WebSocket이 종료 후 남지 않는다.
- 기존 텍스트 질문, LOT 선택, reset 동작이 회귀하지 않는다.

## 10. UI 통합과 프런트엔드 검증

작업:

- composer에 `실시간 음성 시작`을 추가한다.
- 활성 세션에 입력 레벨, 전사문, 상태, LOT와 제어 버튼을 표시한다.
- `마이크 끄기`, `답변 중단`, `음성 세션 종료`를 분리한다.
- 샘플 데이터와 자동 승인 불가 안내를 유지한다.
- 작은 화면에서는 음성 패널을 단일 열로 축소한다.
- `prefers-reduced-motion`에서 입력 레벨 애니메이션을 정적으로 바꾼다.

검증:

```bash
npm run build --prefix v3/web
```

브라우저 검증:

- 데스크톱과 390px
- 마이크 허용·거부
- partial/final transcript
- 음성 재생과 barge-in
- 음성 종료 뒤 텍스트 질문
- 콘솔 오류와 미디어 리소스 해제

## 11. CDK Voice Runtime과 IAM

추가·수정:

- `infra/agentcore-v3/stacks/agentcore_stack.py`
- `infra/agentcore-v3/stacks/ecs_web_stack.py`
- `infra/agentcore-v3/tests/test_stack.py`
- `infra/agentcore-v3/tests/test_ecs_web_stack.py`

작업:

1. retained Voice ECR repository와 출력값을 추가한다.
2. 조건부 Voice Runtime, Endpoint와 execution role을 추가한다.
3. execution role을 Transcribe Streaming, Polly와 기존 Text Runtime 호출로 제한한다.
4. ECS Task Role에 Voice Runtime WebSocket 호출 권한만 추가한다.
5. ECS 환경에 voice feature flag, Runtime ARN과 qualifier를 주입한다.
6. 기존 Runtime, web ECR, Gateway와 Memory 조건을 보존한다.

수용 기준:

- Voice 비활성 synth에서 기존 리소스가 변하지 않는다.
- Voice 활성 synth의 IAM에 관리자·불필요 wildcard 권한이 없다.
- Voice와 Text Runtime ARN이 서로 바뀌지 않는다.

## 12. CloudFront HTTPS

추가·수정:

- `infra/agentcore-v3/stacks/ecs_web_stack.py`
- `infra/agentcore-v3/tests/test_ecs_web_stack.py`

작업:

1. 기존 ALB를 origin으로 하는 CloudFront distribution을 추가한다.
2. viewer HTTP를 HTTPS로 redirect한다.
3. `/api/*`는 캐시를 비활성화하고 필요한 메서드·쿠키·헤더를 전달한다.
4. 정적 asset은 content hash 기반으로 캐시한다.
5. CloudFront HTTPS URL을 stack output으로 제공한다.
6. FastAPI의 secure cookie와 허용 Origin을 CloudFront 도메인 기준으로 설정한다.

수용 기준:

- CloudFront HTTPS에서 `/`, `/api/health`, `/api/chat`, `/api/voice/session`이 동작한다.
- 음성 API 응답이 캐시되지 않는다.
- ALB HTTP URL은 운영 사용자용 URL로 안내하지 않는다.

## 13. 로컬 전체 회귀

검증:

```bash
.venv-v2/bin/python -m pytest v3/tests -q
npm run build --prefix v3/web
cd infra/agentcore-v3 && /tmp/imjingang-agentcore-cdk/bin/python -m pytest tests -q
git diff --check
```

추가 확인:

- 기존 API 15개 이상 통과
- 신규 voice 계약·session·adapter 테스트 통과
- CDK synth 성공
- V1/V2 변경 없음
- 번들과 synth template에 자격증명·서명 URL 없음

## 14. 단계별 AWS 배포

### 14.1 ECR과 IAM

- 기존 AgentCore stack을 업데이트해 Voice ECR을 먼저 생성한다.
- 기존 Text Runtime, Endpoint와 Gateway 상태를 확인한다.

### 14.2 Voice 이미지

- 서울 ECR 로그인
- Linux ARM64 이미지 빌드·push
- digest와 scan 결과 기록

### 14.3 Voice Runtime

- Voice Runtime과 `ImjingangVoiceV3Live` Endpoint 생성
- Endpoint `READY`, `/ping`과 execution role 확인
- mock 또는 테스트 WebSocket client로 연결 확인

### 14.4 웹과 CloudFront

- 서명 API가 포함된 웹 이미지를 ECR에 push
- ECS task definition을 배포하되 `V3_VOICE_ENABLED=0` 유지
- CloudFront HTTPS에서 기존 텍스트 기능 회귀 확인

### 14.5 기능 활성화

- `V3_VOICE_ENABLED=1`로 ECS 롤링 배포
- Voice 세션 URL 발급과 WSS 연결 확인
- ECS desired/running 1, rollout `COMPLETED` 확인

## 15. AWS 종단 간 검증

자동·수동 검증:

- CloudFront HTTPS에서 마이크 권한 획득
- 한국어 partial/final transcript
- `PACK-260903-001 출하 가능 여부` 음성 질문
- 응답 `mode=agentcore`
- `get_lot_trace`, `get_shipment_readiness`
- Polly 한국어 음성 청취
- 답변 중 발화로 즉시 재생 중단
- 세션 종료 후 텍스트 채팅 정상
- CloudWatch 로그에 오디오, 질문 전문, 서명 URL 없음
- 실패 시 Transcribe, Text Runtime, Polly 오류가 각각 구분됨

## 16. 문서와 아키텍처 HTML 갱신

수정:

- `docs/aws-agentcore-v3.md`
- `docs/imjingang-v3-aws-architecture.html`

기록:

- CloudFront HTTPS 테스트 URL
- Voice Runtime·Endpoint 상태
- Voice 및 Web 이미지 digest
- IAM과 데이터 비저장 경계
- 실제 한국어 전사·음성·barge-in 검증 결과
- 비용과 세션 quota 주의사항

## 17. 롤백

- UI 비활성화: `V3_VOICE_ENABLED=0`으로 ECS 재배포
- Voice 장애: Voice Runtime endpoint 트래픽 중지
- 웹 장애: 직전 web image digest와 task definition으로 복구
- CloudFront 장애: 기존 ALB는 진단용으로 유지하되 사용자에게는 HTTPS 복구 전 음성 기능을 제공하지 않음
- Text Runtime, Gateway, V1/V2는 수정·삭제하지 않음

## 완료 조건

- 로컬 Python·React·CDK 테스트 통과
- Voice Runtime과 Endpoint `READY`
- CloudFront HTTPS URL 제공
- ECS 서비스 1/1, rollout `COMPLETED`
- 한국어 양방향 음성 세션 성공
- 제조 근거 도구와 답변 출처 유지
- barge-in과 명시적 종료 성공
- 오디오·서명 URL·자격증명 비저장 확인
- 텍스트 채팅과 기존 AWS 리소스 회귀 없음
