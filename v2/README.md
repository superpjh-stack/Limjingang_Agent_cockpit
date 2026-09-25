# 임진강김치 Operations V2 · 스킬2

React·TypeScript·Vite 화면과 FastAPI 서버를 사용하는 두 번째 제조 Agent 버전입니다. 기존 Streamlit V1은 프로젝트 루트에서 별도로 실행됩니다. V2는 V1의 LOT·품질·지식·도구 모듈을 재사용하고, 별도의 DB 경로와 HTTP API를 사용합니다.

모바일 음성과 PC 고객 여정을 다시 설계한 [v2.0 제품 기획](../docs/v2.0-product-plan.md)과 [개발 명세](../docs/v2.0-delivery-spec.md)가 있습니다. 해당 문서의 제안 기능과 아래의 현재 구현 기능은 구분합니다.

## V1 / V2 구분

| 항목 | 스킬1 · V1 | 스킬2 · V2 |
|---|---|---|
| 화면 | Streamlit | React 19 · TypeScript · Vite 7 |
| 서버 | Streamlit Python 실행 | FastAPI, 동일 출처 REST API |
| 주 화면 | 분석용 통합 Cockpit | 운영 개요·LOT·품질·문서·규칙·DB 전용 화면 |
| 대화 | 서버 키 기반 AI | API 키 없는 명시적 데모 조회 + 접근 코드로 보호된 AI |
| 상태 | Streamlit 세션 | React 상태 + 서버의 HTTP-only 대화 세션 |
| DB | PostgreSQL/SQLite | PostgreSQL/SQLite, V1과 별도 기본 DB |
| 실행 | `streamlit run app.py` | 빌드 후 `uvicorn v2.api:app` |
| Docker 호스트 포트 | 기존 임진강 서버 8502 | V2 예시 8503 |

## 동작하는 기능

- 위험·주의·출하 대기 기록을 먼저 보여주는 운영 개요
- 제품·LOT·상태 검색, 공정 필터, 공정 계보와 측정 기록 상세
- CCP·출하 승인 상태·원료 재고 확인 및 CSV 내려받기
- 문서 검색·본문·다운로드, 규칙에서 근거 문서로 이동
- 허용된 업무 테이블 선택·페이지 조회·원본 레코드 상세
- 추천질문·직접 입력·LOT 문맥 질문과 근거 상세, 대화 초기화
- 모바일 접이식 메뉴와 대화 패널, 키보드 조작·Escape 닫기
- AI 연결 시 WebRTC 실시간 음성 대화: 녹음 파일 생성 없이 말하면 자동 응답하고, 답변 중 끼어들기·마이크 음소거·대화 종료 지원
- 조직 계정 로그인, 업무 저장·담당·상태·버전 이력, 답변 근거 스냅샷, 내부 인계·수신 확인·검토 완료
- `/work/{id}` 직접 링크로 다른 기기에서 같은 업무·근거·문맥 이어보기, 동시 수정 충돌 표시
- 내부 검토·고객 회신 초안 편집·내려받기 (외부 발송 없음)
- 파일럿 여정 계측(ME-01): 이벤트 이름·소요시간만 수집, 관리자 설정 화면에서 기기별 지표와 초기 목표 비교

모든 수치·거래·식별자·문서·규칙은 **2026년 9월 샘플**입니다. 실제 HACCP 승인기준이나 실시간 예측이 아닙니다. 데모 조회는 정해진 항목을 DB·문서에서 찾는 기능으로 범용 LLM 분석과 구분해 표시합니다. 분할·합류 및 양념 원료 전체 계보, 실제 ERP·IoT 연결은 별도 현장 연동이 필요합니다.

## 로컬 실행

프로젝트 루트에서 Python 3.12와 Node 22 이상을 사용합니다.

```bash
python3.12 -m venv .venv-v2
source .venv-v2/bin/activate
pip install -r v2/requirements.lock
npm ci --prefix v2/web
npm run build --prefix v2/web
uvicorn v2.api:app --host 127.0.0.1 --port 8510
```

접속: `http://127.0.0.1:8510`

