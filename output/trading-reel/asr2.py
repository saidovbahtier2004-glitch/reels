import sherpa_onnx, wave, numpy as np, json, sys
S=sys.argv[1]; M=S+'/models/sherpa-onnx-whisper-large-v3/'
w=wave.open(S+'/a.wav'); a=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768
cfg=sherpa_onnx.VadModelConfig(); cfg.silero_vad.model=S+'/models/silero_vad.onnx'; cfg.silero_vad.min_silence_duration=0.9; cfg.silero_vad.min_speech_duration=0.2; cfg.silero_vad.max_speech_duration=25; cfg.sample_rate=16000
vad=sherpa_onnx.VoiceActivityDetector(cfg,buffer_size_in_seconds=100)
rec=sherpa_onnx.OfflineRecognizer.from_whisper(encoder=M+'large-v3-encoder.int8.onnx',decoder=M+'large-v3-decoder.int8.onnx',tokens=M+'large-v3-tokens.txt',language=sys.argv[2],task='transcribe',num_threads=4)
segs=[]
i=0
while i<len(a):
    vad.accept_waveform(a[i:i+512]); i+=512
vad.flush()
while not vad.empty():
    s=vad.front; st=s.start/16000; x=np.array(s.samples,np.float32)
    strm=rec.create_stream(); strm.accept_waveform(16000,x); rec.decode_stream(strm)
    segs.append(dict(start=st,end=st+len(x)/16000,text=strm.result.text.strip())); print(segs[-1],flush=True)
    vad.pop()
json.dump(segs,open(S+'/segs2_%s.json'%sys.argv[2],'w'),ensure_ascii=False,indent=1)
