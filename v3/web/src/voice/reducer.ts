import type {VoiceView} from './types';

export type Action=
  |{type:'state';state:VoiceView['state']}
  |{type:'partial';text:string}
  |{type:'answer';text:string}
  |{type:'level';level:number}
  |{type:'error';message:string}
  |{type:'reset'};

export const initialVoice:VoiceView={state:'idle',partial:'',answer:'',error:'',level:0};
export function voiceReducer(state:VoiceView,action:Action):VoiceView{
  switch(action.type){
    case 'state':return {...state,state:action.state,error:''};
    case 'partial':return {...state,partial:action.text};
    case 'answer':return {...state,answer:action.text,partial:'',state:'speaking'};
    case 'level':return {...state,level:action.level};
    case 'error':return {...state,state:'error',error:action.message};
    case 'reset':return initialVoice;
  }
}
