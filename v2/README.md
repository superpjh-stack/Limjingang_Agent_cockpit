# 임진강김치 Operations V2 · 스킬2

React·TypeScript·Vite 화면과 FastAPI 서버를 사용하는 두 번째 제조 Agent 버전입니다. 기존 Streamlit V1은 프로젝트 루트에서 별도로 실행됩니다. V2는 V1의 LOT·품질·지식·도구 모듈을 재사용하고, 별도의 DB 경로와 HTTP API를 사용합니다.

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
- AI 연결 시 음성 파일을 텍스트로 변환한 뒤 편집·전송, 답변 AI 음성 재생

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

음성 기능은 녹음 파일 선택 방식입니다. 선택하면 OpenAI로 전송하고, 변환된 텍스트는 질문 입력창에서 검토 후 보내도록 합니다. 브라우저 내 마이크 실시간 녹음과 문서 업로드·인덱싱 UI는 V2에 포함하지 않았습니다. 등록 문서 조회·검색·내려받기를 제공하며 문서 등록은 기존 관리 경로를 사용합니다.

대화 연결은 서버 프로세스 메모리에 한 시간 유지되며 최대 1,000개 세션을 보관합니다. 서버 재시작 시 연결은 초기화됩니다. 운영에서 여러 API 워커를 사용할 때는 공유 세션 저장소로 전환해야 합니다. 현재 실행은 단일 워커입니다.

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

브라우저에서 데스크톱과 390px 화면, LOT 상세, 직접 질문/응답, 대화 초기화, 문서·DB 화면을 확인했습니다. 실제 OpenAI 응답·음성 생성은 유효한 서버 자격증명이 필요한 별도 검증입니다. Docker 이미지의 실제 빌드는 이 로컬 환경에서 검증하지 않았습니다.

## 재사용 스킬

- [`skill-1-streamlit`](../skills/skill-1-streamlit/SKILL.md): Streamlit 방식
- [`skill-2-react`](../skills/skill-2-react/SKILL.md): React + FastAPI 방식

두 스킬은 개인 Codex 스킬 폴더에도 설치했습니다. 다른 회사에 적용할 때에는 공정·샘플·규칙·문서·브랜딩을 해당 회사 기준으로 바꾸고 임진강의 식별자와 예시 수치를 운영값으로 재사용하지 않습니다.

구현 참고: [Vite 공식 가이드](https://vite.dev/guide/), [FastAPI 정적 파일](https://fastapi.tiangolo.com/tutorial/static-files/).
