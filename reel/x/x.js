// ===== "Exclusive" edit: black / yellow / white. Camera program, speed ramps, whips, tracked icons, glass UI cards, karaoke subtitles =====
const Y1 = '#FFD426', Y2 = '#FFAE00', BLK = '#0B0B0C', GLASS = 'rgba(12,12,14,.80)';
E.inC = t => t * t * t;
const FPS = 60, K0 = W / 720;
let WD = [], FACE = null, CUTS = [], TOTAL = 45.5, CNV, CTX;
const imgs = [new Image(), new Image()];
const w0 = i => WD[i].t0, w1 = i => WD[i].t1;
const yg = (c, x0, y0, x1, y1) => linGrad(c, x0, y0, x1, y1, [[0, Y1], [1, Y2]]);
const sine = (T, f, p = 0) => Math.sin(T * f + p);

// ---------- camera program ----------
const EZ = { soft: E.inOutS, punch: E.outE, out: E.outC, in: E.inE, lin: E.lin };
let TRACK = [], WHIPS = [], RAMPS = [], SRCCUT = [];
function buildCamera() {
  const K = []; const k = (t, z, roll = 0, ease = 'soft', bx = 0, by = 0) => K.push({ t, z, roll, ease, bx, by });
  k(0, 1.0); k(w0(3) - .1, 1.05, 0, 'soft', 20); k(w0(3) + .1, 1.14, .5, 'punch'); k(w0(6) + .1, 1.08, 0, 'out');
  k(w0(7) - .02, 1.09); k(w0(7) + .12, 1.27, -.9, 'punch'); k(w0(8) - .22, 1.12, 0, 'out');
  k(w0(8) + .3, 1.0, 0, 'soft', -30); k(w0(13) - .1, 1.07, .3, 'soft', 40); k(w0(13) + .02, 1.13, -.5, 'punch'); k(w0(16), 1.06, 0, 'out');
  k(w0(19), 1.08, 0, 'soft', -30); k(w0(20) + .1, 1.17, .6, 'punch'); k(w0(24), 1.05, 0, 'out'); k(w0(27) - .2, 1.05);
  k(w0(27) + .25, 1.0, 0, 'soft', 30); k(w0(33) - .1, 1.07, 0, 'soft', -30); k(w0(33) + .08, 1.15, .5, 'punch'); k(w0(36), 1.07, 0, 'out'); k(CUTS[0] - .32, 1.1, 0, 'soft');
  k(CUTS[0], 1.5, 0, 'in'); k(CUTS[0] + .02, 1.5); k(CUTS[0] + .55, 1.0, 0, 'out');
  k(w0(42), 1.08, -.3, 'soft'); k(w0(44) + .05, 1.16, .5, 'punch'); k(CUTS[1] - .32, 1.2, 0, 'soft'); k(CUTS[1], 1.55, 0, 'in'); k(CUTS[1] + .02, 1.55); k(CUTS[1] + .55, 1.03, 0, 'out');
  k(w0(50) + .02, 1.15, .6, 'punch'); k(w0(52) - .08, 1.07, 0, 'out'); k(w0(52) + .1, 1.26, -.9, 'punch'); k(w0(53) + .25, 1.1, 0, 'out'); k(w0(54) - .12, 1.0, 0, 'soft');
  k(w0(56) - .05, 1.04, 0, 'soft', 30); k(w0(56) + .1, 1.13, .4, 'punch'); k(w0(59), 1.06, 0, 'out'); k(w0(63) - .1, 1.0, 0, 'soft', -30);
  k(w0(67), 1.1, 0, 'soft'); k(w0(68) + .02, 1.18, .6, 'punch'); k(w0(71), 1.08, 0, 'out'); k(w0(74) - .05, 1.07); k(w0(74) + .08, 1.16, -.7, 'punch'); k(w0(76) - .2, 1.06, 0, 'out');
  k(w0(76) + .3, 1.0, 0, 'soft', 30); k(w0(84) - .05, 1.07); k(w0(84) + .08, 1.15, .6, 'punch'); k(w0(86), 1.07, 0, 'out'); k(w0(88) + .03, 1.22, -.8, 'punch'); k(w0(89) - .15, 1.06, 0, 'out');
  k(w0(89) + .3, 1.0, 0, 'soft', -30); k(w0(94) + .02, 1.17, .5, 'punch'); k(w0(96), 1.07, 0, 'out'); k(w0(97) - .05, 1.04, 0, 'soft'); k(w0(97) + .4, 1.12, 0, 'soft'); k(TOTAL, 1.2, 0, 'soft');
  TRACK = K.sort((a, b) => a.t - b.t);
  const wh = (t, dir) => WHIPS.push({ t, dir, d: .36 }); wh(w0(8) - .12, 1); wh(w0(27) - .1, -1); wh(w0(54) - .14, 1); wh(w0(76) - .14, -1); wh(w0(89) - .14, 1);
  RAMPS = [{ t: w0(7) - .06, d: .55, A: .08 }, { t: w0(20) - .1, d: .5, A: .07 }, { t: w0(52) - .08, d: .55, A: .08 }, { t: w0(88) - .1, d: .5, A: .07 }];
}
function camAt(T) {
  let z, roll, bx, by; const t = TRACK;
  if (T <= t[0].t) ({ z, roll, bx, by } = t[0]); else if (T >= t[t.length - 1].t) ({ z, roll, bx, by } = t[t.length - 1]);
  else for (let i = 1; i < t.length; i++) if (T <= t[i].t) { const a = t[i - 1], b = t[i], p = EZ[b.ease](prog(T, a.t, b.t)); z = lerp(a.z, b.z, p); roll = lerp(a.roll, b.roll, p); bx = lerp(a.bx, b.bx, p); by = lerp(a.by, b.by, p); break; }
  for (const w of WHIPS) { const p = prog(T, w.t, w.t + w.d); if (p > 0 && p < 1) z *= 1 + .10 * Math.sin(p * Math.PI); }
  return { z, roll, bx, by };
}
function whipAt(T) { for (const w of WHIPS) { const p = prog(T, w.t, w.t + w.d); if (p > 0 && p < 1) { const off = p < .5 ? -E.inC(p * 2) : (1 - E.outC((p - .5) * 2)); return { off: off * W * 1.05 * w.dir * -1, p, speed: p < .5 ? E.inC(p * 2) : 1 - E.outC((p - .5) * 2) }; } } return null; }
function videoTime(T) { let off = 0; for (const r of RAMPS) { const p = prog(T, r.t, r.t + r.d); if (p > 0 && p < 1) off -= r.A * Math.pow(Math.sin(Math.PI * p), 2); } return T + off; }

