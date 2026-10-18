// 3D-looking chain link (rotating about Y, extruded layers)
function linkIcon(c, x, y, size, ang, alpha = 1) {
  c.save(); c.translate(x, y); c.globalAlpha *= alpha; c.rotate(-.7);
  const cs = Math.cos(ang), depth = 14;
  const ringDraw = (ox, col, col2, lw) => { c.save(); c.translate(ox, 0); c.scale(Math.max(.18, Math.abs(cs)), 1); rr(c, -size * .62, -size * .27, size * 1.24, size * .54, size * .27); c.lineWidth = lw; c.strokeStyle = linGrad(c, -size * .6, -size * .3, size * .6, size * .3, [[0, col], [1, col2]]); c.stroke(); c.restore(); };
  for (let d = depth; d >= 0; d--) { const k = d / depth; c.save(); c.translate(Math.sin(ang) * d * 1.2, d * .9); c.globalAlpha *= .95; ringDraw(-size * .3, k > 0 ? '#1d4ed8' : '#7db2ff', k > 0 ? '#1e3a8a' : '#b48cff', size * .17); ringDraw(size * .3, k > 0 ? '#9a3412' : '#ffb27a', k > 0 ? '#7c2d12' : '#ff6a3d', size * .17); c.restore(); }
  c.restore();
}
function miniTimeline(c, x, y, w, t, a) {
  c.save(); c.globalAlpha *= a; rr(c, x, y, w, 330, 28); c.fillStyle = 'rgba(8,12,26,.94)'; c.fill(); c.strokeStyle = 'rgba(120,160,255,.3)'; c.lineWidth = 2; c.stroke();
  const cols = [C.blue, C.vio, C.org], r = rng(4);
  for (let i = 0; i < 3; i++) { let cx = x + 24; for (let j = 0; j < 4; j++) { const ww = (w - 48) / 4 * (.8 + r() * .18), p = E.outC(prog(t, i * .18 + j * .1, i * .18 + j * .1 + .35)); if (p > 0) { rr(c, cx, y + 36 + i * 90, ww * p, 68, 14); c.fillStyle = rgba(cols[i], .9); c.fill(); } cx += (w - 48) / 4; } }
  const px = x + 24 + (w - 48) * prog(t, .2, 1.6); c.strokeStyle = '#fff'; c.lineWidth = 4; c.beginPath(); c.moveTo(px, y + 10); c.lineTo(px, y + 310); c.stroke(); c.restore();
}

