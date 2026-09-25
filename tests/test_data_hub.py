import json

from imjingang_agent import ImjingangRepository, ImjingangToolRegistry


def test_dashboard_capacity_and_alerts(tmp_path):
    repo = ImjingangRepository(tmp_path / "factory.db")
    kpi = repo.dashboard()
    assert kpi["current_capacity_kg"] == 10000
    assert kpi["three_year_target_kg"] == 30000
    assert kpi["fermentation_risks"] == 1


def test_lot_trace_reaches_raw_material(tmp_path):
    repo = ImjingangRepository(tmp_path / "factory.db")
    trace = repo.lot_trace("PACK-260903-001")
    assert [row["process"] for row in trace] == ["원재료 입고", "선별", "세척·절임", "양념·혼합", "발효·숙성", "포장"]


def test_fermentation_prediction_is_labeled_demo(tmp_path):
    repo = ImjingangRepository(tmp_path / "factory.db")
    risky = repo.fermentation_status("FERM-260903-002")[0]
    assert risky["abnormal_risk"] == 0.78
    assert risky["model_status"] == "시제품 데모"


def test_claim_traces_to_source_lot(tmp_path):
    repo = ImjingangRepository(tmp_path / "factory.db")
    result = repo.claim_trace("CLM-260903-01")
    assert result["claim"]["destination"] == "대한민국"
    assert result["lot_trace"][0]["lot_id"] == "RAW-260901-001"


def test_registry_blocks_write_tools(tmp_path):
    registry = ImjingangToolRegistry(ImjingangRepository(tmp_path / "factory.db"))
    allowed = json.loads(registry.execute("get_inventory_status", '{"item":"율무","shortage_only":true}'))
    denied = json.loads(registry.execute("approve_shipment", "{}"))
    assert allowed["data"][0]["stock_status"] == "부족"
    assert "error" in denied