// ---------- footage ----------
function faceAt(T) { const i = Math.min(FACE.n - 1, Math.max(0, Math.round(T * FPS))); return [FACE.x[i] * K0, FACE.y[i] * K0, FACE.w[i] * K0]; }
function handheld(T) { return { x: 2.6 * sine(T, 1.9) + 1.6 * sine(T, 3.3, 1), y: 2.1 * sine(T, 1.5, .5) + 1.2 * sine(T, 2.9), r: .11 * sine(T, 1.1, 2) * Math.PI / 180 }; }
function drawVideo(c, T, vt) {
  const [fx, fy] = faceAt(T); const cm = camAt(T); const px = lerp(W / 2, fx, .55) + cm.bx, py = lerp(H * .42, fy, .6) + cm.by;
  const hh = handheld(T), wp = whipAt(T);
  const dz = Math.abs(camAt(T + .004).z - camAt(T - .004).z) / .008; const nz = dz > 1.2 ? Math.min(7, 2 + Math.floor(dz * 1.0)) : 1;
  const n = wp ? 9 : nz; c.fillStyle = '#000'; c.fillRect(0, 0, W, H); c.imageSmoothingEnabled = true; c.imageSmoothingQuality = 'high';
  c.filter = 'contrast(1.09) saturate(1.07) brightness(1.03)';
  const bl = vt - Math.floor(vt * FPS) / FPS, mix = clamp(bl * FPS);
  for (let s = 0; s < n; s++) {
    const ts = T - s * (wp ? .0055 : .0042), cs = camAt(ts), wps = whipAt(ts), ox = wps ? wps.off : 0;
    c.save(); c.globalAlpha = s === 0 ? 1 : 1 / (s + 1);
    c.translate(px + hh.x, py + hh.y); c.rotate(cs.roll * Math.PI / 180 + hh.r); const zz = cs.z * 1.025 * (1 + .02 * Math.abs(cs.roll)); c.scale(zz, zz); c.translate(-px + ox / zz, -py);
    for (let m = -1; m <= 1; m++) { c.save(); if (m) { c.translate(m * W + (m % 2 ? W : 0), 0); c.scale(-1, 1); } else c.translate(0, 0); c.drawImage(imgs[0], m ? 0 : 0, 0, W, H); if (mix > .02 && !m) { c.globalAlpha *= mix; c.drawImage(imgs[1], 0, 0, W, H); } c.restore(); }
    c.restore();
  }
  c.filter = 'none';
  // grade: warm highlights, deeper blacks, soft vignette
  c.save(); c.globalCompositeOperation = 'soft-light'; c.fillStyle = 'rgba(255,196,110,.10)'; c.fillRect(0, 0, W, H); c.restore();
}
function facePos(T, cm, hh) { const [fx, fy, fw] = faceAt(T); const px = lerp(W / 2, fx, .55) + cm.bx, py = lerp(H * .42, fy, .6) + cm.by, z = cm.z * 1.025; return [px + (fx - px) * z + hh.x, py + (fy - py) * z + hh.y, fw * z]; }

