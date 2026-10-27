import type {VoiceState} from './types';

const labels:Record<VoiceState,string>={idle:'대기',connecting:'연결 중',listening:'듣는 중',thinking:'근거 확인 중',speaking:'답변 중',error:'오류'};
export function VoicePanel({state,partial,answer,error,level,onStop}:{state:VoiceState;partial:string;answer:string;error:string;level:number;onStop:()=>void}){
  return <section className={`voice-panel ${state}`} aria-live="polite">
    <div className="voice-head"><div><i style={{transform:`scale(${1+Math.min(level,1)*1.8})`}}/><strong>{labels[state]}</strong></div><button type="button" onClick={onStop}>음성 종료</button></div>
    <p>{error||partial||answer||'말씀해 주세요. 제조 기록을 조회해 음성으로 답합니다.'}</p>
    <div className="voice-bars" aria-hidden="true">{Array.from({length:18},(_,i)=><span key={i} style={{height:`${8+Math.min(32,level*220*(1+(i%4)/5))}px`}}/>)}</div>
  </section>
}
