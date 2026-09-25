import uuid

import pytest
from fastapi.testclient import TestClient

from imjingang_agent import ImjingangRepository
from v2.api import create_app


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.delenv('V2_REQUIRE_LOGIN', raising=False)
    repo = ImjingangRepository(tmp_path / 'work.db')
    app = create_app(repo)
    with TestClient(app) as client:
        store = app.state.work
        people = {name: store.add_user(name, name, org, role, 'test-password-123!') for name, org, role in (
            ('operator', 'factory-a', 'operator'), ('reviewer', 'factory-a', 'reviewer'), ('outsider', 'factory-b', 'admin'))}
        yield client, app, people


def login(client, name):
    response = client.post('/api/auth/login', json={'username': name, 'password': 'test-password-123!'})
    assert response.status_code == 200
    return response.json()['user']


def create(client, answer=None):
    payload = {'request_id': str(uuid.uuid4()), 'title': '포장 LOT 검토', 'lot_id': 'PACK-260903-001', 'note': '현장 확인 필요'}
    if answer:
        payload['answer_id'] = answer['answer_id']
    result = client.post('/api/work-items', json=payload)
    assert result.status_code == 200, result.text
    return result.json(), payload


def change(client, item, action, **kwargs):
    return client.patch('/api/work-items/' + item['id'], json={'expected_version': item['version'], 'request_id': str(uuid.uuid4()), 'action': action, **kwargs})


def test_login_session_cookie_csrf_and_logout(environment):
    client, app, people = environment
    assert client.get('/api/work-items').status_code == 401
    assert client.post('/api/auth/login', json={'username': 'operator', 'password': 'wrong'}).status_code == 401
    login(client, 'operator')
    assert client.get('/api/auth/me').json()['user']['id'] == people['operator']
    assert 'password' not in str(client.get('/api/users').json())
    assert all(u['organization'] == 'factory-a' for u in client.get('/api/users').json())
    assert client.post('/api/auth/logout', headers={'Origin': 'https://attacker.example'}).status_code == 403
    assert client.post('/api/auth/logout').status_code == 200
    assert client.get('/api/work-items').status_code == 401


def test_snapshot_is_server_owned_immutable_and_persistent(environment):
    client, app, people = environment
    login(client, 'operator')
    answer = client.post('/api/chat', json={'question': 'CCP 근거를 확인해줘', 'lot_id': 'PACK-260903-001'}).json()
    item, payload = create(client, answer)
    assert item['snapshot']['answer']['records']
    assert client.post('/api/work-items', json=payload).json()['id'] == item['id']
    with app.state.repo._connect() as c:
        c.execute("UPDATE lots SET product_name='changed' WHERE lot_id='PACK-260903-001'")
    assert client.get('/api/work-items/' + item['id']).json()['snapshot'] == item['snapshot']
    with TestClient(create_app(app.state.repo)) as second_device:
        login(second_device, 'operator')
        assert second_device.get('/api/work-items/' + item['id']).json()['snapshot'] == item['snapshot']
    login(client, 'outsider')
    assert client.get('/api/work-items/' + item['id']).status_code == 404
    assert client.post('/api/work-items', json={**payload, 'request_id': str(uuid.uuid4())}).status_code == 404


def test_handoff_acknowledgement_completion_and_conflicts(environment):
    client, app, people = environment
    login(client, 'operator')
    item, _ = create(client)
    assert change(client, item, 'complete', text='검토 완료').status_code == 403
    assert change(client, item, 'handoff', text='검토 요청', recipient_id=people['outsider']).status_code == 422
    transferred = change(client, item, 'handoff', text='CCP 기록 추가 확인', recipient_id=people['reviewer']).json()
    assert transferred['status'] == '인계 대기'
    assert change(client, transferred, 'note', text='다른 담당자의 업무').status_code == 403
    login(client, 'reviewer')
    assert change(client, transferred, 'complete', text='검토 결과').status_code == 409
    acknowledged = change(client, transferred, 'acknowledge').json()
    assert acknowledged['status'] == '검토 대기'
    assert change(client, transferred, 'note', text='낡은 버전').status_code == 409
    before = app.state.repo.shipment_readiness(None)
    completed = change(client, acknowledged, 'complete', text='근거 확인, 추가 검사 필요').json()
    assert completed['status'] == '검토 완료'
    assert app.state.repo.shipment_readiness(None) == before
    assert len(completed['events']) == 4


