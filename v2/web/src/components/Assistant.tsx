import {forwardRef,useEffect,useImperativeHandle,useRef,useState} from 'react';
import {Mic,MicOff,PhoneOff,Play,Send,X,Volume2,RotateCcw,Save,Copy,LoaderCircle,Check} from 'lucide-react';
import {request,track,type Answer,type Workspace,type User,type WorkItem} from '../types';
import {DailyReport} from './DailyReport';
import {useVoice} from '../hooks/useVoice';
import {useRealtimeVoice} from '../hooks/useRealtimeVoice';

export type AssistantHandle={ask:(text:string,lot?:string)=>void;prepare:(text:string,lot?:string)=>void;focus:()=>void};
type Props={active?:boolean;data:Workspace;token:string;user:User|null;lot:string;onLot:(lot:string)=>void;onSettings:()=>void;onSave:(answer:Answer,question:string)=>void;work:WorkItem|null;open:boolean;onClose:()=>void;voiceFirst?:boolean;onQuestion?:(question:string)=>void};
export const Assistant=forwardRef<AssistantHandle,Props>(function Assistant({active=true,data,token,user,lot,onLot,onSettings,onSave,work,open,onClose,voiceFirst=false,onQuestion},ref){
 const [copied,setCopied]=useState<number|null>(null);
 const mode:'ai'|'demo'=data.meta.ai_configured?'ai':'demo';
 const [text,setText]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const [pendingQuestion,setPendingQuestion]=useState('');
 const [messages,setMessages]=useState<{question:string;answer:Answer}[]>([]),[transcribed,setTranscribed]=useState(false),[liveTurns,setLiveTurns]=useState<{role:'user'|'assistant';text:string;answer?:Answer}[]>([]);
 const staged=useRef<string|null>(null),heard=useRef('');
 const lock=useRef(false),epoch=useRef(0),abort=useRef<AbortController|null>(null),input=useRef<HTMLTextAreaElement>(null),panel=useRef<HTMLElement>(null),chatScroll=useRef<HTMLDivElement>(null);
 const voice=useVoice(token,value=>{setText(value);heard.current=value;setTranscribed(true);input.current?.focus()});
 const realtime=useRealtimeVoice(token,lot,turn=>setLiveTurns(items=>[...items,turn]),(_name,output)=>{try{const answer=JSON.parse(output) as Answer;if(answer.text)setLiveTurns(items=>[...items,{role:'assistant',text:answer.text,answer}])}catch{/* Invalid tool output is not evidence. */}});
 useEffect(()=>{if(!active){voice.cancel();realtime.stop()}},[active]);
 const voiceAvailable=data.meta.ai_configured&&(!!token||!!data.meta.local_dev_ai);
 function cancel(){epoch.current++;abort.current?.abort();lock.current=false;setBusy(false);setPendingQuestion('');voice.cancel();realtime.stop()}
 useEffect(()=>{cancel();setMessages(work?.snapshots?.length?work.snapshots:work?.snapshot?[work.snapshot]:[]);setLiveTurns([]);setText(staged.current||'');staged.current=null;setError('');setTranscribed(false);setCopied(null)},[lot,work?.id,user?.id,token]);
 useEffect(()=>()=>{epoch.current++;abort.current?.abort()},[]);
 useEffect(()=>{if(!open)return;const previous=document.activeElement as HTMLElement|null;input.current?.focus();return()=>previous?.focus()},[open]);
 useEffect(()=>{if(!open){voice.cancel();realtime.stop()}},[open]);
 const scrollAnchor=useRef('');
 useEffect(()=>{const node=chatScroll.current;if(!node)return;const key=liveTurns.length?'voice-'+liveTurns.filter(t=>t.role==='user').length:'text-'+messages.length;if(scrollAnchor.current===key)return;const target=liveTurns.length?Array.from(node.querySelectorAll<HTMLElement>('.live-caption')).find((_,i,all)=>i>all.map(n=>n.classList.contains('user-message')).lastIndexOf(true)):node.querySelector<HTMLElement>('.exchange:last-of-type .assistant-message');if(target){scrollAnchor.current=key;node.scrollTop+=target.getBoundingClientRect().top-node.getBoundingClientRect().top-16}},[messages,liveTurns]);
 async function ask(question:string,explicitLot?:string,source:'text'|'suggestion'='suggestion'){
   if(lock.current||realtime.active||!question.trim())return;
   const selected=explicitLot??lot;
   if(explicitLot!==undefined&&(explicitLot!==lot||work)){staged.current=question;onLot(explicitLot);return}
   onQuestion?.(question.trim());
   lock.current=true;setBusy(true);setPendingQuestion(question.trim());setError('');voice.cancel();const run=epoch.current;abort.current=new AbortController();
   const spoken=transcribed&&source==='text';if(spoken&&question!==heard.current)track('transcript_edited');track('question_submitted',{source:spoken?'voice':source,mode});const began=performance.now();
   try{
    const answer=await request<Answer>('/chat',{method:'POST',headers:{'Content-Type':'application/json',...(token?{Authorization:'Bearer '+token}:{})},body:JSON.stringify({question,lot_id:selected||null,work_id:work?.id||null,mode,history:messages.flatMap(m=>[{role:"user",text:m.question},{role:"assistant",text:m.answer.text}]).slice(-12)}),signal:abort.current.signal});
    if(run!==epoch.current)return;
    if(answer.ignored){setPendingQuestion('');return;}
    track('answer_ready',{mode,duration_ms:performance.now()-began});
    setMessages(m=>[...m,{question,answer}]);setPendingQuestion('');setText('');setTranscribed(false);
   }catch(e){if(run===epoch.current&&(e as Error).name!=='AbortError'){setPendingQuestion('');setError((e as Error).message);setText(question)}}
   finally{if(run===epoch.current){setBusy(false);lock.current=false}}
 }
 function prepare(question:string,targetLot=lot){if(lock.current)return;if(targetLot!==lot){staged.current=question;onLot(targetLot)}else setText(question);input.current?.focus()}
 useImperativeHandle(ref,()=>({ask,prepare,focus:()=>input.current?.focus()}));
 async function reset(){cancel();try{await request('/chat/reset',{method:'POST'});setMessages([]);setLiveTurns([]);setText('');setError('');setTranscribed(false);setCopied(null);input.current?.focus()}catch(e){setError((e as Error).message)}}
 function trap(e:React.KeyboardEvent){if(!open)return;if(e.key==='Escape'){voice.cancel();onClose()}if(e.key==='Tab'){const nodes=Array.from(panel.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),textarea,select,summary')??[]).filter(el=>el.getClientRects().length);const first=nodes[0],last=nodes.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}}
 return <aside ref={panel} className={`assistant-panel ${!messages.length&&!pendingQuestion&&!liveTurns.length?'is-empty':''} ${open?'mobile-open':''} ${voiceFirst?'voice-first':''}`} role={open?'dialog':undefined} aria-modal={open||undefined} aria-label="업무 에이전트" onKeyDown={trap}>
  <header className="agent-header"><div><span className="eyebrow">생산부터 납품까지, 기록을 함께 확인합니다</span><h2>임진강김치 에이전트</h2></div><button className="icon-btn" aria-label="대화 초기화" onClick={reset}><RotateCcw size={18}/></button><button className="icon-btn agent-close" aria-label="대화 닫기" onClick={()=>{voice.cancel();onClose()}}><X/></button></header>


  {work&&<p className="context-note">이어 보는 업무: {work.title}</p>}
  <div className="chat-scroll" ref={chatScroll}>
    {!messages.length&&!pendingQuestion&&!liveTurns.length&&<div className="agent-welcome"><h3>오늘 궁금한거 질문해!!</h3></div>}
    {messages.map((m,i)=><article className="exchange" key={i}><p className="user-message">{m.question}</p><div className="assistant-message"><div className="answer-label">{m.answer.mode==='demo'?'자료 조회':'임진강김치 · AI 분석'}</div><AnswerContent answer={m.answer}/><small>질문 대상: {m.answer.context?.lot_id||'전체 기록'}</small><details onToggle={e=>{if(e.currentTarget.open)track('evidence_opened')}}><summary>답변 근거 보기 · 문서 {m.answer.evidence.length}개 · 조회 기록 {m.answer.records.length}건</summary>{m.answer.demo_data&&<p>2026년 9월 샘플 자료입니다. 문서·예측값은 승인된 품질 판정이 아닙니다.</p>}{m.answer.evidence.map((ev,j)=><details className="source-detail" key={j}><summary>{ev.filename}</summary><pre>{ev.text}</pre></details>)}{m.answer.records.map((row,j)=><details className="source-detail" key={j}><summary>기록 {j+1} · {String(row.lot_id??row.item_name??row.name??'조회 결과')}</summary><pre>{JSON.stringify(row,null,2)}</pre></details>)}{!m.answer.evidence.length&&!m.answer.records.length&&<p>연결된 근거가 없습니다.</p>}</details>{m.answer.source_details&&<details><summary>조회 출처와 기준</summary><pre>{JSON.stringify(m.answer.source_details,null,2)}</pre></details>}<div className="answer-actions"><button disabled={!voiceAvailable} onClick={()=>voice.speak(m.answer.summary||m.answer.text)}><Volume2 size={16}/>답변 듣기</button><button onClick={async()=>{if(user){onSave(m.answer,m.question);return}try{await navigator.clipboard.writeText(`${m.question}\n\n${m.answer.text}\n\n질문 대상: ${m.answer.context?.lot_id||'전체 기록'}\n${m.answer.mode==='demo'?'샘플 기록 조회':'AI 답변'}\n근거 문서: ${m.answer.evidence.map(e=>e.filename).join(', ')||'없음'}`);setCopied(i)}catch{setError('복사하지 못했습니다. 답변을 선택해 복사해 주세요.')}}}>{copied===i?<Check size={16}/>:user?<Save size={16}/>:<Copy size={16}/>} {user?(work?'업무에 답변 추가':'업무로 저장'):(copied===i?'복사 완료':'답변 복사')}</button></div>{m.answer.captured_at&&<small>근거 보존: {new Date(m.answer.captured_at).toLocaleString('ko-KR')}</small>}</div></article>)}
    {liveTurns.map((turn,i)=>turn.role==='user'?<p className="user-message live-caption" key={`live-${i}`}>{turn.text}</p>:<div className="assistant-message live-caption" key={`live-${i}`}><div className="answer-label">실시간 음성 · AI 답변</div>{turn.answer?<><AnswerContent answer={turn.answer}/><details><summary>조회 근거</summary><pre>{JSON.stringify({documents:turn.answer.evidence,records:turn.answer.records},null,2)}</pre></details></>:<p>{turn.text}</p>}</div>)}
    {pendingQuestion&&<p className="user-message pending-message">{pendingQuestion}</p>}
    {busy&&<p role="status" className="thinking"><LoaderCircle className="spin" size={18}/>기록을 확인하고 있습니다. <button onClick={cancel}>대기 취소</button></p>}
  </div>
  <div className={`realtime-voice ${realtime.active?'active':''}`} aria-live="polite">
   {!realtime.active?<button className="voice-start" disabled={busy} onClick={()=>{if(!voiceAvailable){onSettings();return}voice.cancel();setLiveTurns([]);void realtime.start()}}><Mic size={22}/>{voiceAvailable?'실시간 음성으로 질문하기':'AI 연결 설정 확인'}</button>:<><div className="live-status"><i/><span>{realtime.state==='permission'?'마이크 권한 확인 중':realtime.state==='connecting'?'연결 중':realtime.state==='speaking'?'듣고 있어요':realtime.state==='responding'?'답변 준비 중':'편하게 말씀하세요'}</span></div><button className="icon-btn" aria-label={realtime.muted?'마이크 켜기':'마이크 끄기'} onClick={realtime.toggleMute}>{realtime.muted?<MicOff size={19}/>:<Mic size={19}/>}</button>{realtime.needsPlay&&<button className="icon-btn" aria-label="음성 재생" onClick={()=>void realtime.play()}><Play size={19}/></button>}<button className="voice-end" onClick={realtime.stop}><PhoneOff size={17}/>종료</button></>}
  </div>
  {voice.error&&<p className="voice-error" role="alert">{voice.error}</p>}
  {realtime.error&&<p className="voice-error" role="alert">{realtime.error}</p>}
  {error&&<p className="voice-error" role="alert">{error}</p>}
  <form className="composer" onSubmit={e=>{e.preventDefault();ask(text,undefined,'text')}}>{transcribed&&<p className="transcript-notice">인식한 문장과 LOT·수치를 확인한 뒤 보내세요.</p>}<textarea ref={input} aria-label="에이전트에게 질문" value={text} onChange={e=>setText(e.target.value)} rows={2} maxLength={2000} placeholder="LOT·발효·CCP·출하에 대해 질문하세요…" onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing&&e.keyCode!==229){e.preventDefault();if(voice.state==='idle')void ask(text,undefined,'text')}}} disabled={busy||realtime.active||voice.state!=='idle'}/><div><small>호출명 없이 질문 · Enter로 보내기</small><button className="send-button" aria-label="질문 보내기" disabled={!text.trim()||busy||realtime.active||voice.state!=='idle'}><Send size={18}/><span>보내기</span></button></div></form>
  <p className="assistant-disclaimer">{voiceAvailable?'음성 답변 중에도 편하게 말씀하세요. 새 질문을 들으면 이전 답변을 멈춥니다.':'음성 사용은 설정에서 AI 연결이 필요합니다.'}<br/>공정 변경·출하 승인은 담당자가 결정합니다.</p>
 </aside>
});

function AnswerContent({answer}:{answer:Answer}){return <>{(answer.report||answer.report_picker)&&<DailyReport initial={answer.report}/>}{answer.comparison_tables?.map((table,i)=><section className="comparison-table" key={i}><h3>{table.title}</h3><div className="table-scroll" tabIndex={0} role="region" aria-label={table.title}><table><thead><tr>{table.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{table.rows.map((r,ri)=><tr key={ri}>{r.map((v,ci)=><td key={ci}>{v}</td>)}</tr>)}</tbody></table></div></section>)}{answer.comparison_tables?.length?<details><summary>분석 설명과 다음 확인사항</summary><p>{answer.text}</p></details>:<p>{answer.text}</p>}{answer.request_coverage&&<details><summary>요청별 답변 확인</summary><ul>{answer.request_coverage.map((c,i)=><li key={i}>{c.request} · {c.status==='answered'?'답변·근거 확인':'추가 확인 필요'}</li>)}</ul></details>}</>}
