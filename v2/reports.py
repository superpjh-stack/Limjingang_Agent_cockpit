"""Read-only daily reporting: immutable snapshot, template XLSX and printable PDF."""
from datetime import date,datetime,timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import json,re,uuid,zipfile,xml.etree.ElementTree as ET
from fastapi import HTTPException,Request
from fastapi.responses import Response
from pydantic import BaseModel

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
TEMPLATE=Path(__file__).parent/'templates/daily-production.xlsx'
NOTICE='임진강김치 가상 샘플 · 실제 생산 및 승인 기록 아님'
class ReportInput(BaseModel):
    business_date:date

def initialize(repo):
    with repo._connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS daily_report_exports (report_id TEXT PRIMARY KEY, owner_id TEXT, snapshot TEXT NOT NULL)')

def is_daily(question):
    return bool(re.search(r'일일\s*생산\s*(보고서|일지)|일일\s*실적표',question))

def requested_date(question):
    today=datetime.now(ZoneInfo('Asia/Seoul')).date()
    matches=re.findall(r'(20\d{2})\s*(?:년\s*|[-./])(\d{1,2})\s*(?:월\s*|[-./])(\d{1,2})\s*일?',question)
    if len(matches)>1 or any(x in question for x in ['부터','까지','이번 주','이번 달']):
        raise ValueError('일일생산보고서는 하루씩 생성합니다. 날짜 한 개를 선택해 주세요.')
    if matches:return date(*map(int,matches[0]))
    if '어제' in question:return today-timedelta(days=1)
    if '오늘' in question:return today
    return None

def snapshot(repo,day):
    with repo._connect() as c:
        rows=[dict(r) for r in c.execute('''SELECT r.*,p.product_name,p.category FROM report_sample_production r
          JOIN report_sample_products p ON p.product_code=r.product_code
          WHERE r.business_date=? ORDER BY r.record_id''',(day.isoformat(),)).fetchall()]
    if not rows:raise HTTPException(404,f'{day}의 생산자료가 없습니다. 샘플 기간은 2026-09-01~2026-09-20입니다.')
    groups={'포기김치류':[],'기타김치류':[]}
    for r in rows:
        for field in ['good','planned','reject']:
            expected=Decimal(str(r['kg_per_unit']))*r[field+'_ea']
            if expected!=Decimal(str(r[field+'_kg'])):raise HTTPException(422,'수량과 규격의 환산값이 일치하지 않습니다. 원본을 확인하세요.')
        groups['포기김치류' if '포기' in r['category'] else '기타김치류'].append(r)
    if len(groups['포기김치류'])>17 or len(groups['기타김치류'])>6:
        raise HTTPException(422,'현재 양식의 행 수를 초과했습니다. 보고서 분할이 필요합니다.')
    total=lambda field:float(sum((Decimal(str(r[field])) for r in rows),Decimal(0)))
    planned=total('planned_kg');good=total('good_kg')
    return {'report_id':uuid.uuid4().hex,'business_date':day.isoformat(),'created_at':datetime.now(ZoneInfo('Asia/Seoul')).isoformat(),
        'title':'임진강김치 일일생산보고서','notice':NOTICE,'rows':rows,'groups':groups,
        'planned_kg':planned,'good_kg':good,'reject_kg':total('reject_kg'),'achievement':round(good/planned*100,2) if planned else None,
        'missing':['근무인원·근무시간','환경온도·금속검출 판정','반제품 사용량·혼합 LOT','작성·검토·승인 담당자']}

def create_report(repo,day,owner=None):
    data=snapshot(repo,day)
    with repo._connect() as c:c.execute('INSERT INTO daily_report_exports VALUES (?,?,?)',(data['report_id'],owner,json.dumps(data,ensure_ascii=False)))
    return data

def chat_report(repo,question,owner=None,lot=None):
    if lot:raise HTTPException(422,'일일생산보고서는 전체 제품 기준입니다. LOT 선택을 해제하고 요청해 주세요.')
    try:day=requested_date(question)
    except ValueError as e:raise HTTPException(422,str(e))
    data=create_report(repo,day,owner) if day else None
    return {'text':f"{day} 일일생산보고서를 생성했습니다. 양품 {data['good_kg']:,.2f}kg · {NOTICE}" if data else '보고서 날짜를 선택해 주세요. 샘플 자료는 2026년 9월 1~20일에 있습니다.',
        'report':data,'report_picker':not bool(data),'sources':[],'evidence':[],'data_tools':['daily_production_report'],'records':data['rows'] if data else [],'searched_documents':False,'mode':'demo','demo_data':True}

