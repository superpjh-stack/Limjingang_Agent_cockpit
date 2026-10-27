import {useCallback,useEffect,useReducer,useRef} from 'react';
import {api,type Answer} from '../types';
import {MicrophoneCapture} from './MicrophoneCapture';
import {PcmPlayer} from './PcmPlayer';
import {initialVoice,voiceReducer} from './reducer';
import type {VoiceEvent} from './types';

type SessionTicket={session_id:string;url:string;expires_in:number};
type Options={lotId:string;onUser:(text:string)=>void;onAnswer:(answer:Answer)=>void};

export function useRealtimeVoice({lotId,onUser,onAnswer}:Options){
  const [view,dispatch]=useReducer(voiceReducer,initialVoice);
  const socket=useRef<WebSocket|null>(null);
  const mic=useRef<MicrophoneCapture|null>(null);
  const player=useRef(new PcmPlayer());
  const ids=useRef({session:'',utterance:'',response:'',sequence:0});
  const speaking=useRef(false);
  const loudSince=useRef(0);
  const playbackTimer=useRef<number|null>(null);

  const stop=useCallback(async()=>{
    const ws=socket.current;
    if(ws?.readyState===WebSocket.OPEN)ws.send(JSON.stringify({type:'session.end'}));
    socket.current=null;ws?.close();await mic.current?.stop();mic.current=null;
    if(playbackTimer.current!==null)window.clearTimeout(playbackTimer.current);
    playbackTimer.current=null;await player.current.close();speaking.current=false;dispatch({type:'reset'});
  },[]);

  const start=useCallback(async()=>{
    if(socket.current)return;
    dispatch({type:'state',state:'connecting'});
    try{
      const ticket=await api<SessionTicket>('/voice/session',{method:'POST',body:JSON.stringify({lot_id:lotId||null})});
      ids.current={session:ticket.session_id,utterance:'',response:'',sequence:0};
      const ws=new WebSocket(ticket.url);socket.current=ws;
      await new Promise<void>((resolve,reject)=>{
        const timeout=window.setTimeout(()=>reject(new Error('음성 연결 시간이 초과되었습니다.')),10000);
        ws.onopen=()=>{window.clearTimeout(timeout);resolve()};
        ws.onerror=()=>{window.clearTimeout(timeout);reject(new Error('음성 채널에 연결하지 못했습니다.'))};
      });
      ws.onmessage=event=>{
        const data=JSON.parse(event.data) as VoiceEvent;
        if(data.type==='transcript.partial')dispatch({type:'partial',text:data.text||''});
        if(data.type==='transcript.final'){
          if(data.text)onUser(data.text);
          ids.current.utterance='';ids.current.sequence=0;
          dispatch({type:'state',state:'thinking'});
        }
        if(data.type==='agent.status'&&data.response_id)ids.current.response=data.response_id;
        if(data.type==='answer.text'&&data.answer)onAnswer(data.answer);
        if(data.type==='answer.text')dispatch({type:'answer',text:data.text||data.answer?.text||''});
        if(data.type==='audio.chunk'&&data.audio){speaking.current=true;void player.current.play(data.audio)}
        if(data.type==='answer.complete'){
          const finish=()=>{speaking.current=false;dispatch({type:'state',state:'listening'})};
          const remaining=player.current.remainingMs();
          if(remaining>0)playbackTimer.current=window.setTimeout(finish,remaining);else finish();
        }
        if(data.type==='error')dispatch({type:'error',message:data.message||'음성 처리 중 오류가 발생했습니다.'});
      };
      ws.onclose=()=>{socket.current=null;void mic.current?.stop();mic.current=null;dispatch({type:'reset'})};
      ws.send(JSON.stringify({type:'session.start',session_id:ticket.session_id,lot_id:lotId||null}));
      mic.current=new MicrophoneCapture();
      await mic.current.start((audio,level)=>{
        dispatch({type:'level',level});
        if((speaking.current||player.current.isPlaying())&&level>.12){
          if(!loudSince.current)loudSince.current=Date.now();
          if(Date.now()-loudSince.current>800){
            player.current.cancel();speaking.current=false;
            if(playbackTimer.current!==null)window.clearTimeout(playbackTimer.current);playbackTimer.current=null;
            if(ids.current.response)ws.send(JSON.stringify({type:'response.cancel',response_id:ids.current.response}));
            dispatch({type:'state',state:'listening'});loudSince.current=0;
          }
        }else loudSince.current=0;
        if(ws.readyState!==WebSocket.OPEN)return;
        if(!ids.current.utterance)ids.current.utterance=crypto.randomUUID();
        ws.send(JSON.stringify({type:'audio.chunk',session_id:ids.current.session,utterance_id:ids.current.utterance,sequence:ids.current.sequence++,audio}));
      });
      dispatch({type:'state',state:'listening'});
    }catch(error){await stop();dispatch({type:'error',message:error instanceof Error?error.message:'마이크를 시작하지 못했습니다.'})}
  },[lotId,onAnswer,onUser,stop]);

  useEffect(()=>()=>{void stop()},[stop]);
  return {...view,active:view.state!=='idle'&&view.state!=='error',start,stop};
}
