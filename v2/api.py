from __future__ import annotations

import os
import re
import secrets
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path
from threading import BoundedSemaphore, Lock
from time import monotonic

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from imjingang_agent import ImjingangRepository, ImjingangToolRegistry, ManufacturingAgent, QUESTION_GROUPS
from imjingang_agent.data_hub import PostgresRepository, create_repository
from imjingang_agent.service import DEFAULT_MODEL
from imjingang_agent.ui_helpers import lot_snapshot

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


class Question(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    lot_id: str | None = Field(default=None, max_length=80)
    mode: str = Field(default='demo', pattern='^(demo|ai)$')


class Speech(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


def demo_answer(repo, question: str, lot_id: str | None = None):
    """Deterministic lookup with explicit limits; never masquerades as an LLM."""
    evidence = repo.search_knowledge(question)
    tools, records = [], []
    matched = re.search(r'(?:RAW|SORT|SALT|MIX|FERM|PACK)-\d{6}-\d{3}', question.upper())
    selected = matched.group() if matched else lot_id
    claim = re.search(r'CLM-\d{6}-\d{2}', question.upper())
    if claim:
        result = repo.claim_trace(claim.group())
        records = result['lot_trace']
        tools = ['get_claim_trace']
        text = f"{claim.group()} 관련 계보 {len(records)}건을 확인했습니다." if result['claim'] else '해당 클레임은 샘플 DB에서 확인되지 않습니다.'
    elif '재고' in question or '부족' in question or '율무' in question:
        records = repo.inventory_status('율무' if '율무' in question else None, '부족' in question)
        tools = ['get_inventory_status']
        text = '\n'.join(f"{r['item_name']}: 재고 {r['quantity_kg']:,.0f}kg · 안전재고 대비 부족 {max(0, r['safety_stock_kg']-r['quantity_kg']):,.0f}kg" for r in records[:3]) or '조건에 맞는 재고 기록이 없습니다.'
    elif ('발효' in question and 'CCP' in question.upper()) or '브리핑' in question:
        predictions = repo.fermentation_status(None)
        alerts = repo.ccp_deviations(None)
        risky = [r for r in predictions if (r['abnormal_risk'] or 0) >= .5]
        tools = ['get_fermentation_status', 'get_ccp_deviations']
        records = [*risky, *alerts]
        text = f"샘플 발효 위험 {len(risky)}건 · CCP 주의 {len(alerts)}건입니다."
        if risky:
            r = risky[0]
            text += f"\n{r['lot_id']}: 온도 {r['temperature']}℃ · pH {r['ph']} · 위험 예측 {r['abnormal_risk']:.0%}. 담당자 검토가 필요합니다."
    elif selected:
        records = repo.lot_trace(selected)
        tools = ['get_lot_trace']
        snap = lot_snapshot(repo, selected)
        text = f"{selected} 연결 공정 {len(records)}건 · CCP 주의 {len(snap['ccp'])}건을 확인했습니다." if records else '해당 LOT는 샘플 DB에서 확인되지 않습니다.'
        if records and any(word in question for word in ['발효', 'pH', '온도', '산도', '염도', '위험']):
            measurements = repo.process_measurements(selected)
            tools.append('get_process_measurements')
            if measurements:
                r = measurements[0]
                text += f"\n최근 샘플 측정: 온도 {r['temperature']}℃ · pH {r['ph']} · 염도 {r['salinity']} · 산도 {r['acidity']} ({r['measured_at']})."
            else:
                text += '\n선택 LOT의 직접 측정 기록은 미확인입니다. 연결된 공정의 상세 기록을 확인하세요.'
    elif '출하' in question:
        records = repo.shipment_readiness(None)
        tools = ['get_shipment_readiness']
        text = f"출하 기록 {len(records)}건 중 승인대기 {sum(r['approval_status'] != '승인' for r in records)}건입니다. 승인 여부는 담당자가 결정합니다."
    elif 'CCP' in question.upper():
        records = repo.ccp_deviations(None)
        tools = ['get_ccp_deviations']
        text = f"샘플 CCP 주의 기록 {len(records)}건입니다. 관련 LOT·발생시각·처분 승인 이력을 확인하세요."
    elif '발효' in question or '위험' in question or '브리핑' in question:
        records = repo.fermentation_status(None)
        tools = ['get_fermentation_status']
        risky = [r for r in records if (r['abnormal_risk'] or 0) >= .5]
        text = '\n'.join(f"{r['lot_id']}: 샘플 위험 예측 {r['abnormal_risk']:.0%} · 온도 {r['temperature']}℃ · pH {r['ph']}" for r in risky) or '조건에 맞는 위험 예측이 없습니다.'
    elif '룰' in question or '규칙' in question:
        records = repo.get_rules()
        tools = ['get_rules']
        text = f"검토 규칙 {len(records)}개가 등록되어 있습니다. 모두 미승인 샘플이며 자동 조치를 실행하지 않습니다."
    else:
        text = f"관련 샘플 문서 {len(evidence)}개를 찾았습니다. 아래 근거에서 절차와 담당자를 확인하세요." if evidence else '현재 샘플 DB·문서에서 질문의 답을 확인하지 못했습니다.'
    if '오늘' in question or '현재' in question:
        text = '오늘의 실시간 기록은 없습니다. 아래는 2026년 9월 샘플 조회입니다.\n' + text
    return {'text': text + '\n근거: ' + (', '.join(tools + [d['document_id'] for d in evidence[:2]]) or '일치하는 기록·문서 없음'), 'sources': [d['filename'] for d in evidence], 'evidence': evidence, 'data_tools': tools, 'records': records, 'searched_documents': True, 'mode': 'demo', 'demo_data': True}


def create_app(repository=None, static_dir: Path | None = None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.repo = repository or create_repository(os.getenv('V2_SQLITE_PATH', str(ROOT / 'data/imjingang_v2_demo.db')))
        yield

    app = FastAPI(title='Imjingang Operations API', version='2.0.0', lifespan=lifespan)
    sessions: dict[str, dict] = {}
    mutex = Lock()
    capacity = BoundedSemaphore(3)

    def require_ai(authorization):
        expected = os.getenv('COCKPIT_ACCESS_TOKEN', '')
        if not expected or not os.getenv('OPENAI_API_KEY', ''):
            raise HTTPException(503, '서버에서 AI 키와 접근 코드를 설정해야 합니다. 데모 조회는 계속 사용할 수 있습니다.')
        if not secrets.compare_digest(authorization or '', 'Bearer ' + expected):
            raise HTTPException(401, '설정에서 올바른 AI 접근 코드를 입력해 주세요.')
        from openai import OpenAI
        return OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=35, max_retries=1)

    @app.get('/api/health')
    def health():
        app.state.repo.dashboard()
        return {'status': 'ok', 'version': '2.0.0'}

    @app.get('/api/workspace')
    def workspace():
        repo = app.state.repo
        return {'kpi': repo.dashboard(), 'lots': repo.all_lots(), 'fermentation': repo.fermentation_status(None), 'ccp': repo.ccp_deviations(None), 'inventory': repo.inventory_status(None, False), 'shipments': repo.shipment_readiness(None), 'rules': repo.get_rules(), 'tables': repo.table_inventory(), 'questions': QUESTION_GROUPS, 'meta': {'company': '임진강김치', 'version': '2.0', 'demo_data': True, 'as_of': '2026-09-03 10:40', 'backend': 'PostgreSQL + pgvector' if isinstance(repo, PostgresRepository) else 'SQLite 데모', 'ai_configured': bool(os.getenv('OPENAI_API_KEY') and os.getenv('COCKPIT_ACCESS_TOKEN')), 'model': os.getenv('OPENAI_MODEL') or DEFAULT_MODEL}}

    @app.get('/api/lots/{lot_id}')
    def detail(lot_id: str):
        result = lot_snapshot(app.state.repo, lot_id)
        if not result['lot']:
            raise HTTPException(404, 'LOT를 찾을 수 없습니다.')
        result['measurements'] = [row for row in app.state.repo.process_measurements(None) if row['lot_id'] in {r['lot_id'] for r in result['trace']}]
        return result

    @app.get('/api/documents')
    def documents(q: str = Query(default='', max_length=200)):
        repo = app.state.repo
        matches = {d['document_id'] for d in repo.search_knowledge(q)} if q.strip() else None
        return [{k: v for k, v in d.items() if k not in {'embedding', 'embedding_model'}} for d in repo.knowledge_documents() if matches is None or d['document_id'] in matches]

    @app.get('/api/tables/{table}')
    def table_records(table: str, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)):
        try:
            return app.state.repo.table_records(table, limit, offset)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post('/api/chat/reset')
    def reset(request: Request, response: Response):
        with mutex:
            sessions.pop(request.cookies.get('imj_session', ''), None)
        response.delete_cookie('imj_session', path='/api')
        return {'status': 'ok'}

    @app.post('/api/chat')
    def chat(body: Question, request: Request, response: Response, authorization: str | None = Header(default=None)):
        if not body.question.strip():
            raise HTTPException(422, '질문을 입력해 주세요.')
        repo = app.state.repo
        if body.mode == 'demo':
            return demo_answer(repo, body.question, body.lot_id)
        client = require_ai(authorization)
        if not capacity.acquire(blocking=False):
            client.close()
            raise HTTPException(429, '다른 질문을 처리 중입니다. 잠시 후 다시 시도해 주세요.')
        sid = request.cookies.get('imj_session') or secrets.token_urlsafe(32)
        identity = os.getenv('COCKPIT_ACCESS_TOKEN', '')
        now = monotonic()
        with mutex:
            for key in list(sessions):
                if now - sessions[key]['at'] > 3600:
                    sessions.pop(key)
            current = sessions.get(sid)
            previous = current.get('response_id') if current and current['identity'] == identity else None
        try:
            question = body.question + (f'\n선택 LOT: {body.lot_id}' if body.lot_id else '')
            result = ManufacturingAgent(client, model=os.getenv('OPENAI_MODEL') or DEFAULT_MODEL, factory_tools=ImjingangToolRegistry(repo)).ask(question, previous_response_id=previous)
            with mutex:
                if len(sessions) >= 1000:
                    sessions.pop(min(sessions, key=lambda key: sessions[key]['at']))
                sessions[sid] = {'response_id': result.response_id, 'at': monotonic(), 'identity': identity}
            response.set_cookie('imj_session', sid, httponly=True, samesite='strict', secure=request.url.scheme == 'https', path='/api', max_age=3600)
            answer = asdict(result)
            answer.pop('response_id')
            return {**answer, 'mode': 'ai', 'demo_data': True, 'records': []}
        except Exception as exc:
            raise HTTPException(502, 'AI 응답을 받지 못했습니다. 잠시 후 다시 시도하거나 데모 조회를 이용해 주세요.') from exc
        finally:
            client.close()
            capacity.release()

    @app.post('/api/voice/transcribe')
    def transcribe(file: UploadFile, authorization: str | None = Header(default=None)):
        client = require_ai(authorization)
        try:
            content = file.file.read(20 * 1024 * 1024 + 1)
            if not content or len(content) > 20 * 1024 * 1024:
                raise HTTPException(413, '녹음 파일은 20MB 이하로 선택해 주세요.')
            result = client.audio.transcriptions.create(model='gpt-4o-mini-transcribe', file=(Path(file.filename or 'recording.webm').name, content, file.content_type), language='ko')
            return {'text': result.text}
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(502, '음성 변환에 실패했습니다. 텍스트 질문을 이용해 주세요.') from exc
        finally:
            client.close()

    @app.post('/api/voice/speak')
    def speak(body: Speech, authorization: str | None = Header(default=None)):
        client = require_ai(authorization)
        try:
            from imjingang_agent.voice import VoiceService
            return Response(VoiceService(client).speak(body.text), media_type='audio/mpeg')
        except Exception as exc:
            raise HTTPException(502, '음성 재생 파일을 만들지 못했습니다.') from exc
        finally:
            client.close()

    dist = static_dir or ROOT / 'v2/web/dist'
    if dist.exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/')
        def index():
            return FileResponse(dist / 'index.html')
    return app


app = create_app()
