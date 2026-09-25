import uuid

import pytest
from fastapi.testclient import TestClient

from imjingang_agent import ImjingangRepository
from v2.api import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.delenv('V2_REQUIRE_LOGIN', raising=False)
    app = create_app(ImjingangRepository(tmp_path / 'metrics.db'))
    with TestClient(app) as client:
        for name, role in (('admin', 'admin'), ('operator', 'operator')):
            app.state.work.add_user(name, name, 'factory-a', role, 'test-password-123!')
        yield client, app


def send(client, *events):
    return client.post('/api/events', json={'events': list(events)})


def event(name, journey, device='mobile', **kwargs):
    return {'event': name, 'journey_id': journey, 'device': device, **kwargs}


def test_events_reject_free_text_and_unknown_names(client):
    client, app = client
    journey = str(uuid.uuid4())
    assert send(client, event('voice_started', journey)).status_code == 204
    assert send(client, event('voice_started', journey, text='PACK-260903-001 염도 이상')).status_code == 422
    assert send(client, event('page_scrolled', journey)).status_code == 422
    assert send(client, event('answer_ready', journey, duration_ms=-1)).status_code == 422
    assert client.post('/api/events', json={'events': [event('voice_started', journey)] * 21}).status_code == 422
    with app.state.repo._connect() as c:
        stored = [dict(r) for r in c.execute('SELECT * FROM v2_journey_events').fetchall()]
    assert len(stored) == 1 and set(stored[0]) == {'id', 'event', 'journey_id', 'device', 'source', 'mode', 'duration_ms', 'role', 'created_at'}


def test_metrics_are_admin_only_and_split_by_device(client):
    client, _ = client
    mobile, desktop = str(uuid.uuid4()), str(uuid.uuid4())
    send(client,
         event('voice_started', mobile), event('transcript_ready', mobile, duration_ms=4000),
         event('question_submitted', mobile, source='voice', mode='demo'),
         event('answer_ready', mobile, mode='demo', duration_ms=900),
         event('voice_started', mobile), event('voice_cancelled', mobile),
         event('voice_started', mobile), event('transcript_ready', mobile, duration_ms=9000),
         event('task_saved', mobile),
         event('task_opened', desktop, 'desktop', duration_ms=12000),
         event('task_resumed', mobile, 'desktop'))
    assert client.get('/api/metrics').status_code == 401
    client.post('/api/auth/login', json={'username': 'operator', 'password': 'test-password-123!'})
    assert client.get('/api/metrics').status_code == 403
    client.post('/api/auth/login', json={'username': 'admin', 'password': 'test-password-123!'})
    report = client.get('/api/metrics').json()
    phone, pc = report['devices']['mobile'], report['devices']['desktop']
    assert phone['voice_completion_rate'] == 0.5
    assert phone['transcript_p95_s'] == 9
    assert phone['answer_p95_s'] == {'demo': 0.9, 'ai': None}
    assert phone['journey_completion_rate'] == 1
    assert pc['first_task_open_median_s'] == 12
    assert pc['voice_completion_rate'] is None
    assert report['targets']['answer_p95_s'] == 15
