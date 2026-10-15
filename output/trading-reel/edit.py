import json, math, random, subprocess, sys, wave
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter

S = sys.argv[1]
SRC = sys.argv[2]
OUT = sys.argv[3]
PREVIEW = len(sys.argv) > 4 and sys.argv[4]  # "t0,t1" output seconds -> only render those
FPS = 30
W, H = 1080, 1920
SR = 48000
F = S + '/fonts/'
random.seed(7); np.random.seed(7)

RED = (232, 28, 40); WHITE = (255, 255, 255)

# ---------------------------------------------------------------- transcript
PHR = [
    (0.152, 0.806, "Do‘stlar,"),
    (1.112, 4.294, "hozirgi treyding sohasiga qiziqib kelayotgan bolalarning"),
    (4.792, 6.054, "juda ham ko‘plari"),
    (6.584, 9.286, "bozorda qancha ko‘p strategiya bilsam,"),
    (9.912, 11.846, "shuncha ko‘p foyda olaman deb o‘ylashar ekan."),
    (13.176, 13.958, "Yo‘q!"),
    (15.416, 16.198, "Bu noto‘g‘ri."),
    (17.4, 19.942, "Bozorda strategiya katta rol o‘ynamaydi."),
    (20.344, 21.734, "Bozorda strategiya"),
    (22.072, 23.782, "faqatgina bozorning"),
    (24.184, 27.11, "70–80% qayerga ketishini aniqlab beradi."),
    (29.272, 33.318, "Siz foydaga chiqishingiz uchun kerak bo‘ladigan narsa — bu risk menejment."),
    (34.808, 36.134, "O‘z nafsingizni"),
    (36.376, 37.35, "boshqara olishingiz."),
    (38.392, 40.102, "Siz nafsingizni boshqara olsangiz,"),
    (40.696, 43.078, "risk menejmentga amal qiladigan bo‘lsangiz,"),
    (43.64, 44.582, "ana shundagina"),
    (44.984, 45.99, "foyda olasiz."),
    (46.712, 47.43, "Aks holda"),
    (47.8, 49.83, "faqatgina sliv, sliv, sliv."),
    (51.8, 53.894, "Strategiya katta rol o‘ynamaydi, do‘stlar."),
    (55.16, 55.942, "Bu videoni"),
    (56.216, 56.71, "treyding"),
    (57.08, 59.686, "sohasiga qiziqadigan do‘stlaringizga jo‘nating."),
    (60.248, 62.022, "Obuna bo‘lib qo‘yishni esdan chiqarmang."),
    (62.872, 63.462, "Ko‘rishguncha!"),
]
KEY = {"treyding", "strategiya", "foyda", "foydaga", "70–80%", "risk", "menejment", "menejmentga",
       "nafsingizni", "sliv", "yo‘q", "noto‘g‘ri", "obuna", "jo‘nating", "katta"}
SMALL = {"bu", "ham", "juda", "deb", "ekan", "siz", "uchun", "ana", "o‘z", "aks", "holda", "—", "qancha", "shuncha"}

def norm(w):
    return w.strip(".,!?").lower()

words = []  # dict(t0,t1,text,phrase)
for pi, (a, b, txt) in enumerate(PHR):
    ws = txt.split()
    wt = [10 if norm(w) == "70–80%" else len(w.strip(".,!?")) + 2 for w in ws]
    tot = sum(wt); t = a
    for w, k in zip(ws, wt):
        d = (b - a) * k / tot
        words.append(dict(t0=t, t1=t + d, text=w, p=pi)); t += d

# ---------------------------------------------------------------- edit (pause trimming)
SRC_DUR = 64.36
iv = []
for a, b, _ in PHR:
    a, b = max(0, a - 0.10), min(SRC_DUR, b + 0.20)
    if iv and a - iv[-1][1] < 0.40: iv[-1][1] = max(iv[-1][1], b)
    else: iv.append([a, b])
iv[0][0] = 0.0
iv[-1][1] = min(SRC_DUR, iv[-1][1] + 0.5)
offs = []; acc = 0
for a, b in iv: offs.append(acc - a); acc += b - a
OUT_DUR = acc

def m(ts):  # source time -> output time
    for (a, b), o in zip(iv, offs):
        if ts < a: return a + o
        if ts <= b: return ts + o
    return OUT_DUR

CUTS = [iv[k][0] + offs[k] for k in range(1, len(iv))]
for w in words: w['o0'] = m(w['t0']); w['o1'] = m(w['t1'])
PO = [(m(a), m(b)) for a, b, _ in PHR]
print('segments', len(iv), 'out dur %.2f' % OUT_DUR, 'cuts', ['%.2f' % c for c in CUTS])

def wfind(txt, after=0.0):
    for w in words:
        if norm(w['text']) == txt and w['o0'] >= after: return w
    raise KeyError(txt)

