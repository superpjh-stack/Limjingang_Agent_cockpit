import json
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from v2.api import create_app, EvidenceRegistry
from imjingang_agent import ImjingangRepository
from v2.compound import analyze, resolve_lot, comparison_tables


def test_context_uses_user_history_and_rejects_ambiguity():
    history=[{'role':'user','text':'PACK-260903-001 상태'},{'role':'assistant','text':'FERM-260903-002'}]
    assert resolve_lot('그 LOT 품질은?',None,history)=='PACK-260903-001'
    with pytest.raises(ValueError):resolve_lot('그 LOT 품질은?',None,history[1:])
    with pytest.raises(ValueError):resolve_lot('FERM-260903-002 조회','PACK-260903-001',history)


def test_verification_requires_actual_quote_and_valid_evidence_and_retries_once():
    class Model:
        responses=None
        def __init__(self):self.responses=self
        def with_options(self,**kwargs):return self
        def create(self,**kwargs):
            payload=json.loads(kwargs['input'])
            if 'requests' not in payload:return SimpleNamespace(output_text=json.dumps({'parts':[{'request':'생산','quote':'생산'},{'request':'품질','quote':'품질'},{'request':'우선순위','quote':'원문에 없는 요청'}]}))
            return SimpleNamespace(output_text=json.dumps({'checks':[{'request':'생산','quote':'확인됨','evidence_indices':[0]},{'request':'품질','quote':'없는 문장','evidence_indices':[0]}],'voice_summary':'생산 기록을 확인했습니다. 품질은 추가 확인이 필요합니다.'}))
    calls=[]
    def retrieve(q,parts):
        calls.append(parts)
        return {'text':'생산 확인됨','records':[{'unit':'식','quantity':0}],'evidence':[]}
    result=analyze('생산과 품질 비교',[],retrieve,Model(),'test')
    assert len(calls)==2
    assert result['partial'] is True
    assert [c['status'] for c in result['request_coverage']]==['unconfirmed','answered','unconfirmed']
    assert result['voice_summary'].startswith('생산 기록')


def test_comparison_preserves_zero_missing_and_units():
    tables=comparison_tables([{'quantity':0,'unit':'식'},{'quantity':None,'unit':'kg'}])
    assert tables[0]['rows']==[['0','식'],['미확인','kg']]


def test_api_question_groups_followup_and_reset(tmp_path,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with TestClient(create_app(ImjingangRepository(tmp_path/'test.db'))) as client:
        groups=client.get('/api/workspace').json()['questions']
        assert list(map(len,groups.values()))==[10,10,10]
        assert all(not q.startswith('니즈,') for qs in groups.values() for q in qs)
        response=client.post('/api/chat',json={'question':'그 LOT 조리와 품질을 함께 알려줘','history':[{'role':'user','text':'FERM-260903-002'}]})
        assert response.status_code==200
        assert response.json()['context']['lot_id']=='FERM-260903-002'
        assert response.json()['engine']=='langgraph'
        assert response.json()['comparison_tables']
        client.post('/api/chat/reset')
        assert client.post('/api/chat',json={'question':'그 LOT 조리는?'}).status_code==422


def test_voice_tool_routes_to_same_graph(tmp_path,monkeypatch):
    from imjingang_agent.service import AgentAnswer
    monkeypatch.setenv('OPENAI_API_KEY','test-only')
    monkeypatch.setenv('COCKPIT_ACCESS_TOKEN','test-code')
    monkeypatch.setattr('v2.api.ManufacturingAgent.ask', lambda *a,**k: AgentAnswer(text='재고 근거를 확인했습니다.',sources=[],evidence=[],response_id=None,data_tools=[]))
    with TestClient(create_app(ImjingangRepository(tmp_path/'voice.db'))) as client:
        response=client.post('/api/realtime/tool',headers={'Authorization':'Bearer test-code'},json={'name':'analyze_manufacturing_question','arguments':{'question':'재고 비교','lot_id':None,'history':[]}})
        assert response.status_code==200
        result=json.loads(response.json()['output'])
        assert result['engine']=='langgraph' and result['records']
        assert result['voice_summary']


def test_selected_lot_cannot_expand_to_unrelated_records(tmp_path):
    repo=ImjingangRepository(tmp_path/'scope.db')
    registry=EvidenceRegistry(repo,'PACK-260903-001')
    related={r['lot_id'] for r in repo.lot_trace('PACK-260903-001')}
    result=json.loads(registry.execute('get_process_measurements',{'lot_id':'FERM-260903-002'}))
    assert result['status']=='ok'
    assert all(r['lot_id'] in related for r in result['result'])
    assert result['demo_data'] is True and '샘플' in result['source']
    assert 'error' in json.loads(registry.execute('get_inventory_status',{'item':None,'shortage_only':False}))
    assert {d['name'] for d in registry.definitions} <= {'get_lot_trace','get_fermentation_status','get_ccp_deviations','get_shipment_readiness','get_process_measurements','search_knowledge','get_rules'}
