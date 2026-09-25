from types import SimpleNamespace

import pytest

from imjingang_agent import ImjingangRepository, ImjingangToolRegistry, ManufacturingAgent


class FakeResponses:
    def __init__(self):
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if len(self.requests) == 1:
            call = SimpleNamespace(type="function_call", name="get_fermentation_status", arguments='{"lot_id":null}', call_id="call_1")
            return SimpleNamespace(id="resp_1", output_text="", output=[call])
        return SimpleNamespace(id="resp_2", output_text="FERM-260903-002는 시제품 위험도가 높습니다.", output=[])


class FakeClient:
    def __init__(self):
        self.responses = FakeResponses()
        self.vector_stores = SimpleNamespace()


def test_agent_executes_fermentation_tool(tmp_path):
    registry = ImjingangToolRegistry(ImjingangRepository(tmp_path / "factory.db"))
    answer = ManufacturingAgent(FakeClient(), factory_tools=registry).ask("발효 위험 LOT는?")
    assert answer.data_tools == ["get_fermentation_status"]
    assert "FERM-260903-002" in answer.text


def test_agent_rejects_blank_question(tmp_path):
    registry = ImjingangToolRegistry(ImjingangRepository(tmp_path / "factory.db"))
    with pytest.raises(ValueError):
        ManufacturingAgent(FakeClient(), factory_tools=registry).ask(" ")

