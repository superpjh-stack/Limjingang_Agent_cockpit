import type {Answer} from '../types';

export type VoiceState='idle'|'connecting'|'listening'|'thinking'|'speaking'|'error';
export type VoiceEvent={type:string;session_id?:string;utterance_id?:string;response_id?:string;sequence?:number;text?:string;answer?:Answer;audio?:string;message?:string};
export type VoiceView={state:VoiceState;partial:string;answer:string;error:string;level:number};