def xlsx(data):
    ns={'s':NS};source=zipfile.ZipFile(TEMPLATE);root=ET.fromstring(source.read('xl/worksheets/sheet1.xml'))
    sheet=root.find('s:sheetData',ns)
    def put(address,value,formula=None):
        n=int(re.search(r'\d+',address)[0]);row=next((r for r in sheet if r.get('r')==str(n)),None)
        if row is None:row=ET.SubElement(sheet,f'{{{NS}}}row',{'r':str(n)})
        cell=next((c for c in row if c.get('r')==address),None)
        if cell is None:cell=ET.SubElement(row,f'{{{NS}}}c',{'r':address})
        for child in list(cell):cell.remove(child)
        cell.attrib.pop('t',None)
        if value is None:return
        if isinstance(value,(int,float)):
            if formula:ET.SubElement(cell,f'{{{NS}}}f').text=formula
            ET.SubElement(cell,f'{{{NS}}}v').text=str(value)
        else:
            cell.set('t','inlineStr');ET.SubElement(ET.SubElement(cell,f'{{{NS}}}is'),f'{{{NS}}}t').text=str(value)
    day=date.fromisoformat(data['business_date'])
    put('E3',f'{day.year}년');put('H3',(day-date(1899,12,30)).days);put('N3',['월','화','수','목','금','토','일'][day.weekday()]+'요일')
    put('B4',NOTICE);put('U2','미지정');put('V5',data['planned_kg']);put('B60','양품 포장량 기준 · 미입력 항목은 별도 확인 · 샘플 초안')
    for start,end,group in [(12,46,'포기김치류'),(48,60,'기타김치류')]:
        for i,r in enumerate(range(start,end,2)):
            for col in ['B','C','H','K','N','V','Z','AC']:put(f'{col}{r}',None)
            if start==12:
                for col in ['T','V']:
                    put(f'{col}{r}',None);put(f'{col}{r+1}',None)
            else:put(f'S{r}',None)
            if i>=len(data['groups'][group]):continue
            item=data['groups'][group][i]
            for col,val in [('B',i+1),('C',item['category']),('H',item['kg_per_unit']),('K',item['good_ea']),('AC','샘플')]:put(f'{col}{r}',val)
            put(f'N{r}',item['good_kg'],f'K{r}*H{r}')
            if start==48:
                put(f'S{r}','미입력');put(f'V{r}',item['started_at'][11:16]);put(f'Z{r}',item['completed_at'][11:16])
    put('G61',sum(r['good_kg'] for r in data['groups']['포기김치류']),'SUM(N12:Q45)')
    put('V61',sum(r['good_kg'] for r in data['groups']['기타김치류']),'SUM(N48:R59)')
    put('G63',data['good_kg'],'G61+G62+V61+V62')
    put('V63',data['good_kg']/data['planned_kg'] if data['planned_kg'] else '미집계','G63/V5' if data['planned_kg'] else None)
    # XML rows/cells must be in spreadsheet order, including newly inserted values.
    def colindex(cell):
        result=0
        for c in re.match('[A-Z]+',cell.get('r'))[0]:result=result*26+ord(c)-64
        return result
    for row in sheet:row[:]=sorted(row,key=colindex)
    sheet[:]=sorted(sheet,key=lambda r:int(r.get('r')))
    stream=BytesIO()
    with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():target.writestr(source.getinfo(name),ET.tostring(root) if name=='xl/worksheets/sheet1.xml' else source.read(name))
    return stream.getvalue()

