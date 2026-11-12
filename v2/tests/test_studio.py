import pytest
from imjingang_agent import ImjingangRepository
from v2.studio import StudioRequest,build_studio
from fastapi.testclient import TestClient
from v2.api import create_app

@pytest.fixture
def repo(tmp_path):
    return ImjingangRepository(tmp_path/'studio.db')

@pytest.mark.parametrize('mode',['detective','journey'])
def test_scope_and_evidence(repo,mode):
    with pytest.raises(ValueError):build_studio(repo,StudioRequest(mode=mode))
    with pytest.raises(ValueError):build_studio(repo,StudioRequest(mode=mode,lot_id='missing'))
    result=build_studio(repo,StudioRequest(mode=mode,lot_id='PACK-260903-001'))
    ids={r['lot_id'] for r in repo.lot_trace('PACK-260903-001')}
    for e in result['evidence']:assert e['record']['lot_id'] in ids
    references={e['id'] for e in result['evidence']}
    for card in result['cards']:
        assert set(card['evidence_ids'])<=references
        if card['kind']=='creative':assert not card['evidence_ids']
    assert len(result['pipeline'])==3
    assert '샘플' in result['source_notice']

def test_ideas_and_irrelevant_lot(repo):
    body=StudioRequest(mode='ideas',audience='캠핑 고객',lot_id='not-a-lot')
    result=build_studio(repo,body)
    assert len([c for c in result['cards'] if c['kind']=='creative'])==3
    assert result['generation']=='guided'
    assert all(e['kind']=='등록 제품·재고' for e in result['evidence'])

def test_partial_failure_disclosed(repo,monkeypatch):
    def fail(*args):raise RuntimeError('db offline')
    monkeypatch.setattr(repo,'ccp_deviations',fail)
    result=build_studio(repo,StudioRequest(mode='briefing'))
    assert result['warnings'] and 'CCP' in result['warnings'][0]
    assert '실시간 현황은 아닙니다' in result['speech']

def test_api_validation_and_auth(repo,monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    with TestClient(create_app(repo)) as client:
        assert client.post('/api/v3/studio',json={'mode':'detective'}).status_code==422
        assert client.post('/api/v3/studio',json={'mode':'unsafe'}).status_code==422
        assert client.post('/api/v3/studio',json={'mode':'briefing'}).status_code==200
        assert client.post('/api/v3/studio',json={'mode':'ideas','use_ai':True}).status_code!=200

def test_invalid_ai_response_not_silently_guided(repo):
    class Fake:
        output_text='{"ideas":[]}'
        responses=None
        def with_options(self,**kw):self.responses=self;return self
        def create(self,**kw):return self
    with pytest.raises(ValueError):build_studio(repo,StudioRequest(mode='ideas'),Fake(),'fake')
