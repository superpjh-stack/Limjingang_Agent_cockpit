import {FormEvent,useEffect,useMemo,useRef,useState} from 'react';
import {api,type Answer,type Workspace} from './types';
import {useRealtimeVoice} from './voice/useRealtimeVoice';
import {VoicePanel} from './voice/VoicePanel';

type Message={role:'user'|'assistant';text:string;answer?:Answer};

function statusText(backend:'demo'|'agentcore'){return backend==='agentcore'?'AgentCore 연결':'로컬 데모'}

export default function App(){
  const [workspace,setWorkspace]=useState<Workspace|null>(null);
  const [messages,setMessages]=useState<Message[]>([]);
  const [question,setQuestion]=useState('');
  const [lot,setLot]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const abort=useRef<AbortController|null>(null);
  const voice=useRealtimeVoice({lotId:lot,onUser:text=>setMessages(items=>[...items,{role:'user',text}]),onAnswer:answer=>setMessages(items=>[...items,{role:'assistant',text:answer.text,answer}])});
  useEffect(()=>{api<Workspace>('/workspace').then(setWorkspace).catch(e=>setError(e.message))},[]);
  const suggestions=useMemo(()=>workspace?Object.values(workspace.questions).flat():[],[workspace]);

  async function ask(value:string){
    const text=value.trim();if(!text||busy)return;
    abort.current?.abort();const controller=new AbortController();abort.current=controller;
    setBusy(true);setError('');setMessages(items=>[...items,{role:'user',text}]);setQuestion('');
    try{
      const answer=await api<Answer>('/chat',{method:'POST',signal:controller.signal,body:JSON.stringify({question:text,lot_id:lot||null})});
      setMessages(items=>[...items,{role:'assistant',text:answer.text,answer}]);
    }catch(e){if(!controller.signal.aborted)setError(e instanceof Error?e.message:'응답을 받지 못했습니다.')}
    finally{if(!controller.signal.aborted)setBusy(false)}
  }
  function submit(event:FormEvent){event.preventDefault();void ask(question)}
  async function reset(){abort.current?.abort();await voice.stop();setBusy(false);setMessages([]);setError('');await api('/chat/reset',{method:'POST'}).catch(()=>{})}
  if(error&&!workspace)return <main className="fatal"><h1>V3 연결 실패</h1><p>{error}</p><button onClick={()=>location.reload()}>다시 연결</button></main>;
  if(!workspace)return <main className="fatal"><p>임진강김치 V3를 준비하고 있습니다…</p></main>;

  return <div className="shell">
    <header className="topbar"><div className="brand"><span>IMJ</span><div><strong>임진강김치</strong><small>AWS 제조 Agent</small></div></div><div className={`connection ${workspace.meta.backend}`}><i/>{statusText(workspace.meta.backend)}</div><button onClick={reset}>새 대화</button></header>
    <aside className="context">
      <p className="eyebrow">PRODUCTION CONTEXT</p><h2>현장 기록</h2>
      <div className="metric"><span>위험·주의</span><strong>{workspace.kpi.risk_count??workspace.ccp.length}</strong></div>
      <div className="metric"><span>재고 품목</span><strong>{workspace.inventory.length}</strong></div>
      <label>선택 LOT<select value={lot} onChange={e=>{abort.current?.abort();setBusy(false);setLot(e.target.value)}}><option value="">전체 기록</option>{workspace.lots.map(item=><option key={item.lot_id} value={item.lot_id}>{item.lot_id} · {item.process}</option>)}</select></label>
      <section className="runtime"><p className="eyebrow">RUNTIME</p><dl><div><dt>버전</dt><dd>V{workspace.meta.version}</dd></div><div><dt>리전</dt><dd>{workspace.meta.region}</dd></div><div><dt>모델</dt><dd>{workspace.meta.model}</dd></div><div><dt>DB</dt><dd>{workspace.meta.database}</dd></div></dl></section>
    </aside>
    <main className="chat">
      <div className="chat-title"><div><p className="eyebrow">EVIDENCE-FIRST COPILOT</p><h1>제조 기록을 근거로 답합니다.</h1></div><span>AWS AgentCore V3</span></div>
      <div className="messages" aria-live="polite">
        {!messages.length&&<section className="welcome"><div className="orb">A3</div><h2>무엇을 확인할까요?</h2><p>LOT 계보, CCP, 발효, 재고와 출하 준비 기록을 읽기 전용으로 조회합니다.</p><div>{suggestions.slice(0,6).map(item=><button key={item} onClick={()=>ask(item)}>{item}<b>↗</b></button>)}</div></section>}
        {messages.map((message,index)=><article key={index} className={message.role}><span>{message.role==='assistant'?'A3':'나'}</span><div><p>{message.text}</p>{message.answer&&<><div className="chips"><em>{message.answer.mode==='agentcore'?'AgentCore':'데모 조회'}</em>{message.answer.data_tools.map(tool=><code key={tool}>{tool}</code>)}</div><details><summary>근거 {message.answer.evidence.length}건 · 기록 {message.answer.records.length}건</summary><ul>{message.answer.evidence.map((item,i)=><li key={i}>{item.filename||item.document_id||'등록 문서'}</li>)}</ul><small>{new Date(message.answer.retrieved_at).toLocaleString('ko-KR')} · {message.answer.region}</small></details></>}</div></article>)}
        {busy&&<article className="assistant"><span>A3</span><div><p className="thinking">근거를 확인하고 있습니다<span>•••</span></p></div></article>}
      </div>
      {error&&<div className="error" role="alert">{error}<button onClick={()=>setError('')}>닫기</button></div>}
      {(voice.active||voice.state==='error')&&<VoicePanel state={voice.state} partial={voice.partial} answer={voice.answer} error={voice.error} level={voice.level} onStop={()=>void voice.stop()}/>}
      <form onSubmit={submit}><textarea value={question} onChange={e=>setQuestion(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void ask(question)}}} placeholder={lot?`${lot} 기준으로 질문하세요`:'제조 기록에 질문하세요'} maxLength={2000}/><div><small>{workspace.meta.demo_data?'2026년 9월 샘플 · 자동 승인/제어 없음':'운영 데이터'}</small><div className="composer-actions">{workspace.meta.voice_enabled&&!voice.active&&<button className="voice-start" type="button" onClick={()=>void voice.start()}>● 음성 대화</button>}<button disabled={busy||!question.trim()}>{busy?'조회 중':'질문 보내기'}</button></div></div></form>
    </main>
  </div>
}
