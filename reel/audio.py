"""Synthesised music bed + sound design, driven by timeline.json. 48 kHz stereo, no external samples."""
import json, numpy as np, wave, sys
SR = 48000; TL = json.load(open("timeline.json")); TOT = TL["total"] + 1.2
N = int(TOT * SR); rs = np.random.RandomState(4)
def sc(n): return TL["scenes"][n]
def cue(i, name): s = TL["scenes"][i]; return s["cues"][name]
def S(idx): return TL["scenes"][idx]["start"]
tt = lambda d: np.arange(int(d * SR)) / SR
def lp(x, fc, n=1):
    a = np.exp(-2 * np.pi * fc / SR)
    for _ in range(n):
        y = np.empty_like(x); z = 0.0
        for i, v in enumerate(x): z = (1 - a) * v + a * z; y[i] = z
        x = y
    return x
def lp_fast(x, fc):  # FFT brickwall-ish smoothing (fast)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR); X *= 1 / (1 + (f / fc) ** 4); return np.fft.irfft(X, len(x))
def hp_fast(x, fc): return x - lp_fast(x, fc)
def bp_fast(x, lo, hi): return lp_fast(hp_fast(x, lo), hi)
def env(n, a, d): t = np.arange(n) / SR; return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)
L = np.zeros(N); R = np.zeros(N)
def add(buf, x, t0, g=1.0, pan=0.0):
    i = int(t0 * SR); 
    if i >= N or i < 0: return
    x = x[:N - i]; l = g * np.sqrt(.5 * (1 - pan)); r = g * np.sqrt(.5 * (1 + pan)); L[i:i + len(x)] += x * l; R[i:i + len(x)] += x * r
db = lambda d: 10 ** (d / 20)
# ---------- SFX ----------
def whoosh(dur=.55, up=True, bright=1.0):
    n = int(dur * SR); x = rs.randn(n); t = np.arange(n) / n
    # time-varying band: sweep via crossfading filtered copies
    lo = bp_fast(x, 300, 1500); hi = bp_fast(x, 1500, 7000 * bright); w = (t if up else 1 - t)
    y = lo * (1 - w) + hi * w; a = np.sin(np.pi * t) ** 1.6; return y * a * .9
def impact(dur=1.2, f0=95, f1=38):
    t = tt(dur); ph = 2 * np.pi * (f1 * t + (f0 - f1) * .09 * (1 - np.exp(-t / .09))); s = np.sin(ph) * np.exp(-t / .38)
    n = bp_fast(rs.randn(len(t)), 60, 900) * np.exp(-t / .07) * .8; k = np.sin(2 * np.pi * 52 * t) * np.exp(-t / .6) * .5
    return np.tanh(1.8 * (s + n + k)) * .85
def click(f=2400): t = tt(.07); return (np.sin(2 * np.pi * f * t) * np.exp(-t / .008) + hp_fast(rs.randn(len(t)), 3000) * np.exp(-t / .004) * .6) * .8
def pop_(f=620): t = tt(.18); fr = f * (1 + .9 * np.exp(-t / .03)); return np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t / .05) * .9
def riser(dur=1.2):
    n = int(dur * SR); t = np.arange(n) / n; x = rs.randn(n); y = bp_fast(x, 400, 2500) * t ** 2.2
    s = np.sin(2 * np.pi * np.cumsum(200 * 2 ** (t * 2.5)) / SR) * .25 * t ** 2; return (y * .6 + s) * np.minimum(1, (1 - t) * 40 + .0)
def blip(f=1200, n=3, gap=.06):
    out = np.zeros(int((n * gap + .15) * SR))
    for k in range(n):
        t = tt(.1); s = np.sin(2 * np.pi * f * (1 + .25 * k) * t) * np.exp(-t / .03) * .5; i = int(k * gap * SR); out[i:i + len(s)] += s
    return out
