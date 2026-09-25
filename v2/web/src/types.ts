export type Row = Record<string, string | number | null>;
export type Lot = Row & {lot_id:string; parent_lot_id:string|null; process:string; product_name:string; quantity_kg:number; status:string; created_at:string};
export type Fermentation = Row & {lot_id:string; product_name:string; temperature:number|null; ph:number|null; salinity:number|null; acidity:number|null; abnormal_risk:number|null; remaining_hours:number|null; predicted_at:string};
export type Rule = {rule_id:string; name:string; condition:string; owner:string; action:string; source_document:string; revision:string; status:string; source_table:string};
export type Document = {document_id:string; filename:string; content:string; source:string; status:string};
export type TableInfo = {table:string;label:string;count:number;exists:boolean};
export type Workspace = {kpi: Record<string,number>;lots:Lot[];fermentation:Fermentation[];ccp:Row[];inventory:Row[];shipments:Row[];rules:Rule[];tables:TableInfo[];questions:Record<string,string[]>;meta:{company:string;version:string;demo_data:boolean;as_of:string;backend:string;ai_configured:boolean;local_dev_ai?:boolean;model:string;retrieved_at:string}};
export type Detail = {lot:Lot;trace:Lot[];fermentation:Fermentation[];ccp:Row[];shipments:Row[];measurements:Row[]};
export type Evidence = {filename:string;document_id?:string;text:string};
export type Answer = {answer_id?:string;captured_at?:string;summary?:string;retrieved_at?:string;context?:{lot_id:string|null;as_of:string};unknowns?:string[];text:string;sources:string[];evidence:Evidence[];data_tools:string[];records:Row[];searched_documents:boolean;mode:'ai'};
export async function request<T>(path:string, init?:RequestInit):Promise<T> {
 const response = await fetch('/api'+path, init);
 if (!response.ok) {const data = await response.json().catch(()=>({})); throw new Error(typeof data.detail === 'string' ? data.detail : `요청을 처리하지 못했습니다 (${response.status}).`);}
 return response.json();
}

export type User={id:string;username:string;name:string;organization:string;role:'operator'|'reviewer'|'admin'};
export type WorkItem={id:string;title:string;lot_id:string|null;kind:string;status:string;creator_id:string;assignee_id:string;version:number;created_at:string;updated_at:string;snapshot:{question:string;answer:Answer}|null;snapshots?:{question:string;answer:Answer}[];notes:{text:string;author:string;at:string}[];events:{action:string;actor:string;at:string;request_id:string}[];handoff:{sender_id:string;recipient_id:string;request:string;sent_at:string;acknowledged_at:string|null}|null};
export type JourneyEvent='task_opened'|'voice_started'|'voice_cancelled'|'transcript_ready'|'transcript_edited'|'question_submitted'|'answer_ready'|'evidence_opened'|'task_saved'|'handoff_sent'|'handoff_acknowledged'|'task_resumed'|'review_completed';
// Pilot journey events: names and timings only, never text, audio or keys. Losing one never blocks work.
const journeyId=crypto.randomUUID(), queue:Record<string,unknown>[]=[];let flushTimer:ReturnType<typeof setTimeout>|null=null;
function flush(){flushTimer=null;const events=queue.splice(0,20);if(!events.length)return;fetch('/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({events}),keepalive:true}).catch(()=>{});if(queue.length)flush()}
// Work events use the work item id as journey so a save on the phone links to the PC review.
export function track(event:JourneyEvent,extra:{source?:'voice'|'text'|'suggestion';mode?:'demo'|'ai';duration_ms?:number;work?:string}={}){
 const {work,...rest}=extra;
 queue.push({event,journey_id:work||journeyId,device:matchMedia('(max-width:740px)').matches?'mobile':'desktop',...rest,...(extra.duration_ms!==undefined?{duration_ms:Math.max(0,Math.round(extra.duration_ms))}:{})});
 if(!flushTimer)flushTimer=setTimeout(flush,1500);
}
if(typeof document!=='undefined')document.addEventListener('visibilitychange',()=>{if(document.hidden){if(flushTimer)clearTimeout(flushTimer);flush()}});
