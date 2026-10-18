"""Refine word timings with syllable nuclei detected in the real voice track (monotonic Viterbi alignment).
Prior = proportional placement (align.py). No ASR model available offline: text comes from the supplied script."""
import json, re, sys, wave, subprocess, numpy as np
src, prior_f, out = sys.argv[1:4]
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "/tmp/v16.wav"], check=True)
w = wave.open("/tmp/v16.wav"); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / sr); X[(f < 250) | (f > 3200)] = 0; y = np.fft.irfft(X, len(x))
k = int(.012 * sr); e = np.sqrt(np.convolve(y ** 2, np.ones(k) / k, "same")); hop = int(.005 * sr); s = np.convolve(e[::hop], np.ones(9) / 9, "same")
thr = np.percentile(s, 40) * 1.2; pk = [i for i in range(3, len(s) - 3) if s[i] == s[i - 3:i + 4].max() and s[i] > thr]; fp = []
for i in pk:
    if fp:
        dip = s[fp[-1]:i].min()
        if dip > .8 * min(s[fp[-1]], s[i]) or (i - fp[-1]) * .005 < .07:
            if s[i] > s[fp[-1]]: fp[-1] = i
            continue
    fp.append(i)
nuc = np.array(fp) * .005
P = json.load(open(prior_f)); words = P["words"]
def syl(w): w = w.lower().replace('‘', '').replace('’', '').replace("'", ''); return max(1, len(re.findall('[aeiouy]', w)))
SP = {"2": "ikki", "10": "o‘n", "AI": "eyay", "Claude": "klod", "‘+’": "plyus", "motion": "moushn"}
syls = []  # (word idx, prior time)
for i, wd in enumerate(words):
    n = syl(SP.get(wd["w"], wd["w"])); 
    for j in range(n): syls.append((i, wd["t0"] + (wd["t1"] - wd["t0"]) * (j + .5) / n))
S, Nn = len(syls), len(nuc); SKS, SKN, TH = .22, .12, .38
INF = 1e9; D = np.full((S + 1, Nn + 1), INF); B = np.zeros((S + 1, Nn + 1), np.int8); D[0, 0] = 0
for j in range(1, Nn + 1): D[0, j] = D[0, j - 1] + SKN; B[0, j] = 2
for i in range(1, S + 1):
    D[i, 0] = D[i - 1, 0] + SKS; B[i, 0] = 1
    for j in range(1, Nn + 1):
        d = abs(syls[i - 1][1] - nuc[j - 1]); best = D[i - 1, j] + SKS; b = 1
        if D[i, j - 1] + SKN < best: best = D[i, j - 1] + SKN; b = 2
        if d < TH and D[i - 1, j - 1] + d < best: best = D[i - 1, j - 1] + d; b = 0
        D[i, j] = best; B[i, j] = b
i, j = S, Nn; m = [None] * S
while i > 0 or j > 0:
    b = B[i, j]
    if b == 0: m[i - 1] = nuc[j - 1]; i -= 1; j -= 1
    elif b == 1: i -= 1
    else: j -= 1
t = np.array([m[k] if m[k] is not None else np.nan for k in range(S)]); ok = ~np.isnan(t)
tp = np.array([a[1] for a in syls]); t[~ok] = np.interp(np.where(~ok)[0], np.where(ok)[0], (t - tp)[ok]) + tp[~ok]  # interpolate offset from neighbours
for k in range(1, S): t[k] = max(t[k], t[k - 1] + .03)
res = []
for i, wd in enumerate(words):
    idx = [k for k, a in enumerate(syls) if a[0] == i]; res.append(dict(w=wd["w"], t0=round(float(t[idx[0]]) - .06, 3), t1=round(float(t[idx[-1]]) + .11, 3)))
for i in range(len(res) - 1):
    res[i]["t1"] = min(res[i]["t1"], res[i + 1]["t0"] - .005); res[i]["t1"] = max(res[i]["t1"], res[i]["t0"] + .1)
shift = np.abs(np.array([r["t0"] - wd["t0"] for r, wd in zip(res, words)]))
json.dump(dict(words=res, matched=float(ok.mean())), open(out, "w"), ensure_ascii=False, indent=1)
print(f"nuclei {Nn}, script syllables {S}, matched {ok.mean():.0%}, mean shift vs prior {shift.mean():.2f}s, max {shift.max():.2f}s")
