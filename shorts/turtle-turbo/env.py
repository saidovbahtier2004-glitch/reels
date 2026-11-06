import json, soundfile as sf, numpy as np
s,sr=sf.read("voice.wav"); fps=30; hop=sr//fps
n=len(s)//hop; env=[float(np.sqrt(np.mean(s[i*hop:(i+1)*hop]**2))) for i in range(n)]
m=max(env); env=[round(min(1,e/m*1.6),3) for e in env]
tl=json.load(open("timeline.json")); tl["env"]=env; tl["fps"]=fps
open("timeline.js","w").write("window.TL="+json.dumps(tl)+";")
