type FrameHandler=(base64:string,level:number)=>void;

export class MicrophoneCapture{
  private stream:MediaStream|null=null;
  private context:AudioContext|null=null;
  async start(onFrame:FrameHandler){
    this.stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
    this.context=new AudioContext();
    await this.context.resume();
    await this.context.audioWorklet.addModule('/pcm-processor.js');
    const source=this.context.createMediaStreamSource(this.stream);
    const worklet=new AudioWorkletNode(this.context,'pcm-processor');
    const silent=this.context.createGain();silent.gain.value=0;
    worklet.port.onmessage=({data}:{data:{pcm:ArrayBuffer;level:number}})=>{
      const bytes=new Uint8Array(data.pcm);let binary='';
      for(let i=0;i<bytes.length;i++)binary+=String.fromCharCode(bytes[i]);
      onFrame(btoa(binary),data.level);
    };
    source.connect(worklet);worklet.connect(silent);silent.connect(this.context.destination);
  }
  async stop(){this.stream?.getTracks().forEach(track=>track.stop());this.stream=null;await this.context?.close();this.context=null}
}
