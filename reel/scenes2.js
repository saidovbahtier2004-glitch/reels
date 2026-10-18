function fitText(c, s, maxW, size, o = {}) { const w = measure(c, s, { ...o, size }); return w > maxW ? size * maxW / w : size; }

// ===== Scene 5: WANT — fast motion-design montage =====
const TILE_T = [0, .5, .92, 1.28, 1.6, 1.9, 2.2]; // tile boundaries (speed ramp: shorter and shorter)
function tileArt(k, c, t) { // draws in 800x800 local box
  const R = 800;
  if (k === 0) { c.fillStyle = linGrad(c, 0, 0, R, R, [[0, '#2a1bd6'], [1, '#6a2bd9']]); c.fillRect(0, 0, R, R);
    for (let i = 0; i < 6; i++) { const p = E.outC(prog(t, i * .04, i * .04 + .3)); c.fillStyle = `rgba(255,255,255,${.1 + i * .02})`; c.fillRect(0, 60 + i * 120, R * p, 70); }
    T(c, 'MOTION', R / 2, R / 2, { size: 190, glow: 30, sx: 1 + t * .08 }); }
  else if (k === 1) { c.fillStyle = '#0b1230'; c.fillRect(0, 0, R, R); for (let i = 0; i < 9; i++) { const r = ((t * 260 + i * 70) % 630) + 20; ring(c, R / 2, R / 2, r, 10, i % 2 ? C.cyan : C.vio, 1 - r / 650); } glowDot(c, R / 2, R / 2, 260, C.blue, .6); }
  else if (k === 2) { c.fillStyle = linGrad(c, 0, 0, 0, R, [[0, '#14081f'], [1, '#2a0f3a']]); c.fillRect(0, 0, R, R);
    const P = [[-1, -1, -1], [1, -1, -1], [1, 1, -1], [-1, 1, -1], [-1, -1, 1], [1, -1, 1], [1, 1, 1], [-1, 1, 1]], a = t * 2.2, b = t * 1.5;
    const pr = P.map(([x, y, z]) => { let x1 = x * Math.cos(a) - z * Math.sin(a), z1 = x * Math.sin(a) + z * Math.cos(a), y1 = y * Math.cos(b) - z1 * Math.sin(b), z2 = y * Math.sin(b) + z1 * Math.cos(b); const f = 520 / (3.4 - z2 * .7); return [R / 2 + x1 * f * .62, R / 2 + y1 * f * .62]; });
    c.strokeStyle = C.org; c.lineWidth = 9; c.shadowColor = C.org; c.shadowBlur = 22; c.beginPath(); [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]].forEach(([i, j]) => { c.moveTo(pr[i][0], pr[i][1]); c.lineTo(pr[j][0], pr[j][1]); }); c.stroke(); c.shadowBlur = 0; }
  else if (k === 3) { c.fillStyle = '#071a1a'; c.fillRect(0, 0, R, R); for (let i = 0; i < 7; i++) { const h = (160 + i * 60) * E.outB(prog(t, i * .035, i * .035 + .3)); c.fillStyle = linGrad(c, 0, R - h, 0, R, [[0, C.mint], [1, '#0e7c66']]); rr(c, 70 + i * 100, R - 70 - h, 72, h, 14); c.fill(); }
    c.strokeStyle = '#fff'; c.lineWidth = 8; c.lineCap = 'round'; c.beginPath(); for (let i = 0; i < 7 * clamp(t * 4); i++) { const h = 160 + i * 60; i ? c.lineTo(106 + i * 100, R - 120 - h) : c.moveTo(106, R - 120 - h); } c.stroke(); }
  else if (k === 4) { c.fillStyle = linGrad(c, 0, 0, R, R, [[0, '#ff7a45'], [1, '#d6245f']]); c.fillRect(0, 0, R, R);
    for (let i = 0; i < 5; i++) glowDot(c, R / 2 + Math.cos(t * 2 + i * 1.3) * 250, R / 2 + Math.sin(t * 2.3 + i * 2.1) * 250, 230, i % 2 ? '#ffd2a8' : '#7b2cff', .85);
    T(c, 'FLOW', R / 2, R / 2, { size: 200, glow: 20, glowC: 'rgba(0,0,0,.4)' }); }
  else { c.fillStyle = '#080c1c'; c.fillRect(0, 0, R, R); for (let i = 0; i < 8; i++) for (let j = 0; j < 8; j++) { const s = .5 + .5 * Math.sin(t * 5 - (i + j) * .55); c.fillStyle = rgba(i % 2 ? C.blue : C.vio, .35 + s * .6); rr(c, 40 + i * 90 + (1 - s) * 18, 40 + j * 90 + (1 - s) * 18, 74 * (.5 + s * .5), 74 * (.5 + s * .5), 16); c.fill(); } }
}
function sceneWant(c, t, S, u) {
  const tM = u('motion'), tY = u('yas');
  const [sx, sy] = shakeAt(t, tY, 16, .4);
  c.save(); cam(c, 1 + .02 * prog(t, 0, S.dur), 540, 900, 0, sx, sy);
  backdrop(c, t, { c1: C.vio, c2: C.org, px: t * 60 });
  // tiles
  const bx = 140, by = 170, bs = 800;
  let k = 0; for (let i = 0; i < 6; i++) if (t >= .1 + TILE_T[i]) k = i; const tt = t - .1 - TILE_T[k];
  const dur = TILE_T[k + 1] - TILE_T[k];
  if (t > .08) {
    const inP = E.outE(prog(tt, 0, .16)), out = k === 5 ? 0 : E.inQ(prog(tt, dur - .1, dur));
    const sc = lerp(1.3, 1, inP) * (1 + out * .08) * (1 + (k === 5 ? .04 * tt : 0)), off = (1 - inP) * 160 * (k % 2 ? 1 : -1);
    c.save(); c.translate(bx + bs / 2 + off, by + bs / 2); c.scale(sc, sc); c.translate(-bs / 2, -bs / 2); c.globalAlpha = clamp(inP * 2) * (1 - out);
    c.shadowColor = 'rgba(0,0,0,.6)'; c.shadowBlur = 50; rr(c, 0, 0, bs, bs, 56); c.fillStyle = '#000'; c.fill(); c.shadowBlur = 0;
    c.save(); rr(c, 0, 0, bs, bs, 56); c.clip(); tileArt(k, c, tt + .05); c.restore();
    if (inP < .9) { c.save(); c.globalCompositeOperation = 'lighter'; c.globalAlpha = (1 - inP) * .5; c.restore(); }
    c.restore();
    // speed streaks on cut
    if (tt < .14) { c.save(); c.globalAlpha = (1 - tt / .14) * .5; c.strokeStyle = '#fff'; c.lineWidth = 3; const r = rng(k * 9 + 3); for (let i = 0; i < 18; i++) { const y = r() * H, x = r() * W, l = 250 + r() * 400; c.beginPath(); c.moveTo(x, y); c.lineTo(x + (k % 2 ? -l : l), y); c.stroke(); } c.restore(); }
  }
  // typography
  const p0 = E.outC(prog(t, .12, .55)); T(c, 'Siz ham xuddi shunday', 540, 1075, { size: 58, font: SERIF, italic: true, weight: 400, fill: '#c7d2ee', alpha: p0 });
  const pm = pop(prog(t, tM - .05, tM + .7), 8, 11); if (pm > 0) {
    const sz = fitText(c, 'motion videolar', 930, 112); c.save(); c.translate(540, 1215); c.scale(clamp(pm, 0, 1.08), clamp(pm, 0, 1.08)); c.globalAlpha = clamp(pm * 2);
    const w = measure(c, 'motion videolar', { size: sz }); const g = linGrad(c, -w / 2, 0, w / 2, 0, [[0, '#7db2ff'], [.55, '#b48cff'], [1, '#ff9a5a']]);
    T(c, 'motion videolar', 0, 0, { size: sz, fill: g, glow: 34, glowC: 'rgba(130,140,255,.7)' });
    c.fillStyle = linGrad(c, -w / 2, 0, w / 2, 0, [[0, C.blue], [1, C.org]]); rr(c, -w / 2 * E.outE(prog(t, tM + .2, tM + .6)), sz * .58, w * E.outE(prog(t, tM + .2, tM + .6)), 7, 4); c.fill(); c.restore();
    emoji(c, '🔥', 960, 1215, 80, { s: pop(prog(t, tM + .25, tM + 1)), rot: .2, alpha: clamp((t - tM - .25) * 7) });
  }
  const py = prog(t, tY - .02, tY + .5); if (py > 0) {
    const sz = fitText(c, 'yasamoqchimisiz?', 900, 100); const s = lerp(1.35, 1, E.outE(py));
    const fl = 1 - prog(t, tY, tY + .18); if (fl > 0) { c.fillStyle = `rgba(255,255,255,${.35 * fl})`; c.fillRect(0, 0, W, H); }
    Tghost(c, 'yasamoqchimisiz?', 540, 1385, { size: sz, s, alpha: clamp(py * 3), fill: '#fff', glow: 28, glowC: 'rgba(255,138,61,.7)' }, (1 - py) * 120, 0, 6);
    ring(c, 540, 1385, 40 + py * 700, 6 * (1 - py), C.org, (1 - py) * .8);
  }
  c.restore();
}

