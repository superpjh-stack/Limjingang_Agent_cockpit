from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from imjingang_agent import ImjingangRepository
from v2.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)
    monkeypatch.delenv('V2_LOCAL_AI_NO_TOKEN', raising=False)
    repo = ImjingangRepository(tmp_path / 'v2.db')
    with TestClient(create_app(repo)) as client:
        yield client


def test_workspace_returns_real_counts_and_no_credentials(client):
    data = client.get('/api/workspace').json()
    assert data['kpi']['packed_kg'] == 9600
    assert len(data['lots']) == 7
    assert len(data['rules']) == 7
    assert not data['meta']['ai_configured']
    assert client.get('/api/health').json()['status'] == 'ok'
    assert not any(k in str(data) for k in ['OPENAI_API_KEY', 'DATABASE_URL', 'COCKPIT_ACCESS_TOKEN'])


def test_lot_and_query_boundaries(client):
    detail = client.get('/api/lots/PACK-260903-001').json()
    assert detail['trace'][0]['lot_id'] == 'RAW-260901-001'
    assert len(detail['measurements']) == 3
    assert client.get('/api/lots/unknown').status_code == 404
    assert client.get('/api/tables/app_settings').status_code == 400
    assert client.get('/api/tables/lots?limit=101').status_code == 422
    assert client.get('/api/tables/lots?offset=-1').status_code == 422
    assert client.get('/api/tables/lots?limit=2&offset=2').json() != client.get('/api/tables/lots?limit=2').json()


def test_demo_chat_retrieves_trace_and_evidence_without_provider(client):
    result = client.post('/api/chat', json={'question': 'PACK-260903-001을 원재료까지 추적해줘'}).json()
    assert result['mode'] == 'demo'
    assert result['records'][0]['lot_id'] == 'RAW-260901-001'
    assert result['evidence'] and result['searched_documents']
    assert 'get_lot_trace' in result['data_tools']
    assert client.post('/api/chat', json={'question':'  '}).status_code == 422
    assert client.post('/api/chat', json={'question':'x','mode':'write'}).status_code == 422
    assert client.post('/api/chat', json={'question':'x'*2001}).status_code == 422


def test_demo_stock_and_historical_time_disclosure(client):
    result = client.post('/api/chat', json={'question':'오늘 율무 재고 부족량은?'}).json()
    assert '80kg' in result['text']
    assert '오늘의 실시간 기록은 없습니다' in result['text']
    assert result['records'][0]['item_code'] == 'R002'


def test_documents_rules_linkage_and_empty_search(client):
    docs = client.get('/api/documents').json()
    ids = {d['document_id'] for d in docs}
    rules = client.get('/api/workspace').json()['rules']
    assert len(docs) == 10
    assert all(r['source_document'] in ids for r in rules)
    assert client.get('/api/documents?q=절임').json()
    assert client.get('/api/documents?q=xyzxyzxyz').json() == []
    assert all('embedding' not in d for d in docs)


def test_paid_api_gate_and_configuration_secrecy(client, monkeypatch):
    assert client.post('/api/chat', json={'question':'발효','mode':'ai'}).status_code == 503
    monkeypatch.setenv('OPENAI_API_KEY','sk-test-must-not-leak')
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN','private-test-code')
    meta = client.get('/api/workspace').json()['meta']
    assert meta['ai_configured']
    assert 'private-test-code' not in str(meta) and 'sk-test-must-not-leak' not in str(meta)
    assert client.post('/api/chat', json={'question':'발효','mode':'ai'}).status_code == 401
    assert client.post('/api/voice/speak', json={'text':'발효'}, headers={'Authorization':'Bearer wrong'}).status_code == 401
    assert client.post('/api/chat/reset').json()['status'] == 'ok'


def test_realtime_voice_session_is_gated_and_uses_verified_lot_context(client, monkeypatch):
    assert client.post('/api/realtime/session', content='offer', headers={'Content-Type':'application/sdp'}).status_code == 503
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-test-realtime-secret')
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN', 'voice-code')
    captured = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured['client'] = kwargs
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def post(self, url, **kwargs):
            captured['url'] = url
            captured['request'] = kwargs
            return httpx.Response(200, text='answer-sdp')

    monkeypatch.setattr('v2.api.httpx.AsyncClient', FakeAsyncClient)
    headers = {'Content-Type':'application/sdp', 'Authorization':'Bearer voice-code'}
    response = client.post('/api/realtime/session?lot_id=PACK-260903-001', content='offer-sdp', headers=headers)
    assert response.status_code == 200
    assert response.text == 'answer-sdp'
    assert response.headers['content-type'].startswith('application/sdp')
    assert captured['url'] == 'https://api.openai.com/v1/realtime/calls'
    assert captured['request']['headers']['Authorization'] == 'Bearer sk-test-realtime-secret'
    assert 'sk-test-realtime-secret' not in response.text
    session = captured['request']['files']['session'][1]
    assert 'PACK-260903-001' in session
    assert 'semantic_vad' in session and 'gpt-realtime-2.1' in session
    assert client.post('/api/realtime/session?lot_id=UNKNOWN', content='offer', headers=headers).status_code == 404
    assert client.post('/api/realtime/session', content='offer', headers={'Content-Type':'application/sdp','Authorization':'Bearer wrong'}).status_code == 401