// ---------- atoms ----------
function glass(c, x, y, w, h, p, o = {}) {
  if (p <= 0) return false; const s = clamp(pop(p, 8, 10), 0, 1.06), a = clamp(p * 3), dx = (o.fromX ?? 0) * (1 - clamp(p, 0, 1));
  c.save(); c.translate(x + w / 2 + dx, y + h / 2); c.scale(s, s); c.globalAlpha *= a; c.translate(-w / 2, -h / 2);
  c.shadowColor = 'rgba(0,0,0,.55)'; c.shadowBlur = 40; c.shadowOffsetY = 16; rr(c, 0, 0, w, h, o.r ?? 34); c.fillStyle = GLASS; c.fill(); c.shadowBlur = 0; c.shadowOffsetY = 0;
  c.save(); rr(c, 0, 0, w, h, o.r ?? 34); c.clip(); c.fillStyle = linGrad(c, 0, 0, 0, h * .5, [[0, 'rgba(255,255,255,.10)'], [1, 'rgba(255,255,255,0)']]); c.fillRect(0, 0, w, h); c.restore();
  rr(c, 0, 0, w, h, o.r ?? 34); c.strokeStyle = 'rgba(255,255,255,.16)'; c.lineWidth = 2; c.stroke(); return true;
}
function gEnd(c) { c.restore(); }
function wt(c, s, x, y, o = {}) { // text
  c.save(); c.font = font(o.weight ?? 800, o.size ?? 40, SANS); c.textAlign = o.align ?? 'left'; c.textBaseline = 'middle'; if (o.ls) c.letterSpacing = o.ls + 'px'; c.globalAlpha *= o.alpha ?? 1; c.fillStyle = o.fill ?? '#fff'; c.fillText(s, x, y); c.restore();
}
function coin(c, x, y, r, p, spin, draw, o = {}) { // 3D-ish rotating coin
  if (p <= 0) return; const s = clamp(pop(p, 8, 10), 0, 1.12); c.save(); c.translate(x, y); c.rotate(o.rot ?? 0); c.scale(s, s); c.globalAlpha *= clamp(p * 4);
  const cs = Math.cos(spin), sn = Math.sin(spin), sx = Math.max(.08, Math.abs(cs)), side = cs >= 0;
  c.shadowColor = 'rgba(0,0,0,.5)'; c.shadowBlur = 36; c.shadowOffsetY = 18;
  for (let d = 12; d >= 1; d--) { c.save(); c.translate(-sn * d * 1.3, 0); c.scale(sx, 1); c.beginPath(); c.arc(0, 0, r, 0, 7); c.fillStyle = o.dark ? '#050505' : '#c07a00'; c.fill(); c.restore(); c.shadowBlur = 0; c.shadowOffsetY = 0; }
  c.save(); c.scale(sx, 1); c.beginPath(); c.arc(0, 0, r, 0, 7); c.fillStyle = o.dark ? linGrad(c, 0, -r, 0, r, [[0, '#2a2a2c'], [1, '#0b0b0c']]) : yg(c, 0, -r, 0, r); c.fill(); c.lineWidth = r * .06; c.strokeStyle = o.dark ? 'rgba(255,255,255,.22)' : 'rgba(255,245,200,.95)'; c.stroke();
  c.save(); c.beginPath(); c.arc(0, 0, r, 0, 7); c.clip(); c.fillStyle = linGrad(c, 0, -r, 0, 0, [[0, 'rgba(255,255,255,.4)'], [1, 'rgba(255,255,255,0)']]); c.fillRect(-r, -r, 2 * r, r); c.restore();
  if (!side) c.scale(-1, 1); draw(c, r); c.restore(); c.restore();
}
const IC = {
  ai: (c, r) => wt(c, 'AI', 0, r * .03, { size: r * .85, weight: 900, align: 'center', fill: BLK }),
  play: (c, r) => { c.fillStyle = BLK; c.beginPath(); c.moveTo(-r * .22, -r * .38); c.lineTo(r * .42, 0); c.lineTo(-r * .22, r * .38); c.fill(); },
  plus: (c, r) => { c.fillStyle = BLK; rr(c, -r * .46, -r * .09, r * .92, r * .18, r * .09); c.fill(); rr(c, -r * .09, -r * .46, r * .18, r * .92, r * .09); c.fill(); },
  link: (c, r) => { c.strokeStyle = BLK; c.lineWidth = r * .15; c.lineCap = 'round'; c.save(); c.rotate(-.7); rr(c, -r * .5, -r * .2, r * .62, r * .4, r * .2); c.stroke(); rr(c, -r * .12, -r * .2, r * .62, r * .4, r * .2); c.stroke(); c.restore(); },
  bell: (c, r) => emoji(c, '🔔', 0, 0, r * 1.0),
  folder: (c, r) => { c.fillStyle = BLK; rr(c, -r * .5, -r * .3, r * 1.0, r * .66, r * .1); c.fill(); rr(c, -r * .5, -r * .42, r * .42, r * .2, r * .06); c.fill(); },
  phone: (c, r) => { c.fillStyle = BLK; rr(c, -r * .26, -r * .5, r * .52, r * 1.0, r * .12); c.fill(); c.fillStyle = Y1; rr(c, -r * .2, -r * .38, r * .4, r * .66, r * .06); c.fill(); },
  spark: (c, r) => star4(c, 0, 0, r * .62, 0, BLK),
  q: (c, r) => wt(c, '?', 0, r * .05, { size: r * 1.25, weight: 900, align: 'center', fill: BLK }),
  tg: (c, r) => { c.save(); c.scale(r / 50, r / 50); c.fillStyle = '#fff'; c.beginPath(); c.moveTo(-23, -1.5); c.lineTo(22, -19.5); c.bezierCurveTo(24.5, -20.4, 26.8, -18.8, 26, -15.6); c.lineTo(18.5, 19.5); c.bezierCurveTo(18, 22, 15, 23, 13, 21.5); c.lineTo(1.5, 13); c.lineTo(-6.5, 21); c.bezierCurveTo(-8.5, 23, -11, 21.8, -11, 19); c.lineTo(-11, 9.5); c.lineTo(15, -12.5); c.lineTo(-14.5, 6.5); c.lineTo(-22.5, 3.5); c.bezierCurveTo(-25.5, 2.3, -25.8, -0.6, -23, -1.5); c.closePath(); c.fill(); c.restore(); },
  lock: (c, r) => emoji(c, '🔒', 0, 0, r * 1.0),
};
function drawTgCoin(c, x, y, r, p, spin) { coin(c, x, y, r, p, spin, (c, r) => { c.save(); c.beginPath(); c.arc(0, 0, r * .86, 0, 7); c.fillStyle = linGrad(c, 0, -r, 0, r, [[0, '#4cc0f0'], [1, '#1e8fcf']]); c.fill(); c.restore(); IC.tg(c, r); }); }
const ICONS = () => [
  { t0: w0(3), t1: w0(7) - .05, k: 'ai', side: 1, dy: -150, r: 92 }, { t0: w0(4), t1: w0(7) - .05, k: 'play', side: -1, dy: -40, r: 74 },
  { t0: w0(11), t1: w0(13) - .1, k: 'phone', side: -1, dy: -60, r: 78 }, { t0: w0(23), t1: w1(26), k: 'folder', side: 1, dy: -80, r: 80 },
  { t0: w0(33), t1: w1(36) + .1, k: 'ai', side: 1, dy: -120, r: 90 }, { t0: w0(39), t1: w0(42), k: 'ai', side: -1, dy: -110, r: 78 }, { t0: w0(44), t1: w1(45) + .1, k: 'spark', side: 1, dy: -90, r: 74 },
  { t0: w0(50), t1: w1(52) + .3, k: 'play', side: -1, dy: -90, r: 80 }, { t0: w0(56), t1: w1(62), k: 'tg', side: 1, dy: -130, r: 92 }, { t0: w0(57), t1: w1(62), k: 'lock', side: -1, dy: -50, r: 66 },
  { t0: w0(67) + .2, t1: w1(71) + .2, k: 'plus', side: -1, dy: -110, r: 82 }, { t0: w0(74), t1: w1(79) + .1, k: 'link', side: 1, dy: -120, r: 84 },
  { t0: w0(89), t1: w0(94) - .3, k: 'bell', side: 1, dy: -110, r: 74 }, { t0: w0(94), t1: w0(97) - .1, k: 'plus', side: -1, dy: -110, r: 90 }];