def ding(): t = tt(.9); return (np.sin(2 * np.pi * 1318 * t) * np.exp(-t / .22) + .6 * np.sin(2 * np.pi * 1760 * t) * np.exp(-t / .18) * (t > .09)) * .35 * (1 - np.exp(-t / .002))
def tick(): t = tt(.03); return np.sin(2 * np.pi * 1800 * t) * np.exp(-t / .006) * .4
def glitch(): n = int(.22 * SR); x = np.sign(rs.randn(n)) * (rs.rand(n) > .6); x = hp_fast(x, 1500) * np.exp(-np.arange(n) / SR / .1); return x * .6
def sweep(dur=.5): return whoosh(dur, True, 1.2) * .8
def chime_end():
    out = np.zeros(int(3.2 * SR))
    for k, f in enumerate([523.25, 659.25, 783.99, 1046.5]):
        t = tt(2.6); s = np.sin(2 * np.pi * f * t) * np.exp(-t / 1.0) * .22; i = int(k * .09 * SR); out[i:i + len(s)] += s[:len(out) - i]
    return out
# ---------- scene cue map (name -> time) ----------
H_, I_, A_, G_, W_, T_, P_, K_, C_ = range(9)
ev = []  # (fn, t, gain_db, pan)
def E_(fn, t, g=0, pan=0): ev.append((fn, t, g, pan))
# 1 HOOK
E_(lambda: whoosh(.5, True), 0.0, -9); E_(lambda: pop_(500), cue(H_, 'dostlar') + .05, -12)
E_(lambda: riser(.5), cue(H_, 'ai') - .45, -14); E_(lambda: impact(1.3), cue(H_, 'ai') + .02, -4); E_(glitch, cue(H_, 'ai') + .03, -14)
E_(lambda: pop_(700), cue(H_, 'montaj') + .3, -12)
E_(lambda: riser(.55), cue(H_, 'ishon') - .55, -12); E_(lambda: impact(1.8, 80, 32), cue(H_, 'ishon') + .0, -2); E_(lambda: pop_(450), cue(H_, 'ishon') + .35, -12)
E_(lambda: sweep(.45), S(I_) - .30, -9)
# 2 INTRO
E_(lambda: whoosh(.4, True, .8), cue(I_, 'name') - .05, -12); E_(lambda: click(3200), cue(I_, 'name') + .55, -17)
E_(lambda: pop_(660), cue(I_, 'mob') + .02, -12)
E_(lambda: whoosh(.3), cue(I_, 'two') - .1, -14); [E_(tick, cue(I_, 'two') + k * .2, -18) for k in range(3)]
E_(lambda: pop_(760), cue(I_, 'two') + .58, -12)
E_(lambda: riser(.5), cue(I_, 'ten') - .45, -17); [E_(tick, cue(I_, 'ten') + k * .065, -20) for k in range(10)]
E_(lambda: impact(.9, 85, 45), cue(I_, 'ten') + .64, -7); E_(lambda: pop_(820), cue(I_, 'ten') + .7, -12)
E_(lambda: whoosh(.45, True, .9), S(A_) - .32, -8)
# 3 AI
E_(lambda: whoosh(.7, False), S(A_) + .05, -14); E_(lambda: blip(1000, 3), S(A_) + .5, -18)
[E_(lambda: click(2000), S(A_) + 1.0 + k * .16, -19) for k in range(5)]
E_(lambda: impact(1.0, 90, 40), cue(A_, 'claude'), -6); E_(lambda: pop_(700), cue(A_, 'claude') + .02, -12)
[E_(lambda: blip(1500 + 250 * k, 2, .05), cue(A_, 'ai') + k * .38, -17) for k in range(4)]
E_(lambda: glitch(), S(G_) - .22, -13)
# 4 GROW
E_(lambda: impact(.9, 95, 42), cue(G_, 'ai') - .02, -8); E_(lambda: blip(1400, 4, .05), cue(G_, 'ai') + .2, -16)
E_(lambda: whoosh(.35, True), cue(G_, 'kundan') - .1, -14); E_(lambda: whoosh(.4, True), cue(G_, 'riv') - .05, -12); E_(lambda: whoosh(.4, True), cue(G_, 'riv') + .12, -13)
E_(lambda: riser(.8), S(W_) - .8, -14); E_(lambda: sweep(.5), S(W_) - .3, -10)
# 5 WANT
tiles = [.1, .6, 1.02, 1.38, 1.7, 2.0]
[E_(lambda: whoosh(.22, True, 1.2), S(W_) + tl - .02, -15 + k * .6) for k, tl in enumerate(tiles)]
E_(lambda: pop_(600), cue(W_, 'motion') + .02, -12); E_(lambda: riser(.4), cue(W_, 'yas') - .4, -13)
E_(lambda: impact(1.4, 100, 40), cue(W_, 'yas') - .02, -4); E_(lambda: whoosh(.35, True), cue(W_, 'yas'), -12)
E_(lambda: sweep(.5), S(T_) - .3, -9)
# 6 TELEGRAM
E_(lambda: whoosh(.6, True, .8), cue(T_, 'tg') - .8, -13); E_(lambda: impact(.8, 110, 50), cue(T_, 'tg') - .02, -9); E_(lambda: pop_(800), cue(T_, 'tg') + .02, -13)
E_(ding, cue(T_, 'video') - .0, -11); E_(lambda: pop_(700), cue(T_, 'video') + .12, -16); E_(lambda: pop_(760), cue(T_, 'lesson') + .0, -16); E_(lambda: pop_(820), cue(T_, 'lesson') + .45, -16)
E_(lambda: whoosh(.4, True), S(P_) - .3, -9)
# 7 PLUS COMMENT
tP = cue(P_, 'plus') + .1; tTap = tP - 1.05; tSend = cue(P_, 'send') + .25; tOpen = cue(P_, 'open') - .05
E_(lambda: whoosh(.5, False), tOpen, -14); E_(lambda: pop_(500), tOpen + .45, -17)
E_(lambda: whoosh(.5, True, .7), tTap - .5, -17); E_(lambda: click(1800), tTap + .02, -13)
E_(lambda: whoosh(.3, False, .6), tTap + .06, -18)
E_(lambda: click(2200), tP - .06 + .06, -9); E_(lambda: impact(1.0, 100, 45), tP - .02, -6); E_(lambda: pop_(900), tP + .02, -13)
E_(lambda: riser(.45), tP - .5, -19)
E_(lambda: whoosh(.4, True), tP + .65, -13); E_(lambda: pop_(620), tP + .75, -12)
E_(lambda: click(2600), tSend - .02, -12); E_(lambda: whoosh(.5, True, 1.1), tSend, -13); E_(lambda: pop_(700), tSend + .3, -13)
E_(lambda: sweep(.45), S(K_) - .3, -9)
# 8 LINK
E_(lambda: whoosh(.6, True), S(K_) + .3, -12); E_(lambda: impact(.9, 95, 42), cue(K_, 'link'), -7); E_(lambda: blip(1300, 3), cue(K_, 'link') + .1, -17); E_(lambda: pop_(800), cue(K_, 'link') + .3, -13)
E_(lambda: whoosh(.35, True), cue(K_, 'tg') - .25, -14); E_(ding, cue(K_, 'tg') + .05, -14)
[E_(lambda: pop_(600 + 80 * k), cue(K_, 'tg') + .2 + k * .22, -17) for k in range(3)]
E_(lambda: whoosh(.45, False), cue(K_, 'motion') - .2, -14); [E_(lambda: click(2000), cue(K_, 'motion') + .1 + k * .12, -20) for k in range(4)]
E_(lambda: riser(.5), cue(K_, 'learn') - .5, -16); E_(lambda: impact(.9, 100, 45), cue(K_, 'learn') - .08, -9); E_(lambda: pop_(900), cue(K_, 'learn') + .4, -12)
E_(lambda: impact(1.5, 100, 36), S(C_) - .02, -3); E_(lambda: whoosh(.4, True), S(C_) - .22, -10)
# 9 CTA
E_(lambda: click(2400), cue(C_, 'sub') + .75, -9); E_(lambda: pop_(700), cue(C_, 'sub') + .8, -12); E_(lambda: chime_end(), cue(C_, 'sub') + .82, -26)
E_(lambda: click(2200), cue(C_, 'plus') + .0, -9); E_(lambda: impact(1.0, 100, 45), cue(C_, 'plus') - .02, -6); E_(lambda: pop_(900), cue(C_, 'plus') + .05, -12)
E_(lambda: riser(.5), cue(C_, 'bye') - .5, -17); E_(lambda: impact(1.6, 90, 38), cue(C_, 'bye') - .02, -6); E_(lambda: chime_end(), cue(C_, 'bye') + .05, -17)
sfxL, sfxR = None, None
for fn, t, g, pan in ev:
    x = fn(); x = x / max(1e-9, np.max(np.abs(x))) * db(g); add(None, x, t, 1.0, pan)
