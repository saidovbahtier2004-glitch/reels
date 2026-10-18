"""Forced-alignment-lite: script words -> times, using speech/pause structure of the real voice track.
No ASR model is reachable offline, so this uses (a) silence detection to find speech segments and
(b) syllable-weighted proportional placement inside voiced time, snapping phrase ends to real pauses."""
import re, subprocess, json, sys, numpy as np
src = sys.argv[1]; out = sys.argv[2]
SCRIPT = [  # (display word, spoken form for syllable count)
 "Do‘stlar,|do‘stlar","bu","videoni","AI|eyay","montaj","qildi","desam,","ishonasizmi?",
 "Men","Saidov","Baxtiyor,","mobilograf","sohasida","2|ikki","yildan","buyon","ishlab","kelmoqdaman","va","hozirda","10|o‘n","dan","ortiq","loyihalar","bilan","ishlab","kelmoqdaman.",
 "Siz","ko‘rib","turganingizdek,","mana","shu","videoni","Claude|klod","AI|eyay","yasab","bermoqda-da,","do‘stlar.",
 "Hozirda","AI|eyay","juda","ham","kundan","kunga","rivojlanib","ketmoqda.",
 "Siz","ham","xuddi","shunday","motion|moushn","videolar","yasamoqchimisiz?",
 "Albatta,","sizlar","uchun","Telegramda","yopiq","kanalda","video","darslik","joylab","qo‘yganman.",
 "Bu","darslikni","olish","uchun","kommentariyada","‘+’|plyus","belgisini","yozib","qoldiring,","men","sizga","silkasini","jo‘nataman.",
 "Men","sizga","silkasini","jo‘nataman,","siz","ham","xuddi","shunday","motion|moushn","videolarni","osongina","yasashni","o‘rganasiz.",
 "Obuna","bo‘lib","qo‘yishni","unutmang,","kommentga","plus","belgisini","qoldiring,","ko‘rishguncha!"]
def syl(w): w = w.lower().replace('‘','').replace('’','').replace("'",''); return max(1, len(re.findall('[aeiouy]', w)))
words = [(s.split('|')[0], s.split('|')[-1]) for s in SCRIPT]; sy = np.array([syl(sp) for _, sp in words], float)
# silence detection
r = subprocess.run(["ffmpeg","-hide_banner","-i",src,"-vn","-af","silencedetect=noise=-36dB:d=0.16","-f","null","-"],capture_output=True,text=True).stderr
st = [float(m) for m in re.findall(r"silence_start: (-?[\d.]+)", r)]; en = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", r)]
dur = float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",src],capture_output=True,text=True).stdout)
segs = []; t = 0.0
if en and (not st or en[0] < st[0]): t = en[0]; en = en[1:]
for s_, e_ in zip(st, en + [dur]): 
    if s_ - t > .05: segs.append([t, s_])
    t = e_
if t < dur - .05 and len(en) < len(st) + 1: pass
segs = [s for s in segs if s[1] - s[0] > .12]
if segs and segs[0][1] - segs[0][0] < .7 and segs[0][0] < .05: segs = segs[1:]
U = sum(b - a for a, b in segs); cum = np.concatenate([[0], np.cumsum([b - a for a, b in segs])])  # voiced coordinate at segment starts
def u2t(u):
    j = max(0, min(len(segs) - 1, np.searchsorted(cum, u, 'right') - 1)); return segs[j][0] + (u - cum[j])
def t2u(t):
    for j, (a, b) in enumerate(segs):
        if t <= b: return cum[j] + max(0, t - a)
    return U
# phrase ends (indices of words ending with punctuation)
ends = [i for i, (w, _) in enumerate(words) if re.search(r"[,.?!]$", w)]
tot = sy.sum(); cs = np.cumsum(sy)
gaps_u = [cum[j + 1] for j in range(len(segs) - 1)]  # voiced position of each pause
# weight words by syllables + small per-word constant
wt = sy + .35; cw = np.cumsum(wt); T = wt.sum()
bounds = {}
inner = ends[:-1]; G = len(gaps_u); SKIP = 1.15
us = [cw[i] / T * U for i in inner]
INF = 1e9; f = np.full((len(inner) + 1, G + 1), INF); bk = {}
f[0, :] = 0
for i in range(1, len(inner) + 1):
    for j in range(G + 1):
        # option 1: boundary i skipped
        best = f[i - 1, j] + SKIP; arg = ('skip', j)
        # option 2: boundary i matched to gap j-1 (previous gaps < j-1 used)
        if j >= 1:
            for jj in range(0, j):
                c = f[i - 1, jj] + abs(us[i - 1] - gaps_u[j - 1])
                if c < best: best = c; arg = ('match', jj)
        f[i, j] = best; bk[(i, j)] = arg
j = int(np.argmin(f[len(inner)])); i = len(inner)
while i > 0:
    kind, pj = bk[(i, j)]
    if kind == 'match': bounds[inner[i - 1]] = gaps_u[j - 1]
    i -= 1; j = pj
bounds[len(words) - 1] = U
# piecewise proportional placement
res = []; prev_i = -1; prev_u = 0.0
anch = sorted(bounds.items())
for bi, bu in anch:
    idx = list(range(prev_i + 1, bi + 1)); w_ = wt[idx]; tt = w_.sum(); c = prev_u
    for k, i in enumerate(idx):
        d = (bu - prev_u) * w_[k] / tt; res.append((words[i][0], u2t(c), u2t(c + d) if c + d <= U else u2t(U))); c += d
    prev_i, prev_u = bi, bu
json.dump(dict(segments=segs, anchors={words[i][0] + f"@{i}": round(u2t(v), 2) for i, v in bounds.items()},
               words=[dict(w=a, t0=round(b, 3), t1=round(c_, 3)) for a, b, c_ in res]), open(out, "w"), ensure_ascii=False, indent=1)
print(len(segs), "segments; anchored", len(bounds), "of", len(ends), "phrase ends; voiced", round(U, 1), "s of", round(dur, 1))
for a, b, c_ in res[::6]: print(f"{b:6.2f} {a}")
