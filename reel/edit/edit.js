// ===== Talking-head edit: amber/white kinetic style, zoom track, white cut-aways =====
const AM1 = '#FFD561', AM2 = '#F59E0B', AM3 = '#B86A00', INK = '#15110a', PAPER = '#F7F7F4';
const FPS = 60, SRCW = 720, SRCH = 1280, K0 = W / SRCW;
let WD = [], FACE = null, img = new Image(), CTX, CNV;
const w0 = i => WD[i].t0, w1 = i => WD[i].t1;
const amber = (c, x0, y0, x1, y1) => linGrad(c, x0, y0, x1, y1, [[0, AM1], [1, AM2]]);
const skewTf = (c, k) => c.transform(1, 0, -k, 1, 0, 0);

// ---------- zoom track ----------
function buildTrack() {
  const K = []; const k = (t, z, roll = 0, ease = 'soft') => K.push({ t, z, roll, ease });
  k(0, 1.0); k(w0(3) - .05, 1.05); k(w0(3) + .12, 1.17, .5, 'punch'); k(w0(6), 1.09, 0, 'out');
  k(w0(7) - .02, 1.09); k(w0(7) + .13, 1.27, -.9, 'punch'); k(w0(8), 1.14, 0, 'out'); k(w0(9) + .15, 1.0, 0, 'soft');
  k(w0(12), 1.07, .3); k(w0(13) + .01, 1.14, -.5, 'punch'); k(w0(15), 1.05, 0, 'out');
  k(w0(20) - .03, 1.07); k(w0(20) + .12, 1.2, .6, 'punch'); k(w0(24), 1.06, 0, 'out'); k(CUTS[0].a - .5, 1.1, 0, 'soft');
  CUTS.forEach((c, ci) => { if (ci) { k(c.a - .55, 1.05, 0, 'soft'); } k(c.a, 1.55, 0, 'in'); k(c.b, 1.5, 0, 'soft'); k(c.b + .55, ci === 0 ? 1.0 : 1.04, 0, 'out'); });
  return K.sort((a, b) => a.t - b.t);
}
// segments between cut-aways get extra keys, inserted after CUTS exist
function trackExtra(K) {
  const k = (t, z, roll = 0, ease = 'soft') => K.push({ t, z, roll, ease });
  k(w0(38) + .4, 1.0, 0, 'soft'); k(w0(42), 1.08, .4); k(w0(44) + .05, 1.2, -.6, 'punch'); k(w0(46) - .05, 1.08, 0, 'out');
  k(w0(50) + .02, 1.15, .6, 'punch'); k(w0(52) - .05, 1.07, 0, 'out'); k(w0(52) + .12, 1.25, -.9, 'punch'); k(w0(53) + .2, 1.1, 0, 'out'); k(w0(54), 1.02, 0, 'soft');
  k(w0(63) - .1, 1.04); k(w0(67), 1.12, .5, 'punch'); k(CUTS[2].a - .55, 1.06, 0, 'soft');
  k(w0(74) + .02, 1.18, -.7, 'punch'); k(w0(76), 1.05, 0, 'out');
  k(w0(84) + .02, 1.16, .6, 'punch'); k(w0(86) - .1, 1.08, 0, 'out'); k(w0(88) + .05, 1.22, -.8, 'punch'); k(w0(89) - .1, 1.05, 0, 'out');
  k(w0(94) + .02, 1.18, .5, 'punch'); k(w0(96), 1.08, 0, 'out'); k(w0(97) - .05, 1.04, 0, 'soft'); k(w0(97) + .3, 1.16, 0, 'soft'); k(TOTAL, 1.2, 0, 'soft');
  return K.sort((a, b) => a.t - b.t);
}
const EZ = { soft: E.inOutS, punch: E.outE, out: E.outC, in: E.inE };
let TRACK = [];
function zoomAt(T) {
  if (T <= TRACK[0].t) return [TRACK[0].z, TRACK[0].roll];
  for (let i = 1; i < TRACK.length; i++) if (T <= TRACK[i].t) { const a = TRACK[i - 1], b = TRACK[i], p = EZ[b.ease](prog(T, a.t, b.t)); return [lerp(a.z, b.z, p), lerp(a.roll, b.roll, p)]; }
  const l = TRACK[TRACK.length - 1]; return [l.z, l.roll];
}
// ---------- cut-aways ----------
let CUTS = [], TOTAL = 45.5;
const WIPE = .42;
function cutState(T) { for (const c of CUTS) if (T > c.a - WIPE && T < c.b + WIPE) return c; return null; }