sL, sR = L.copy(), R.copy()
# ---------- MUSIC ----------
L[:] = 0; R[:] = 0
BPM = 112; beat = 60 / BPM; bars = int(TOT / (beat * 4)) + 2
def kick(): t = tt(.35); f = 48 + 90 * np.exp(-t / .03); return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .16)
def hat(o=False): d = .22 if o else .06; t = tt(d); return hp_fast(rs.randn(len(t)), 7000) * np.exp(-t / (.08 if o else .018)) * .5
def clap(): t = tt(.25); return bp_fast(rs.randn(len(t)), 900, 4500) * np.exp(-t / .07) * .8
def bass(f, d): t = tt(d); s = np.sin(2 * np.pi * f * t) + .35 * np.sin(4 * np.pi * f * t); return s * np.minimum(1, t / .01) * np.exp(-t / (d * .8)) * .8
def pluck(f, d=.5): t = tt(d); s = np.sin(2 * np.pi * f * t) + .4 * np.sin(4 * np.pi * f * t) * np.exp(-t / .1) + .2 * np.sin(6 * np.pi * f * t) * np.exp(-t / .05); return s * np.exp(-t / .16) * (1 - np.exp(-t / .002))
def pad(fs, d):
    t = tt(d); s = sum(np.sin(2 * np.pi * f * t * (1 + k * .003)) + .5 * np.sin(2 * np.pi * f * 2 * t) * .3 for f in fs for k in (-1, 0, 1)); s = lp_fast(s, 1400); return s * np.minimum(1, t / .8) * np.minimum(1, (d - t) / .8)
