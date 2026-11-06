import json, soundfile as sf, numpy as np
from kokoro_onnx import Kokoro
k=Kokoro("/tmp/claude-0/tts/kokoro.onnx","/tmp/claude-0/tts/voices.bin")
N="af_heart"; FOX="af_nicole"; OWL="bm_george"
lines=[
 ("intro",N,"Once upon a time, in a sunny forest, there lived a little fox named Finn."),
 ("play",N,"Every day, Finn played with his very best friend... his shadow!"),
 ("cloud",N,"But one cloudy morning, Finn looked down... and his shadow was gone!"),
 ("search",N,"He searched everywhere. Under the rocks. Behind the trees. Even in the river."),
 ("cry",FOX,"Shadow? Where are you?"),
 ("owl",OWL,"Your shadow never left you, little one. It is just waiting for the light."),
 ("wait",N,"So Finn waited, and waited... until the clouds drifted away."),
 ("back",N,"And there it was! His shadow, dancing right beside him."),
 ("moral",N,"Remember: on cloudy days, the ones who love you are never really gone."),
]
sr=24000; out=[]; t=0.6; tl=[]
out.append(np.zeros(int(sr*0.6)))
for key,v,txt in lines:
    s,sr=k.create(txt,voice=v,speed=0.92 if v!=OWL else 0.85,lang="en-gb" if v==OWL else "en-us")
    d=len(s)/sr; tl.append({"key":key,"start":round(t,3),"end":round(t+d,3),"text":txt})
    out.append(s); gap=0.7; out.append(np.zeros(int(sr*gap))); t+=d+gap
out.append(np.zeros(int(sr*1.5))); t+=1.5
sf.write("voice.wav",np.concatenate(out).astype(np.float32),sr)
json.dump({"duration":round(t,3),"lines":tl},open("timeline.json","w"),indent=1)
print(round(t,2)); [print(l["key"],l["start"],l["end"]) for l in tl]
