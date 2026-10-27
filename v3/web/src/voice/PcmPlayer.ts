export class PcmPlayer{
  private context:AudioContext|null=null;
  private next=0;
  private sources=new Set<AudioBufferSourceNode>();

  async play(base64:string){
    this.context??=new AudioContext({sampleRate:16000});
    await this.context.resume();
    const bytes=Uint8Array.from(atob(base64),c=>c.charCodeAt(0));
    const pcm=new Int16Array(bytes.buffer);
    const audio=this.context.createBuffer(1,pcm.length,16000);
    const channel=audio.getChannelData(0);
    for(let i=0;i<pcm.length;i++)channel[i]=pcm[i]/32768;
    const source=this.context.createBufferSource();
    source.buffer=audio;source.connect(this.context.destination);
    this.next=Math.max(this.next,this.context.currentTime+.02);
    source.start(this.next);this.next+=audio.duration;this.sources.add(source);
    source.onended=()=>this.sources.delete(source);
  }
  cancel(){for(const source of this.sources){try{source.stop()}catch{}}this.sources.clear();this.next=0}
  remainingMs(){return this.context?Math.max(0,(this.next-this.context.currentTime)*1000):0}
  isPlaying(){return this.remainingMs()>0}
  async close(){this.cancel();await this.context?.close();this.context=null}
}
