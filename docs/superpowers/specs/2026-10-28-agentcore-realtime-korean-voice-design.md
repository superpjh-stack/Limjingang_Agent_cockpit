# 임진강김치 V3 AgentCore 실시간 한국어 음성 설계

## 1. 목적

현재 V3 React·FastAPI 앱에 양방향 실시간 음성 질의와 음성 답변을 추가한다. 사용자는 브라우저 마이크로 한국어 제조 질문을 말하고, 부분 전사문을 확인하며, 기존 AgentCore의 LOT·CCP·출하 근거 답변을 음성으로 들을 수 있어야 한다.

성공 기준:

- 브라우저와 AgentCore Voice Runtime이 WebSocket으로 양방향 오디오를 스트리밍한다.
- Amazon Transcribe Streaming이 `ko-KR` 부분·최종 전사를 반환한다.
- 최종 전사문이 기존 `ImjingangV3Live` Runtime의 읽기 전용 제조 질의로 연결된다.
- 답변 텍스트, 출처, 사용 도구가 기존 채팅 메시지에 표시된다.
- Amazon Polly가 한국어 음성을 스트리밍하며 사용자가 답변 도중 새로 말하면 재생을 중단한다.
- 음성 실패 후에도 기존 텍스트 채팅을 계속 사용할 수 있다.
- 음성 원본, 서명 URL, AWS 자격증명을 저장하거나 로그에 남기지 않는다.

## 2. 선택한 접근

### 채택

AgentCore WebSocket Voice Runtime 안에서 Amazon Transcribe Streaming, 기존 AgentCore Text Runtime, Amazon Polly를 순서대로 연결한다.

```text
Browser microphone / speaker
        |-- HTTPS --> CloudFront --> ALB --> ECS FastAPI
        |                                  `-- /api/voice/session
        |
        `-- signed WSS: PCM + JSON --> AgentCore Voice Runtime /ws
                                          |-- Amazon Transcribe Streaming ko-KR
                                          |-- ImjingangV3Live HTTP Runtime
                                          |     `-- LOT, CCP, shipment evidence tools
                                          `-- Amazon Polly ko-KR
                                                `-- PCM audio chunks
