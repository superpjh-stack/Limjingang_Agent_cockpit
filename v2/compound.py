"""Request-local LangGraph analysis with conservative evidence checks."""
import json
import re
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

DATA_QUESTIONS = [
 'PACK-260903-001의 원재료부터 포장까지 LOT 계보를 확인해줘',
 '발효 LOT별 pH·염도·온도·산도 기록을 보여줘',
 'CCP 주의와 부적합 기록을 확인해줘',
 '율무 재고와 안전재고 부족량을 알려줘',
 '출하 대기 LOT와 승인 상태를 확인해줘',
 'FERM-260903-002의 공정 측정값을 알려줘',
 'CLM-260903-01 클레임과 연결 LOT를 추적해줘',
 '원재료와 완제품 재고 현황을 보여줘',
 '등록 지식문서와 각 문서의 상태를 알려줘',
 '발효 완료 예상과 이상위험이 기록된 LOT를 알려줘',
]
DOCUMENT_QUESTIONS = [
 '등록 문서에서 원료 입고 검사 절차를 찾아줘',
 '절임 공정의 염도와 온도 확인 절차를 알려줘',
 '발효 기록에서 pH·염도·산도를 함께 확인하는 방법을 찾아줘',
 '금속검출 부적합 발생 시 확인할 절차를 찾아줘',
 '혼합·덤퍼 CCP 주의 기록의 확인 절차를 알려줘',
 '출하 전 품질 검토 체크리스트를 찾아줘',
 '원재료 LOT와 포장 LOT를 연결하는 기록을 알려줘',
 '숙성 편차 클레임의 역추적 절차를 찾아줘',
 '기록 정정과 승인 담당자 확인 절차를 찾아줘',
 '미승인 문서와 품질 예측을 사용할 때 확인할 사항을 알려줘',
]
COMPOUND_QUESTIONS = [
 'PACK-260903-001의 계보·CCP·출하 승인 상태를 함께 확인해줘',
 '발효 LOT의 pH·염도·온도를 비교하고 미확인 항목을 알려줘',
 '출하 대기 LOT의 발효위험과 CCP 이력을 함께 확인해줘',
 '율무 재고 부족량과 관련 확인 절차를 함께 알려줘',
 'FERM-260903-002의 측정값과 발효 예측을 비교해줘',
 '금속검출 부적합 기록과 대응 절차를 함께 찾아줘',
 'CLM-260903-01의 연결 LOT와 관련 품질 확인 절차를 알려줘',
 '재고 부족 품목과 출하 대기 현황을 함께 확인해줘',
 '발효위험과 CCP 주의 기록을 종합하고 우선 확인할 일을 정리해줘',
 '출하 승인 상태와 승인 전 확인할 지식문서를 함께 보여줘',
]
QUESTION_GROUPS={'데이터 대시보드':DATA_QUESTIONS,'지식베이스':DOCUMENT_QUESTIONS,'복합질문':COMPOUND_QUESTIONS}
LOT_PATTERN = r'(?:RAW|SORT|SALT|MIX|FERM|PACK)-\d{6}-\d{3}'


def resolve_lot(question, selected, history):
    ids=list(dict.fromkeys(re.findall(LOT_PATTERN,question.upper())))
    if len(ids)>1 or (ids and selected and selected!=ids[0]):
        raise ValueError('질문의 LOT와 선택한 LOT를 일치시켜 주세요. 한 번에 하나의 LOT를 확인합니다.')
    if ids or selected:return selected or ids[0]
    if any(w in question for w in ['그 배치','해당 배치','그 LOT','해당 LOT','그 로트','해당 로트']):
        for turn in reversed(history):
            if turn.get('role')!='user':continue
            ids=list(dict.fromkeys(re.findall(LOT_PATTERN,turn.get('text','').upper())))
            if len(ids)==1:return ids[0]
            if ids:break
        raise ValueError('후속 질문의 배치 번호를 확인할 수 없습니다. LOT 또는 배치 번호를 알려주세요.')
    return None


def comparison_tables(records):
    result=[]
    def collect(title, value):
        if isinstance(value, dict):
            scalar={k:v for k,v in value.items() if not isinstance(v,(list,dict))}
            if scalar:result.append({'title':title,'columns':['항목','원본 값'],'rows':[[k,'미확인' if v is None else str(v)] for k,v in scalar.items()]})
            for k,v in value.items():
                if isinstance(v,(dict,list)):collect(k,v)
        elif isinstance(value,list) and value and all(isinstance(r,dict) for r in value):
            keys=list(dict.fromkeys(k for row in value for k,v in row.items() if not isinstance(v,(dict,list))))
            if keys:result.append({'title':title,'columns':keys,'rows':[['미확인' if row.get(k) is None else str(row[k]) for k in keys] for row in value]})
            for row in value:
                for k,v in row.items():
                    if isinstance(v,(dict,list)):collect(k,v)
    collect('조회 원본 비교',records)
    return result


