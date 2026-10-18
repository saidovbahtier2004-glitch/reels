"""SFX + music bed for the talking-head edit, timed from words.json (same word indices as edit2.js)."""
import json, numpy as np, wave, re
src = open("../audio.py").read()
head = src.split("# ---------- scene cue map")[0].replace('TL = json.load(open("timeline.json")); TOT = TL["total"] + 1.2', 'TOT = 46.7')
ns = {}; exec(head, ns); globals().update({k: v for k, v in ns.items() if not k.startswith("__")})
music_defs = src.split("# ---------- MUSIC ----------")[1].split("for b in range(bars):")[0]
exec(music_defs.replace("def inten(t):", "def _old(t):"), globals())
WD = json.load(open("words.json"))["words"]; w0 = lambda i: WD[i]["t0"]; w1 = lambda i: WD[i]["t1"]
CUTS = [(w0(33) - .25, w1(36) + .15), (w0(56) - .05, w1(62) + .1), (w0(67) + .4, w1(71) + .6), (w0(78) - .35, w1(79) + .35)]
ev = []
def E_(fn, t, g=0, pan=0): ev.append((fn, t, g, pan))
# hook
E_(lambda: whoosh(.45, True), .55, -15)
for k in range(3): E_(lambda: pop_(620 + 120 * k), w0(3) + k * .09, -15)
E_(lambda: impact(1.1, 95, 40), w0(3) + .1, -9); E_(lambda: riser(.5), w0(7) - .5, -15); E_(lambda: impact(1.6, 85, 34), w0(7) + .12, -6); E_(lambda: whoosh(.35, True), w0(7) + .05, -12)
# intro
E_(lambda: whoosh(.4, True, .8), w0(9) - .05, -14); E_(lambda: pop_(640), w0(11) + .05, -15); E_(lambda: pop_(760), w0(13) + .02, -14); E_(lambda: impact(.8, 90, 45), w0(13) + .02, -10)
for k in range(3): E_(lambda: pop_(600 + 90 * k), w0(20) + k * .1, -14)
E_(lambda: impact(1.0, 95, 42), w0(20) + .12, -8)
# cut-aways
for ci, (a, b) in enumerate(CUTS):
    E_(lambda: riser(.6), a - .75, -17); E_(lambda: whoosh(.45, True, 1.1), a - .42, -10); E_(lambda: impact(.9, 95, 42), a, -10)
    E_(lambda: whoosh(.45, False, .9), b, -11)
E_(lambda: click(2200), CUTS[0][0] + 1.55, -12); E_(lambda: blip(1300, 3), CUTS[0][0] + .55, -18)
E_(ding, w0(59) - .15, -13); [E_(lambda: pop_(700 + 60 * k), w0(59) + .3 * k - .1, -16) for k in range(3)]
tP = w0(68) + .02
E_(lambda: click(1900), tP - .75, -13); E_(lambda: click(2400), tP, -9); E_(lambda: impact(1.0, 100, 45), tP, -7); E_(lambda: pop_(900), tP + .02, -13)
E_(lambda: click(2600), w1(71) + .1, -12); E_(lambda: whoosh(.4, True), w1(71) + .12, -13)
E_(lambda: impact(.9, 95, 42), CUTS[3][0] + .08, -9); E_(lambda: blip(1300, 3), CUTS[3][0] + .15, -17); [E_(tick, CUTS[3][0] + .7 + k * .45, -17) for k in range(3)]
# grow
for k in range(2): E_(lambda: pop_(660 + 100 * k), w0(39) + k * .08, -16)
E_(lambda: whoosh(.4, True), w0(44) - .05, -13); E_(lambda: impact(.9, 95, 42), w0(44) + .05, -9)
# want
for k in range(6): E_(lambda: pop_(520 + 70 * k), w0(50) + k * .06, -16)
E_(lambda: riser(.4), w0(52) - .35, -15); E_(lambda: impact(1.4, 95, 38), w0(52) + .12, -6); E_(lambda: whoosh(.35, True), w0(52) + .1, -12)
# silka / result
E_(lambda: impact(.9, 95, 42), w0(74) + .02, -9); E_(lambda: pop_(800), w0(74) + .1, -14)
E_(lambda: impact(.9, 95, 42), w0(84) + .02, -10); E_(lambda: whoosh(.35, True), w0(85) - .05, -13); E_(lambda: impact(1.1, 90, 40), w0(88) + .05, -8); E_(lambda: whoosh(.4, True), w0(88), -12)
# CTA
E_(lambda: pop_(700), w0(89) + .05, -13); ck = w0(91) + .2; E_(lambda: click(2400), ck, -10); E_(lambda: pop_(760), ck + .02, -14); E_(lambda: chime_end(), ck + .05, -24)
E_(lambda: impact(1.0, 100, 45), w0(94) + .02, -7); E_(lambda: pop_(900), w0(94) + .06, -13)
E_(lambda: impact(1.5, 90, 36), w0(97) - .02, -8); E_(lambda: chime_end(), w0(97) + .1, -18)
for fn, t, g, pan in ev:
    x = fn(); x = x / max(1e-9, np.max(np.abs(x))) * db(g); add(None, x, t, 1.0, pan)
sL, sR = L.copy(), R.copy(); L[:] = 0; R[:] = 0
# music bed: pad + pluck throughout, rhythm enters progressively
def inten(t): return 0.35 if t < 3.0 else .6 if t < 13 else .9 if t < 22 else .75 if t < 33 else 1.0 if t < 42 else .7
for b in range(int(TOT / (beat * 4)) + 2):
    t0 = b * beat * 4; ch = chords[b % 4]; it = inten(t0)
    add(None, pad(ch[1], beat * 4 + .6), t0, .12, 0)
    for q in range(4):
        tb = t0 + q * beat; it = inten(tb)
        if it >= .6 and q % 2 == 0: add(None, kick(), tb, .8 * it, 0)
        if it >= .9 and q % 2 == 1: add(None, clap(), tb, .22, 0)
        if it >= .6: add(None, hat(), tb + beat / 2, .16 * it, .2)
        if it >= .9: add(None, bass(ch[0], beat * .9), tb, .4, 0)
        arp = ch[1][(q * 2) % 3] * (2 if q % 2 else 1)
        for h_ in range(2): add(None, pluck(arp * (1.5 if h_ else 1)), tb + h_ * beat / 2, .08 * (.5 + it * .5), -.4 if h_ else .4)
mL, mR = L.copy(), R.copy(); d = int(beat * .75 * SR)
for m in (mL, mR): m[d:] += m[:-d] * .25
tm = np.arange(N) / SR; fade = np.clip((45.5 + .6 - tm) / 1.5, 0, 1); mL *= fade; mR *= fade
def wr(name, l, r, g):
    x = np.clip(np.stack([l, r], 1) * g, -1, 1); w = wave.open(name, "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((x * 32767).astype("<i2").tobytes()); w.close()
wr("music.wav", mL, mR, .5 / max(np.abs(mL).max(), np.abs(mR).max())); wr("sfx.wav", sL, sR, .9 / max(np.abs(sL).max(), np.abs(sR).max()))
print("audio ok", len(ev), "sfx")