# ---------------------------------------------------------------- key events (output time)
T_YOQ = wfind("yo‘q")['o0']
T_NOTO = wfind("noto‘g‘ri")['o0']
T_PCT = wfind("70–80%")
SCENE = (PO[11][0] - 0.05, PO[11][1] + 0.35)        # polaroid / grid scene
T_RISK = wfind("risk", SCENE[0])['o0']
SLIVS = [w['o0'] for w in words if norm(w['text']) == 'sliv']
T_SEND = wfind("jo‘nating")['o0']
T_OBUNA = wfind("obuna")['o0']
T_END = PO[-1][0]
# words shown by special graphics instead of subtitles
SPECIAL_PHR = {0, 5, 6, 10, 11, 19, 25}

# ---------------------------------------------------------------- face track (smoothed)
faces = json.load(open(S + '/faces.json'))
fa = np.array(faces, float)
k = np.exp(-np.linspace(-2, 2, 31) ** 2); k /= k.sum()
fs = np.stack([np.convolve(np.pad(fa[:, j], 15, mode='edge'), k, 'valid') for j in range(3)], 1)

# ---------------------------------------------------------------- camera
def ease(x): x = min(max(x, 0), 1); return x * x * (3 - 2 * x)
def eout(x): x = min(max(x, 0), 1); return 1 - (1 - x) ** 3
def back(x):
    x = min(max(x, 0), 1); c = 1.9
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2

shot_starts = []
for (o0, o1) in PO:
    if not shot_starts or o0 - shot_starts[-1] > 0.9: shot_starts.append(o0)
shot_starts[0] = 0.0
STYLES = [(1.00, 1.07), (1.20, 1.24), (1.15, 1.04), (1.27, 1.30), (1.06, 1.12), (1.22, 1.17)]
impulses = []   # (t, amp, dur) zoom kicks
shakes = []     # (t, amp, dur)
for c in CUTS: impulses.append((c, 0.05, 0.28))
impulses += [(T_YOQ, 0.16, 0.55), (T_NOTO, 0.06, 0.4), (T_PCT['o0'], 0.07, 0.5), (T_RISK, 0.0, 0.1),
             (T_SEND, 0.05, 0.4), (T_OBUNA, 0.05, 0.4)]
for t in SLIVS: impulses.append((t, 0.07, 0.3)); shakes.append((t, 16, 0.32))
shakes += [(T_YOQ, 22, 0.45), (T_RISK, 10, 0.3)]
for w in words:
    if norm(w['text']) in KEY and not any(abs(w['o0'] - i[0]) < 0.25 for i in impulses):
        impulses.append((w['o0'], 0.035, 0.3))

def cam(t):
    k = max(i for i, s in enumerate(shot_starts) if s <= t + 1e-6)
    s0 = shot_starts[k]; s1 = shot_starts[k + 1] if k + 1 < len(shot_starts) else OUT_DUR
    a, b = STYLES[k % len(STYLES)]
    if k == 0: a, b = 1.42, 1.06
    p = (t - s0) / max(0.01, s1 - s0)
    z = a + (b - a) * (eout(p / 0.12) * 0.8 + 0.2 * p if k == 0 else ease(p))
    for (ti, amp, d) in impulses:
        if ti <= t < ti + d: z += amp * (1 - eout((t - ti) / d))
    if t > T_END: z -= 0.12 * ease((t - T_END) / 0.8)
    ox = oy = 0.0
    for (ti, amp, d) in shakes:
        if ti <= t < ti + d:
            r = 1 - (t - ti) / d
            ox += amp * r * math.sin((t - ti) * 95); oy += amp * r * math.cos((t - ti) * 77)
    return max(1.0, z), ox, oy

