export type Row=Record<string,string|number|boolean|null>;
export type Lot=Row&{lot_id:string;process:string;product_name:string;status:string};
export type Evidence={filename?:string;document_id?:string;text?:string;content?:string};
export type Workspace={
  kpi:Record<string,number>;lots:Lot[];inventory:Row[];ccp:Row[];shipments:Row[];
  questions:Record<string,string[]>;
  meta:{company:string;version:string;agent_platform:string;backend:'demo'|'agentcore';region:string;model:string;database:string;demo_data:boolean;voice_enabled:boolean;as_of:string;retrieved_at:string};
};
export type Answer={text:string;sources:string[];evidence:Evidence[];data_tools:string[];records:Row[];session_id:string;mode:'demo'|'agentcore';demo_data:boolean;region:string;model:string;retrieved_at:string};

export async function api<T>(path:string,init?:RequestInit):Promise<T>{
  const response=await fetch('/api'+path,{...init,headers:{'Content-Type':'application/json',...(init?.headers||{})}});
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(typeof data.detail==='string'?data.detail:`요청 실패 (${response.status})`)}
  return response.json();
}