화면 개발 중에는 API 서버와 함께 `npm run dev --prefix v2/web`를 실행하고 `http://127.0.0.1:5173`에서 확인합니다. Vite가 `/api` 요청을 8510으로 프록시합니다. `.env`는 루트에서 읽으며 환경변수로 덮어쓸 수 있습니다. `DATABASE_URL`이 없으면 `data/imjingang_v2_demo.db`를 생성합니다.

## AI와 음성 설정

서버 환경변수에 `OPENAI_API_KEY`와 충분히 긴 `COCKPIT_ACCESS_TOKEN`을 설정합니다. 기본 모델은 공유 서비스의 `DEFAULT_MODEL`이며 `OPENAI_MODEL`로 변경할 수 있습니다. 재시작 후 화면의 설정에서 **접근 코드**를 입력하면 AI 모드를 선택할 수 있습니다.

OpenAI 키는 브라우저로 전달하지 않습니다. 접근 코드는 브라우저 메모리에만 유지되고 새로고침하면 사라집니다. AI/음성 유료 호출은 접근 코드로 보호하며 데모 조회는 키 없이 가능합니다. 외부 제공 시 HTTPS 및 조직 인증을 적용하세요. 현재 접근 코드는 역할별 권한·사용자 관리 전체를 대체하지 않습니다.

음성은 **음성 대화 시작** 버튼으로 WebRTC 실시간 세션을 엽니다(HTTPS 또는 localhost 필요). 앱은 녹음 파일을 만들거나 보관하지 않으며 마이크 스트림을 실시간 음성 서비스로 전달합니다. 말이 끝난 시점은 음성 활동 감지가 판단하고 답변 음성이 즉시 재생됩니다. 답변 중 다시 말하면 기존 답변을 중단할 수 있고, 화면에서 마이크 음소거와 대화 종료가 가능합니다. 화면 자막은 세션 중 대화 확인용이며 업무 근거로 저장하려면 기존 문자 질문·근거 조회 흐름을 사용합니다. 문서 업로드·인덱싱 UI는 V2에 포함하지 않았습니다. 등록 문서 조회·검색·내려받기를 제공하며 문서 등록은 기존 관리 경로를 사용합니다.

실시간 모델과 음성은 필요할 때 서버 환경변수로 바꿀 수 있습니다. 기본값은 `OPENAI_REALTIME_MODEL=gpt-realtime-2.1`, `OPENAI_REALTIME_VOICE=marin`입니다. 표준 `OPENAI_API_KEY`는 서버에만 있고 브라우저에는 전달되지 않습니다.

대화 연결은 서버 프로세스 메모리에 한 시간 유지되며 최대 1,000개 세션을 보관합니다. 서버 재시작 시 연결은 초기화됩니다. 운영에서 여러 API 워커를 사용할 때는 공유 세션 저장소로 전환해야 합니다. 현재 실행은 단일 워커입니다.

## 업무 계정과 파일럿 지표

업무 저장·인계는 로그인한 사용자만 사용할 수 있습니다. 계정은 비밀번호가 명령행에 남지 않도록 대화형으로 만듭니다.

```bash
.venv-v2/bin/python -m v2.manage_users kim --name 김품질 --role reviewer   # operator | reviewer | admin
```

`V2_REQUIRE_LOGIN=1`이면 `/api/health`와 로그인 외 모든 API에 로그인이 필요합니다. 검토 완료는 업무 상태만 바꾸며 ERP 출하 승인·공정 설정은 변경하지 않습니다.

화면은 `/api/events`로 계획서의 13개 여정 이벤트(`task_opened` … `review_completed`)를 보냅니다. 저장 항목은 이벤트 이름·기기 구분(모바일/PC)·입력 방식·모드·소요시간·역할뿐이며 질문 문장·음성·API 키는 받지 않습니다(추가 필드는 422로 거절). 업무 관련 이벤트는 업무 ID로 묶여 모바일 저장 → PC 이어보기가 연결됩니다. 관리자는 **연결·계정 설정 → 파일럿 지표**에서 기기별 첫 업무 진입 중앙값, 음성 질문 완료율(의도적 취소 제외), 변환·답변 P95, 저장 후 이어보기 비율을 초기 목표와 비교합니다. 목표는 실적이 아니며 현행 흐름 기준값은 파일럿 전에 별도로 측정합니다.

