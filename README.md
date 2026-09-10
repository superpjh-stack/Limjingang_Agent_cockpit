# 임진강김치 제조 AI Agent Cockpit

경동글로벌텍의 `agent-cokpit-maker` 스킬과 원본 cockpit 구조를 임진강김치의 원료·절임·발효·CCP·포장·출하 업무에 적용한 Streamlit 시제품입니다. ERP·IoT Data Hub를 조회하는 구조이며 MES 신규 구축을 전제로 하지 않습니다.

## 두 가지 버전

- **스킬1 · Streamlit V1**: 기존 루트 앱과 Hostinger 8502 배포
- **스킬2 · React V2**: React·TypeScript + FastAPI 웹앱, [V2 실행 안내](v2/README.md)
- 재사용 스킬: [스킬1](skills/skill-1-streamlit/SKILL.md), [스킬2](skills/skill-2-react/SKILL.md)

## 구성

- 포장·CCP·발효·재고·출하 KPI와 근거형 한국어 대화
- 원재료 → 선별 → 절임 → 혼합 → 발효 → 포장 LOT 계보와 클레임 역추적
- 지식베이스·DB·룰별 추천질문 각 10개, 대화 이력, LOT 브리핑
- 임진강 전용 지식문서 10개와 연결된 검토 규칙 7개
- 문서 검색·본문·내려받기, 읽기 전용 테이블·건수·레코드 상세
- PostgreSQL + pgvector 운영용 기반, SQLite 오프라인 데모
- 문서 근거를 여러 검색 라운드에 걸쳐 유지하고 도구 반복 횟수 제한
- API 키 마스킹, 세션별 설정, 키 변경 시 대화 연결 초기화
- 녹음 → 변환 → 내용 수정 → 전송 및 답변 음성 재생
- 휴대전화에서는 대화와 입력을 우선하는 반응형 화면

모든 수치·거래·식별자·예측은 **2026년 9월 가상 데모**입니다. 샘플 문서·규칙은 미승인 예시이며 실제 HACCP 기준서가 아닙니다. ML 모델은 실제 학습·추론 구현이 아니라 저장된 예측 예시입니다. 품질예측 정확도 90%와 생산 CAPA는 기존 기획의 예시·목표로, 검증된 실적이 아닙니다. 공정조건 변경·CCP 처분·발주·출하는 자동 실행하지 않습니다.

## 로컬 실행

Python 3.11 이상을 권장합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

API 키 없이도 KPI, LOT, 문서, DB, 규칙을 볼 수 있습니다. 자연어 대화·업로드 문서 인덱싱·음성 변환은 `.env`의 `OPENAI_API_KEY`가 필요합니다. 서버 키는 새 세션에 자동 적용되고 화면에는 마지막 네 글자만 표시됩니다. 화면에서 입력한 키는 현재 세션에만 적용됩니다. 빈 키 입력은 기존 키를 유지합니다.

기본 모델은 `imjingang_agent/service.py`의 `DEFAULT_MODEL` 한 곳에서 정의합니다. `OPENAI_MODEL`을 설정하면 이를 덮어씁니다. `DATABASE_URL`을 비우면 SQLite 데모를 사용하며, 운영용 DB로 설명하지 않습니다.

## Docker 실행

`.env`에서 `POSTGRES_PASSWORD`를 URL에 안전한 긴 영숫자 비밀번호로 설정합니다. DB는 외부 포트를 공개하지 않으며 앱은 8501 포트를 사용합니다.

```bash
docker compose config --quiet
docker compose up -d --build
```

PostgreSQL 17과 pgvector가 먼저 정상 상태가 된 뒤 앱이 시작됩니다. 새 DB에 vector 확장, 업무 테이블, 문서·규칙, 1536차원 벡터 열과 HNSW 인덱스를 만듭니다. DB 데이터는 named volume에 유지됩니다. 로컬 문서는 API 키나 임베딩 없이 키워드로 검색합니다. 벡터 저장·검색은 `PostgresRepository.save_uploaded_document(..., embedding=...)`와 `vector_search_knowledge()`로 제공하며, 앱의 문서 업로드는 OpenAI File Search를 사용합니다. 로컬 문서 임베딩 일괄 생성은 자동 실행하지 않습니다.

`.env`와 키는 커밋하거나 이미지에 포함하지 않습니다. 서버 키를 바꾸려면 배포 서버의 `.env` 또는 Docker Manager의 `OPENAI_API_KEY` 환경변수를 수정하고 앱 컨테이너를 재생성합니다.

```bash
docker compose up -d --force-recreate app
```

## SQLite → PostgreSQL 이전

원본 SQLite는 앱을 한 번 실행해 문서·규칙 스키마까지 초기화합니다. 이전 시 파일을 덮어쓰지 말고 아래 스크립트를 사용합니다. 기본 동작은 **대상 업무·문서·규칙·설정 전체 교체**이므로 대상 DB를 백업하고 점검시간에 실행하세요. 기존 운영 DB에 데모를 이전하지 마세요. 교체는 하나의 트랜잭션으로 처리하며 반복 실행해도 행이 중복되지 않습니다. 실패하면 교체를 롤백합니다.

```bash
DATABASE_URL='postgresql://user:password@localhost:5432/imj_cockpit' \
  python scripts/migrate_sqlite_to_postgres.py --source data/imjingang_demo.db
```

기존 행을 보존하며 기본키가 없는 항목만 추가하려면 `--append`를 사용합니다. 기본키가 충돌하는 기존 행은 유지합니다.

## 검증

```bash
python -m pytest -q
# 권한 있는 별도 테스트 DB 서버에서만 실행 (임시 DB 생성·삭제)
TEST_POSTGRES_ADMIN_URL='postgresql://user:password@localhost:5432/postgres' python -m pytest -q
```

테스트는 LOT·클레임 계보, 상위 공정 CCP 조회, 예측 누락 표시, 문서·규칙 연결과 지속성, 읽기 도구 제한, 검색 근거·반복 상한, 화면 렌더링과 대화 초기화·추천·설정 변경을 확인합니다. PostgreSQL 테스트는 새 DB 초기화·재접속, 반복 이전, 벡터 검색도 검증합니다.

이 작업 환경에서 SQLite·Streamlit 검증과 로컬 PostgreSQL 검증을 수행했습니다. Docker 실행 도구와 연결 가능한 브라우저는 없어 컨테이너 실제 구동, 화면 대비·휴대전화 넘침·브라우저 콘솔 오류는 검증하지 못했습니다. 실제 OpenAI 호출과 마이크·음성 재생도 API 키를 설정한 환경에서 별도 확인해야 합니다.

## 현장 연동 전 확인

현재 LOT 스키마는 단일 부모 계보입니다. 분할·합류, 양념 원료 투입, 재작업·운송·보관 이력과 품목별 승인 기준은 현장 ERP·IoT 조사 후 연결해야 합니다. 예측·검사 기록이 없으면 정상으로 추정하지 않습니다. 출하 조회는 연결된 공정의 CCP 이력까지 보여주지만 승인 완료를 결정하지 않습니다. 실제 운용에는 승인된 기준서, 접근권한·감사로그·백업 및 현장 데이터 품질 검증이 필요합니다.
