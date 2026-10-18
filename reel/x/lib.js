// ---------- helpers ----------
const W = 1080, H = 1920, SC = +(new URLSearchParams(location.search).get('sc') || 2);
const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
const lerp = (a, b, t) => a + (b - a) * t;
const prog = (t, a, b) => clamp((t - a) / (b - a));
const E = {
  lin: t => t,
  inQ: t => t * t,
  outQ: t => 1 - (1 - t) * (1 - t),
  outC: t => 1 - Math.pow(1 - t, 3),
  outE: t => t >= 1 ? 1 : 1 - Math.pow(2, -10 * t),
  inOutC: t => t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2,
  inOutS: t => t * t * (3 - 2 * t),
  outB: t => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
  inE: t => t <= 0 ? 0 : Math.pow(2, 10 * t - 10),
};
const pop = (t, k = 7, f = 11) => t <= 0 ? 0 : 1 - Math.exp(-k * t) * Math.cos(f * t); // damped spring 0->1
function rng(seed) { let a = seed >>> 0; return () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const C = { bg: '#05070d', blue: '#4f8cff', cyan: '#35d0ff', vio: '#8b5cf6', org: '#ff8a3d', mint: '#34d399', pink: '#ff4d8d', gray: '#9aa4b8', white: '#ffffff' };
const SANS = 'Inter, "Inter Display", sans-serif', SERIF = '"DejaVu Serif", "Liberation Serif", serif';
const font = (w, s, f = SANS, it = false) => `${it ? 'italic ' : ''}${w} ${s}px ${f}`;
const rgba = (hex, a) => { const n = parseInt(hex.slice(1), 16); return `rgba(${n >> 16},${n >> 8 & 255},${n & 255},${a})`; };

function rr(c, x, y, w, h, r) { c.beginPath(); c.roundRect(x, y, w, h, r); }
// text with transform/alpha/blur-ghost/shadow. o: {size,weight,font,fill,align,base,alpha,sx,sy,rot,italic,glow,glowC,stroke,strokeW,ls}
function T(c, s, x, y, o = {}) {
  const a = o.alpha ?? 1; if (a <= 0.001) return;
  c.save(); c.globalAlpha *= a; c.translate(x, y); if (o.rot) c.rotate(o.rot); c.scale(o.sx ?? o.s ?? 1, o.sy ?? o.s ?? 1);
  c.font = font(o.weight ?? 900, o.size ?? 80, o.font ?? SANS, o.italic); c.textAlign = o.align ?? 'center'; c.textBaseline = o.base ?? 'middle';
  if (o.ls) c.letterSpacing = o.ls + 'px';
  if (o.glow) { c.shadowColor = o.glowC ?? 'rgba(79,140,255,.9)'; c.shadowBlur = o.glow; }
  if (o.shadow) { c.shadowColor = 'rgba(0,0,0,.55)'; c.shadowBlur = o.shadow; c.shadowOffsetY = o.shadow * .3; }
  if (o.stroke) { c.lineWidth = o.strokeW ?? 4; c.strokeStyle = o.stroke; c.lineJoin = 'round'; c.strokeText(s, 0, 0); }
  c.fillStyle = o.fill ?? '#fff'; c.fillText(s, 0, 0); c.restore();
}
function measure(c, s, o = {}) { c.save(); c.font = font(o.weight ?? 900, o.size ?? 80, o.font ?? SANS, o.italic); if (o.ls) c.letterSpacing = o.ls + 'px'; const w = c.measureText(s).width; c.restore(); return w; }
// text with horizontal motion ghosts (cheap motion blur)
function Tghost(c, s, x, y, o, dx, dy, n = 5) {
  for (let i = n; i >= 1; i--) T(c, s, x - dx * i / n, y - dy * i / n, { ...o, alpha: (o.alpha ?? 1) * 0.16 * (1 - i / (n + 1)), glow: 0 });
  T(c, s, x, y, o);
}
// per-letter staggered reveal (mask slide up + blur-free fade); returns nothing
function letters(c, s, x, y, t, o = {}) {
  const step = o.step ?? 0.035, dur = o.dur ?? 0.5, rise = o.rise ?? 0.6;
  const w = measure(c, s, o); let cx = x - (o.align === 'left' ? 0 : w / 2);
  for (let i = 0; i < s.length; i++) {
    const ch = s[i], cw = measure(c, ch, o), p = E.outC(prog(t, i * step, i * step + dur));
    if (ch !== ' ' && p > 0) T(c, ch, cx + cw / 2, y + (1 - p) * (o.size ?? 80) * rise, { ...o, align: 'center', alpha: p * (o.alpha ?? 1), sy: lerp(1.25, 1, p) });
    cx += cw + (o.ls ?? 0);
  }
}
function glowDot(c, x, y, r, col, a = 1) {
  const g = c.createRadialGradient(x, y, 0, x, y, r); g.addColorStop(0, rgba(col, a)); g.addColorStop(1, rgba(col, 0));
  c.fillStyle = g; c.fillRect(x - r, y - r, r * 2, r * 2);
}
function linGrad(c, x0, y0, x1, y1, stops) { const g = c.createLinearGradient(x0, y0, x1, y1); stops.forEach(([p, col]) => g.addColorStop(p, col)); return g; }

// Telegram paper-plane logo (blue disc + white plane)
function tgLogo(c, x, y, r) {
  c.save(); c.translate(x, y); c.scale(r / 50, r / 50);
  c.fillStyle = linGrad(c, 0, -50, 0, 50, [[0, '#37aee2'], [1, '#1e96c8']]); c.beginPath(); c.arc(0, 0, 50, 0, 7); c.fill();
  c.fillStyle = '#fff'; c.beginPath(); c.moveTo(-23, -1.5); c.lineTo(22, -19.5); c.bezierCurveTo(24.5, -20.4, 26.8, -18.8, 26, -15.6); c.lineTo(18.5, 19.5); c.bezierCurveTo(18, 22, 15, 23, 13, 21.5); c.lineTo(1.5, 13); c.lineTo(-6.5, 21); c.bezierCurveTo(-8.5, 23, -11, 21.8, -11, 19); c.lineTo(-11, 9.5); c.lineTo(15, -12.5); c.lineTo(-14.5, 6.5); c.lineTo(-22.5, 3.5); c.bezierCurveTo(-25.5, 2.3, -25.8, -0.6, -23, -1.5); c.closePath(); c.fill();
  c.fillStyle = 'rgba(190,215,235,.9)'; c.beginPath(); c.moveTo(-11, 9.5); c.lineTo(15, -12.5); c.lineTo(-6, 13.5); c.lineTo(-6.5, 21); c.lineTo(-11, 19); c.closePath(); c.globalAlpha *= .55; c.fill(); c.restore();
}
function emoji(c, ch, x, y, size, o = {}) {
  const a = o.alpha ?? 1; if (a <= 0.001) return;
  c.save(); c.globalAlpha *= a; c.translate(x, y); if (o.rot) c.rotate(o.rot); c.scale(o.s ?? 1, o.s ?? 1);
  if (o.glow) { c.shadowColor = o.glowC ?? 'rgba(255,255,255,.5)'; c.shadowBlur = o.glow; }
  c.font = `${size}px "Noto Color Emoji"`; c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText(ch, 0, 0); c.restore();
}
function ring(c, x, y, r, w, col, a) { if (a <= 0) return; c.save(); c.globalAlpha *= a; c.strokeStyle = col; c.lineWidth = w; c.beginPath(); c.arc(x, y, r, 0, 7); c.stroke(); c.restore(); }
function star4(c, x, y, r, rot, col, a = 1) {
  c.save(); c.translate(x, y); c.rotate(rot); c.globalAlpha *= a; c.fillStyle = col; c.beginPath();
  for (let i = 0; i < 8; i++) { const rad = i % 2 ? r * .22 : r, ang = i * Math.PI / 4; c.lineTo(Math.cos(ang) * rad, Math.sin(ang) * rad); } c.fill(); c.restore();
}
// camera: zoom z about focus (fx,fy) with optional rotation & shake; call inside save/restore
function cam(c, z, fx, fy, rot = 0, ox = 0, oy = 0) { c.translate(W / 2 + ox, H / 2 + oy); c.rotate(rot); c.scale(z, z); c.translate(-fx, -fy); }
const shakeAt = (t, t0, amp = 10, dur = 0.35) => { const p = prog(t, t0, t0 + dur); if (p <= 0 || p >= 1) return [0, 0]; const d = Math.pow(1 - p, 2) * amp; return [Math.sin(t * 91) * d, Math.cos(t * 77) * d]; };

// background: dark gradient, parallax grid, glow orbs, drifting particles
const PART = (() => { const r = rng(7); return Array.from({ length: 70 }, () => ({ x: r() * W, y: r() * H, z: .3 + r() * .9, s: 1 + r() * 2.4, ph: r() * 6.3 })); })();
function backdrop(c, t, o = {}) {
  const h1 = o.c1 ?? C.blue, h2 = o.c2 ?? C.vio, px = o.px ?? 0, py = o.py ?? 0;
  c.fillStyle = linGrad(c, 0, 0, 0, H, [[0, '#070b17'], [.55, '#05070d'], [1, '#080a14']]); c.fillRect(-200, -200, W + 400, H + 400);
  glowDot(c, 220 + Math.sin(t * .5) * 120 + px * .3, 420 + Math.cos(t * .4) * 90, 760, h1, .30 * (o.glow ?? 1));
  glowDot(c, 880 - Math.sin(t * .45) * 120 + px * .5, 1300 + Math.cos(t * .5) * 120, 820, h2, .26 * (o.glow ?? 1));
  if (o.grid !== false) {
    c.save(); c.strokeStyle = 'rgba(140,170,255,.07)'; c.lineWidth = 1.4; const g = 90, gx = ((px * .6 + t * 8) % g + g) % g, gy = ((py * .6 + t * 5) % g + g) % g;
    c.beginPath(); for (let x = -g + gx; x < W + g; x += g) { c.moveTo(x, -50); c.lineTo(x, H + 50); } for (let y = -g + gy; y < H + g; y += g) { c.moveTo(-50, y); c.lineTo(W + 50, y); } c.stroke(); c.restore();
  }
  if (o.particles !== false) for (const p of PART) {
    const x = ((p.x + px * p.z * .8 + t * 6 * p.z) % W + W) % W, y = ((p.y - t * 14 * p.z + py * p.z * .8) % H + H) % H;
    c.fillStyle = `rgba(190,210,255,${(.10 + .22 * Math.abs(Math.sin(t * .8 + p.ph))) * p.z})`; c.beginPath(); c.arc(x, y, p.s * p.z, 0, 7); c.fill();
  }
}
