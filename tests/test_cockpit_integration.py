import json
from types import SimpleNamespace as NS

import pytest
from streamlit.testing.v1 import AppTest

from imjingang_agent import ImjingangRepository, ImjingangToolRegistry, ManufacturingAgent
from imjingang_agent.service import MAX_TOOL_ROUNDS


def test_documents_rules_and_persistence(tmp_path):
    path = tmp_path / 'demo.db'
    repo = ImjingangRepository(path)
    docs = repo.knowledge_documents()
    assert len(docs) == 10
    assert len(repo.get_rules()) == 7
    assert all(rule['source_document'] in {doc['document_id'] for doc in docs} for rule in repo.get_rules())
    assert repo.search_knowledge('절임의 확인 절차')
    repo.save_setting('test', 'persisted')
    assert ImjingangRepository(path).setting('test') == 'persisted'
    assert len(repo.knowledge_documents()) == 10
    with pytest.raises(ValueError):
        repo.table_records('lots; DROP TABLE lots')


def test_shipment_includes_upstream_ccp_and_missing_prediction(tmp_path):
    repo = ImjingangRepository(tmp_path / 'demo.db')
    with repo._connect() as c:
        c.execute("UPDATE ccp_checks SET result='주의' WHERE lot_id='MIX-260902-001'")
        c.execute('DELETE FROM fermentation_predictions')
    shipment = repo.shipment_readiness('PACK-260903-001')[0]
    assert shipment['ccp_alerts'] == 1
    assert shipment['abnormal_risk'] is None
    assert shipment['evidence_status'] == '검사 또는 예측 미확인'


def test_local_evidence_retained_and_hard_cap(tmp_path):
    registry = ImjingangToolRegistry(ImjingangRepository(tmp_path / 'demo.db'))
    requests = []
    def create(**kwargs):
        requests.append(kwargs)
        call = NS(type='function_call', name='search_knowledge', arguments='{"query":"발효"}', call_id=f'call_{len(requests)}')
        return NS(id=f'resp_{len(requests)}', output=[call], output_text='')
    answer = ManufacturingAgent(NS(responses=NS(create=create)), factory_tools=registry).ask('발효 기준은?')
    assert len(requests) == MAX_TOOL_ROUNDS + 1
    assert requests[-1]['tool_choice'] == 'none'
    assert answer.text and answer.evidence and answer.sources and answer.searched_documents
    assert answer.tool_rounds == MAX_TOOL_ROUNDS
    assert json.loads(registry.execute('get_rules', '{}'))['demo_data'] is True


def test_streamlit_render_and_controls(monkeypatch):
    monkeypatch.setenv('OPENAI_API_KEY', '')
    monkeypatch.setenv('DATABASE_URL', '')
    monkeypatch.setenv('POSTGRES_URL', '')
    app = AppTest.from_file('app.py', default_timeout=20).run()
    assert not app.exception
    for _ in range(2):
        next(b for b in app.button if b.label == '새 대화').click().run()
        assert not app.exception
    app.radio(key='recommendation_group').set_value('룰').run()
    assert app.session_state['question_group'] == '룰'
    app.selectbox(key='data_table').select('rules').run()
    app.text_input(key='document_query').set_value('발효').run()
    assert not app.exception
    assert app.session_state['previous_response_id'] is None
    assert len(app.session_state['messages']) == 1
    # Session settings can be reviewed without making network calls.
    next(t for t in app.text_input if t.label == '새 OpenAI API Key').set_value('fake-session-key')
    next(b for b in app.button if b.label == '설정 반영').click().run()
    assert app.session_state['agent_settings']['api_key'] == 'fake-session-key'
    assert not app.exception
