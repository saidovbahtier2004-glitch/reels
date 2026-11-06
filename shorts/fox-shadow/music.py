import numpy as np, soundfile as sf, json
sr=44100; D=json.load(open("timeline.json"))["duration"]; n=int(sr*D); out=np.zeros(n)
def note(f,t0,dur,amp,kind="bell"):
    i0=int(t0*sr); L=int(dur*sr); 
    if i0>=n: return
    L=min(L,n-i0); t=np.arange(L)/sr
    if kind=="bell": w=(np.sin(2*np.pi*f*t)+.3*np.sin(2*np.pi*2*f*t)+.1*np.sin(2*np.pi*3*f*t))*np.exp(-t*3)
    else: w=(np.sin(2*np.pi*f*t)+.5*np.sin(2*np.pi*f*1.005*t))*np.minimum(1,t/.5)*np.minimum(1,(dur-t)/.6)
    out[i0:i0+L]+=amp*w
hz=lambda m:440*2**((m-69)/12)
bpm=96; beat=60/bpm
happy=[[60,64,67,72],[57,60,64,69],[53,57,60,65],[55,59,62,67]]  # C Am F G
sad=[[57,60,64,69],[53,57,60,65],[52,55,59,64],[57,60,64,69]]     # Am F Em Am
t=0;bar=0
while t<D:
    gloom = 11.5<t<31.5
    ch=(sad if gloom else happy)[bar%4]
    note(hz(ch[0]-12),t,beat*4,.10,"pad")
    pattern=[0,1,2,3,2,1,2,3] if not gloom else [0,2,1,3]
    step=beat/2 if not gloom else beat
    for k,p in enumerate(pattern): note(hz(ch[p]+12),t+k*step,1.2,.08 if not gloom else .06)
    t+=beat*4;bar+=1
# sparkle when shadow returns
for k,m in enumerate([72,76,79,84,88,91]): note(hz(m),32.4+k*.08,1.5,.07)
out/=np.max(np.abs(out))*1.1
fade=np.minimum(1,np.minimum(np.arange(n)/sr/1.0,(n-np.arange(n))/sr/1.5))
sf.write("music.wav",(out*fade).astype(np.float32),sr)