// ===== Scene 8: LINK + RESULT =====
function sceneLink(c, t, S, u) {
  const tMe = u('me'), tL = u('link'), tTg = u('tg'), tMo = u('motion'), tLn = u('learn');
  // each phase has its own camera move
  const ph = t < tTg - .15 ? 0 : t < tMo - .15 ? 1 : t < tLn - .15 ? 2 : 3;
  const [sx, sy] = shakeAt(t, tL, 10, .3);
  c.save();
  let z = 1, fx = 540, fy = 960, rot = 0;
  if (ph === 0) { z = lerp(1.12, 1.0, E.outC(prog(t, 0, 1.5))); rot = .02 * (1 - E.outC(prog(t, 0, 1.2))); }
  if (ph === 1) { z = lerp(1.0, 1.1, prog(t, tTg, tMo)); fy = lerp(960, 1000, prog(t, tTg, tMo)); }
  if (ph === 2) { z = lerp(1.3, 1.0, E.outC(prog(t, tMo - .15, tMo + 1.2))); }
  if (ph === 3) { z = lerp(.88, 1.04, E.outC(prog(t, tLn - .15, tLn + 1.3))); rot = -.012; }
  cam(c, z, fx, fy, rot, sx, sy);
  backdrop(c, t, { c1: C.cyan, c2: C.org, px: t * 30, glow: 1 });
  // phase 0: comment bubble -> paper plane flies away, link icon appears
  if (ph === 0) {
    const fo = prog(t, tTg - .3, tTg - .05); c.save(); c.globalAlpha = 1 - fo; c.translate(540, 960); c.scale(1 + fo * .25, 1 + fo * .25); c.translate(-540, -960);
    const pb = prog(t, 0, .7); const bubble = (1 - E.inQ(prog(t, .3, .75)));
    if (bubble > 0) { c.save(); c.translate(300 + E.inOutS(prog(t, .3, .9)) * 400, 640 - Math.sin(prog(t, .3, .9) * Math.PI) * 140); c.scale(bubble, bubble); c.globalAlpha = bubble; rr(c, -110, -80, 220, 150, 40); c.fillStyle = C.blue; c.fill(); c.beginPath(); c.moveTo(-40, 68); c.lineTo(-70, 120); c.lineTo(0, 70); c.fill(); T(c, '+', 0, -6, { size: 120, weight: 800 }); c.restore(); }
    // trail
    if (t > .4 && t < 1.2) { const q = prog(t, .4, 1.0); for (let i = 0; i < 12; i++) glowDot(c, 300 + 400 * E.inOutS(clamp(q - i * .02)), 640 - Math.sin(clamp(q - i * .02) * Math.PI) * 140, 30 - i * 2, C.cyan, (1 - i / 12) * .6 * (1 - prog(t, .9, 1.2))); }
    T(c, 'Men sizga', 540, 410, { size: 72, font: SERIF, italic: true, weight: 400, fill: '#c7d2ee', alpha: E.outC(prog(t, .05, .4)) });
    const pl = pop(prog(t, tL - .1, tL + .9), 7, 9); if (pl > 0) { const sp = t * 1.1; glowDot(c, 540, 900, 600, C.cyan, .35 * clamp(pl));
      c.save(); c.translate(540, 900); c.scale(clamp(pl, 0, 1.15), clamp(pl, 0, 1.15)); linkIcon(c, 0, 0, 340, sp * 2.2 + 0.6, clamp(pl * 2)); c.restore();
      ring(c, 540, 900, 100 + prog(t, tL, tL + .7) * 600, 8 * (1 - prog(t, tL, tL + .7)), C.cyan, (1 - prog(t, tL, tL + .7)) * .9);
      emoji(c, '🔗', 840, 700, 100, { s: pop(prog(t, tL + .3, tL + 1)), rot: .25, alpha: clamp((t - tL - .3) * 6) }); }
    const ps = E.outC(prog(t, tL + .25, tL + .7)); T(c, 'silkasini', 540, 1190, { size: 120, alpha: ps, glow: 28, glowC: 'rgba(79,140,255,.7)', sx: 1 + (1 - ps) * .2 });
    const pj = E.outC(prog(t, tL + .6, tL + 1.0)); T(c, 'jo‘nataman', 540, 1310, { size: 78, font: SERIF, italic: true, weight: 400, fill: '#cfd9f4', alpha: pj });
    // fade out the whole block into next phase
    c.restore();
  }
  // phase 1: Telegram lesson cards fly in with parallax
  if (ph === 1) {
    const q = t - tTg;
    for (let i = 0; i < 3; i++) { const p = prog(q, .1 + i * .22, .7 + i * .22); const depth = [1.0, .85, 1.12][i]; c.save(); c.translate((i - 1) * 40 * (1 - p), (1 - E.outC(p)) * 500 * depth + Math.sin(t * 1.2 + i) * 6);
      const cw = 760, ch = 400; c.save(); c.translate(540, 470 + i * 430); c.scale(1, 1); tgCard(c, -cw / 2, -ch / 2, cw, ch, i, p); c.restore(); c.restore(); }
    const pt = pop(prog(q, 0, .7)); tgLogo(c, 540, 270, 62 * clamp(pt, 0, 1.1)); T(c, 'Telegram', 540, 385, { size: 50, weight: 800, alpha: clamp(pt) });
    ring(c, 540, 270, 60 + prog(q, 0, .6) * 420, 6 * (1 - prog(q, 0, .6)), '#37aee2', 1 - prog(q, 0, .6));
  }
  // phase 2: timeline of the video lesson, camera pulls through
  if (ph === 2) {
    const q = t - tMo; const p = E.outC(prog(q, -.1, .5));
    miniTimeline(c, 70, 560, 940, q + .1, p);
    const pv = E.outB(prog(q, .1, .6)); c.save(); c.translate(540, 410); c.scale(pv, pv); rr(c, -150, -170, 300, 340, 34); c.fillStyle = linGrad(c, -150, -170, 150, 170, [[0, C.vio], [1, C.org]]); c.fill(); c.fillStyle = 'rgba(0,0,0,.35)'; c.beginPath(); c.arc(0, 0, 50, 0, 7); c.fill(); c.fillStyle = '#fff'; c.beginPath(); c.moveTo(-14, -28); c.lineTo(28, 0); c.lineTo(-14, 28); c.fill(); c.restore();
    const pe = prog(q, .4, 1.0); for (let i = 0; i < 3; i++) { const e = E.outB(prog(q, .5 + i * .12, 1 + i * .12)); T(c, ['✂️', '🎞️', '🎧'][i], 220 + i * 320, 1010 + (1 - e) * 60, { size: 100, alpha: e, s: e }); }
    for (let i = 0; i < 3; i++) emoji(c, ['✂️', '🎞️', '🎧'][i], 220 + i * 320, 1000 + (1 - clamp(E.outB(prog(q, .5 + i * .12, 1 + i * .12)))) * 60, 110, { s: clamp(E.outB(prog(q, .5 + i * .12, 1 + i * .12))), alpha: clamp(prog(q, .5 + i * .12, .8 + i * .12)) });
  }
  // phase 3: finishing frames
  if (ph === 3) {
    const q = t - tLn; const p = pop(prog(q, -.05, .8), 7, 10);
    glowDot(c, 540, 820, 700, C.mint, .28 * clamp(p));
    c.save(); c.translate(540, 820); c.scale(clamp(p, 0, 1.1), clamp(p, 0, 1.1)); c.globalAlpha = clamp(p * 2);
    rr(c, -190, -300, 380, 600, 50); c.fillStyle = linGrad(c, -190, -300, 190, 300, [[0, C.blue], [.55, C.vio], [1, C.org]]); c.fill(); c.strokeStyle = 'rgba(255,255,255,.4)'; c.lineWidth = 4; c.stroke();
    c.fillStyle = 'rgba(255,255,255,.85)'; rr(c, -130, -190, 200 * E.outC(prog(q, .2, .6)), 38, 19); c.fill(); rr(c, -130, -120, 140 * E.outC(prog(q, .3, .7)), 38, 19); c.fill();
    c.fillStyle = 'rgba(0,0,0,.3)'; c.beginPath(); c.arc(0, 90, 70, 0, 7); c.fill(); c.fillStyle = '#fff'; c.beginPath(); c.moveTo(-20, 55); c.lineTo(42, 90); c.lineTo(-20, 125); c.fill(); c.restore();
    const ck = pop(prog(q, .4, 1.1), 7, 9); if (ck > 0) { c.save(); c.translate(690, 560); c.scale(clamp(ck, 0, 1.15), clamp(ck, 0, 1.15)); c.fillStyle = C.mint; c.shadowColor = C.mint; c.shadowBlur = 40; c.beginPath(); c.arc(0, 0, 70, 0, 7); c.fill(); c.shadowBlur = 0; c.strokeStyle = '#04120c'; c.lineWidth = 16; c.lineCap = 'round'; c.lineJoin = 'round'; c.beginPath(); c.moveTo(-28, 4); c.lineTo(-6, 28); c.lineTo(32, -22); c.stroke(); c.restore(); ring(c, 690, 560, 70 + prog(q, .4, 1.1) * 300, 8 * (1 - prog(q, .4, 1.1)), C.mint, 1 - prog(q, .4, 1.1)); }
    emoji(c, '🎓', 330, 470, 130, { s: pop(prog(q, .55, 1.3)), rot: -.2, alpha: clamp((q - .55) * 6) });
    const r = rng(3); for (let i = 0; i < 26; i++) { const ang = r() * 6.28, sp = 200 + r() * 520, k = E.outC(prog(q, .35, 1.4)); star4(c, 690 + Math.cos(ang) * sp * k, 560 + Math.sin(ang) * sp * k, 16 * (1 - k) + 3, ang + q * 4, [C.org, C.cyan, C.mint, '#fff'][i % 4], (1 - k)); }
  }
  c.restore();
}

