class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buffer = [];
    this.ratio = sampleRate / 16000;
    this.cursor = 0;
  }

  process(inputs) {
    const input = inputs[0]?.[0];
    if (!input) return true;
    while (this.cursor < input.length) {
      const value = Math.max(-1, Math.min(1, input[Math.floor(this.cursor)]));
      this.buffer.push(Math.round(value * 32767));
      this.cursor += this.ratio;
    }
    this.cursor -= input.length;
    while (this.buffer.length >= 320) {
      const frame = this.buffer.splice(0, 320);
      const pcm = new Int16Array(frame);
      let sum = 0;
      for (const sample of pcm) sum += sample * sample;
      this.port.postMessage({pcm: pcm.buffer, level: Math.sqrt(sum / pcm.length) / 32768}, [pcm.buffer]);
    }
    return true;
  }
}

registerProcessor('pcm-processor', PcmProcessor);
