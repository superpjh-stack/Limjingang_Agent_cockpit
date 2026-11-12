import {useRef,useState,useEffect} from 'react';
import {request} from '../types';
import {apiPath} from '../apiPath';
export type DailyReportData={report_id:string;business_date:string;created_at:string;notice:string;good_kg:number;planned_kg:number;reject_kg:number;achievement:number|null;missing:string[];rows:{record_id:string;product_name:string;kg_per_unit:number;good_ea:number;good_kg:number;lot_id:string}[]};
export function DailyReport({initial}:{initial?:DailyReportData}){
 const [data,setData]=useState(initial),[day,setDay]=useState(initial?.business_date||'2026-09-20'),[busy,setBusy]=useState(false),[error,setError]=useState(''),[status,setStatus]=useState(initial?'보고서가 준비되었습니다. Excel 또는 PDF를 내려받으세요.':''),[downloading,setDownloading]=useState('');const controller=useRef<AbortController|null>(null);
 useEffect(()=>()=>controller.current?.abort(),[]);
 async function generate(){
  controller.current?.abort();const c=new AbortController();controller.current=c;
  setBusy(true);setError('');setStatus('생산자료를 조회하고 보고서를 생성하고 있습니다…');setData(undefined);
  let timedOut=false;const timeout=setTimeout(()=>{timedOut=true;c.abort()},20000);
  try{const r=await request<DailyReportData>('/reports/daily-production',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({business_date:day}),signal:c.signal});if(!c.signal.aborted){setData(r);setStatus('생성이 완료되었습니다. 아래 Excel 또는 PDF 버튼을 눌러 파일을 받으세요.')}}
  catch(e){if(controller.current===c&&(!c.signal.aborted||timedOut)){setStatus('');setError(timedOut?'20초 안에 응답하지 않았습니다. 서버 연결을 확인하고 다시 시도해 주세요.':(e as Error).message)}}
  finally{clearTimeout(timeout);if(controller.current===c){setBusy(false);controller.current=null}}
 }
 async function download(ext:'pdf'|'xlsx'){
  if(!data||downloading)return;setError('');setDownloading(ext);setStatus(`${ext.toUpperCase()} 파일을 준비하고 있습니다…`);
  const c=new AbortController();const timeout=setTimeout(()=>c.abort(),20000);
  try{const response=await fetch(apiPath(`/api/reports/${data.report_id}/${ext}`),{signal:c.signal});if(!response.ok){const e=await response.json();throw Error(e.detail||'다운로드 실패')}const url=URL.createObjectURL(await response.blob());const a=document.createElement('a');a.href=url;a.download=`임진강김치_일일생산보고서_${data.business_date}.${ext}`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);setStatus(`${ext.toUpperCase()} 파일 다운로드를 시작했습니다. 브라우저 다운로드 목록을 확인하세요.`)}
  catch(e){setStatus('');setError(c.signal.aborted?'파일 준비 시간이 초과되었습니다. 다시 다운로드해 주세요.':(e as Error).message)}
  finally{clearTimeout(timeout);setDownloading('')}
 }

 return <section className="daily-report"><h3>일일생산보고서</h3><p>샘플 기간: 2026-09-01 ~ 09-20 · 실제 운영자료 아님</p><div className="report-controls"><label>생산일 <input type="date" value={day} onChange={e=>setDay(e.target.value)} disabled={busy||!!downloading}/></label><button className="primary-button" type="button" disabled={busy||!!downloading||!day} onClick={generate}>{busy?'생성 중…':data?'보고서 다시 생성':'보고서 생성'}</button></div>{status&&<p className="report-status" role="status" aria-live="polite">{status}</p>}{error&&<p className="report-error" role="alert">{error}</p>}{data&&<><div className="answer-actions report-downloads"><button type="button" disabled={!!downloading||busy} onClick={()=>download('xlsx')}>{downloading==='xlsx'?'Excel 준비 중…':'Excel 다운로드'}</button><button type="button" disabled={!!downloading||busy} onClick={()=>download('pdf')}>{downloading==='pdf'?'PDF 준비 중…':'인쇄용 PDF 다운로드'}</button></div><small>생성 시각: {new Date(data.created_at).toLocaleString('ko-KR')} · 보고서 {data.report_id.slice(-8)}</small><h4>{data.business_date} · 미리보기</h4><p>계획 {data.planned_kg.toLocaleString()}kg / 양품 {data.good_kg.toLocaleString()}kg / 달성률 {data.achievement??'미집계'}{data.achievement===null?'':'%'}</p><div className="table-scroll"><table><thead><tr><th>품목</th><th>규격 kg</th><th>수량 ea</th><th>양품 kg</th></tr></thead><tbody>{data.rows.map(r=><tr key={r.record_id}><td>{r.product_name}</td><td>{r.kg_per_unit}</td><td>{r.good_ea}</td><td>{r.good_kg.toLocaleString()}</td></tr>)}</tbody></table></div><p>미입력: {data.missing.join(', ')}</p><small>{data.notice}</small></>}</section>
}