def test_mutation_idempotency_and_validation(environment):
    client, app, people = environment
    login(client, 'reviewer')
    item, payload = create(client)
    mutation = {'expected_version': 1, 'request_id': str(uuid.uuid4()), 'action': 'note', 'text': '동일 요청'}
    first = client.patch('/api/work-items/' + item['id'], json=mutation).json()
    assert client.patch('/api/work-items/' + item['id'], json=mutation).json() == first
    assert client.post('/api/work-items', json={**payload,'request_id':str(uuid.uuid4()),'title':' '}).status_code == 422
    assert client.post('/api/work-items', json={**payload,'request_id':str(uuid.uuid4()),'lot_id':'bad'}).status_code == 404
    assert client.post('/api/chat', json={'question':'PACK-260903-001', 'lot_id':'RAW-260901-001'}).status_code == 422
    assert client.post('/api/chat', json={'question':'PACK-000000-000'}).status_code == 404
    assert client.post('/api/chat', json={'question':'확인', 'lot_id':'bad'}).status_code == 404


def test_optional_protected_deployment_and_deep_links(environment, monkeypatch):
    client, app, people = environment
    monkeypatch.setenv('V2_REQUIRE_LOGIN', '1')
    assert client.get('/api/workspace').status_code == 401
    assert client.get('/api/health').status_code == 200
    login(client, 'operator')
    assert client.get('/api/workspace').status_code == 200
    assert client.get('/work/' + str(uuid.uuid4())).status_code == 200
    assert client.get('/api/not-a-route').status_code == 404
    assert client.get('/assets/not-a-file.js').status_code == 404
    assert client.get('/api/work-items').headers['cache-control'] == 'no-store'


def test_login_rate_limit(environment):
    client, _, _ = environment
    for _ in range(10):
        assert client.post('/api/auth/login', json={'username':'operator','password':'wrong'}).status_code == 401
    assert client.post('/api/auth/login', json={'username':'operator','password':'wrong'}).status_code == 429


def test_followup_answers_preserve_prior_evidence(environment):
    client, app, people = environment
    login(client, 'reviewer')
    first = client.post('/api/chat', json={'question':'공정 계보', 'lot_id':'PACK-260903-001'}).json()
    item, _ = create(client, first)
    second = client.post('/api/chat', json={'question':'발효 측정', 'lot_id':item['lot_id'], 'work_id':item['id']}).json()
    response = change(client, item, 'attach_answer', answer_id=second['answer_id'])
    assert response.status_code == 200
    updated = response.json()
    assert len(updated['snapshots']) == 2
    assert updated['snapshots'][0]['answer'] == first
    assert updated['snapshot']['answer'] == second
    assert client.post('/api/chat', json={'question':'확인', 'lot_id':'RAW-260901-001', 'work_id':item['id']}).status_code == 409
    login(client, 'outsider')
    assert client.post('/api/chat', json={'question':'확인', 'lot_id':item['lot_id'], 'work_id':item['id']}).status_code == 404


def test_lot_trace_count_does_not_count_ccp_as_process(environment):
    client, _, _ = environment
    answer = client.post('/api/chat', json={'question':'공정 계보', 'lot_id':'FERM-260903-002'}).json()
    assert '연결 공정 1건' in answer['text']
    assert len(answer['records']) == 2
    assert len(answer['summary']) < 450
