from imjingang_agent import ImjingangRepository
from v3.agent.tools import ALLOWED_TOOLS, ReadOnlyTools


def test_only_read_only_tools_are_exposed(tmp_path):
    tools = ReadOnlyTools(ImjingangRepository(tmp_path / "tools.db"))
    assert {item["name"] for item in tools.definitions} == ALLOWED_TOOLS
    assert "get_table_records" not in ALLOWED_TOOLS


def test_unknown_tool_never_executes(tmp_path):
    tools = ReadOnlyTools(ImjingangRepository(tmp_path / "tools.db"))
    result = tools.execute("run_sql", {"query": "DROP TABLE lots"})
    assert "허용되지 않은" in result["error"]
