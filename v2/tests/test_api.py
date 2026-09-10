from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from imjingang_agent import ImjingangRepository
from v2.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    monkeypatch.delenv('COCKPIT_ACCESS_TOKEN', raising=False)
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
            with TestClient(create_app(repo)) as client:
                workspace = client.get('/api/workspace').json()
                assert workspace['meta']['backend'] == 'PostgreSQL + pgvector'
                assert len(client.get('/api/documents').json()) == 10
                assert len(client.get('/api/lots/PACK-260903-001').json()['trace']) == 6
                assert client.post('/api/chat', json={'question':'율무 재고 부족량'}).json()['records'][0]['item_code'] == 'R002'
            reopened = PostgresRepository(url)
            assert len(reopened.knowledge_documents()) == 10
            assert len(reopened.get_rules()) == 7
        finally:
            admin.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(name)))
