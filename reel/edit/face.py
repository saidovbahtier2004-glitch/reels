import cv2, json, numpy as np, glob
fs = sorted(glob.glob("frames/*.jpg")); casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
pts = {}
for i in range(0, len(fs), 3):
    g = cv2.cvtColor(cv2.imread(fs[i]), cv2.COLOR_BGR2GRAY)
    r = casc.detectMultiScale(g, 1.1, 5, minSize=(24, 24))
    if len(r): x, y, w, h = max(r, key=lambda b: b[2]); pts[i] = (x + w / 2, y + h / 2, w)
ks = sorted(pts); print(len(ks), "of", len(range(0, len(fs), 3)), "detections")
xs = np.interp(range(len(fs)), ks, [pts[k][0] for k in ks]); ys = np.interp(range(len(fs)), ks, [pts[k][1] for k in ks]); ws = np.interp(range(len(fs)), ks, [pts[k][2] for k in ks])
def sm(a, n=45):
    k = np.ones(n) / n; p = np.pad(a, n // 2, mode="edge"); return np.convolve(p, k, "valid")[:len(a)]
json.dump(dict(fps=60, n=len(fs), x=[round(v, 1) for v in sm(xs)], y=[round(v, 1) for v in sm(ys)], w=[round(v, 1) for v in sm(ws)]), open("face.json", "w"))
print("face x/y/w sample", xs[0], ys[0], ws[0], xs[1200], ys[1200], ws[1200])