// ===== phone helpers =====
function phoneBody(c, PW, PH) {
  c.shadowColor = 'rgba(0,0,0,.65)'; c.shadowBlur = 90; c.shadowOffsetY = 40; rr(c, 0, 0, PW, PH, 112); c.fillStyle = '#0a0a0c'; c.fill(); c.shadowBlur = 0; c.shadowOffsetY = 0;
  rr(c, 0, 0, PW, PH, 112); c.strokeStyle = linGrad(c, 0, 0, PW, PH, [[0, '#6c7280'], [.5, '#262a33'], [1, '#5a606d']]); c.lineWidth = 7; c.stroke();
  rr(c, 12, 12, PW - 24, PH - 24, 100); c.fillStyle = '#000'; c.fill();
}
function tgCard(c, x, y, w, h, n, p) { // video-lesson cover bubble
  c.save(); c.translate(x + w / 2, y + h / 2); const s = clamp(pop(p, 8, 10), 0, 1.06); c.scale(s, s); c.globalAlpha = clamp(p * 3); c.translate(-w / 2, -h / 2);
  rr(c, 0, 0, w, h, 28); c.fillStyle = '#182533'; c.fill();
  c.save(); rr(c, 8, 8, w - 16, h - 78, 22); c.clip(); const cols = [[C.blue, C.vio], [C.org, C.pink], [C.cyan, C.mint]][n % 3];
  c.fillStyle = linGrad(c, 0, 0, w, h, [[0, cols[0]], [1, cols[1]]]); c.fillRect(0, 0, w, h); glowDot(c, w * .7, h * .25, w * .6, '#fff', .22);
  T(c, `${n + 1}-dars`, w / 2, (h - 78) / 2 - 20, { size: 58, weight: 900, shadow: 14 });
  c.restore();
  // play button
  c.fillStyle = 'rgba(0,0,0,.45)'; c.beginPath(); c.arc(w / 2, (h - 78) / 2 + 60, 38, 0, 7); c.fill(); c.fillStyle = '#fff'; c.beginPath(); c.moveTo(w / 2 - 12, (h - 78) / 2 + 40); c.lineTo(w / 2 + 20, (h - 78) / 2 + 60); c.lineTo(w / 2 - 12, (h - 78) / 2 + 80); c.fill();
  c.fillStyle = 'rgba(255,255,255,.28)'; rr(c, 20, h - 56, w * .6, 14, 7); c.fill(); rr(c, 20, h - 30, w * .35, 12, 6); c.fill();
  c.restore();
}

