import io
import json

import pytest

from v3.aws import AgentCoreClient, AgentCoreError
from v3.backends.agentcore import AgentCoreBackend
from v3.contracts import AgentRequest


def request():
    return AgentRequest(question="LOT 확인", session_id="session-1234567890", lot_id=None)


class FakeClient:
    kwargs = None
    def invoke_agent_runtime(self, **kwargs):
        self.kwargs = kwargs
        return {"response": io.BytesIO(json.dumps({
            "text": "확인했습니다.", "sources": [], "evidence": [], "data_tools": [], "records": [],
            "searched_documents": False,
        }, ensure_ascii=False).encode())}


def test_client_invokes_runtime_with_session():
    fake = FakeClient()
    client = AgentCoreClient("arn:aws:bedrock-agentcore:ap-northeast-2:123:runtime/test", "ap-northeast-2", qualifier="ImjingangV3Live", client=fake)
    result = client.invoke(request())
    assert result["text"] == "확인했습니다."
    assert fake.kwargs["qualifier"] == "ImjingangV3Live"
    assert fake.kwargs["contentType"] == "application/json"
    assert fake.kwargs["accept"] == "application/json"


def test_backend_normalizes_platform_metadata():
    class Wrapped:
        def invoke(self, value):
            return {"text": "ok"}
    result = AgentCoreBackend(Wrapped(), "ap-northeast-2", "model-id").ask(request())
    assert result.mode == "agentcore"
    assert result.region == "ap-northeast-2"
    assert result.model == "model-id"


def test_client_sanitizes_runtime_errors():
    class Broken:
        def invoke_agent_runtime(self, **kwargs):
            raise TimeoutError("secret endpoint")
    with pytest.raises(AgentCoreError, match="시간이 초과") as error:
        AgentCoreClient("secret-arn", "ap-northeast-2", client=Broken()).invoke(request())
    assert "secret" not in str(error.value)