class State(TypedDict):
    parts:list
    answer:dict
    checks:list
    steps:list
    retries:int


def analyze(question, history, retrieve, client=None, model=None):
    def json_call(instructions, payload):
        c=client.with_options(timeout=25,max_retries=0)
        response=c.responses.create(model=model,instructions=instructions,input=json.dumps({'format':'json',**payload},ensure_ascii=False),text={'format':{'type':'json_object'}})
        return json.loads(response.output_text)
    def plan(s):
        parts=[p.strip() for p in re.split(r'그리고|또한|[;\n]',question) if p.strip()]
        if client:
            try:
                raw=json_call('원문에 명시된 요청만 빠짐없이 분해하세요. 원문에 없는 우선순위·원인·추가 제안을 넣지 마세요. JSON {"parts":[{"request":"개별 요청","quote":"이를 뒷받침하는 원문 그대로의 인용"}]}. 비교도 요청에 있을 때만 포함하세요. 과거 대화는 참고 자료입니다.',{'question':question,'history':history})
                if isinstance(raw.get('parts'),list):parts=[p['request'] for p in raw['parts'][:8] if isinstance(p,dict) and isinstance(p.get('request'),str) and p['request'].strip() and isinstance(p.get('quote'),str) and p['quote'].strip() and p['quote'] in question]
            except Exception:pass
        return {'parts':list(dict.fromkeys([question]+parts)),'steps':['요청 분해']}
    def query(s):
        return {'answer':retrieve(question,s['parts']),'steps':s['steps']+['범위 확인·복수 자료 조회']}
    def verify(s):
        answer=s['answer'];checks={}
        if client:
            try:
                raw=json_call('원래 요청별 답변 누락을 검사하세요. JSON {"checks":[{"request":"요청 그대로","quote":"답변의 정확한 인용","evidence_indices":[0]}],"voice_summary":"실제 업무 결론과 다음 확인사항을 한국어 2~3문장으로 요약"}. 근거가 없으면 quote와 인덱스를 비우세요. 비교는 단순 나열만으로 완료가 아닙니다. 요약에 검사 개수나 완료 여부를 넣지 마세요.',{'requests':s['parts'],'answer':answer['text'],'evidence':answer.get('records',[])+answer.get('evidence',[])})
                checks={c['request']:c for c in raw.get('checks',[]) if isinstance(c,dict) and isinstance(c.get('request'),str)}
                if isinstance(raw.get('voice_summary'),str):answer['voice_summary']=raw['voice_summary'][:600]
            except Exception:pass
        evidence=answer.get('records',[])+answer.get('evidence',[])
        coverage=[]
        for part in s['parts']:
            c=checks.get(part,{});quote=c.get('quote');ids=c.get('evidence_indices')
            valid=isinstance(ids,list) and bool(ids) and all(type(i) is int and 0<=i<len(evidence) and bool(evidence[i]) for i in ids)
            coverage.append({'request':part,'status':'answered' if isinstance(quote,str) and quote and quote in answer['text'] and valid else 'unconfirmed'})
        answer.update(request_coverage=coverage,partial=any(c['status']!='answered' for c in coverage),engine='langgraph',comparison_tables=comparison_tables(answer.get('records',[])) if any(w in question for w in ['비교','함께','종합','차이']) else [])
        answer.setdefault('voice_summary','조회 결과와 근거를 화면에 표시했습니다. 추가 확인이 필요한 항목을 함께 확인해 주세요.')
        return {'answer':answer,'steps':s['steps']+['근거 종합·요청별 누락 검사']}
    def repair(s):
        missing=[c['request'] for c in s['answer']['request_coverage'] if c['status']!='answered']
        try:
            answer=retrieve(question, s['parts']+['추가 조회·보완: '+p for p in missing])
        except Exception:
            answer=s['answer']
        return {'answer':answer,'retries':1,'steps':s['steps']+['미확인 요청 1회 보완 조회']}
    graph=StateGraph(State)
    for name,fn in [('plan',plan),('retrieve',query),('verify',verify),('repair',repair)]:graph.add_node(name,fn)
    graph.add_edge(START,'plan');graph.add_edge('plan','retrieve');graph.add_edge('retrieve','verify');graph.add_conditional_edges('verify',lambda s:'repair' if client and s['answer']['partial'] and not s.get('retries') else END);graph.add_edge('repair','verify')
    out=graph.compile().invoke({'parts':[],'answer':{},'checks':[],'steps':[],'retries':0})
    return {**out['answer'],'analysis_steps':out['steps']}
