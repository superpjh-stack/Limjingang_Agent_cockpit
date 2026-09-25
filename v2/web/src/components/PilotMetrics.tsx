import {useState} from 'react';
import {request} from '../types';

type Device={journeys:number;first_task_open_median_s:number|null;voice_completion_rate:number|null;transcript_p95_s:number|null;answer_p95_s:{demo:number|null;ai:number|null};journey_completion_rate:number|null};
type Report={targets:Record<string,number>;devices:{mobile:Device;desktop:Device};note:string;generated_at:string};
const rate=(v:number|null)=>v==null?'표본 없음':Math.round(v*100)+'%',sec=(v:number|null)=>v==null?'표본 없음':v+'초';
export function PilotMetrics(){
 const [report,setReport]=useState<Report|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(){setBusy(true);setError('');try{setReport(await request<Report>('/metrics'))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}
 const t=report?.targets;
 const rows:[string,string,(d:Device)=>string][]=t?[['첫 업무 진입 (중앙값)',`${t.first_task_open_median_s}초 이내`,d=>sec(d.first_task_open_median_s)],['음성 질문 완료율',`${t.voice_completion_rate*100}% 이상`,d=>rate(d.voice_completion_rate)],['음성 변환 P95',`${t.transcript_p95_s}초 이내`,d=>sec(d.transcript_p95_s)],['답변 P95 · 데모',`${t.answer_p95_s}초 이내`,d=>sec(d.answer_p95_s.demo)],['답변 P95 · AI',`${t.answer_p95_s}초 이내`,d=>sec(d.answer_p95_s.ai)],['저장 후 이어보기',`${t.journey_completion_rate*100}% 이상`,d=>rate(d.journey_completion_rate)],['여정 수','',d=>String(d.journeys)]]:[];
 return <section><h3>파일럿 지표</h3><p className="muted">이벤트 이름과 소요시간만 모읍니다. 질문 문장·음성·키는 저장하지 않습니다.</p><button className="secondary" disabled={busy} onClick={load}>{busy?'불러오는 중':report?'다시 불러오기':'지표 보기'}</button>{error&&<p role="alert" className="error-note">{error}</p>}
  {report&&<><div className="table-scroll"><table><thead><tr><th>지표</th><th>초기 목표</th><th>모바일</th><th>PC</th></tr></thead><tbody>{rows.map(([label,target,value])=><tr key={label}><td>{label}</td><td>{target}</td><td>{value(report.devices.mobile)}</td><td>{value(report.devices.desktop)}</td></tr>)}</tbody></table></div><p className="small-note">{report.note}</p></>}
 </section>;
}
