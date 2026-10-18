const TXT = T;
const KEY = new Set([3, 4, 7, 9, 10, 11, 13, 14, 20, 23, 33, 34, 39, 42, 43, 44, 50, 51, 52, 56, 60, 67, 68, 74, 84, 85, 88, 89, 94, 97]);
// ---------- subtitles (karaoke) ----------
let CH = null;
function chunksOf() { const out = []; let cur = []; WD.forEach((w, i) => { cur.push(i); if (cur.length >= 3 || /[,.?!]$/.test(w.w) || (cur.length === 2 && KEY.has(i) && KEY.has(i - 1))) { out.push(cur); cur = []; } }); if (cur.length) out.push(cur); return out; }
function drawSubs(c, T) {
  CH = CH || chunksOf();
  for (let ci = 0; ci < CH.length; ci++) {
    const ch = CH[ci], nx = CH[ci + 1]; if (ch.includes(97)) continue; const a = w0(ch[0]) - .08; let b = w1(ch[ch.length - 1]) + .28; if (nx) b = Math.min(b, w0(nx[0]) - .06); if (T < a || T > b) continue;
    const base = 74, items = ch.map(i => { const k = KEY.has(i); const sz = base * (k ? 1.32 : 1); c.save(); c.font = font(900, sz, SANS); const wd = c.measureText(WD[i].w).width; c.restore(); return { i, k, sz, wd }; });
    const gap = 22, tot = items.reduce((s, it) => s + it.wd, 0) + gap * (items.length - 1), fit = Math.min(1, 960 / tot);
    const al = clamp((T - a) / .1) * clamp((b - T) / .08), rise = (1 - E.outC(clamp((T - a) / .18))) * 26; let x = 540 - tot * fit / 2;
    c.save(); c.globalAlpha *= al; c.translate(0, rise);
    for (const it of items) {
      const w = WD[it.i], act = T >= w.t0 && T <= w.t1, past = T > w.t1, bump = act ? Math.sin(clamp((T - w.t0) / .22) * Math.PI) : 0, s = fit * (1 + .10 * bump);
      c.save(); c.translate(x + it.wd * fit / 2, 1415); c.scale(s, s); c.font = font(900, it.sz, SANS); c.textAlign = 'center'; c.textBaseline = 'middle'; c.lineJoin = 'round'; c.letterSpacing = '-1px';
      c.lineWidth = it.sz * .17; c.strokeStyle = 'rgba(0,0,0,.88)'; c.shadowColor = 'rgba(0,0,0,.6)'; c.shadowBlur = 18; c.shadowOffsetY = 5; c.strokeText(w.w, 0, 0); c.shadowBlur = 0;
      c.fillStyle = it.k ? yg(c, 0, -it.sz * .5, 0, it.sz * .5) : (act || past ? '#fff' : 'rgba(255,255,255,.62)'); c.fillText(w.w, 0, 0); c.restore(); x += (it.wd + gap) * fit;
    }
    c.restore();
  }
}
// ---------- cards ----------
function cardName(c, T) {
  const a = w0(9) - .1, b = w0(13) - .12, p = prog(T, a, a + .5) * (1 - prog(T, b, b + .25)); if (p <= 0 || T > b + .3) return;
  if (glass(c, 60, 985, 600, 200, p, { fromX: -300 })) { const tI = T - w0(9); wt(c, 'Men', 38, 40, { size: 34, weight: 500, fill: 'rgba(255,255,255,.7)', alpha: prog(T, w0(8), w0(8) + .3) });
    letters(c, 'Saidov Baxtiyor', 38, 112, tI, { size: 68, weight: 900, align: 'left', step: .028, dur: .4, rise: .5 });
    const q = pop(prog(T, w0(11), w0(11) + .5)); if (q > 0) { c.save(); c.translate(38, 166); c.scale(clamp(q, 0, 1.1), clamp(q, 0, 1.1)); c.font = font(800, 28, SANS); c.letterSpacing = '3px'; const tw = c.measureText('MOBILOGRAF').width + 40; rr(c, 0, -22, tw, 44, 22); c.fillStyle = yg(c, 0, -22, 0, 22); c.fill(); c.fillStyle = BLK; c.textBaseline = 'middle'; c.fillText('MOBILOGRAF', 20, 2); c.restore(); } gEnd(c); }
}
function statCard(c, T, a, b, x, y, w, big, unit, count, sub) {
  const p = prog(T, a - .1, a + .5) * (1 - prog(T, b, b + .25)); if (p <= 0) return;
  if (glass(c, x, y, w, 215, p, { fromX: x < 400 ? -240 : 240 })) { const n = count(T); const bt = big(n); c.save(); c.font = font(900, 140, SANS); const bw = c.measureText(bt).width; c.restore();
    c.save(); c.shadowColor = 'rgba(255,174,0,.5)'; c.shadowBlur = 30; wt(c, bt, 36, 92, { size: 140, weight: 900, fill: Y1 }); c.restore(); wt(c, unit, 36 + bw + 18, 112, { size: 60, weight: 800 }); wt(c, sub, 38, 182, { size: 30, weight: 500, fill: 'rgba(255,255,255,.65)' });
    const hl = Math.max(0, 1 - Math.abs(T - a - .6) / .5); if (hl > 0) { rr(c, 0, 0, w, 215, 34); c.strokeStyle = rgba('#FFD426', hl * .9); c.lineWidth = 5; c.stroke(); } gEnd(c); }
}
function cardAI(c, T) {
  const a = w0(33) - .15, b = w1(36) + .12, p = prog(T, a, a + .5) * (1 - prog(T, b, b + .25)); if (p <= 0) return; const tc = T - a;
  if (glass(c, 90, 950, 900, 345, p, { fromX: 0 })) { star4(c, 56, 50, 22, T * .8, Y1); wt(c, 'Claude AI', 94, 50, { size: 42, weight: 800 }); wt(c, 'video montaj', 864, 50, { size: 28, weight: 500, align: 'right', fill: 'rgba(255,255,255,.6)' });
    const tr = [[Y1, 5], ['#ffffff', 4], ['#6b6b6e', 6]]; const r = rng(3); tr.forEach(([col, n], ri) => { let x = 36; const y = 100 + ri * 76; c.fillStyle = 'rgba(255,255,255,.06)'; rr(c, 30, y - 4, 840, 64, 12); c.fill(); for (let j = 0; j < n; j++) { const ww = 800 / n * (.72 + r() * .2), st = .25 + ri * .15 + j * .09, q = E.outC(prog(tc, st, st + .3)); if (q > 0) { c.fillStyle = col; rr(c, x, y, ww * q, 56, 10); c.fill(); } x += 800 / n; } });
    const px = lerp(60, 840, prog(tc, .3, b - a)); c.strokeStyle = '#fff'; c.lineWidth = 4; c.shadowColor = '#fff'; c.shadowBlur = 12; c.beginPath(); c.moveTo(px, 88); c.lineTo(px, 330); c.stroke(); gEnd(c); }
}
function cardGrow(c, T) {
  const a = w0(42) - .1, b = w1(45) + .15, p = prog(T, a, a + .5) * (1 - prog(T, b, b + .25)); if (p <= 0) return; const tc = T - a;
  if (glass(c, 90, 1000, 900, 290, p, {})) { wt(c, 'AI', 40, 46, { size: 40, weight: 900, fill: Y1 }); wt(c, 'rivojlanish', 864, 46, { size: 28, weight: 500, align: 'right', fill: 'rgba(255,255,255,.6)' });
    const q = E.inOutS(prog(tc, .1, b - a)); c.save(); c.lineCap = 'round'; c.lineWidth = 9; c.strokeStyle = yg(c, 40, 0, 860, 0); c.shadowColor = 'rgba(255,174,0,.6)'; c.shadowBlur = 20; c.beginPath(); for (let i = 0; i <= 90 * q; i++) { const x = i / 90, px = 40 + x * 820, py = 255 - 175 * (Math.exp(3.2 * x) - 1) / (Math.exp(3.2) - 1); i ? c.lineTo(px, py) : c.moveTo(px, py); } c.stroke(); c.restore();
    const x = q, px = 40 + x * 820, py = 255 - 175 * (Math.exp(3.2 * x) - 1) / (Math.exp(3.2) - 1); glowDot(c, px, py, 46, Y1, .9); c.fillStyle = '#fff'; c.beginPath(); c.arc(px, py, 9, 0, 7); c.fill(); gEnd(c); }
}
function cardTG(c, T) {
  const a = w0(56) - .1, b = w1(62) + .12, p = prog(T, a, a + .5) * (1 - prog(T, b, b + .25)); if (p <= 0) return; const tc = T - a;
  if (glass(c, 90, 950, 900, 345, p, {})) { tgLogo(c, 78, 62, 32); wt(c, 'Video darslik', 128, 50, { size: 40, weight: 800 }); emoji(c, '🔒', 134, 92, 24); wt(c, 'yopiq kanal', 160, 92, { size: 26, weight: 500, fill: 'rgba(255,255,255,.62)' });
    for (let i = 0; i < 3; i++) { const q = prog(T, w0(59) + i * .22 - .1, w0(59) + i * .22 + .5); if (q <= 0) continue; const s = clamp(pop(q, 8, 10), 0, 1.05); c.save(); c.translate(40 + i * 284 + 134, 130 + 100); c.scale(s, s); c.globalAlpha *= clamp(q * 3);
      rr(c, -134, -100, 268, 200, 24); c.fillStyle = linGrad(c, -134, -100, 134, 100, [[0, '#1b1b1d'], [1, '#3a3112']]); c.fill(); c.strokeStyle = 'rgba(255,255,255,.12)'; c.lineWidth = 2; c.stroke();
      c.fillStyle = Y1; c.beginPath(); c.arc(0, -10, 38, 0, 7); c.fill(); c.fillStyle = BLK; c.beginPath(); c.moveTo(-10, -30); c.lineTo(22, -10); c.lineTo(-10, 10); c.fill(); wt(c, `${i + 1}-dars`, 0, 66, { size: 34, weight: 800, align: 'center' }); c.restore(); } gEnd(c); }
}
function cardPlus(c, T) {
  const a = w0(67) - .1, b = w1(71) + .35, p = prog(T, a, a + .5) * (1 - prog(T, b, b + .25)); if (p <= 0) return; const tP = w0(68) + .02, tS = w1(71) + .08;
  if (glass(c, 90, 930, 900, 370, p, {})) { wt(c, 'Izohlar', 450, 44, { size: 34, weight: 800, align: 'center' });
    const post = E.outB(prog(T, tS, tS + .45)); const skel = (y, col) => { c.fillStyle = col; c.beginPath(); c.arc(70, y + 30, 28, 0, 7); c.fill(); c.fillStyle = 'rgba(255,255,255,.18)'; rr(c, 118, y + 8, 220, 18, 9); c.fill(); rr(c, 118, y + 40, 520, 16, 8); c.fill(); };
    skel(90 + post * 100, '#6b6b6e'); skel(190 + post * 100, '#8a6a10');
    if (post > 0) { c.save(); c.globalAlpha *= clamp(post * 2); const y = 82 + (1 - post) * -20; rr(c, 20, y - 4, 860, 96, 18); c.fillStyle = 'rgba(255,212,38,.14)'; c.fill(); c.fillStyle = yg(c, 40, y, 100, y + 60); c.beginPath(); c.arc(70, y + 44, 28, 0, 7); c.fill(); wt(c, 'siz', 118, y + 24, { size: 28, weight: 800 }); rr(c, 178, y + 8, 104, 30, 15); c.fillStyle = 'rgba(255,255,255,.16)'; c.fill(); wt(c, 'namuna', 230, y + 23, { size: 18, weight: 600, align: 'center', fill: '#cfcfcf' }); wt(c, '+', 118, y + 66, { size: 44, weight: 900, fill: Y1 }); c.restore(); }
    rr(c, 20, 280, 860, 72, 36); c.fillStyle = 'rgba(255,255,255,.10)'; c.fill(); c.fillStyle = yg(c, 40, 280, 90, 350); c.beginPath(); c.arc(62, 316, 24, 0, 7); c.fill();
    const typed = T >= tP && T < tS, q = prog(T, tP, tP + .4); if (typed) { wt(c, '+', 110, 316, { size: 58 * lerp(2.2, 1, E.outB(q)), weight: 900, fill: '#fff' }); const bl = Math.floor(T * 2) % 2 === 0; if (bl) { c.fillStyle = Y1; c.fillRect(140, 292, 4, 48); } c.fillStyle = Y1; c.beginPath(); c.arc(838, 316, 28, 0, 7); c.fill(); c.strokeStyle = BLK; c.lineWidth = 5; c.lineCap = 'round'; c.beginPath(); c.moveTo(838, 330); c.lineTo(838, 304); c.moveTo(826, 316); c.lineTo(838, 303); c.lineTo(850, 316); c.stroke(); }
    else if (T < tP) wt(c, 'Izoh qo‘shing...', 110, 316, { size: 28, weight: 500, fill: 'rgba(255,255,255,.45)' });
    const k = prog(T, tP, tP + .8); if (k > 0) { for (let i = 0; i < 2; i++) { const r2 = clamp(k * 1.3 - i * .25); ring(c, 130, 316, 30 + r2 * 220, 7 * (1 - r2), i ? '#fff' : Y1, (1 - r2) * .85); } glowDot(c, 130, 316, 160 * (1 - k * .5), Y1, .45 * (1 - k)); }
    // pointer
    const tap = tP - .55, mx = lerp(900, 330, E.inOutS(prog(T, tap - .6, tap))), my = lerp(430, 330, E.inOutS(prog(T, tap - .6, tap))), pr = Math.max(0, 1 - Math.abs(T - tap) / .09);
    if (T < tS + .1) { c.save(); c.translate(mx, my); c.scale(1 - pr * .14, 1 - pr * .14); c.fillStyle = '#fff'; c.shadowColor = 'rgba(0,0,0,.6)'; c.shadowBlur = 12; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 38); c.lineTo(10, 29); c.lineTo(19, 44); c.lineTo(26, 40); c.lineTo(17, 26); c.lineTo(30, 25); c.closePath(); c.fill(); c.restore(); }
    gEnd(c); }
}
function cardLink(c, T) {
  const a = w0(74) - .1, b = w1(79) + .1, p = prog(T, a, a + .5) * (1 - prog(T, b, b + .25)); if (p <= 0) return; const tc = T - a;
  if (glass(c, 90, 960, 900, 330, p, {})) { c.save(); c.translate(130, 100); rr(c, -70, -70, 140, 140, 34); c.fillStyle = '#000'; c.fill(); c.strokeStyle = 'rgba(255,255,255,.2)'; c.lineWidth = 2; c.stroke(); c.strokeStyle = Y1; c.lineWidth = 12; c.lineCap = 'round'; c.rotate(-.7); rr(c, -34, -14, 44, 28, 14); c.stroke(); rr(c, -6, -14, 44, 28, 14); c.stroke(); c.restore();
    wt(c, 'silka', 240, 82, { size: 76, weight: 900 }); c.fillStyle = yg(c, 240, 0, 460, 0); rr(c, 242, 128, 190 * E.outC(prog(tc, .25, .7)), 9, 4); c.fill();
    const steps = ['Telegram', 'Darslik', 'Montaj'], pr = E.inOutS(prog(tc, .5, b - a - .2)), y = 250; c.strokeStyle = 'rgba(255,255,255,.18)'; c.lineWidth = 8; c.lineCap = 'round'; c.beginPath(); c.moveTo(130, y); c.lineTo(770, y); c.stroke(); c.strokeStyle = Y1; c.beginPath(); c.moveTo(130, y); c.lineTo(130 + 640 * pr, y); c.stroke();
    steps.forEach((s, i) => { const x = 130 + i * 320, on = pr >= i / 2 - .001; c.fillStyle = on ? Y1 : 'rgba(255,255,255,.25)'; c.beginPath(); c.arc(x, y, on ? 17 : 12, 0, 7); c.fill(); wt(c, s, x, y + 46, { size: 26, weight: 700, align: 'center', fill: on ? '#fff' : 'rgba(255,255,255,.45)' }); }); gEnd(c); }
}
function heroes(c, T) {
  // 1: "?" coin + shockwave at "ishonasizmi?"
  { const a = w0(7), b = w0(8) - .02, p = prog(T, a, a + .5) * (1 - prog(T, b, b + .2)); if (p > 0) { const sw = prog(T, a, a + .7); ring(c, 540, 1110, 90 + sw * 600, 14 * (1 - sw), Y1, 1 - sw); ring(c, 540, 1110, 50 + sw * 380, 6 * (1 - sw), '#fff', .8 * (1 - sw)); coin(c, 540, 1110, 150, p, (T - a) * 5 + .01, IC.q); } }
  // CTA: subscribe button
  { const a = w0(89), b = w0(94) - .38, ck = w0(91) + .2; const p = prog(T, a, a + .45) * (1 - prog(T, b, b + .2)); if (p > 0) { const done = T > ck, pr = Math.max(0, 1 - Math.abs(T - ck) / .09); const s = clamp(pop(prog(T, a, a + .6), 8, 10), 0, 1.08) * (1 - pr * .06); c.save(); c.translate(540, 1140); c.scale(s, s); c.globalAlpha *= p; const w = done ? 660 : 720, h = 150;
      c.shadowColor = 'rgba(0,0,0,.5)'; c.shadowBlur = 40; c.shadowOffsetY = 16; rr(c, -w / 2, -h / 2, w, h, 75); c.fillStyle = done ? '#111' : yg(c, 0, -h / 2, 0, h / 2); c.fill(); c.shadowBlur = 0; if (done) { c.strokeStyle = 'rgba(255,255,255,.2)'; c.lineWidth = 3; c.stroke(); }
      wt(c, done ? 'Obuna bo‘lindi ✓' : 'Obuna bo‘lish', 40, 4, { size: 58, weight: 900, align: 'center', fill: done ? Y1 : BLK }); const bell = done ? Math.sin((T - ck) * 26) * .5 * Math.exp(-(T - ck) * 2.2) : 0; emoji(c, '🔔', -w / 2 + 92, 0, 66, { rot: bell }); c.restore();
      ring(c, 600, 1175, 20 + prog(T, ck, ck + .5) * 170, 5 * (1 - prog(T, ck, ck + .5)), '#fff', 1 - prog(T, ck, ck + .5));
      const cp = E.outC(prog(T, a + .2, ck)); if (T < ck + .5) { c.save(); c.translate(lerp(900, 640, cp), lerp(1420, 1190, cp)); c.scale(1 - pr * .14, 1 - pr * .14); c.fillStyle = '#fff'; c.shadowColor = 'rgba(0,0,0,.6)'; c.shadowBlur = 12; c.beginPath(); c.moveTo(0, 0); c.lineTo(0, 38); c.lineTo(10, 29); c.lineTo(19, 44); c.lineTo(26, 40); c.lineTo(17, 26); c.lineTo(30, 25); c.closePath(); c.fill(); c.restore(); } } }
  // CTA: plus coin
  { const a = w0(94), b = w0(97) - .08, p = prog(T, a, a + .5) * (1 - prog(T, b, b + .2)); if (p > 0) { const q = prog(T, a, a + .8); for (let i = 0; i < 2; i++) { const k = clamp(q * 1.3 - i * .25); ring(c, 540, 1130, 120 + k * 480, 9 * (1 - k), i ? '#fff' : Y1, (1 - k) * .85); }
      coin(c, 540, 1130, 140, p, (T - a) * 4.4 + .01, IC.plus); const r = rng(8); for (let i = 0; i < 20; i++) { const ang = r() * 6.28, sp = 180 + r() * 340, k = E.outC(clamp(q * 1.1)); star4(c, 540 + Math.cos(ang) * sp * k, 1130 + Math.sin(ang) * sp * k, 13 * (1 - k) + 2, ang, i % 3 ? Y1 : '#fff', 1 - k); } } }
  // finale
  { const a = w0(97) - .02, p = prog(T, a, a + .5); if (p > 0) { c.save(); c.globalAlpha *= 1 - prog(T, TOTAL - .3, TOTAL); const sz = 96; letters(c, 'Ko‘rishguncha!', 540, 1135, T - a, { size: sz, step: .028, dur: .45, rise: .4, glow: 0 }); c.fillStyle = yg(c, 200, 0, 880, 0); rr(c, 540 - 320 * E.outC(prog(T, a + .3, a + .9)), 1215, 640 * E.outC(prog(T, a + .3, a + .9)), 9, 4); c.fill(); c.restore(); } }
}
// ---------- frame ----------
async function renderX(T) {
  const vt = videoTime(T), i0 = Math.min(FACE.n - 2, Math.max(0, Math.floor(vt * FPS + 1e-6)));
  imgs[0].src = `frames/${String(i0 + 1).padStart(5, '0')}.jpg`; imgs[1].src = `frames/${String(i0 + 2).padStart(5, '0')}.jpg`; await Promise.all([imgs[0].decode(), imgs[1].decode()]);
  const c = CTX; c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.globalCompositeOperation = 'source-over';
  drawVideo(c, T, vt);
  // readability scrim + vignette
  const g = c.createLinearGradient(0, 880, 0, 1700); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(.5, 'rgba(0,0,0,.30)'); g.addColorStop(1, 'rgba(0,0,0,.52)'); c.fillStyle = g; c.fillRect(0, 880, W, H - 880);
  const v = c.createRadialGradient(540, 960, 650, 540, 960, 1300); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.30)'); c.fillStyle = v; c.fillRect(0, 0, W, H);
  const cm = camAt(T), hh = handheld(T), fp = facePos(T, cm, hh);
  drawIcons(c, T, fp, cm, hh);
  heroes(c, T); cardName(c, T);
  statCard(c, T, w0(13), w1(17) + .1, 60, 985, 420, n => String(n), 'yil', T => Math.min(2, Math.floor(prog(T, w0(13), w0(13) + .5) * 3)), 'tajriba');
  statCard(c, T, w0(20), w1(26), 500, 985, 520, n => n + (n >= 10 ? '+' : ''), 'loyiha', T => Math.round(10 * E.outC(prog(T, w0(20), w0(20) + .6))), 'ustida ishlayapman');
  cardAI(c, T); cardGrow(c, T); cardTG(c, T); cardPlus(c, T); cardLink(c, T);
  drawSubs(c, T);
  // whip streaks
  const wp = whipAt(T); if (wp) { c.save(); c.globalAlpha = .35 * Math.sin(wp.p * Math.PI); c.strokeStyle = '#fff'; c.lineWidth = 3; const r = rng(Math.floor(T * 60)); for (let i = 0; i < 16; i++) { const y = r() * H, x = r() * W, l = 260 + r() * 520; c.beginPath(); c.moveTo(x, y); c.lineTo(x + l, y); c.stroke(); } c.restore(); }
  // flashes (only two): "ishonasizmi?" and the farewell
  [w0(7) + .12, w0(97) - .02].forEach((tf, i) => { const f = 1 - prog(T, tf, tf + .24); if (T >= tf && f > 0) { c.fillStyle = `rgba(255,255,255,${(i ? .45 : .6) * f * f})`; c.fillRect(0, 0, W, H); } });
  const fo = 1 - prog(T, TOTAL - .25, TOTAL); if (fo < 1) { c.fillStyle = `rgba(0,0,0,${1 - fo})`; c.fillRect(0, 0, W, H); }
}
async function initX(words, face, cuts, total) { WD = words; FACE = face; CUTS = cuts.filter(t => t > 10); TOTAL = total; CNV = document.getElementById('c'); CNV.width = W; CNV.height = H; CTX = CNV.getContext('2d'); buildCamera(); ICON_LIST = ICONS(); }
window.initX = initX; window.renderX = renderX;