def install(app):
    def owner(request):
        user=app.state.work.user(request,False)
        return user['id'] if user else None
    @app.post('/api/reports/daily-production')
    def create(body:ReportInput,request:Request):return create_report(app.state.repo,body.business_date,owner(request))
    @app.get('/api/reports/{report_id}/{extension}')
    def download(report_id:str,extension:str,request:Request):
        if not re.fullmatch('[0-9a-f]{32}',report_id) or extension not in ('xlsx','pdf'):raise HTTPException(404,'보고서를 찾을 수 없습니다.')
        with app.state.repo._connect() as c:row=c.execute('SELECT owner_id,snapshot FROM daily_report_exports WHERE report_id=?',(report_id,)).fetchone()
        if not row or row['owner_id']!=owner(request):raise HTTPException(404,'보고서를 찾을 수 없습니다.')
        data=json.loads(row['snapshot']);body=xlsx(data) if extension=='xlsx' else pdf(data)
        return Response(body,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' if extension=='xlsx' else 'application/pdf',headers={'Content-Disposition':f'attachment; filename="imjingang-daily-{data["business_date"]}.{extension}"','Cache-Control':'no-store'})

# Render the same worksheet geometry for PDF, without requiring Excel/LibreOffice on the server.
def pdf(data):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.pagesizes import A4
    font='HYSMyeongJo-Medium'
    if font not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(UnicodeCIDFont(font))
    z=zipfile.ZipFile(BytesIO(xlsx(data)));ns={'s':NS}
    sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));styles=ET.fromstring(z.read('xl/styles.xml'))
    strings=[''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))] if 'xl/sharedStrings.xml' in z.namelist() else []
    def address(text):
        col=0
        for ch in re.match('[A-Z]+',text)[0]:col=col*26+ord(ch)-64
        return col,int(re.search('[0-9]+',text)[0])
    widths={i:48 for i in range(2,30)}
    for col in sheet.findall('s:cols/s:col',ns):
        for i in range(int(col.get('min')),int(col.get('max'))+1):
            if i in widths:widths[i]=(float(col.get('width','8.43'))*7+5)*.75
    heights={i:15 for i in range(1,64)}
    for r in sheet.findall('s:sheetData/s:row',ns):
        if int(r.get('r')) in heights:heights[int(r.get('r'))]=float(r.get('ht','15'))
    xs={2:0};ys={1:0}
    for col in range(2,30):xs[col+1]=xs[col]+widths[col]
    for row in range(1,64):ys[row+1]=ys[row]+heights[row]
    merges={};covered=set()
    for m in sheet.findall('s:mergeCells/s:mergeCell',ns):
        a,b=m.get('ref').split(':');x,y=address(a);xx,yy=address(b)
        if 2<=x<=xx<=29 and yy<=63:
            merges[(x,y)]=(xx,yy)
            covered.update((c,r) for c in range(x,xx+1) for r in range(y,yy+1) if (c,r)!=(x,y))
    cells={address(c.get('r')):c for c in sheet.findall('s:sheetData/s:row/s:c',ns)}
    fonts=list(styles.find('s:fonts',ns));fills=list(styles.find('s:fills',ns));borders=list(styles.find('s:borders',ns));xfs=list(styles.find('s:cellXfs',ns))
    stream=BytesIO();pw,ph=A4;c=canvas.Canvas(stream,pagesize=A4);scale=min((pw-36)/xs[30],(ph-36)/ys[64]);left=(pw-xs[30]*scale)/2;top=ph-18
    c.setTitle('Imjingang Daily Production '+data['business_date']);c.translate(left,top);c.scale(scale,scale)
    for row in range(1,64):
        for col in range(2,30):
            if (col,row) in covered:continue
            endcol,endrow=merges.get((col,row),(col,row));x=xs[col];y=-ys[endrow+1];w=xs[endcol+1]-x;h=ys[endrow+1]-ys[row]
            cell=cells.get((col,row))
            if cell is None:continue
            xf=xfs[int(cell.get('s','0'))];fill=fills[int(xf.get('fillId','0'))];color=fill.find('s:patternFill/s:fgColor',ns)
            if color is not None and color.get('rgb'):
                rgb=color.get('rgb')[-6:];c.setFillColorRGB(*[int(rgb[i:i+2],16)/255 for i in (0,2,4)]);c.rect(x,y,w,h,fill=1,stroke=0)
            border=borders[int(xf.get('borderId','0'))]
            c.setStrokeColorRGB(.35,.35,.35);c.setLineWidth(.4)
            for edge,points in [('left',(x,y,x,y+h)),('right',(x+w,y,x+w,y+h)),('top',(x,y+h,x+w,y+h)),('bottom',(x,y,x+w,y))]:
                b=border.find('s:'+edge,ns)
                if b is not None and b.get('style'):c.line(*points)
            value=cell.findtext('s:v',default='',namespaces=ns)
            if cell.get('t')=='s':value=strings[int(value)] if value else ''
            elif cell.get('t')=='inlineStr':value=''.join(cell.find('s:is',ns).itertext())
            elif value and cell.get("t") not in ("str","e"):
                if (col,row)==(8,3):value=date.fromisoformat(data['business_date']).strftime('%m월 %d일')
                elif (col,row)==(22,63):value=f'{float(value)*100:.1f}%'
                else:
                    n=float(value);value=f'{n:,.2f}'.rstrip('0').rstrip('.') if n!=int(n) else f'{int(n):,}'
            if not value:continue
            f=fonts[int(xf.get('fontId','0'))];size=float(f.find('s:sz',ns).get('val','10'));size=min(size,18)
            lines=str(value).split('\n');available=w-5
            maxwidth=max(pdfmetrics.stringWidth(line,font,size) for line in lines)
            if maxwidth>available:size=max(6,size*available/maxwidth)
            c.setFont(font,size);c.setFillColorRGB(0,0,0)
            for i,line in enumerate(lines):c.drawCentredString(x+w/2,y+h/2+(len(lines)-1)*size*.55-i*size*1.1-size*.35,line)
    c.showPage();c.save();return stream.getvalue()
