from datetime import date
from io import BytesIO
import zipfile,xml.etree.ElementTree as ET
from fastapi.testclient import TestClient
from imjingang_agent import ImjingangRepository
from v2.api import create_app
from v2 import reports

def test_date_intent():
    assert reports.requested_date('2026년 9월 20일 일일생산보고서 만들어줘')==date(2026,9,20)
    assert reports.requested_date('일일생산보고서 만들어줘') is None

def test_daily_exports(tmp_path):
    repo=ImjingangRepository(tmp_path/'report.db')
    with TestClient(create_app(repo)) as c:
        result=c.post('/api/chat',json={'question':'2026년 9월 20일 일일생산보고서 만들어줘','mode':'ai'})
        assert result.status_code==200,result.text
        data=result.json()['report'];assert data['good_kg']==3913.5
        rid=data['report_id'];xlsx=c.get(f'/api/reports/{rid}/xlsx');pdf=c.get(f'/api/reports/{rid}/pdf')
        assert xlsx.status_code==pdf.status_code==200
        assert pdf.content.startswith(b'%PDF')
        root=ET.fromstring(zipfile.ZipFile(BytesIO(xlsx.content)).read('xl/worksheets/sheet1.xml'))
        ns={'s':reports.NS};cells={x.get('r'):x for x in root.findall('.//s:c',ns)}
        assert cells['G63'].findtext('s:v',namespaces=ns)=='3913.5'
        assert cells['N48'].findtext('s:f',namespaces=ns)=='K48*H48'
        assert not root.findall('.//s:c[@t="e"]',ns)
        with repo._connect() as conn:conn.execute("UPDATE report_sample_production SET good_kg=999 WHERE record_id='IMJ-SMP-R100'")
        assert c.get(f'/api/reports/{rid}/xlsx').content==xlsx.content
        assert c.post('/api/reports/daily-production',json={'business_date':'2026-09-20'}).status_code==422
        assert c.post('/api/chat',json={'question':'일일생산보고서 만들어줘'}).json()['report_picker']
        assert c.post('/api/chat',json={'question':'2026-09-31 일일생산보고서'}).status_code==422
        assert c.post('/api/chat',json={'question':'2026-09-01부터 2026-09-20까지 일일생산보고서'}).status_code==422
        assert c.post('/api/reports/daily-production',json={'business_date':'2027-01-01'}).status_code==404
        assert c.get('/api/reports/not-an-id/pdf').status_code==404
        assert c.post('/api/chat',json={'question':'2026-09-01 일일생산보고서','lot_id':'PACK-260903-001'}).status_code==422
        with repo._connect() as conn:conn.execute('UPDATE daily_report_exports SET owner_id=? WHERE report_id=?',('other-user',rid))
        assert c.get(f'/api/reports/{rid}/pdf').status_code==404

def test_pogi_template_does_not_keep_previous_day(tmp_path):
    repo=ImjingangRepository(tmp_path/'pogi.db');data=reports.snapshot(repo,date(2026,9,1))
    root=ET.fromstring(zipfile.ZipFile(BytesIO(reports.xlsx(data))).read('xl/worksheets/sheet1.xml'));ns={'s':reports.NS}
    cells={x.get('r'):x for x in root.findall('.//s:c',ns)}
    assert cells['N12'].findtext('s:v',namespaces=ns)=='20.0'
    assert cells['N48'].find('s:v',ns) is None
