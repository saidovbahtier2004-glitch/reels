import cv2, numpy as np, subprocess, json, sys
V=sys.argv[1]; W,H=360,640
p=subprocess.Popen(['ffmpeg','-v','error','-i',V,'-vf',f"fps=30,curves=master='0/0 0.06/0.13 0.25/0.42 0.55/0.72 1/0.97',scale={W}:{H}",'-f','rawvideo','-pix_fmt','gray','-'],stdout=subprocess.PIPE)
cc=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
out=[];last=None
while True:
    b=p.stdout.read(W*H)
    if len(b)<W*H: break
    g=np.frombuffer(b,np.uint8).reshape(H,W); g=cv2.equalizeHist(g)
    f=cc.detectMultiScale(g,1.1,5,minSize=(80,80))
    if len(f): x,y,w,h=max(f,key=lambda r:r[2]*r[3]); last=[(x+w/2)/W,(y+h/2)/H,w/W]
    out.append(last)
json.dump(out,open('faces.json','w')); 
a=np.array([o for o in out if o]); print(len(out),sum(o is None for o in out),a.mean(0),a.min(0),a.max(0))