let ICON_LIST = [];
function drawIcons(c, T, fp, cm, hh) {
  for (const ic of ICON_LIST) {
    if (T < ic.t0 || T > ic.t1 + .25) continue; const pin = prog(T, ic.t0, ic.t0 + .5), pout = prog(T, ic.t1, ic.t1 + .22), p = pin * (1 - E.inQ(pout)); if (p <= 0.001) continue;
    const half = Math.min(260, fp[2] * .5) + ic.r * .5; let x = fp[0] + ic.side * (half + 70) - (cm.bx + hh.x) * 1.4, y = fp[1] + ic.dy + 12 * sine(T, 2.1, ic.t0) - hh.y * 1.6;
    x = clamp(x, ic.r + 20, W - ic.r - 20); y = clamp(y, 260, 1000);
    const spin = ic.k === 'ai' || ic.k === 'play' || ic.k === 'link' ? (T - ic.t0) * 2.6 + .01 : sine(T, 1.6, ic.t0) * .55;
    if (ic.k === 'tg') drawTgCoin(c, x, y, ic.r, p, spin); else coin(c, x, y, ic.r, p, spin, IC[ic.k], { dark: ic.k === 'lock' || ic.k === 'bell' ? false : false, rot: .12 * sine(T, 1.3, ic.t0) });
  }
}
