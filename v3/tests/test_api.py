def test_health_identifies_isolated_v3(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["version"] == "3.0.0"
    assert response.json()["backend"] == "demo"


def test_workspace_exposes_agentcore_metadata(client):
    data = client.get("/api/workspace").json()
    assert data["meta"]["version"] == "3.0.0"
    assert data["meta"]["region"] == "ap-northeast-2"
    assert data["meta"]["agent_platform"] == "로컬 결정형 데모"


def test_demo_chat_returns_evidence_and_session_cookie(client):
    response = client.post("/api/chat", json={"question": "PACK-260903-001 출하 확인사항"})
    assert response.status_code == 200
    answer = response.json()
    assert answer["mode"] == "demo"
    assert "get_lot_trace" in answer["data_tools"]
    assert "get_shipment_readiness" in answer["data_tools"]
    assert answer["session_id"]
    assert "imj_v3_session" in response.cookies


def test_chat_rejects_conflicting_lots(client):
    response = client.post("/api/chat", json={"question": "PACK-260903-001 확인", "lot_id": "PACK-260904-001"})
    assert response.status_code == 422


def test_unknown_lot_is_not_assumed_healthy(client):
    response = client.post("/api/chat", json={"question": "PACK-991231-999 확인"})
    assert response.status_code == 404


def test_arbitrary_table_is_rejected(client):
    response = client.get("/api/tables/sqlite_master")
    assert response.status_code == 400


def test_default_repository_boots_without_injected_fixture(tmp_path):
    from fastapi.testclient import TestClient
    from v3.api import create_app
    from v3.config import V3Settings

    settings = V3Settings(sqlite_path=str(tmp_path / "standalone.db"))
    with TestClient(create_app(settings=settings)) as standalone:
        assert standalone.get("/api/health").json()["status"] == "ok"
