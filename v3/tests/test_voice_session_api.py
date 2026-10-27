from fastapi.testclient import TestClient

from v3.api import create_app
from v3.config import V3Settings


SIGNED_URL = "wss://bedrock-agentcore.ap-northeast-2.amazonaws.com/runtimes/test/ws?X-Amz-Signature=redacted"


class FakeSigner:
    def create_url(self, session_id=None):
        assert session_id and len(session_id) == 48
        return SIGNED_URL


def test_voice_session_is_disabled_by_default(client):
    response = client.post("/api/voice/session", json={})
    assert response.status_code == 404
    assert client.get("/api/workspace").json()["meta"]["voice_enabled"] is False


def test_voice_session_returns_short_lived_signed_url(repository):
    settings = V3Settings(voice_enabled=True, voice_runtime_arn="arn:aws:bedrock-agentcore:ap-northeast-2:123:runtime/voice")
    with TestClient(create_app(repository, settings, voice_signer=FakeSigner())) as client:
        response = client.post("/api/voice/session", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["url"] == SIGNED_URL
        assert data["expires_in"] == 60
        assert len(data["session_id"]) == 48


def test_voice_session_rejects_unknown_lot(repository):
    settings = V3Settings(voice_enabled=True, voice_runtime_arn="arn:aws:bedrock-agentcore:ap-northeast-2:123:runtime/voice")
    with TestClient(create_app(repository, settings, voice_signer=FakeSigner())) as client:
        assert client.post("/api/voice/session", json={"lot_id": "PACK-991231-999"}).status_code == 404