// ===== Scene 6: TELEGRAM =====
function sceneTg(c, t, S, u) {
  const tTg = u('tg'), tV = u('video'), tL = u('lesson');
  const rise = E.outC(prog(t, tTg - .85, tTg + .35));
  const z = lerp(1.0, 1.1, E.inOutS(prog(t, 0, S.dur))), tilt = lerp(-.07, .0, E.outC(prog(t, 0, 1.6))) + Math.sin(t * .8) * .006;
  c.save(); cam(c, z, 540, 1000, 0, 0, 0);
  backdrop(c, t, { c1: '#2aa6e0', c2: C.vio, px: 0, glow: 1.2 });
  // big logo pop (cinematic) then moves into the phone header
  const PW = 800, PH = 1720, px = 140, py = lerp(1900, 470, rise);
  c.save(); c.translate(px + PW / 2, py + PH / 2); c.rotate(tilt); c.translate(-PW / 2, -PH / 2);
  phoneBody(c, PW, PH);
  const X = 22, Y = 22, SW = PW - 44, SH = PH - 44; c.save(); rr(c, X, Y, SW, SH, 92); c.clip();
  c.fillStyle = '#0e1621'; c.fillRect(X, Y, SW, SH);
  // chat wallpaper
  c.fillStyle = 'rgba(40,80,120,.10)'; for (let i = 0; i < 14; i++) for (let j = 0; j < 30; j++) { c.beginPath(); c.arc(X + 30 + i * 62 + (j % 2) * 31, Y + 190 + j * 62, 3, 0, 7); c.fill(); }
  // header
  c.fillStyle = '#17212b'; c.fillRect(X, Y, SW, 178);
  T(c, '9:41', X + 70, Y + 42, { size: 28, weight: 700, align: 'left', fill: '#fff' });
  rr(c, X + SW / 2 - 70, Y + 14, 140, 38, 19); c.fillStyle = '#000'; c.fill();
  c.strokeStyle = '#6ab3f3'; c.lineWidth = 6; c.lineCap = 'round'; c.beginPath(); c.moveTo(X + 50, Y + 113); c.lineTo(X + 32, Y + 130); c.lineTo(X + 50, Y + 147); c.stroke();
  const hp = E.outC(prog(t, tTg + .5, tTg + 1.1)); const hv = (1 - hp);
  if (hp > 0) { c.save(); c.globalAlpha = hp; tgLogo(c, X + 130, Y + 130, 36); c.restore(); }
  T(c, 'Video darslik', X + 190, Y + 118, { size: 36, weight: 700, align: 'left', fill: '#fff', alpha: hp });
  T(c, 'yopiq kanal', X + 190, Y + 156, { size: 26, weight: 500, align: 'left', fill: '#6c7f93', alpha: hp * (.6 + .4 * prog(t, u('closed') - .05, u('closed') + .3)) });
  // lesson cards
  const cw = SW - 90, ch = 420;
  tgCard(c, X + 28, Y + 230, cw, ch, 0, prog(t, tV, tV + .8));
  tgCard(c, X + 28, Y + 230 + ch + 36, cw, ch, 1, prog(t, tL - .1, tL + .8));
  tgCard(c, X + 28, Y + 230 + (ch + 36) * 2, cw, ch, 2, prog(t, tL + .45, tL + 1.25));
  // glass reflection
  c.globalCompositeOperation = 'lighter'; c.fillStyle = linGrad(c, X, Y, X + SW * .9, Y + SH * .5, [[0, 'rgba(255,255,255,.10)'], [.45, 'rgba(255,255,255,.02)'], [.46, 'rgba(255,255,255,0)'], [1, 'rgba(255,255,255,0)']]); c.fillRect(X, Y, SW, SH);
  c.restore();
  c.restore();
  // soft notification pill
  const pn = pop(prog(t, tV - .05, tV + .6)); if (pn > 0 && t < tV + 1.9) { const o = 1 - prog(t, tV + 1.5, tV + 1.9); c.save(); c.globalAlpha = clamp(pn) * o; c.translate(540, 385 + (1 - clamp(pn, 0, 1)) * -120);
    rr(c, -330, -54, 660, 108, 40); c.fillStyle = 'rgba(28,36,48,.95)'; c.fill(); c.strokeStyle = 'rgba(255,255,255,.12)'; c.lineWidth = 2; c.stroke(); tgLogo(c, -270, 0, 34); T(c, 'Telegram', -210, -16, { size: 30, weight: 700, align: 'left' }); T(c, 'Yangi video darslik', -210, 22, { size: 28, weight: 500, align: 'left', fill: '#9fb0c4' }); c.restore(); }
  // big Telegram logo burst at the word
  const pl = prog(t, tTg - .05, tTg + .9); if (pl > 0 && pl < 1) { const s = lerp(.2, 4.2, E.outC(pl)); c.save(); c.globalAlpha = Math.sin(pl * Math.PI) * .95; tgLogo(c, 540, 860 - 120 * E.inOutS(pl), 100 * s * .7); ring(c, 540, 860, 60 + pl * 800, 10 * (1 - pl), '#37aee2', 1 - pl); c.restore(); }
  c.restore();
}