// ===== Scene 9: CTA =====
function sceneCta(c, t, S, u) {
  const tS = u('sub'), tP = u('plus'), tB = u('bye');
  const [sx, sy] = shakeAt(t, 0.02, 14, .4), [sx2, sy2] = shakeAt(t, tP, 10, .35), [sx3, sy3] = shakeAt(t, tB, 8, .3);
  const z = 1 + .04 * prog(t, 0, S.dur) + .03 * E.outE(prog(t, tP, tP + .3)) * (1 - prog(t, tP + .3, tP + 1));
  c.save(); cam(c, z, 540, 960, 0, sx + sx2 + sx3, sy + sy2 + sy3);
  backdrop(c, t, { c1: C.blue, c2: C.org, px: t * 20 });
  // opening burst
  const b = prog(t, 0, .6); if (b < 1) { glowDot(c, 540, 600, 300 + b * 900, '#fff', .55 * (1 - b)); ring(c, 540, 600, 60 + b * 800, 14 * (1 - b), C.cyan, 1 - b); }
  // subscribe button
  const bp = pop(prog(t, .05, .8), 7, 9), press = Math.max(0, 1 - Math.abs(t - (tS + .75)) / .1), done = t > tS + .8;
  c.save(); c.translate(540, 520); c.scale(clamp(bp, 0, 1.1) * (1 - press * .06), clamp(bp, 0, 1.1) * (1 - press * .06)); c.globalAlpha = clamp(bp * 2);
  const w = done ? 640 : 660; rr(c, -w / 2, -80, w, 160, 80);
  c.fillStyle = done ? '#262a38' : linGrad(c, -w / 2, 0, w / 2, 0, [[0, '#3b82f6'], [1, '#6a5cff']]); c.shadowColor = done ? 'rgba(0,0,0,.5)' : 'rgba(79,140,255,.7)'; c.shadowBlur = 50; c.fill(); c.shadowBlur = 0;
  if (done) { c.strokeStyle = 'rgba(255,255,255,.25)'; c.lineWidth = 3; c.stroke(); }
  T(c, done ? 'Obuna bo‘lindi ✓' : 'Obuna bo‘lish', done ? 72 : 60, 4, { size: 62, weight: 800, fill: done ? C.mint : '#fff' });
  const bell = t > tS + .8 ? Math.sin((t - tS - .8) * 26) * .5 * Math.exp(-(t - tS - .8) * 2.2) : 0;
  emoji(c, '🔔', done ? -w / 2 + 80 : -w / 2 + 90, 0, 70, { rot: bell, alpha: 1, s: 1 });
  c.restore();
  const pr = prog(t, tS + .7, tS + 1.2); if (pr > 0 && pr < 1) ring(c, 540, 520, 80 + pr * 400, 8 * (1 - pr), '#fff', (1 - pr) * .7);
  // tap cursor
  const cp = prog(t, tS + .1, tS + .72); if (cp > 0 && t < tS + 1.5) { const a = 1 - prog(t, tS + 1.0, tS + 1.5); c.save(); c.globalAlpha = a; finger(c, lerp(900, 640, E.outC(cp)), lerp(780, 560, E.outC(cp)), press, 1); c.restore(); }
  // plus
  const pp = pop(prog(t, tP, tP + .9), 7, 9); if (pp > 0) {
    glowDot(c, 540, 1000, 520 * clamp(pp), C.org, .55); const q = prog(t, tP, tP + .9);
    T(c, 'kommentga', 540, 780, { size: 66, font: SERIF, italic: true, weight: 400, fill: '#c7d2ee', alpha: clamp(pp * 2) });
    T(c, '+', 540, 1000, { size: 420, fill: C.org, sx: clamp(pp, 0, 1.15), sy: clamp(pp, 0, 1.15), glow: 70, glowC: 'rgba(255,138,61,.9)', alpha: clamp(pp * 3) });
    for (let i = 0; i < 2; i++) { const k = clamp(q * 1.3 - i * .25); ring(c, 540, 1000, 80 + k * 520, 10 * (1 - k), i ? C.cyan : '#fff', (1 - k) * .85); }
    const r = rng(8); for (let i = 0; i < 22; i++) { const ang = r() * 6.28, sp = 180 + r() * 380, k = E.outC(clamp(q * 1.1)); star4(c, 540 + Math.cos(ang) * sp * k, 1000 + Math.sin(ang) * sp * k, 14 * (1 - k) + 2, ang, i % 3 ? C.cyan : C.org, 1 - k); }
  }
  // bye
  const pb = prog(t, tB - .05, tB + .6); if (pb > 0) {
    const sz = fitText(c, 'Ko‘rishguncha!', 860, 128), fade = 1 - prog(t, S.dur - .45, S.dur);
    c.save(); c.globalAlpha = fade; letters(c, 'Ko‘rishguncha!', 540, 1340, t - tB, { size: sz, step: .028, dur: .45, rise: .4, glow: 30, glowC: 'rgba(79,140,255,.7)' });
    T(c, 'Saidov Baxtiyor', 540, 1450, { size: 52, weight: 700, ls: 3, fill: '#c7d2ee', alpha: E.outC(prog(t, tB + .35, tB + .8)) });
    c.restore();
  }
  c.restore();
}
