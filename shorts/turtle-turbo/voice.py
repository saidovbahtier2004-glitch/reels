import json, soundfile as sf, numpy as np
from kokoro_onnx import Kokoro
k=Kokoro("/tmp/claude-0/tts/kokoro.onnx","/tmp/claude-0/tts/voices.bin")
N="af_heart"; BUN="af_sky"
lines=[
 ("intro",N,"In a green meadow lived Turbo... the slowest turtle in the whole forest."),
 ("race",N,"One day, the animals had a big race to the old oak tree. Ready... set... go!"),
 ("zoom",N,"Zoom! Bunny dashed ahead. Turbo just kept going, step by step."),
 ("fall",N,"But at the river, Bunny slipped... and fell into the water!"),
 ("help",BUN,"Help! Help! I can't swim!"),
 ("swim",N,"Turbo didn't think twice. He swam out, and carried Bunny safely on his shell."),
 ("thanks",BUN,"Thank you, Turbo! You're my hero!"),
 ("finish",N,"They crossed the finish line together. Last place... but the biggest winners of all."),
 ("moral",N,"Remember: being kind is always better than being first."),
]
sr=24000; out=[np.zeros(int(sr*0.6))]; t=0.6; tl=[]
for key,v,txt in lines:
    s,sr=k.create(txt,voice=v,speed=0.92 if v==N else 1.0,lang="en-us")
    d=len(s)/sr; tl.append({"key":key,"start":round(t,3),"end":round(t+d,3),"text":txt})
    out.append(s); out.append(np.zeros(int(sr*0.6))); t+=d+0.6
out.append(np.zeros(int(sr*1.6))); t+=1.6
sf.write("voice.wav",np.concatenate(out).astype(np.float32),sr)
json.dump({"duration":round(t,3),"lines":tl},open("timeline.json","w"),indent=1)
print(round(t,2)); [print(l["key"],l["start"],l["end"]) for l in tl]