```

이 방식은 한국어 지원, 서울 리전 유지, 기존 제조 근거 계약 재사용, 음성 Runtime의 독립 배포를 동시에 만족한다.

### 제외한 접근

- Amazon Nova 2 Sonic 직접 speech-to-speech: 지연시간은 낮지만 현재 공식 한국어 지원이 없어 제외한다.
- ECS 웹 태스크 내부 WebSocket 서버: 웹 배포와 장시간 음성 세션의 수명·확장이 결합되고 AgentCore의 세션 격리를 활용하기 어려워 제외한다.
- 브라우저 Web Speech API: 브라우저·운영체제별 품질과 가용성이 일정하지 않고 AWS 관리 경계를 벗어나므로 제외한다.

## 3. AWS 구성

### 3.1 Voice Runtime

기존 Text Runtime은 유지하고 별도 AgentCore Runtime을 추가한다.

- 이름: `ImjingangManufacturingVoiceV3`
- Endpoint qualifier: `ImjingangVoiceV3Live`
- 프로토콜: AgentCore Runtime WebSocket
- 컨테이너 포트: `8080`
- WebSocket path: `/ws`
- 플랫폼: Linux ARM64
- 세션: 브라우저 음성 세션 하나당 AgentCore 세션 하나

Voice Runtime은 제조 데이터를 직접 변경하지 않는다. 최종 전사문을 기존 Text Runtime 계약의 `AgentRequest`로 변환하고 `InvokeAgentRuntime`으로 호출한다.

### 3.2 AWS 서비스

- Amazon Transcribe Streaming, region `ap-northeast-2`, language `ko-KR`
- Amazon Polly, region `ap-northeast-2`, language `ko-KR`
- 기본 음성: `Seoyeon`, generative engine
- 기존 Text Runtime: `ImjingangV3Live`
- 기존 모델: `global.amazon.nova-2-lite-v1:0`
- CloudWatch Logs: 이벤트 메타데이터와 오류 유형만 기록

배포 전 계정에서 서울 리전 `Seoyeon` generative engine 호출을 검증한다. 지원되지 않으면 배포를 중단하며 다른 음성·엔진·리전으로 자동 전환하지 않는다.

### 3.3 HTTPS 진입점

현재 ALB HTTP 주소는 원격 브라우저의 안전한 컨텍스트가 아니므로 마이크 기능을 사용할 수 없다. 별도 도메인 구매 없이 CloudFront 기본 도메인을 HTTPS 진입점으로 추가한다.

- CloudFront origin: 기존 public ALB
- Viewer protocol: HTTPS only, HTTP 요청은 HTTPS로 redirect
- `/api/*`: 캐시 비활성화, 모든 필요한 헤더·쿠키·메서드 전달
- 정적 React asset: content hash 기준 캐시
- AgentCore WebSocket은 CloudFront를 경유하지 않고 서명된 `wss://bedrock-agentcore...` 주소로 직접 연결
- 최종 테스트 URL은 CloudFront HTTPS 주소로 교체

### 3.4 브라우저 인증

브라우저는 AWS 장기 자격증명을 받지 않는다.

1. 브라우저가 ECS FastAPI의 `POST /api/voice/session`을 호출한다.
2. FastAPI가 Voice Runtime용 60초 만료 SigV4 pre-signed WebSocket URL을 생성한다.
3. 브라우저는 URL을 메모리에서만 사용해 Voice Runtime에 직접 연결한다.
4. 세션 종료 또는 URL 만료 시 URL을 폐기한다.

초기 공개 테스트 환경에서는 URL 발급 요청을 동일 출처와 요청 빈도로 제한한다. 운영 전에는 Cognito 또는 조직 SSO로 인증된 사용자에게만 발급한다.

## 4. IAM

### ECS Task Role

- `bedrock-agentcore:InvokeAgentRuntimeWithWebSocketStream`
- 대상은 Voice Runtime과 `ImjingangVoiceV3Live` Endpoint ARN으로 제한
- pre-signed URL 생성 이외에 Transcribe·Polly 직접 권한 없음

### Voice Runtime Execution Role

- `transcribe:StartStreamTranscription`
- `polly:SynthesizeSpeech`
- `bedrock-agentcore:InvokeAgentRuntime`
- Invoke 대상은 기존 Text Runtime과 `ImjingangV3Live` Endpoint ARN으로 제한
- CloudWatch 로그 기록에 필요한 최소 권한

Voice Runtime에는 ECR 쓰기, IAM 변경, S3, 임의 데이터베이스 쓰기, 설비 제어 권한을 부여하지 않는다.

## 5. 오디오와 세션 계약

### 입력

- 브라우저 `getUserMedia`와 Web Audio API 사용
- PCM signed 16-bit little-endian
- mono, 16kHz
- 20ms 단위 프레임을 묶어 전송
- 한 오디오 메시지와 누적 버퍼의 최대 크기 제한
- 기본 세션 최대 15분, 최대 무음 시간 60초
- 서명 URL은 발급 후 60초 안에 연결할 때만 사용

AudioWorklet을 우선 사용하고 지원하지 않는 브라우저에서는 실시간 음성 기능을 비활성화한다. 오래된 ScriptProcessor 기반 폴백은 추가하지 않는다.

### 브라우저에서 Runtime으로 보내는 이벤트

```json
{"type":"session.start","session_id":"opaque-id","lot_id":"PACK-260903-001"}
{"type":"audio.chunk","utterance_id":"u-1","sequence":12,"audio":"base64-pcm"}
{"type":"audio.stop","utterance_id":"u-1"}
{"type":"response.cancel","response_id":"r-1"}
{"type":"session.end"}
```

### Runtime에서 브라우저로 보내는 이벤트

```json
{"type":"session.ready"}
{"type":"transcript.partial","utterance_id":"u-1","text":"포장 로트의"}
{"type":"transcript.final","utterance_id":"u-1","text":"포장 로트의 출하 가능 여부를 알려줘"}
{"type":"agent.status","utterance_id":"u-1","status":"retrieving"}
{"type":"answer.text","response_id":"r-1","text":"현재 출하 승인은 대기 상태입니다."}
{"type":"audio.chunk","response_id":"r-1","sequence":8,"audio":"base64-pcm"}
{"type":"answer.complete","response_id":"r-1","sources":[],"data_tools":[]}
{"type":"response.cancelled","response_id":"r-1"}
{"type":"error","code":"TRANSCRIBE_UNAVAILABLE","message":"음성 인식을 시작하지 못했습니다."}
```

모든 이벤트에 서버가 검증하는 `session_id`, 발화별 `utterance_id`, 응답별 `response_id`를 연결한다. 동일한 `utterance_id`의 최종 전사는 한 번만 AgentCore에 전달한다.

## 6. 처리 흐름

1. 브라우저가 마이크 권한을 받고 `/api/voice/session`에서 서명 URL과 세션 ID를 받는다.
2. WebSocket 연결 후 브라우저가 `session.start`와 PCM 프레임을 전송한다.
3. Voice Runtime이 Transcribe Streaming에 PCM을 전달한다.
4. 부분 전사는 UI에만 표시한다.
5. 최종 전사를 기존 `AgentRequest`로 변환해 Text Runtime을 호출한다.
6. Text Runtime이 기존 읽기 전용 도구로 LOT·CCP·출하 근거를 조회한다.
7. Voice Runtime이 답변 텍스트를 먼저 전송한다.
8. Polly의 PCM 출력을 청크 단위로 브라우저에 전송한다.
9. 브라우저는 AudioContext로 청크를 순차 재생한다.
10. 새 사용자 발화가 감지되면 `response.cancel`을 보내고 현재 재생 큐와 Polly 스트림을 중단한다.

## 7. UI 상태

기존 채팅 composer에 `실시간 음성 시작` 버튼을 추가한다. 활성 세션에서는 별도 음성 패널을 표시한다.

상태:

- `연결 중`
- `듣는 중`
- `질문 확인 중`
- `근거 조회 중`
- `답변 중`
- `연결 끊김`

패널 요소:

- 입력 레벨 표시
- 부분 전사문과 확정 전사문
- 현재 선택 LOT
- 마이크 켜기·끄기
- 답변 중단
- 음성 세션 종료
- 샘플 데이터와 자동 승인 불가 안내

음성으로 확정된 사용자 질문과 Agent 답변은 기존 메시지 목록에도 추가한다. 텍스트와 음성은 동일한 대화 세션을 공유한다.

## 8. Barge-in과 동시성

- 브라우저의 입력 레벨과 Transcribe 발화 이벤트로 새 발화를 감지한다.
- 답변 재생 중 새 발화가 시작되면 로컬 재생 큐를 즉시 비운다.
- `response.cancel`을 Voice Runtime에 보내 Polly 전송과 이전 응답 후처리를 중단한다.
- 취소된 응답의 늦은 오디오 청크는 `response_id` 비교로 폐기한다.
- 한 세션에서 AgentCore 질의는 한 번에 하나만 활성화한다.
- 새 최종 발화가 들어오면 이전 질의를 취소하거나 완료 결과를 폐기한다.

## 9. 오류 처리

- 마이크 권한 거부: 권한 안내를 표시하고 텍스트 입력 유지
- AudioWorklet 미지원: 지원 브라우저 안내 후 음성 버튼 비활성화
- 서명 URL 발급 실패: 재시도 버튼과 텍스트 채팅 제공
- URL 만료: 새 URL을 한 번 발급해 재연결
- WebSocket 단절: 재생을 중단하고 사용자가 명시적으로 재연결
- Transcribe 장애: 세션을 정리하고 다시 듣기 제공
- Text Runtime 장애: 정상 답변으로 대체하지 않고 오류 이벤트 반환
- Polly 장애: 답변 텍스트는 보존하고 음성 출력만 실패 처리
- 중복 최종 전사: `utterance_id`로 무시
- 잘못된 LOT: 기존 404/422 규칙과 동일한 사용자 메시지 반환

## 10. 개인정보와 로그

저장하지 않는 항목:

- 원본 마이크 오디오
- Polly 출력 오디오
- pre-signed WebSocket URL
- AWS 자격증명 또는 서명 파라미터

기본 로그 항목:

- `request_id`, `session_id`의 비가역 해시
- 음성 세션 시작·종료 시각
- 상태 전환과 오류 코드
- 전사·Agent·TTS 구간별 지연시간
- 사용 도구 이름과 근거 건수
- 입력·출력 오디오 바이트 수

질문 전문, 답변 전문, 제조 원본 레코드는 기본 로그에서 제외한다.

## 11. 코드 경계

예상 구성:

- `v3/voice/runtime.py`: WebSocket 계약과 세션 수명
- `v3/voice/transcribe.py`: 한국어 Transcribe 스트림 어댑터
- `v3/voice/polly.py`: 한국어 PCM 출력 어댑터
- `v3/voice/contracts.py`: 이벤트 모델과 크기 제한
- `v3/voice/Dockerfile`: Voice Runtime 이미지
- `v3/api.py`: `POST /api/voice/session`
- `v3/aws/voice_session.py`: 서명 URL 생성
- `v3/web/src/voice/`: 마이크 캡처, WebSocket, PCM 재생, 상태 reducer
- `v3/web/src/App.tsx`: 음성 패널과 기존 메시지 통합
- `infra/agentcore-v3/stacks/`: Voice ECR, Runtime, Endpoint, IAM, ECS 권한

음성 모듈은 텍스트 채팅 계약을 변경하지 않는다. Voice Runtime은 기존 AgentCore 응답을 전달하는 어댑터 역할만 담당한다.

## 12. 테스트

### 단위 테스트

- 이벤트 모델의 정상·비정상 payload
- 프레임 순서, 크기, 세션 제한
- 부분 전사는 AgentCore를 호출하지 않음
- 같은 발화의 최종 전사 중복 방지
- 취소된 `response_id`의 늦은 오디오 폐기
- Transcribe, AgentCore, Polly 오류 매핑
- 서명 URL 만료와 Runtime ARN 제한
- 로그 필드에 음성·URL·질문 전문이 없는지 확인

### 프런트엔드 테스트

- 상태 reducer 전체 전이
- 마이크 권한 거부
- 부분·최종 전사 표시
- 답변 중단과 재생 큐 비우기
- 세션 종료 후 텍스트 채팅 사용
- 모바일 레이아웃과 키보드 접근성

### 통합 테스트

- 로컬 mock WebSocket에서 PCM 왕복
- AWS Transcribe `ko-KR` 부분·최종 전사
- `PACK-260903-001` 질문에서 `get_lot_trace`, `get_shipment_readiness` 사용
- Polly 한국어 PCM 수신과 브라우저 재생
- 답변 도중 발화로 barge-in
- ECS URL에서 서명 URL 발급 후 Voice Runtime 연결
- 세션 종료 뒤 Runtime·브라우저 리소스 정리

## 13. 배포와 롤백

1. Voice ECR과 IAM을 기존 AgentCore 인프라에 추가한다.
2. Voice Runtime 이미지를 빌드하고 ECR에 push한다.
3. Voice Runtime과 `ImjingangVoiceV3Live` Endpoint를 생성한다.
4. ECS Task Role에 해당 Voice Runtime WebSocket 호출 권한을 추가한다.
5. 웹 앱을 음성 기능 플래그가 꺼진 상태로 배포한다.
6. CloudFront를 생성하고 HTTPS UI·API 경로를 검증한다.
7. AWS 통합 검증 후 `V3_VOICE_ENABLED=1`인 새 ECS task definition을 배포한다.
8. 음성·텍스트·barge-in 종단 간 테스트를 실행한다.

롤백은 `V3_VOICE_ENABLED=0`으로 ECS를 재배포하고 Voice Runtime 트래픽을 중지한다. CloudFront HTTPS 경로와 기존 Text Runtime, Gateway, V1/V2, 텍스트 채팅은 유지한다.

## 14. 운영 전 필수 항목

- 운영 커스텀 도메인이 필요하면 CloudFront에 Route 53과 ACM 인증서를 연결한다.
- Cognito 또는 조직 SSO로 `/api/voice/session` 발급을 제한한다.
- URL 발급과 음성 세션에 사용자별 rate limit을 적용한다.
- WAF와 비용 알람을 추가한다.
- Transcribe·Polly·AgentCore 동시 세션 quota를 확인한다.
- 현장 소음 환경에서 한국어 전사 정확도와 LOT 코드 인식률을 파일럿 검증한다.

## 15. 범위 밖

- 전화망, SIP, Amazon Connect 연동
- 음성 생체정보 저장 또는 화자 식별
- 원본 음성 녹음과 장기 보존
- 다국어 자동 감지
- 설비 제어, 자동 출하 승인, 자동 CCP 처분
- Nova Sonic 한국어 지원 전의 speech-to-speech 직접 전환

## 16. 공식 근거

- AgentCore Runtime bidirectional WebSocket: <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-get-started-websocket.html>
- AgentCore bidirectional streaming overview: <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-bidirectional-streaming.html>
- Amazon Transcribe supported languages: <https://docs.aws.amazon.com/transcribe/latest/dg/supported-languages.html>
- Amazon Transcribe region availability: <https://docs.aws.amazon.com/transcribe/latest/dg/>
- Amazon Polly Korean generative voice and regions: <https://docs.aws.amazon.com/polly/latest/dg/generative-voices.html>
- Amazon Nova model and language support: <https://docs.aws.amazon.com/nova/latest/nova2-userguide/>