## 독립 Docker 배포

V1의 Compose와 함께 실행하지 않고 V2 Compose를 별도 프로젝트로 사용합니다. `.env` 파일은 저장소나 이미지에 포함하지 않습니다.

```bash
cp v2/.env.example v2/.env
# v2/.env의 POSTGRES_PASSWORD를 긴 URL-safe 난수로 설정
# 필요하면 OPENAI_API_KEY와 COCKPIT_ACCESS_TOKEN도 설정
docker compose --env-file v2/.env -f v2/docker-compose.yml config --quiet
docker compose --env-file v2/.env -f v2/docker-compose.yml up -d --build
```

브라우저: `http://서버주소:8503`. PostgreSQL은 외부에 포트를 열지 않고 V2 전용 named volume을 사용합니다. 런타임 컨테이너는 일반 사용자로 실행하며 `/api/health`에서 DB 조회까지 확인합니다. V2 Dockerfile은 React를 빌드한 뒤 Python 이미지에 정적 결과물만 복사합니다.

기존 Hostinger Docker Manager에서는 `build:`를 실행하지 않고 없는 이미지를 시작하려 했습니다. 같은 상황이라면 VPS에서 저장소의 원하는 커밋을 체크아웃하고 `docker build -f v2/Dockerfile -t imjingang-cockpit-v2:local .`을 먼저 실행한 뒤 Compose를 시작합니다. 이 문서는 배포 방법이며 V2가 이미 외부 서버에 배포되었다는 의미가 아닙니다.

## 검증

```bash
npm run build --prefix v2/web
.venv-v2/bin/python -m pytest v2/tests tests/test_data_hub.py tests/test_service.py tests/test_ui_helpers.py -q
# 임시 DB 생성·삭제 권한이 있는 별도 테스트 서버에서 PostgreSQL도 검증
TEST_POSTGRES_ADMIN_URL='postgresql://user:password@localhost:5432/postgres' \
  .venv-v2/bin/python -m pytest v2/tests -q
```

API 테스트는 실제 SQLite 조회, 문서·규칙 연결, 잘못된 LOT/테이블/페이지 거절, 키 없는 데모 조회, 과거 데이터 표시, 유료 호출 접근 제한, 키 노출 방지와 production HTML 응답을 확인합니다. PostgreSQL 테스트는 새 DB 초기화·계보·문서·데모 질문과 재접속 후 지속성을 확인합니다.

브라우저에서 데스크톱과 390px 화면, LOT 상세, 직접 질문/응답, 대화 초기화, 문서·DB 화면을 확인했습니다. 2026-09-23에는 데스크톱 브라우저에서 데모 질문·근거 열기·로그인·업무 저장·목록에서 다시 열기 후 이벤트가 서버에 쌓이고 관리자 지표 화면에 표시되는 것을 확인했습니다. 실제 OpenAI 응답·음성 생성은 유효한 서버 자격증명이 필요한 별도 검증입니다. 실제 휴대전화의 마이크 권한·소음·백그라운드 전환은 실기기 체크리스트로 별도 검증해야 합니다. Docker 이미지의 실제 빌드는 이 로컬 환경에서 검증하지 않았습니다.

## 재사용 스킬

- [`skill-1-streamlit`](../skills/skill-1-streamlit/SKILL.md): Streamlit 방식
- [`skill-2-react`](../skills/skill-2-react/SKILL.md): React + FastAPI 방식

두 스킬은 개인 Codex 스킬 폴더에도 설치했습니다. 다른 회사에 적용할 때에는 공정·샘플·규칙·문서·브랜딩을 해당 회사 기준으로 바꾸고 임진강의 식별자와 예시 수치를 운영값으로 재사용하지 않습니다.

구현 참고: [Vite 공식 가이드](https://vite.dev/guide/), [FastAPI 정적 파일](https://fastapi.tiangolo.com/tutorial/static-files/).