def transform(img, srci, t):
    z, ox, oy = cam(t)
    fx, fy, _ = fs[min(srci, len(fs) - 1)]
    Fx, Fy = fx * W, fy * H
    Tx, Ty = W * 0.5 + ox, H * 0.43 + oy
    Tx = min(max(Tx, W - z * (W - Fx)), z * Fx); Ty = min(max(Ty, H - z * (H - Fy)), z * Fy)
    M = np.float32([[z, 0, Tx - z * Fx], [0, z, Ty - z * Fy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT)

# ---------------------------------------------------------------- transitions at cuts
TR_TYPES = ['flash', 'whip', 'glitch', 'zoomblur', 'whip', 'flash', 'glitch', 'whip']
TRANS = [(c, TR_TYPES[i % len(TR_TYPES)]) for i, c in enumerate(CUTS)]

def motion_blur(img, n, horiz=True):
    small = cv2.resize(img, (W // 2, H // 2))
    kern = np.zeros((n, n), np.float32)
    if horiz: kern[n // 2, :] = 1.0 / n
    else: kern[:, n // 2] = 1.0 / n
    return cv2.resize(cv2.filter2D(small, -1, kern), (W, H))

def apply_trans(img, t):
    flash = 0.0
    for c, typ in TRANS:
        d = t - c
        if not (-0.12 <= d < 0.22): continue
        if typ == 'flash':
            if d >= 0: flash = max(flash, 0.75 * (1 - d / 0.18))
        elif typ == 'whip':
            x = 1 - min(1, abs(d) / 0.12) if d < 0 else 1 - min(1, d / 0.16)
            if x > 0:
                sh = int((-1 if d < 0 else 1) * 260 * x)
                img = np.roll(motion_blur(img, max(3, int(70 * x) | 1)), sh, axis=1)
        elif typ == 'glitch':
            if 0 <= d < 0.14:
                o = int(18 * (1 - d / 0.14))
                img = img.copy(); img[:, :, 0] = np.roll(img[:, :, 0], o, 1); img[:, :, 2] = np.roll(img[:, :, 2], -o, 1)
                for _ in range(5):
                    y = random.randint(0, H - 80); hh = random.randint(10, 70)
                    img[y:y + hh] = np.roll(img[y:y + hh], random.randint(-60, 60), 1)
        elif typ == 'zoomblur':
            x = 1 - min(1, abs(d) / 0.15)
            if x > 0:
                acc = img.astype(np.float32)
                for s in (1.04, 1.08, 1.12):
                    s = 1 + (s - 1) * x
                    M = cv2.getRotationMatrix2D((W / 2, H * 0.45), 0, s)
                    acc += cv2.warpAffine(img, M, (W, H), borderMode=cv2.BORDER_REFLECT)
                img = (acc / 4).astype(np.uint8)
    return img, flash

# ---------------------------------------------------------------- look: vignette + grain
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
r = np.sqrt(((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H * 0.45) / (H * 0.6)) ** 2)
VIG = np.clip(1.08 - 0.55 * np.clip(r - 0.35, 0, None) ** 1.4, 0.35, 1.08)[..., None].astype(np.float32)
GRAIN = [np.random.normal(0, 5.5, (H // 2, W // 2)).astype(np.float32) for _ in range(6)]

def look(img, i):
    f = img.astype(np.float32) * VIG
    g = cv2.resize(GRAIN[i % 6], (W, H), interpolation=cv2.INTER_LINEAR)[..., None]
    return np.clip(f + g, 0, 255)

# ---------------------------------------------------------------- text rendering
FONTS = {}
def font(name, size):
    k = (name, size)
    if k not in FONTS: FONTS[k] = ImageFont.truetype(F + name, size)
    return FONTS[k]

TXT = {}
def text_img(txt, fname, size, fill, shadow=True, box=None, pad=(0, 0)):
    k = (txt, fname, size, fill, shadow, box, pad)
    if k in TXT: return TXT[k]
    fn = font(fname, size)
    l, t_, r_, b = fn.getbbox(txt)
    pw, ph = pad
    w, h = r_ - l + 2 * pw + 24, b - t_ + 2 * ph + 24
    im = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    if box:
        ImageDraw.Draw(im).rectangle([12, 12, w - 12, h - 12], fill=box)
    if shadow and not box:
        sh = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(sh).text((12 + pw - l + 3, 12 + ph - t_ + 5), txt, font=fn, fill=(0, 0, 0, 170))
        im = Image.alpha_composite(im, sh.filter(ImageFilter.GaussianBlur(6)))
    ImageDraw.Draw(im).text((12 + pw - l, 12 + ph - t_), txt, font=fn, fill=fill)
    TXT[k] = im
    return im

def put(layer, im, cx, cy, scale=1.0, alpha=1.0, reveal=1.0, rot=0.0):
    if scale <= 0.01 or alpha <= 0.01 or reveal <= 0: return
    if reveal < 1:
        w = max(1, int(im.width * reveal)); im = im.crop((0, 0, w, im.height)); cx -= (im.width / max(reveal, 1e-3) - im.width) / 2 * scale
    if scale != 1: im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BICUBIC)
    if rot: im = im.rotate(rot, Image.BICUBIC, expand=True)
    if alpha < 1:
        a = im.getchannel('A').point(lambda v: int(v * alpha)); im = im.copy(); im.putalpha(a)
    layer.alpha_composite(im, (int(cx - im.width / 2), int(cy - im.height / 2)))

def style(w):
    n = norm(w)
    if n in KEY: return ('Anton.woff', 118, RED, w.strip(",.").upper())
    if n in SMALL: return ('Play700i.woff', 74, WHITE, w.strip(",.").lower())
    return ('Mont900.woff', 74, WHITE, w.strip(",.").upper())

# subtitle chunks
chunks = []
for pi in range(len(PHR)):
    if pi in SPECIAL_PHR: continue
    pw = [w for w in words if w['p'] == pi]
    cur = []
    for w in pw:
        if cur and (len(cur) >= 3 or sum(len(x['text']) for x in cur) + len(w['text']) > 20):
            chunks.append(cur); cur = []
        cur.append(w)
    if cur: chunks.append(cur)
for i, c in enumerate(chunks):
    nxt = chunks[i + 1][0]['o0'] if i + 1 < len(chunks) else OUT_DUR
    nph = PO[c[0]['p'] + 1][0] if c[0]['p'] + 1 < len(PO) else OUT_DUR
    c_end = min(nxt - 0.03, nph - 0.03, c[-1]['o1'] + 0.6)
    c[0]['softend'] = min(nxt, nph) - c_end > 0.15
    for w in c: w['cend'] = c_end

def layout(chunk):
    items = [style(w['text']) + (w,) for w in chunk]
    imgs = [text_img(txt, fn, sz, col) for fn, sz, col, txt, w in items]
    lines = [[]]; widths = [0]
    for it, im in zip(items, imgs):
        ww = im.width - 24
        if lines[-1] and widths[-1] + ww + 18 > 940: lines.append([]); widths.append(0)
        lines[-1].append((it, im)); widths[-1] += ww + (18 if len(lines[-1]) > 1 else 0)
    out = []; y = 1440
    for ln, lw in zip(lines, widths):
        lh = max(im.height for _, im in ln) - 24
        x = W / 2 - lw / 2
        for it, im in ln:
            ww = im.width - 24
            out.append((it[4], im, x + ww / 2, y + lh / 2 + (lh - (im.height - 24)) * 0.35, norm(it[4]['text']) in KEY))
            x += ww + 18
        y += lh + 16
    return out

LAY = {id(c[0]): layout(c) for c in chunks}

def draw_subs(layer, t):
    for c in chunks:
        if not (c[0]['o0'] - 0.02 <= t < c[0]['cend']): continue
        fade = 1 - ease((t - (c[0]['cend'] - 0.1)) / 0.1) if c[0]['softend'] else 1.0
        for w, im, x, y, key in LAY[id(c[0])]:
            d = t - w['o0'] + 0.04
            if d < 0: continue
            if key:
                put(layer, im, x, y - 14 * (1 - eout(d / 0.2)), 1.0 + 0.12 * (1 - eout(d / 0.25)), fade, reveal=eout(d / 0.22))
            else:
                p = d / 0.18
                put(layer, im, x, y + 26 * (1 - eout(p)), 0.55 + 0.45 * back(p), fade * min(1, p * 1.6))

# ---------------------------------------------------------------- decorative arcs
ARCS = [(c, i) for i, c in enumerate(CUTS[::2])] + [(0.0, 9)]
def draw_arcs(layer, t):
    d = ImageDraw.Draw(layer)
    for t0, i in ARCS:
        x = t - t0
        if not (0 <= x < 1.1): continue
        a = 1 - ease((x - 0.7) / 0.4)
        sweep = 200 * eout(x / 0.55)
        rr = 760 + 90 * (i % 3)
        cx, cy = (-160 if i % 2 else W + 160), 560 + 140 * (i % 4)
        st = 200 if i % 2 == 0 else -40
        d.arc([cx - rr, cy - rr, cx + rr, cy + rr], st, st + sweep, fill=(255, 255, 255, int(150 * a)), width=3)

# ---------------------------------------------------------------- special graphics
def g_intro(layer, t):
    if t > 1.1: return
    im = text_img("DO‘STLAR", 'Anton.woff', 210, WHITE)
    a = 1 - ease((t - 0.85) / 0.25)
    put(layer, im, W / 2, 1470, 1.0 + 0.04 * t, a, reveal=eout((t - 0.05) / 0.45))
    bar = text_img("  ", 'Mont900.woff', 20, RED, box=RED, pad=(160, 0))
    put(layer, bar, W / 2, 1600, 1, a, reveal=eout((t - 0.25) / 0.4))

def g_yoq(layer, t):
    d = t - T_YOQ
    end = min(PO[5][1] - T_YOQ + 0.5, PO[6][0] - T_YOQ - 0.05)
    if not (-0.02 <= d < end): return
    a = 1 - ease((d - end + 0.15) / 0.15)
    im = text_img("YO‘Q!", 'Anton.woff', 330, RED)
    put(layer, im, W / 2, 1520, 2.2 - 1.2 * eout(d / 0.16), a * min(1, d / 0.06 + 0.2), rot=-4)

def g_noto(layer, t):
    d = t - T_NOTO + 0.1
    end = min(PO[6][1] - T_NOTO + 0.55, PO[7][0] - T_NOTO + 0.05)
    if not (0 <= d < end): return
    a = 1 - ease((d - end + 0.2) / 0.2)
    put(layer, text_img("bu", 'Play700i.woff', 90, WHITE), W / 2 - 330, 1380, 0.6 + 0.4 * back(d / 0.2), a)
    im = text_img("NOTO‘G‘RI", 'Mont900.woff', 150, WHITE)
    put(layer, im, W / 2, 1500, 0.6 + 0.4 * back((d - 0.08) / 0.2), a * min(1, d * 6))
    p = eout((d - 0.35) / 0.25)
    if p > 0:
        dr = ImageDraw.Draw(layer); x0 = W / 2 - im.width / 2 + 10
        dr.line([x0, 1515, x0 + (im.width - 20) * p, 1490], fill=RED + (int(255 * a),), width=16)

def g_pct(layer, t):
    w = T_PCT; d = t - w['o0'] + 0.05
    end = PO[10][1] - w['o0'] + 0.3
    if not (0 <= d < end): return
    a = 1 - ease((d - end + 0.2) / 0.2)
    p = eout(d / 0.75)
    n1 = int(round(70 * p)); txt = "70–80%" if p > 0.97 else "%d%%" % n1
    im = text_img(txt, 'Anton.woff', 260, RED)
    put(layer, im, W / 2, 1450, 1.0 + 0.1 * (1 - eout(d / 0.3)), a)
    rest = [x for x in words if x['p'] == 10 and x['o0'] > w['o0']]
    sub = " ".join(x['text'].strip(".").upper() for x in rest if x['o0'] - 0.04 <= t)
    if sub:
        put(layer, text_img(sub, 'Bebas.woff', 92, WHITE), W / 2, 1640, 1, a)

def g_sliv(layer, t):
    e = min(PO[19][1] + 0.6, PO[20][0] - 0.03)
    if not (PO[19][0] - 0.02 <= t < e): return
    a = 1 - ease((t - e + 0.15) / 0.15)
    # falling chart
    pts = [(80, 1270), (230, 1230), (360, 1330), (500, 1300), (640, 1480), (780, 1440), (1000, 1760)]
    p = eout((t - PO[19][0] + 0.2) / 1.6)
    if p > 0:
        L = len(pts) - 1; n = p * L; seg = pts[:int(n) + 1]
        if int(n) < L:
            (x0, y0), (x1, y1) = pts[int(n)], pts[int(n) + 1]; f = n - int(n)
            seg = seg + [(x0 + (x1 - x0) * f, y0 + (y1 - y0) * f)]
        if len(seg) > 1: ImageDraw.Draw(layer).line(seg, fill=RED + (int(170 * a),), width=7, joint='curve')
    hold = [w for w in words if w['p'] == 19 and norm(w['text']) in ('faqatgina',)]
    if hold and t < SLIVS[0] + 0.1:
        put(layer, text_img("faqatgina", 'Play700i.woff', 90, WHITE), W / 2, 1340, 1, min(1, (t - hold[0]['o0']) * 6))
    for i, ts in enumerate(SLIVS):
        d = t - ts
        if d < 0: continue
        im = text_img("SLIV", 'Anton.woff', 170, RED if i != 1 else WHITE)
        put(layer, im, W / 2 + (-160, 150, -20)[i], 1330 + 170 * i, 2.0 - 1.0 * eout(d / 0.12), a * min(1, d / 0.05), rot=(-7, 5, -3)[i])

def g_cta(layer, t):
    # paper plane on "jo'nating"
    d = t - T_SEND
    if 0 <= d < 1.2:
        x = -100 + 1300 * eout(d / 1.1); y = 1330 - 260 * eout(d / 1.1)
        dr = ImageDraw.Draw(layer)
        s = 1.0
        poly = [(x + 70 * s, y), (x - 50 * s, y - 34 * s), (x - 24 * s, y + 4 * s)]
        poly2 = [(x + 70 * s, y), (x - 24 * s, y + 4 * s), (x - 30 * s, y + 40 * s)]
        al = int(255 * (1 - ease((d - 0.8) / 0.4)))
        dr.polygon(poly, fill=(255, 255, 255, al)); dr.polygon(poly2, fill=(200, 200, 200, al))
    # subscribe button
    d = t - T_OBUNA + 0.15
    end = PO[24][1] - T_OBUNA + 0.6
    if 0 <= d < end:
        a = 1 - ease((d - end + 0.25) / 0.25)
        clicked = d > 0.75
        bt = text_img("OBUNA BO‘LING" if not clicked else "OBUNA", 'Mont900.woff', 54,
                      WHITE, box=RED if not clicked else (60, 60, 60), pad=(46, 26))
        sc = (0.4 + 0.6 * back(d / 0.25)) * (0.9 if 0.68 < d < 0.8 else 1)
        put(layer, bt, W / 2, 1740, sc, a)
        cp = eout((d - 0.25) / 0.45)
        cx, cy = W / 2 + 230 - 150 * cp, 1880 - 110 * cp
        dr = ImageDraw.Draw(layer)
        if d > 0.25:
            dr.polygon([(cx, cy), (cx, cy + 62), (cx + 16, cy + 48), (cx + 30, cy + 76), (cx + 40, cy + 70), (cx + 27, cy + 44), (cx + 46, cy + 44)],
                       fill=(255, 255, 255, int(255 * a)), outline=(0, 0, 0, int(255 * a)))
        if 0.72 < d < 1.1:
            rr = 30 + 160 * (d - 0.72); dr.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=(255, 255, 255, int(200 * (1 - (d - 0.72) / 0.38))), width=4)

def g_end(layer, t):
    d = t - T_END
    if d < 0: return
    put(layer, text_img("Ko‘rishguncha!", 'Play900i.woff', 120, WHITE), W / 2, 1480, 0.7 + 0.3 * back(d / 0.3), min(1, d * 5) * (1 - ease((t - OUT_DUR + 0.45) / 0.3)))

# ---------------------------------------------------------------- grid / polaroid scene
GRID = np.full((H, W, 3), 14, np.uint8)
for x in range(0, W, 90): GRID[:, x:x + 2] = 34
for y in range(0, H, 90): GRID[y:y + 2, :] = 34
GRID = (GRID.astype(np.float32) * VIG[..., :1]).astype(np.uint8)

def scene(frame, t):
    s0, s1 = SCENE
    if not (s0 <= t < s1): return frame, 0
    pin = eout((t - s0) / 0.35); pout = ease((t - (s1 - 0.3)) / 0.3)
    p = pin * (1 - pout)
    if p <= 0.001: return frame, 0
    sc = 1 - 0.33 * p; rot = -4.5 * p
    fr = Image.fromarray(frame)
    bw = int(22 * p)
    fw, fh = int(W * sc), int(H * sc)
    card = Image.new('RGB', (fw + 2 * bw, fh + 2 * bw), (245, 245, 242))
    card.paste(fr.resize((fw, fh), Image.BILINEAR), (bw, bw))
    card = card.convert('RGBA').rotate(rot, Image.BICUBIC, expand=True)
    bg = Image.fromarray(GRID).convert('RGBA')
    shadow = Image.new('RGBA', card.size, (0, 0, 0, 0)); shadow.putalpha(card.getchannel('A').point(lambda v: int(v * 0.6)))
    cx, cy = W / 2, H / 2 + 95 * p
    bg.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)), (int(cx - card.width / 2 + 14), int(cy - card.height / 2 + 24)))
    bg.alpha_composite(card, (int(cx - card.width / 2), int(cy - card.height / 2)))
    out = np.asarray(bg.convert('RGB'))
    if p < 1: out = (out.astype(np.float32) * p + frame.astype(np.float32) * (1 - p)).astype(np.uint8)
    return out, p

def g_scene(layer, t, p):
    if p <= 0: return
    pw = [w for w in words if w['p'] == 11]
    risk_i = [i for i, w in enumerate(pw) if norm(w['text']) == 'risk'][0]
    pre = pw[:risk_i]
    # caption above card: mixed typography
    lines = [pre[:3], pre[3:6], pre[6:]]
    y = 105
    for li, ln in enumerate(lines):
        vis = [w for w in ln if w['o0'] - 0.04 <= t]
        if not vis: y += 96; continue
        ims = []
        for w in vis:
            n = norm(w['text'])
            if n in KEY: ims.append(text_img(w['text'].upper(), 'Anton.woff', 88, RED))
            elif n in SMALL: ims.append(text_img(w['text'].lower(), 'Play700i.woff', 66, WHITE))
            else: ims.append(text_img(w['text'], 'Mont700.woff', 60, WHITE))
        tw = sum(i.width - 24 for i in ims) + 16 * (len(ims) - 1)
        x = W / 2 - tw / 2
        for w, im in zip(vis, ims):
            dd = t - w['o0'] + 0.04
            put(layer, im, x + (im.width - 24) / 2, y + 10 * (1 - eout(dd / 0.2)), 0.7 + 0.3 * back(dd / 0.2), p * min(1, dd * 6))
            x += im.width - 24 + 16
        y += 96
    d = t - T_RISK + 0.04
    if d > 0:
        box = text_img("RISK", 'Anton.woff', 150, WHITE, box=RED, pad=(26, 8))
        put(layer, box, 330, 1690, 1.6 - 0.6 * eout(d / 0.14), p, rot=4)
        put(layer, text_img("menejment", 'Play900i.woff', 120, WHITE), 640, 1800, 0.6 + 0.4 * back((d - 0.2) / 0.25), p * min(1, max(0, d - 0.2) * 6), reveal=eout((d - 0.2) / 0.3))
    ImageDraw.Draw(layer).arc([W / 2 - 640, H / 2 - 640 + 80, W / 2 + 640, H / 2 + 640 + 80], 120, 120 + 260 * eout((t - SCENE[0]) / 0.8), fill=(255, 255, 255, int(130 * p)), width=3)

# ---------------------------------------------------------------- render video
def render():
    dec = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', SRC, '-vf',
        "fps=30,hqdn3d=3:3:4:4,curves=master='0/0 0.06/0.13 0.25/0.42 0.55/0.72 1/0.97',eq=contrast=1.06:saturation=0.9,"
        "colorbalance=rs=-0.02:bs=0.05:rm=0.02:rh=0.05:gh=0.01:bh=-0.04,scale=1080:1920:flags=lanczos,unsharp=5:5:0.55",
        '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE, bufsize=10 ** 8)
    t0, t1 = (map(float, PREVIEW.split(',')) if PREVIEW else (0, 1e9))
    enc = subprocess.Popen(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
                            '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-profile:v', 'high', S + '/video_only.mp4'], stdin=subprocess.PIPE)
    i = 0; n = 0
    while True:
        b = dec.stdout.read(W * H * 3)
        if len(b) < W * H * 3: break
        ts = i / FPS; srci = i; i += 1
        if not any(a <= ts < bb for a, bb in iv): continue
        t = n / FPS; n += 1
        if not (t0 <= t < t1): continue
        img = np.frombuffer(b, np.uint8).reshape(H, W, 3)
        img = transform(img, srci, t)
        img, flash = apply_trans(img, t)
        # red pulse for impacts
        red = 0.0
        for tt in [T_YOQ] + SLIVS:
            if 0 <= t - tt < 0.25: red = max(red, 0.35 * (1 - (t - tt) / 0.25))
        f = look(img, n)
        if red: f = f * (1 - red) + np.array([200, 10, 20], np.float32) * red * (f.mean(2, keepdims=True) / 255 * 0.6 + 0.4)
        if flash: f = f * (1 - flash) + 255 * flash
        img = np.clip(f, 0, 255).astype(np.uint8)
        img, p = scene(img, t)
        layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        if p < 0.5: draw_arcs(layer, t)
        g_intro(layer, t); g_yoq(layer, t); g_noto(layer, t); g_pct(layer, t); g_sliv(layer, t); g_cta(layer, t); g_end(layer, t)
        g_scene(layer, t, p)
        draw_subs(layer, t)
        bb = layer.getbbox()
        if bb:
            x0, y0, x1, y1 = bb
            ov = np.asarray(layer.crop(bb)).astype(np.float32)
            a = ov[..., 3:4] / 255
            img = img.copy(); reg = img[y0:y1, x0:x1].astype(np.float32)
            img[y0:y1, x0:x1] = (reg * (1 - a) + ov[..., :3] * a).astype(np.uint8)
        # fade out
        if t > OUT_DUR - 0.45: img = (img * max(0, (OUT_DUR - t) / 0.45)).astype(np.uint8)
        if t < 0.08: img = (img * (t / 0.08)).astype(np.uint8)
        enc.stdin.write(img.tobytes())
        if n % 150 == 0: print('frame', n, flush=True)
    enc.stdin.close(); enc.wait(); dec.kill()

# ---------------------------------------------------------------- audio
def env(n, a, d):
    e = np.ones(n); na = int(a * SR); e[:na] = np.linspace(0, 1, na) if na else 1
    return e * np.exp(-np.arange(n) / (d * SR))

def bandnoise(n, lo, hi):
    x = np.random.randn(n); X = np.fft.rfft(x); f = np.fft.rfftfreq(n, 1 / SR)
    X[(f < lo) | (f > hi)] = 0; y = np.fft.irfft(X, n); return y / (np.abs(y).max() + 1e-9)

def sweep_noise(n, f0, f1):
    x = np.random.randn(n); out = np.zeros(n); blk = 1024
    for s in range(0, n, blk):
        fc = f0 * (f1 / f0) ** (s / n); seg = x[max(0, s - 2048):s + blk]
        X = np.fft.rfft(seg); f = np.fft.rfftfreq(len(seg), 1 / SR)
        X *= np.exp(-((np.log(f + 1) - np.log(fc)) ** 2) / 0.5); y = np.fft.irfft(X, len(seg))
        out[s:s + blk] = y[-min(blk, n - s):]
    return out / (np.abs(out).max() + 1e-9)

def sfx(kind):
    if kind == 'whoosh':
        n = int(0.45 * SR); x = sweep_noise(n, 300, 4500); e = np.sin(np.linspace(0, np.pi, n)) ** 2
        return x * e * 0.55
    if kind == 'whoosh_rev':
        return sfx('whoosh')[::-1] * 0.9
    if kind == 'pop':
        n = int(0.09 * SR); tt = np.arange(n) / SR; f = 900 * np.exp(-tt * 30) + 280
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.002, 0.025) * 0.45
    if kind == 'impact':
        n = int(0.9 * SR); tt = np.arange(n) / SR; f = 38 + 90 * np.exp(-tt * 18)
        sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.003, 0.32)
        cr = bandnoise(n, 100, 3000) * env(n, 0.001, 0.05)
        return np.tanh(1.6 * (sub * 0.9 + cr * 0.5)) * 0.8
    if kind == 'tick':
        n = int(0.025 * SR); return bandnoise(n, 1800, 6000) * env(n, 0.0005, 0.006) * 0.35
    if kind == 'click':
        n = int(0.12 * SR); x = np.zeros(n); c = bandnoise(int(0.015 * SR), 1500, 7000) * env(int(0.015 * SR), 0.0005, 0.004)
        x[:len(c)] += c; x[int(0.06 * SR):int(0.06 * SR) + len(c)] += c * 0.7; return x * 0.7
    if kind == 'ding':
        n = int(1.4 * SR); tt = np.arange(n) / SR
        return sum(a * np.sin(2 * np.pi * f * tt) for f, a in [(1318, 1), (2637, 0.35), (3951, 0.15)]) * env(n, 0.002, 0.45) * 0.22
    if kind == 'glitch':
        n = int(0.16 * SR); x = np.random.randn(n); x = np.round(x * 3) / 3
        g = (np.sin(np.arange(n) / SR * 2 * np.pi * 40) > 0) * 1.0
        return bandnoise(n, 500, 8000) * g * 0.25 + x * g * 0.05
    if kind == 'riser':
        n = int(1.3 * SR); tt = np.arange(n) / SR
        tone = np.sin(2 * np.pi * np.cumsum(200 + 900 * (tt / tt[-1]) ** 2) / SR)
        x = (sweep_noise(n, 400, 7000) * 0.6 + tone * 0.25) * (tt / tt[-1]) ** 2.2
        return x * 0.45
    if kind == 'shutter':
        n = int(0.2 * SR); x = np.zeros(n); c = bandnoise(int(0.03 * SR), 800, 8000) * env(int(0.03 * SR), 0.0005, 0.008)
        x[:len(c)] += c; x[int(0.08 * SR):int(0.08 * SR) + len(c)] += c * 0.8; return x * 0.6

def render_audio():
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', SRC, '-af', 'highpass=f=75,afftdn=nr=10:nf=-45,'
                          'equalizer=f=3500:t=q:w=1:g=2.5,equalizer=f=250:t=q:w=1:g=-2,acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=4',
                          '-ac', '1', '-ar', str(SR), '-f', 'f32le', '-'], capture_output=True).stdout
    v = np.frombuffer(raw, np.float32).astype(np.float64)
    N = int(OUT_DUR * SR) + SR // 10
    voice = np.zeros(N); fd = int(0.012 * SR)
    for (a, b), o in zip(iv, offs):
        seg = v[int(a * SR):int(b * SR)].copy()
        r = np.linspace(0, 1, fd); seg[:fd] *= r; seg[-fd:] *= r[::-1]
        st = int((a + o) * SR); voice[st:st + len(seg)] += seg[:N - st]
    voice /= np.abs(voice).max() + 1e-9; voice *= 0.8
    fx = np.zeros(N)
    def add(t, kind, g=1.0):
        x = sfx(kind) * g
        if kind in ('whoosh', 'riser'): t -= len(x) / SR * (0.55 if kind == 'whoosh' else 1.0)
        st = int(t * SR)
        if st < 0: x = x[-st:]; st = 0
        e = min(N, st + len(x)); fx[st:e] += x[:e - st]
    for c, typ in TRANS:
        add(c, 'glitch' if typ == 'glitch' else 'whoosh', 0.8)
    add(0.02, 'impact', 0.6); add(0.15, 'whoosh', 0.7)
    add(T_YOQ, 'impact', 1.0); add(T_NOTO + 0.25, 'pop', 0.9); add(T_NOTO + 0.3, 'whoosh', 0.4)
    for k in range(0, 23, 2): add(T_PCT['o0'] - 0.05 + k / FPS, 'tick', 0.9)
    add(T_PCT['o0'] + 0.72, 'ding', 0.6)
    add(SCENE[0], 'riser', 0.8); add(SCENE[0] + 0.05, 'shutter', 0.9); add(T_RISK, 'impact', 0.75); add(SCENE[1] - 0.25, 'whoosh', 0.6)
    for ts in SLIVS: add(ts, 'impact', 0.85); add(ts, 'glitch', 0.7)
    add(T_SEND + 0.05, 'whoosh', 0.8)
    add(T_OBUNA - 0.15, 'pop', 0.8); add(T_OBUNA + 0.6, 'click', 1.0); add(T_OBUNA + 0.65, 'ding', 0.7)
    add(T_END, 'whoosh_rev', 0.5)
    for c in chunks:
        if not any(abs(c[0]['o0'] - x) < 0.3 for x in CUTS): add(c[0]['o0'], 'pop', 0.22)
        for w in c:
            if norm(w['text']) in KEY: add(w['o0'], 'tick', 0.6)
    # music bed: dark minimal pulse, 96 bpm, ducked under voice
    tt = np.arange(N) / SR; beat = 60 / 96
    mus = np.zeros(N)
    chords = [(220.0, 261.6, 329.6), (174.6, 220.0, 261.6), (196.0, 246.9, 293.7), (164.8, 207.7, 246.9)]
    bar = beat * 4
    for bi in range(int(OUT_DUR / bar) + 2):
        ch = chords[(bi // 2) % 4]; s = int(bi * bar * SR); n = int(bar * SR) + SR // 2
        n = min(n, N - s)
        if n <= 0: break
        x = np.arange(n) / SR
        pad = sum(np.sin(2 * np.pi * f * x + j) * 0.5 + np.sin(2 * np.pi * f * 1.004 * x) * 0.5 for j, f in enumerate(ch)) / 3
        pad += np.sin(2 * np.pi * ch[0] / 2 * x) * 0.6
        e = np.minimum(1, x / 0.4) * np.minimum(1, (n / SR - x) / 0.5)
        mus[s:s + n] += pad * e * 0.18
        for q in range(4):
            ks = s + int(q * beat * SR); kn = int(0.3 * SR)
            if ks + kn >= N: continue
            kx = np.arange(kn) / SR
            kick = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-kx * 35)) / SR) * np.exp(-kx * 11)
            mus[ks:ks + kn] += kick * (0.55 if q % 2 == 0 else 0.3)
            hs = ks + int(beat / 2 * SR); hn = int(0.03 * SR)
            if hs + hn < N: mus[hs:hs + hn] += np.random.randn(hn) * np.exp(-np.arange(hn) / (0.006 * SR)) * 0.05
    venv = np.convolve(np.abs(voice), np.ones(int(0.25 * SR)) / int(0.25 * SR), 'same')
    duck = 1 - 0.6 * np.clip(venv / (venv.max() * 0.25), 0, 1)
    mus *= duck * 0.16 * np.minimum(1, tt / 0.3) * np.clip((OUT_DUR - tt) / 0.8, 0, 1)
    mix = voice + fx * 0.5 + mus
    mix = np.tanh(mix * 1.1) / np.tanh(1.1)
    with wave.open(S + '/mix.wav', 'wb') as wv:
        wv.setnchannels(1); wv.setsampwidth(2); wv.setframerate(SR)
        wv.writeframes((np.clip(mix, -1, 1) * 32000).astype(np.int16).tobytes())

if __name__ == '__main__':
    render_audio()
    render()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', S + '/video_only.mp4', '-i', S + '/mix.wav',
                    '-af', 'loudnorm=I=-14:TP=-1.0:LRA=9', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-ac', '2',
                    '-shortest', '-movflags', '+faststart', OUT], check=True)
    print('done', OUT)