def test_local_development_can_use_server_ai_without_browser_token(client, monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-local-test')
    monkeypatch.setenv('V2_LOCAL_AI_NO_TOKEN', '1')
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)
    captured = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            return None
        async def post(self, url, **kwargs):
            captured['authorization'] = kwargs['headers']['Authorization']
            return httpx.Response(200, text='local-answer-sdp')

    monkeypatch.setattr('v2.api.httpx.AsyncClient', FakeAsyncClient)
    meta = client.get('/api/workspace').json()['meta']
    assert meta['ai_configured'] is True
    assert meta['local_dev_ai'] is True
    response = client.post('/api/realtime/session', content='offer', headers={'Content-Type':'application/sdp'})
    assert response.status_code == 200
    assert response.text == 'local-answer-sdp'
    assert captured['authorization'] == 'Bearer sk-local-test'


def test_production_frontend_entrypoint(client):
    assert client.get('/').status_code == 200
    assert '<html lang="ko"' in client.get('/').text
    assert client.get('/api/not-a-route').status_code == 404


def test_postgres_v2_workspace_and_reopen(monkeypatch):
    import os
    import uuid
    from imjingang_agent.data_hub import PostgresRepository
    admin_url = os.getenv('TEST_POSTGRES_ADMIN_URL')
    if not admin_url:
        pytest.skip('Set TEST_POSTGRES_ADMIN_URL for PostgreSQL integration')
    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    name = 'imj_v2_test_' + uuid.uuid4().hex
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        try:
            url = make_conninfo(admin_url, dbname=name)
            repo = PostgresRepository(url)
            monkeypatch.delenv('V2_REQUIRE_LOGIN', raising=False)
            app = create_app(repo)
            with TestClient(app) as client:
                workspace = client.get('/api/workspace').json()
                assert workspace['meta']['backend'] == 'PostgreSQL + pgvector'
                assert len(client.get('/api/documents').json()) == 10
                assert len(client.get('/api/lots/PACK-260903-001').json()['trace']) == 6
                assert client.post('/api/chat', json={'question': '율무 재고 부족량'}).json()['records'][0]['item_code'] == 'R002'
                # v2 tables (users, sessions, work, answers, journey events) must work on PostgreSQL too.
                app.state.work.add_user('admin', 'admin', 'factory-a', 'admin', 'test-password-123!')
                assert client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong'}).status_code == 401
                assert client.post('/api/auth/login', json={'username': 'admin', 'password': 'test-password-123!'}).status_code == 200
                answer = client.post('/api/chat', json={'question': 'CCP 근거를 확인해줘', 'lot_id': 'PACK-260903-001'}).json()
                item = client.post('/api/work-items', json={'request_id': str(uuid.uuid4()), 'title': '포장 LOT 검토',
                                                            'lot_id': 'PACK-260903-001', 'note': '현장 확인', 'answer_id': answer['answer_id']}).json()
                assert item['snapshot']['answer']['records']
                assert client.get('/api/work-items/' + item['id']).json()['version'] == item['version']
                journey = item['id']
                assert client.post('/api/events', json={'events': [
                    {'event': 'task_saved', 'journey_id': journey, 'device': 'mobile'},
                    {'event': 'task_resumed', 'journey_id': journey, 'device': 'desktop'}]}).status_code == 204
                report = client.get('/api/metrics').json()
                assert report['devices']['mobile']['journey_completion_rate'] == 1
            reopened = PostgresRepository(url)
            assert len(reopened.knowledge_documents()) == 10
            assert len(reopened.get_rules()) == 7
            with reopened._connect() as c:
                assert len(c.execute('SELECT * FROM v2_journey_events').fetchall()) == 2
                assert c.execute('SELECT COUNT(*) FROM v2_work').fetchone()[0] == 1
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
