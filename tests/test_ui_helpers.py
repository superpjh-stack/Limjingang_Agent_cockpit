from imjingang_agent import ImjingangRepository, QUESTION_GROUPS, lot_snapshot, risk_label, user_question_history

def test_cockpit_helpers(tmp_path):
    repo=ImjingangRepository(tmp_path/"demo.db")
    snap=lot_snapshot(repo,"PACK-260903-001")
    assert snap["trace"][0]["process"]=="원재료 입고"
    assert snap["trace"][-1]["process"]=="포장"
    assert risk_label(snap)[0] in {"안정","주의","높음"}
    assert set(QUESTION_GROUPS) == {"지식베이스", "DB", "룰"}
    assert all(len(items) == 10 for items in QUESTION_GROUPS.values())
    assert user_question_history([{"role":"user","content":"LOT","created_at":"10:00"}])[0]["content"]=="LOT"
