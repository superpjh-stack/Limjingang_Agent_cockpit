export type Row = Record<string, string | number | null>;
export type Lot = Row & {lot_id:string; parent_lot_id:string|null; process:string; product_name:string; quantity_kg:number; status:string; created_at:string};
export type Fermentation = Row & {lot_id:string; product_name:string; temperature:number|null; ph:number|null; salinity:number|null; acidity:number|null; abnormal_risk:number|null; remaining_hours:number|null; predicted_at:string};
export type Rule = {rule_id:string; name:string; condition:string; owner:string; action:string; source_document:string; revision:string; status:string; source_table:string};
export type Document = {document_id:string; filename:string; content:string; source:string; status:string};
export type TableInfo = {table:string;label:string;count:number;exists:boolean};
export type Workspace = {kpi: Record<string,number>;lots:Lot[];fermentation:Fermentation[];ccp:Row[];inventory:Row[];shipments:Row[];rules:Rule[];tables:TableInfo[];questions:Record<string,string[]>;meta:{company:string;version:string;demo_data:boolean;as_of:string;backend:string;ai_configured:boolean;model:string}};
export type Detail = {lot:Lot;trace:Lot[];fermentation:Fermentation[];ccp:Row[];shipments:Row[];measurements:Row[]};
export type Evidence = {filename:string;document_id?:string;text:string};
export type Answer = {text:string;sources:string[];evidence:Evidence[];data_tools:string[];records:Row[];searched_documents:boolean;mode:'demo'|'ai'};
export async function request<T>(path:string, init?:RequestInit):Promise<T> {
 const response = await fetch('/api'+path, init);
 if (!response.ok) {const data = await response.json().catch(()=>({})); throw new Error(typeof data.detail === 'string' ? data.detail : `요청을 처리하지 못했습니다 (${response.status}).`);}
 return response.json();
}