// ---------- footage ----------
function faceAt(T) { const i = Math.min(FACE.n - 1, Math.max(0, Math.round(T * FPS))); return [FACE.x[i] * K0, FACE.y[i] * K0, FACE.w[i] * K0]; }
function drawVideo(c, T) {
  const [z0, roll0] = zoomAt(T); const [fx, fy] = faceAt(T);
  const px = lerp(W / 2, fx, .55), py = lerp(H * .42, fy, .6);
  const dz = Math.abs(zoomAt(T + .004)[0] - zoomAt(T - .004)[0]) / .008; // zoom velocity -> motion blur
  const n = dz > 1.2 ? Math.min(6, 2 + Math.floor(dz * .9)) : 1;
  const sh = [Math.sin(T * 53) * 1.2 * Math.min(1, dz), Math.cos(T * 47) * 1.2 * Math.min(1, dz)];
  c.fillStyle = '#000'; c.fillRect(0, 0, W, H); c.imageSmoothingEnabled = true; c.imageSmoothingQuality = 'high';
  c.filter = 'contrast(1.07) saturate(1.1) brightness(1.02)';
  for (let s = 0; s < n; s++) {
    const [z, roll] = zoomAt(T - s * .0042); c.save(); c.globalAlpha = s === 0 ? 1 : 1 / (s + 1);
    c.translate(px + sh[0], py + sh[1]); c.rotate(roll * Math.PI / 180); const zz = z * (1 + .02 * Math.abs(roll)); c.scale(zz, zz); c.translate(-px, -py);
    c.drawImage(img, 0, 0, W, H); c.restore();
  }
  c.filter = 'none';
}
// ---------- UI atoms (amber / white style) ----------
function label(c, s, x, y, p, o = {}) {
  if (p <= 0) return; const a = E.outC(p);
  c.save(); c.globalAlpha *= a; c.translate(x + (1 - a) * (o.dx ?? 0), y + (1 - a) * 18); skewTf(c, .18);
  c.font = font(o.weight ?? 400, o.size ?? 44, SANS); c.textAlign = o.align ?? 'left'; c.textBaseline = 'middle'; c.shadowColor = 'rgba(0,0,0,.55)'; c.shadowBlur = 14; c.shadowOffsetY = 3;
  c.fillStyle = o.fill ?? '#fff'; c.fillText(s, 0, 0); c.restore();
}
function heavy(c, s, x, y, p, o = {}) { // big heavy text, gradient amber or white, pop + ghost
  if (p <= 0) return; const sc = clamp(pop(p, 8, 11), 0, 1.12), al = clamp(p * 3); const size = o.size ?? 150;
  c.save(); c.translate(x, y); c.rotate(o.rot ?? 0); c.scale(sc * (o.sx ?? 1), sc); c.globalAlpha *= al;
  c.font = font(900, size, SANS); c.textAlign = o.align ?? 'center'; c.textBaseline = 'middle'; c.letterSpacing = (o.ls ?? -3) + 'px';
  const w = c.measureText(s).width; const ox = o.align === 'left' ? w / 2 : 0;
  c.shadowColor = o.amber === false ? 'rgba(0,0,0,.6)' : 'rgba(245,158,11,.55)'; c.shadowBlur = o.amber === false ? 24 : 34; c.shadowOffsetY = 6;
  c.fillStyle = o.amber === false ? '#fff' : linGrad(c, 0, -size * .5, 0, size * .5, [[0, AM1], [1, AM2]]);
  if (o.italic) skewTf(c, .16);
  c.lineJoin = 'round'; c.lineWidth = size * .07; c.strokeStyle = o.amber === false ? 'rgba(0,0,0,.6)' : 'rgba(95,48,0,.92)'; c.strokeText(s, 0, 0); c.fillText(s, 0, 0); c.restore();
}
function tile(c, ch, x, y, size, p, o = {}) {
  if (p <= 0) return; const sc = clamp(pop(p, 9, 12), 0, 1.15), a = clamp(p * 4);
  c.save(); c.translate(x, y + (1 - clamp(p, 0, 1)) * -40); c.scale(sc, sc); c.globalAlpha *= a;
  const r = size * .22, dark = o.dark; c.shadowColor = 'rgba(0,0,0,.45)'; c.shadowBlur = 30; c.shadowOffsetY = 12;
  rr(c, -size / 2, -size / 2, size, size, r); c.fillStyle = dark ? '#16130d' : amber(c, 0, -size / 2, 0, size / 2); c.fill(); c.shadowBlur = 0; c.shadowOffsetY = 0;
  rr(c, -size / 2, -size / 2, size, size, r); c.lineWidth = 3; c.strokeStyle = dark ? 'rgba(255,255,255,.14)' : 'rgba(255,240,190,.9)'; c.stroke();
  c.save(); rr(c, -size / 2, -size / 2, size, size, r); c.clip(); c.fillStyle = linGrad(c, 0, -size / 2, 0, 0, [[0, 'rgba(255,255,255,.45)'], [1, 'rgba(255,255,255,0)']]); c.fillRect(-size / 2, -size / 2, size, size / 2);
  c.fillStyle = linGrad(c, 0, size * .2, 0, size / 2, [[0, 'rgba(0,0,0,0)'], [1, 'rgba(150,70,0,.35)']]); c.fillRect(-size / 2, size * .2, size, size * .3); c.restore();
  if (o.icon) o.icon(c, size); else T(c, ch, 0, size * .02, { size: size * .6, weight: 900, fill: dark ? AM1 : '#fff', shadow: 10 });
  c.restore();
}
function selBox(c, x, y, w, h, p) {
  if (p <= 0) return; c.save(); c.globalAlpha *= clamp(p * 2); c.strokeStyle = AM1; c.lineWidth = 3; c.setLineDash([10, 8]); c.lineDashOffset = -p * 30; const q = E.outC(p);
  c.strokeRect(x - w / 2 * q, y - h / 2 * q, w * q, h * q); c.setLineDash([]); c.fillStyle = AM1; [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sy]) => { c.beginPath(); c.arc(x + sx * w / 2 * q, y + sy * h / 2 * q, 6, 0, 7); c.fill(); }); c.restore();
}
function pill(c, s, x, y, p, o = {}) {
  if (p <= 0) return; const sc = clamp(pop(p, 9, 11), 0, 1.1); c.save(); c.translate(x, y); c.scale(sc, sc); c.globalAlpha *= clamp(p * 4);
  const size = o.size ?? 40; c.font = font(800, size, SANS); const w = c.measureText(s).width + size * 1.6, h = size * 1.7;
  c.shadowColor = 'rgba(0,0,0,.4)'; c.shadowBlur = 22; c.shadowOffsetY = 8; rr(c, -w / 2, -h / 2, w, h, h / 2); c.fillStyle = o.dark ? INK : amber(c, 0, -h / 2, 0, h / 2); c.fill(); c.shadowBlur = 0;
  c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = o.dark ? AM1 : INK; c.fillText(s, 0, 2); c.restore(); return w;
}
function wave(c, y, p, amp = 18, col = AM2, w = 960, x0 = 60) {
  if (p <= 0) return; c.save(); c.strokeStyle = col; c.lineWidth = 9; c.lineCap = 'round'; c.shadowColor = 'rgba(245,158,11,.5)'; c.shadowBlur = 18; c.beginPath();
  const n = 80 * E.outC(clamp(p)); for (let i = 0; i <= n; i++) { const x = x0 + i / 80 * w, yy = y + Math.sin(i / 80 * 6.28 * 2.2 + p * 3) * amp; i ? c.lineTo(x, yy) : c.moveTo(x, yy); } c.stroke(); c.restore();
}
function cursor(c, x, y, tag, p, press = 0) {
  if (p <= 0) return; c.save(); c.globalAlpha *= clamp(p * 3); c.translate(x, y); c.scale(1 - press * .12, 1 - press * .12);
  c.shadowColor = 'rgba(0,0,0,.4)'; c.shadowBlur = 10; c.shadowOffsetY = 3; c.fillStyle = AM1; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 34); c.lineTo(9, 26); c.lineTo(17, 40); c.lineTo(23, 36); c.lineTo(15, 23); c.lineTo(27, 22); c.closePath(); c.fill(); c.shadowBlur = 0;
  if (tag) { c.font = font(700, 22, SANS); const w = c.measureText(tag).width + 30; rr(c, 24, 34, w, 40, 20); c.fillStyle = INK; c.fill(); c.fillStyle = '#fff'; c.textBaseline = 'middle'; c.textAlign = 'left'; c.fillText(tag, 39, 55); } c.restore();
}
function flare(c, p, y = H * .5) { if (p <= 0 || p >= 1) return; c.save(); c.globalCompositeOperation = 'lighter'; const x = lerp(-300, W + 300, E.inOutS(p)); const g = c.createRadialGradient(x, y, 0, x, y, 700); g.addColorStop(0, 'rgba(255,200,90,.85)'); g.addColorStop(.35, 'rgba(255,160,40,.35)'); g.addColorStop(1, 'rgba(255,140,0,0)'); c.fillStyle = g; c.globalAlpha = Math.sin(p * Math.PI); c.fillRect(0, 0, W, H); c.restore(); }