// ===== finger =====
function finger(c, x, y, press, a = 1) { // fingertip at (x,y); press 0..1 scales/shadow
  c.save(); c.globalAlpha *= a; c.translate(x, y); c.rotate(-.42); const s = 1 - press * .06;
  c.scale(s, s); c.shadowColor = 'rgba(0,0,0,.45)'; c.shadowBlur = 40; c.shadowOffsetY = 18 + press * -8;
  const g = linGrad(c, -50, 0, 50, 0, [[0, '#d9a07a'], [.5, '#f1bd98'], [1, '#d4977a']]);
  c.fillStyle = g; rr(c, -46, -20, 92, 520, 46); c.fill(); c.shadowBlur = 0;
  c.fillStyle = 'rgba(255,230,210,.55)'; rr(c, -24, 8, 48, 62, 24); c.fill(); // nail hint
  c.restore();
}
const KEYS = [['[', ']', '{', '}', '#', '%', '^', '*', '+', '='], ['_', '\\', '|', '~', '<', '>', '€', '£', '¥', '•']];
function keyboard(c, y0, pressKey, pressA) {
  c.fillStyle = '#1b1b1d'; c.fillRect(0, y0, W, H - y0 + 20);
  const row = (ys, keys, x0, kw, gap, kh = 108) => keys.forEach((k, i) => { const x = x0 + i * (kw + gap); const down = pressKey === k && pressA > 0; rr(c, x, ys, kw, kh, 14); c.fillStyle = down ? '#7a7a7e' : '#4b4b4f'; c.fill(); T(c, k, x + kw / 2, ys + kh / 2 - 2, { size: 46, weight: 500, fill: '#fff' }); });
  row(y0 + 22, KEYS[0], 14, 94, 12); row(y0 + 152, KEYS[1], 14, 94, 12);
  rr(c, 14, y0 + 282, 150, 108, 14); c.fillStyle = '#343438'; c.fill(); T(c, '123', 89, y0 + 334, { size: 38, weight: 500 });
  row(y0 + 282, ['.', ',', '?', '!', '\''], 186, 124, 12);
  rr(c, 936, y0 + 282, 130, 108, 14); c.fillStyle = '#343438'; c.fill(); T(c, '⌫', 1001, y0 + 334, { size: 44, weight: 500 });
  rr(c, 14, y0 + 412, 150, 108, 14); c.fillStyle = '#343438'; c.fill(); T(c, 'ABC', 89, y0 + 466, { size: 38, weight: 500 });
  rr(c, 176, y0 + 412, 560, 108, 14); c.fillStyle = '#4b4b4f'; c.fill(); T(c, 'bo‘sh joy', 456, y0 + 466, { size: 36, weight: 500, fill: '#ddd' });
  rr(c, 748, y0 + 412, 318, 108, 14); c.fillStyle = '#343438'; c.fill(); T(c, 'yuborish', 907, y0 + 466, { size: 36, weight: 500 });
  rr(c, 390, y0 + 574, 300, 9, 5); c.fillStyle = '#eee'; c.fill();
}
const KX = i => 14 + i * 106 + 47; // key centre x for row 1