chords = [(55.0, [220, 261.63, 329.63]), (43.65, [174.61, 220, 261.63]), (65.41, [196, 261.63, 329.63]), (49.0, [196, 246.94, 293.66])]  # Am F C G
# section intensity (0..1) by scene
def inten(t):
    for i, s in enumerate(TL["scenes"]):
        if t < s["start"] + s["dur"]: return [.55, .35, .9, 1, 1, .8, .85, 1, .9][i]
    return .5
for b in range(bars):
    t0 = b * beat * 4; ch = chords[b % 4]; it = inten(t0)
    add(None, pad(ch[1], beat * 4 + .6), t0, .10 * (1.0 if it < .5 else .8), 0)
    for q in range(4):
        tb = t0 + q * beat; it = inten(tb)
        if it >= .55 and (q % 2 == 0 or it > .85): add(None, kick(), tb, .9 * min(1, it + .1), 0)
        if it >= .8 and q % 2 == 1: add(None, clap(), tb, .30, 0)
        if it >= .6:
            add(None, hat(), tb + beat / 2, .22 * it, .2); add(None, hat(), tb, .12 * it, -.2)
            if it > .85: add(None, hat(True), tb + beat * .75, .1, .1)
        if it >= .8: add(None, bass(ch[0], beat * .9), tb + (beat / 2 if q % 2 else 0), .5, 0)
        # arpeggio pluck
        arp = ch[1][(q * 2) % 3] * (2 if q % 2 else 1)
        for h_ in range(2):
            tp = tb + h_ * beat / 2
            if inten(tp) >= .3: add(None, pluck(arp * (1.5 if h_ else 1)), tp, .09 * (.5 + inten(tp) * .5), -.4 if h_ else .4)
musicL, musicR = L.copy(), R.copy()
# music reverb-ish tail (simple stereo delay) and gain, natural ending
def finish(x): 
    d = int(beat * .75 * SR); y = x.copy(); y[d:] += x[:-d] * .28; y[2 * d:] += x[:-2 * d] * .12; return y
musicL, musicR = finish(musicL), finish(musicR)
endt = TL["total"]; tm = np.arange(N) / SR
fade = np.clip((endt + .9 - tm) / 1.6, 0, 1) ** 1.5; fade_in = np.clip(tm / .05, 0, 1)
musicL *= fade * fade_in; musicR *= fade * fade_in
def wr(name, l, r, g):
    x = np.stack([l, r], 1) * g; x = np.clip(x, -1, 1); w = wave.open(name, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype("<i2").tobytes()); w.close()
pk = max(np.max(np.abs(musicL)), np.max(np.abs(musicR))); mg = 0.5 / pk
wr("out/music.wav", musicL, musicR, mg); sp = max(np.max(np.abs(sL)), np.max(np.abs(sR))); wr("out/sfx.wav", sL, sR, 0.9 / sp)
print("music gain", mg, "sfx peak", sp, "dur", TOT)