// ===== Scene 7: "+" COMMENT =====
function scenePlus(c, t, S, u) {
  const tOpen = u('open') - .05, tC = u('comment'), tP = u('plus') + .1, tSend = u('send') + .25;
  const tTap = tP - 1.05, kbP = E.outC(prog(t, tTap + .05, tTap + .45)), tPress = tP - .06;
  // camera plan
  const zA = lerp(1, 1.12, E.inOutS(prog(t, tOpen + .3, tTap))), approach = E.inOutS(prog(t, tTap - .5, tTap + .3)), toKb = E.inOutS(prog(t, tTap + .25, tTap + .6)), back = E.inOutS(prog(t, tP + .45, tP + 1.2));
  let z = lerp(lerp(1, 1.28, approach), 1.18, toKb); z = lerp(z, 1.0, back); if (t < tTap - .5) z = zA;
  const fy = lerp(lerp(1500, 1740, approach), 1130, toKb), fy2 = lerp(fy, 960, back), fx = lerp(540, 500, toKb) * (1 - back) + 540 * back;
  const [sx, sy] = shakeAt(t, tP, 8, .3);
  c.save(); cam(c, z, fx, fy2, 0, sx, sy);
  // dimmed reel behind
  c.fillStyle = linGrad(c, 0, 0, W, H, [[0, '#1a2250'], [.6, '#2b1646'], [1, '#101226']]); c.fillRect(-100, -100, W + 200, H + 200); glowDot(c, 300, 500, 700, C.blue, .35); glowDot(c, 800, 900, 700, C.vio, .3);
  // reel UI hint: side actions + caption bars, comment icon pulses right before the sheet opens
  { const pc = 1 + .25 * Math.max(0, 1 - Math.abs(t - (tOpen - .15)) / .2);
    ['♥', 'bubble', '➤'].forEach((ic, i) => { const x = 985, y = 1060 + i * 150; c.save(); c.translate(x, y); if (i === 1) c.scale(pc, pc);
      if (ic === 'bubble') { rr(c, -34, -30, 68, 52, 18); c.fillStyle = '#fff'; c.fill(); c.beginPath(); c.moveTo(-14, 20); c.lineTo(-24, 40); c.lineTo(4, 22); c.fill(); }
      else T(c, ic, 0, 0, { size: 66, weight: 700 }); c.restore(); });
    c.fillStyle = 'rgba(255,255,255,.55)'; rr(c, 60, 1500, 330, 24, 12); c.fill(); c.fillStyle = 'rgba(255,255,255,.3)'; rr(c, 60, 1550, 560, 20, 10); c.fill(); rr(c, 60, 1590, 420, 20, 10); c.fill();
    c.fillStyle = linGrad(c, 60, 1420, 120, 1480, [[0, C.blue], [1, C.vio]]); c.beginPath(); c.arc(95, 1440, 34, 0, 7); c.fill(); }
  T(c, '9:41', 110, 64, { size: 34, weight: 700, align: 'left' }); rr(c, 900, 50, 56, 28, 8); c.strokeStyle = '#fff'; c.lineWidth = 3; c.stroke(); c.fillStyle = '#fff'; rr(c, 905, 55, 40, 18, 5); c.fill();
  c.fillStyle = 'rgba(0,0,0,.55)'; c.fillRect(-100, -100, W + 200, H + 200);
  // sheet
  const sheetIn = E.outC(prog(t, tOpen, tOpen + .6)), kbUp = kbP;
  const top = lerp(lerp(1920, 520, sheetIn), 540, 0) ; const sheetTop = lerp(top, 540, kbUp);
  c.save(); rr(c, 0, sheetTop, W, H + 400, 44); c.fillStyle = '#1c1c1e'; c.fill(); rr(c, W / 2 - 50, sheetTop + 18, 100, 9, 5); c.fillStyle = '#58585c'; c.fill();
  T(c, 'Izohlar', W / 2, sheetTop + 82, { size: 42, weight: 700 });
  // skeleton comments
  const posted = E.outB(prog(t, tSend + .05, tSend + .55));
  for (let i = 0; i < 4; i++) {
    const y = sheetTop + 180 + i * 150 + posted * 150; if (y > 1120 && kbUp > .5) continue;
    const a = E.outC(prog(t, tOpen + .25 + i * .1, tOpen + .65 + i * .1)); c.save(); c.globalAlpha = a;
    c.fillStyle = linGrad(c, 40, y, 120, y + 80, [[0, ['#5a6bff', '#ff8a3d', '#34d399', '#ff4d8d'][i]], [1, '#2b2f55']]); c.beginPath(); c.arc(84, y + 38, 38, 0, 7); c.fill();
    c.fillStyle = 'rgba(255,255,255,.22)'; rr(c, 150, y + 6, 200 + i * 20, 22, 11); c.fill(); c.fillStyle = 'rgba(255,255,255,.12)'; rr(c, 150, y + 44, 600 - i * 40, 22, 11); c.fill(); rr(c, 150, y + 80, 380 + i * 30, 22, 11); c.fill(); c.restore();
  }
  // posted comment row (illustrative sample, labeled)
  if (posted > 0) { const y = sheetTop + 180 + (1 - posted) * -40; c.save(); c.globalAlpha = clamp(posted * 2);
    const hl = 1 - prog(t, tSend + .1, tSend + 1.3); rr(c, 14, y - 14, W - 28, 130, 22); c.fillStyle = `rgba(79,140,255,${.18 * hl})`; c.fill();
    c.fillStyle = linGrad(c, 40, y, 120, y + 80, [[0, C.blue], [1, C.vio]]); c.beginPath(); c.arc(84, y + 38, 38, 0, 7); c.fill(); T(c, 'siz', 150, y + 18, { size: 32, weight: 700, align: 'left' });
    rr(c, 232, y + 2, 118, 34, 17); c.fillStyle = 'rgba(255,255,255,.14)'; c.fill(); T(c, 'namuna', 291, y + 20, { size: 22, weight: 600, fill: '#cbd5ff' });
    T(c, '+', 150, y + 80, { size: 56, weight: 800, align: 'left', fill: '#fff', glow: 16 * hl, glowC: C.cyan }); c.restore(); }
  c.restore();
  // input bar
  const barY = lerp(1700, 1020, kbUp), barA = prog(t, tOpen + .3, tOpen + .7);
  c.save(); c.globalAlpha = barA; c.fillStyle = '#1c1c1e'; c.fillRect(0, barY - 30, W, 170); c.fillStyle = 'rgba(255,255,255,.08)'; c.fillRect(0, barY - 30, W, 2);
  c.fillStyle = linGrad(c, 30, barY, 110, barY + 80, [[0, C.blue], [1, C.vio]]); c.beginPath(); c.arc(80, barY + 55, 38, 0, 7); c.fill();
  rr(c, 140, barY + 5, 800, 100, 50); c.fillStyle = '#2c2c2e'; c.fill(); const focus = prog(t, tTap, tTap + .1); c.strokeStyle = rgba(C.blue, .9 * focus); c.lineWidth = 3; c.stroke();
  const typed = t >= tP && t < tSend, pp = prog(t, tP, tP + .55), flyG = 1 - prog(t, tP, tP + 1.2);
  if (!typed) T(c, 'Izoh qo‘shing...', 190, barY + 56, { size: 36, weight: 400, align: 'left', fill: '#8e8e93', alpha: t < tP ? 1 : 0 });
  if (typed) {
    const sPlus = lerp(2.4, 1, E.outB(clamp(pp * 1.4))) ; T(c, '+', 195, barY + 54, { size: 60, weight: 700, align: 'left', fill: '#fff', s: sPlus, glow: 30 * flyG, glowC: 'rgba(120,200,255,.95)' });
    const cx = 232; if (Math.floor(t * 2) % 2 === 0) { c.fillStyle = C.blue; c.fillRect(cx + 4, barY + 28, 4, 56); }
    glowDot(c, 213, barY + 54, 180 * (1 - pp * .4), C.cyan, .5 * flyG);
  } else if (t >= tTap && t < tP && Math.floor((t - tTap) * 2) % 2 === 0) { c.fillStyle = C.blue; c.fillRect(190, barY + 28, 4, 56); }
  // send arrow
  const sA = typed ? 1 : 0; rr(c, 952, barY + 5, 100, 100, 50); c.fillStyle = typed ? C.blue : 'transparent'; if (typed) c.fill();
  if (typed) { c.strokeStyle = '#fff'; c.lineWidth = 7; c.lineCap = 'round'; c.beginPath(); c.moveTo(1002, barY + 78); c.lineTo(1002, barY + 34); c.moveTo(982, barY + 52); c.lineTo(1002, barY + 32); c.lineTo(1022, barY + 52); c.stroke(); }
  c.restore();
  // keyboard
  if (kbUp > 0) { c.save(); c.translate(0, (1 - kbUp) * 760); const y0 = 1160; keyboard(c, y0, t >= tPress && t < tP + .18 ? '+' : null, 1);
    // iOS key preview bubble
    if (t >= tPress && t < tP + .2) { const bx = KX(8), by = y0 + 22 - 130; c.save(); c.shadowColor = 'rgba(0,0,0,.5)'; c.shadowBlur = 30; rr(c, bx - 62, by, 124, 168, 26); c.fillStyle = '#5a5a5e'; c.fill(); c.shadowBlur = 0; T(c, '+', bx, by + 74, { size: 100, weight: 400 }); c.restore(); }
    c.restore(); }
  // ripples around the typed +
  if (t >= tP) { const p = prog(t, tP, tP + 1.0); for (let i = 0; i < 2; i++) { const q = clamp(p * 1.3 - i * .25); ring(c, 214, barY + 54, 40 + q * 260, 8 * (1 - q), i ? C.cyan : '#fff', (1 - q) * .8); }
    const r = rng(5); for (let i = 0; i < 18; i++) { const ang = r() * 6.28, sp = 140 + r() * 260, q = E.outC(clamp(p * 1.1)); glowDot(c, 214 + Math.cos(ang) * sp * q, barY + 54 + Math.sin(ang) * sp * q, 14 * (1 - q) + 2, i % 3 ? C.cyan : C.org, (1 - q)); } }
  // finger
  const fTap = prog(t, tTap - .55, tTap), fToKey = E.inOutS(prog(t, tTap + .15, tPress)), fToSend = E.inOutS(prog(t, tP + .5, tSend - .03)), fOut = E.inQ(prog(t, tSend + .3, tSend + .75));
  const f0 = [1150, 2100], tapPos = [520, barY0(1700)], keyPos = [KX(8), 1160 + 22 + 54], sendPos = [1002, 1020 + 55];
  function barY0(v) { return v + 55; }
  let fx2, fy3;
  if (t < tTap + .15) { const q = E.outC(fTap); fx2 = lerp(f0[0], tapPos[0], q); fy3 = lerp(f0[1], tapPos[1], q); }
  else if (t < tP + .3) { const q = fToKey; fx2 = lerp(tapPos[0], keyPos[0], q); fy3 = lerp(tapPos[1] + 0, keyPos[1], q) + (1 - kbUp) * 0; }
  else { const q = fToSend; fx2 = lerp(keyPos[0], sendPos[0], q); fy3 = lerp(keyPos[1], sendPos[1], q); }
  const pr = Math.max(Math.max(0, 1 - Math.abs(t - (tTap + .02)) / .08), Math.max(0, 1 - Math.abs(t - tPress - .06) / .09), Math.max(0, 1 - Math.abs(t - (tSend - .02)) / .08));
  if (t > tTap - .6 && t < tSend + .8) { const off = fOut * 700; finger(c, fx2 + off * .5, fy3 + off, pr, 1); }
  // tap ripples
  [[tTap + .02, tapPos], [tSend - .02, sendPos]].forEach(([tt, pos]) => { const q = prog(t, tt, tt + .45); if (q > 0 && q < 1) ring(c, pos[0], pos[1], 20 + q * 90, 5 * (1 - q), '#fff', (1 - q) * .8); });
  c.restore();
  // big instruction text (screen-space)
  const tb = tP + .7, pb = pop(prog(t, tb, tb + .8), 8, 10);
  if (pb > 0) {
    c.save(); c.translate(540, 360); c.scale(clamp(pb, 0, 1.06), clamp(pb, 0, 1.06)); c.globalAlpha = clamp(pb * 2) * (1 - prog(t, S.dur - .3, S.dur));
    c.fillStyle = 'rgba(5,7,13,.0)';
    T(c, 'Kommentariyaga', 0, -75, { size: fitText(c, 'Kommentariyaga', 930, 118), glow: 30, glowC: 'rgba(0,0,0,.8)', shadow: 20 });
    const w1 = measure(c, '+', { size: 150 }), w2 = measure(c, ' qoldiring!', { size: 100 }), tot = w1 + w2 + 24;
    T(c, '+', -tot / 2 + w1 / 2, 60, { size: 170, fill: C.org, glow: 50, glowC: 'rgba(255,138,61,.9)', rot: .06 * Math.sin(t * 6) });
    T(c, 'qoldiring!', -tot / 2 + w1 + 24 + measure(c, 'qoldiring!', { size: 100 }) / 2, 62, { size: 100, glow: 20, glowC: 'rgba(0,0,0,.8)', shadow: 18 }); c.restore();
  }
}
