const TXT = T;
// ---------- cloud wipe ----------
function cloudPath(edgeY, covering) {
  const p = new Path2D(); const r = [];
  if (covering) p.rect(-50, -400, W + 100, edgeY + 400); else p.rect(-50, edgeY, W + 100, H + 400 - edgeY);
  for (let x = -40, i = 0; x < W + 120; x += 105, i++) { const rad = 92 + 34 * Math.sin(i * 2.1 + 1) + 20 * Math.cos(i * 3.7), yy = edgeY + (covering ? 1 : -1) * 18 * Math.sin(i * 1.7); p.moveTo(x + rad, yy); p.arc(x, yy, rad, 0, 7); }
  return p;
}
function fit(c, s, maxW, size, weight = 900) { c.save(); c.font = font(weight, size, SANS); c.letterSpacing = '-3px'; const w = c.measureText(s).width; c.restore(); return w > maxW ? size * maxW / w : size; }
function dots(c) { c.fillStyle = 'rgba(0,0,0,.05)'; for (let x = 30; x < W; x += 60) for (let y = 30; y < H; y += 60) { c.beginPath(); c.arc(x, y, 2, 0, 7); c.fill(); } }
function card3d(c, cx, cy, w, h, rot, skew, sc, draw) {
  c.save(); c.translate(cx, cy); c.rotate(rot); c.transform(1, skew, 0, 1, 0, 0); c.scale(sc, sc); c.translate(-w / 2, -h / 2);
  c.shadowColor = 'rgba(0,0,0,.18)'; c.shadowBlur = 60; c.shadowOffsetY = 30; rr(c, 0, 0, w, h, 34); c.fillStyle = '#fff'; c.fill(); c.shadowBlur = 0; c.shadowOffsetY = 0;
  c.save(); rr(c, 0, 0, w, h, 34); c.clip(); draw(c, w, h); c.restore(); c.restore();
}
function inkHeading(c, s, y, p, size = 130) { const sz = fit(c, s, 940, size); heavy(c, s, 540, y, p, { size: sz, amber: false, ls: -3 }); }
function inkText(c, s, x, y, p, o = {}) { // black heavy text (cut-away pages)
  if (p <= 0) return; const a = E.outC(p); c.save(); c.globalAlpha *= a; c.translate(x, y + (1 - a) * 40); c.font = font(o.weight ?? 900, o.size ?? 120, SANS); c.letterSpacing = (o.ls ?? -3) + 'px'; c.textAlign = o.align ?? 'center'; c.textBaseline = 'middle'; c.fillStyle = o.fill ?? INK; c.fillText(s, 0, 0); c.restore();
}
function marker(c, x, y, w, h, p) { if (p <= 0) return; c.save(); c.fillStyle = 'rgba(255,196,40,.85)'; rr(c, x - w / 2, y - h / 2, w * E.outC(p), h, 10); c.fill(); c.restore(); }
function tgTile(c, x, y, size, p) { if (p <= 0) return; const s = clamp(pop(p, 9, 11), 0, 1.12); c.save(); c.translate(x, y); c.scale(s, s); c.shadowColor = 'rgba(30,150,200,.45)'; c.shadowBlur = 30; c.shadowOffsetY = 12; rr(c, -size / 2, -size / 2, size, size, size * .24); c.fillStyle = linGrad(c, 0, -size / 2, 0, size / 2, [[0, '#4cc0f0'], [1, '#1e8fcf']]); c.fill(); c.shadowBlur = 0; c.save(); c.scale(size / 100, size / 100); tgLogoPlane(c); c.restore(); c.restore(); }
function tgLogoPlane(c) { c.fillStyle = '#fff'; c.beginPath(); c.moveTo(-23, -1.5); c.lineTo(22, -19.5); c.bezierCurveTo(24.5, -20.4, 26.8, -18.8, 26, -15.6); c.lineTo(18.5, 19.5); c.bezierCurveTo(18, 22, 15, 23, 13, 21.5); c.lineTo(1.5, 13); c.lineTo(-6.5, 21); c.bezierCurveTo(-8.5, 23, -11, 21.8, -11, 19); c.lineTo(-11, 9.5); c.lineTo(15, -12.5); c.lineTo(-14.5, 6.5); c.lineTo(-22.5, 3.5); c.bezierCurveTo(-25.5, 2.3, -25.8, -0.6, -23, -1.5); c.closePath(); c.fill(); }
function linkIconAmber(c, size) { c.strokeStyle = AM1; c.lineWidth = size * .09; c.lineCap = 'round'; c.save(); c.rotate(-.7); rr(c, -size * .33, -size * .13, size * .4, size * .26, size * .13); c.stroke(); rr(c, -size * .07, -size * .13, size * .4, size * .26, size * .13); c.stroke(); c.restore(); }

// ---------- cut-away pages ----------
function drawCut(c, cut, T) {
  const tc = T - cut.a; c.fillStyle = PAPER; c.fillRect(0, 0, W, H); dots(c);
  const sink = 1 - E.outC(prog(T, cut.b - .25, cut.b)); // gentle exit settle
  const fl = Math.sin(tc * 1.6) * 8;
  if (cut.id === 'ai') {
    label(c, 'bu videoni', 540, 330, prog(tc, .05, .45), { align: 'center', fill: '#8a8a85', size: 40 }); 
    const s1 = 'Claude AI', sz = fit(c, s1, 900, 140);
    c.save(); c.font = font(900, sz, SANS); c.letterSpacing = '-3px'; const wAI = c.measureText('AI').width, wAll = c.measureText(s1).width; c.restore();
    marker(c, 540 + wAll / 2 - wAI / 2, 540 + sz * .12, wAI + 30, sz * .5, prog(tc, .55, 1.0));
    inkText(c, s1, 540, 500, prog(tc, .1, .55), { size: sz });
    card3d(c, 540, 1060 + fl, 840, 700, -.045 + Math.sin(tc * .9) * .01, .03, lerp(.9, 1.0, E.outC(prog(tc, 0, .7))) * (.98 + .02 * sink), (c, w, h) => {
      c.fillStyle = '#f1f1ee'; c.fillRect(0, 0, w, 66); ['#ff5f57', '#febc2e', '#28c840'].forEach((col, i) => { c.fillStyle = col; c.beginPath(); c.arc(40 + i * 34, 33, 10, 0, 7); c.fill(); });
      rr(c, 40, 100, 400, 250, 24); c.fillStyle = linGrad(c, 40, 100, 440, 350, [[0, '#2a2a28'], [1, '#6b5320']]); c.fill(); T_play(c, 240, 225, 70);
      const lines = [[480, 120, 300], [480, 170, 220], [480, 220, 270]]; lines.forEach(([x, y, ww], i) => { const p = E.outC(prog(tc, .4 + i * .15, .8 + i * .15)); c.fillStyle = i ? '#dadad6' : AM2; rr(c, x, y, ww * p, 26, 13); c.fill(); });
      const rows = [[AM2, 5], ['#1c1a14', 4], ['#c9c9c4', 6], [AM1, 3]]; const r = rng(2);
      rows.forEach(([col, n], ri) => { let x = 40; const y = 400 + ri * 70; c.fillStyle = '#f4f4f1'; rr(c, 30, y - 6, w - 60, 62, 12); c.fill(); for (let j = 0; j < n; j++) { const ww = (w - 100) / n * (.7 + r() * .2), st = .5 + ri * .16 + j * .1, p = E.outC(prog(tc, st, st + .35)); if (p > 0) { c.fillStyle = col; rr(c, x, y, ww * p, 50, 10); c.fill(); } x += (w - 80) / n; } });
      const px = lerp(60, w - 60, prog(tc, .4, 2.5)); c.strokeStyle = AM2; c.lineWidth = 5; c.beginPath(); c.moveTo(px, 380); c.lineTo(px, 690); c.stroke(); c.fillStyle = AM2; c.beginPath(); c.moveTo(px - 12, 372); c.lineTo(px + 12, 372); c.lineTo(px, 392); c.fill();
    });
    const cp = E.inOutS(prog(tc, .5, 1.5)); cursor(c, lerp(900, 480, cp), lerp(1500, 1150, cp), 'Claude', prog(tc, .45, .8), Math.max(0, 1 - Math.abs(tc - 1.55) / .1));
    ring(c, 480, 1150, 20 + prog(tc, 1.55, 2.0) * 90, 4 * (1 - prog(tc, 1.55, 2.0)), AM2, 1 - prog(tc, 1.55, 2.0));
    inkText(c, 'yasab bermoqda', 540, 1500, prog(tc, w0(35) - cut.a, w0(35) - cut.a + .4), { size: 70, weight: 800 });
  }
  if (cut.id === 'tg') {
    label(c, 'yopiq kanal', 540, 330, prog(tc, .05, .45), { align: 'center', fill: '#8a8a85', size: 40 }); emoji(c, '🔒', 760, 330, 44, { alpha: E.outC(prog(tc, .2, .5)) });
    tgTile(c, 205, 505, 130, prog(tc, .05, .6)); inkText(c, 'Telegram', 590, 505, prog(tc, .15, .6), { size: 126 });
    card3d(c, 540, 1100 + fl, 800, 800, .05 + Math.sin(tc * .9) * .01, -.03, lerp(.9, 1, E.outC(prog(tc, 0, .7))), (c, w, h) => {
      c.fillStyle = '#f4f4f1'; c.fillRect(0, 0, w, 130); c.save(); c.translate(80, 66); c.fillStyle = '#1e8fcf'; c.beginPath(); c.arc(0, 0, 38, 0, 7); c.fill(); c.scale(.6, .6); tgLogoPlane(c); c.restore();
      TXT(c, 'Video darslik', 140, 50, { size: 38, weight: 800, align: 'left', fill: INK }); TXT(c, 'yopiq kanal', 140, 92, { size: 28, weight: 500, align: 'left', fill: '#8a8a85' });
      for (let i = 0; i < 3; i++) { const p = prog(tc, w0(59) - cut.a + i * .3 - .2, w0(59) - cut.a + i * .3 + .5), y = 160 + i * 210; if (p <= 0) continue; const s = clamp(pop(p, 8, 10), 0, 1.05);
        c.save(); c.translate(w / 2, y + 90); c.scale(s, s); c.globalAlpha = clamp(p * 3); rr(c, -340, -90, 680, 180, 26); c.fillStyle = '#16130d'; c.fill();
        rr(c, -325, -75, 240, 150, 18); c.fillStyle = linGrad(c, -325, -75, -85, 75, [[0, '#2f2a1c'], [1, '#6b5320']]); c.fill(); c.fillStyle = AM1; c.beginPath(); c.moveTo(-225, -25); c.lineTo(-175, 0); c.lineTo(-225, 25); c.fill();
        TXT(c, `${i + 1}-dars`, -50, -28, { size: 40, weight: 800, align: 'left', fill: '#fff' }); c.fillStyle = 'rgba(255,255,255,.25)'; rr(c, -50, 8, 300, 16, 8); c.fill(); rr(c, -50, 40, 190, 14, 7); c.fill(); c.restore(); }
    });
    const cp = E.inOutS(prog(tc, .6, 1.6)); cursor(c, lerp(920, 700, cp), lerp(1600, 1010, cp), 'Baxtiyor', prog(tc, .55, .9), 0);
  }
  if (cut.id === 'plus') {
    const tP = w0(68) + .02 - cut.a, tS = w1(71) + .1 - cut.a;
    label(c, 'kommentariyada', 540, 330, prog(tc, .05, .45), { align: 'center', fill: '#8a8a85', size: 40 });
    inkHeading(c, 'Kommentga', 450, prog(tc, .1, .55), 130);
    tile(c, '+', 540, 700, 200, prog(tc, tP - .1, tP + .5)); ring(c, 540, 700, 110 + prog(tc, tP, tP + .7) * 360, 8 * (1 - prog(tc, tP, tP + .7)), AM2, (1 - prog(tc, tP, tP + .7)) * .9);
    card3d(c, 540, 1190 + fl, 860, 560, -.03, .02, lerp(.9, 1, E.outC(prog(tc, 0, .7))), (c, w, h) => {
      TXT(c, 'Izohlar', w / 2, 56, { size: 36, weight: 800, fill: INK });
      const posted = E.outB(prog(tc, tS, tS + .5)); for (let i = 0; i < 2; i++) { const y = 110 + (posted > 0 ? 80 : 0) * 1 + i * 110; c.fillStyle = ['#e9a23b', '#7a7a74'][i]; c.beginPath(); c.arc(70, y + 30, 28, 0, 7); c.fill(); c.fillStyle = '#e7e7e3'; rr(c, 120, y + 6, 220, 18, 9); c.fill(); rr(c, 120, y + 36, 560, 16, 8); c.fill(); }
      if (posted > 0) { c.save(); c.globalAlpha = clamp(posted * 2); const y = 100 + (1 - posted) * -30; rr(c, 20, y - 6, w - 40, 96, 18); c.fillStyle = 'rgba(255,196,40,.16)'; c.fill(); c.fillStyle = AM2; c.beginPath(); c.arc(70, y + 40, 28, 0, 7); c.fill(); TXT(c, 'siz', 120, y + 16, { size: 26, weight: 800, align: 'left', fill: INK }); rr(c, 176, y + 2, 100, 28, 14); c.fillStyle = '#eee'; c.fill(); TXT(c, 'namuna', 226, y + 17, { size: 18, weight: 600, fill: '#777' }); TXT(c, '+', 120, y + 62, { size: 40, weight: 900, align: 'left', fill: INK }); c.restore(); }
      rr(c, 20, h - 110, w - 40, 90, 45); c.fillStyle = '#f1f1ee'; c.fill(); c.fillStyle = AM2; c.beginPath(); c.arc(70, h - 65, 26, 0, 7); c.fill();
      const typed = tc >= tP && tc < tS; if (typed) { TXT(c, '+', 122, h - 66, { size: 54 * lerp(2.2, 1, E.outB(prog(tc, tP, tP + .35))), weight: 900, align: 'left', fill: INK }); c.fillStyle = AM2; rr(c, w - 120, h - 100, 90, 70, 35); c.fill(); c.strokeStyle = '#fff'; c.lineWidth = 6; c.lineCap = 'round'; c.beginPath(); c.moveTo(w - 75, h - 50); c.lineTo(w - 75, h - 82); c.moveTo(w - 91, h - 66); c.lineTo(w - 75, h - 84); c.lineTo(w - 59, h - 66); c.stroke(); }
      else if (tc < tP) TXT(c, 'Izoh qo‘shing...', 120, h - 66, { size: 30, weight: 500, align: 'left', fill: '#a0a09a' });
    });
    const tapF = tP - .75; const cx = tc < tP ? lerp(900, 330, E.inOutS(prog(tc, tapF - .5, tapF))) : lerp(330, 880, E.inOutS(prog(tc, tS - .6, tS)));
    const cyy = tc < tP ? lerp(1500, 1380, E.inOutS(prog(tc, tapF - .5, tapF))) : lerp(1380, 1380, 0); cursor(c, cx, cyy, 'Baxtiyor', prog(tc, .4, .7), Math.max(0, 1 - Math.abs(tc - tapF) / .1) + Math.max(0, 1 - Math.abs(tc - tS) / .1));
    inkText(c, 'Kommentga  +  qoldiring!', 540, 1620, prog(tc, tP + .5, tP + .95), { size: fit(c, 'Kommentga  +  qoldiring!', 900, 64), weight: 900 });
  }
  if (cut.id === 'link') {
    const pT = pop(prog(tc, .05, .8), 8, 10);
    label(c, 'men sizga', 540, 400, prog(tc, .05, .4), { align: 'center', fill: '#8a8a85', size: 40 });
    c.save(); c.translate(540, 700 + fl * .5); c.scale(clamp(pT, 0, 1.1), clamp(pT, 0, 1.1)); c.shadowColor = 'rgba(0,0,0,.3)'; c.shadowBlur = 50; c.shadowOffsetY = 24; rr(c, -170, -170, 340, 340, 80); c.fillStyle = '#16130d'; c.fill(); c.shadowBlur = 0;
    c.save(); rr(c, -170, -170, 340, 340, 80); c.clip(); c.fillStyle = linGrad(c, 0, -170, 0, 0, [[0, 'rgba(255,255,255,.14)'], [1, 'rgba(255,255,255,0)']]); c.fillRect(-170, -170, 340, 170); c.restore(); c.rotate(Math.sin(tc * 3) * .03); linkIconAmber(c, 220); c.restore();
    inkText(c, 'silka', 540, 990, prog(tc, .3, .7), { size: 100 }); marker(c, 540, 1040, 250, 14, prog(tc, .6, 1.0));
    const steps = ['Telegram', 'Darslik', 'Montaj']; const y = 1210, pr = E.inOutS(prog(tc, .6, 1.8));
    c.strokeStyle = '#dedcd5'; c.lineWidth = 8; c.lineCap = 'round'; c.beginPath(); c.moveTo(200, y); c.lineTo(880, y); c.stroke(); c.strokeStyle = AM2; c.beginPath(); c.moveTo(200, y); c.lineTo(200 + 680 * pr, y); c.stroke();
    steps.forEach((s, i) => { const x = 200 + i * 340, on = pr >= i / 2 - .001; c.fillStyle = on ? AM2 : '#dedcd5'; c.beginPath(); c.arc(x, y, on ? 20 : 14, 0, 7); c.fill(); TXT(c, s, x, y + 60, { size: 30, weight: 700, fill: on ? INK : '#9a9a94' }); });
    cursor(c, 200 + 680 * pr, y + 6, null, prog(tc, .6, .9), 0);
  }
  // light grade vignette so white feels premium
  const v = c.createRadialGradient(540, 960, 600, 540, 960, 1300); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.07)'); c.fillStyle = v; c.fillRect(0, 0, W, H);
}
function T_play(c, x, y, r) { c.fillStyle = 'rgba(255,255,255,.2)'; c.beginPath(); c.arc(x, y, r, 0, 7); c.fill(); c.fillStyle = '#fff'; c.beginPath(); c.moveTo(x - r * .3, y - r * .45); c.lineTo(x + r * .55, y); c.lineTo(x - r * .3, y + r * .45); c.fill(); }

// ---------- speaker overlays ----------
function overlays(c, T) {
  const sp = (a, b, id = .4, od = .25) => ({ pi: prog(T, a, a + id), po: 1 - prog(T, b, b + od), on: T >= a && T < b + od });
  const wrap = (s, fn) => { if (!s.on) return; c.save(); c.globalAlpha = s.po; fn(s.pi); c.restore(); };
  // 1 hook
  wrap(sp(w0(3), w0(7) - .02, .4, .15), pi => { label(c, 'bu videoni', 80, 1030, prog(T, w0(2), w0(2) + .3)); const x0 = 210, g = 190; ['A', 'I'].forEach((ch, i) => tile(c, ch, x0 + i * g, 1170, 170, prog(T, w0(3) + i * .09, w0(3) + .4 + i * .09))); tile(c, '', x0 + 2 * g, 1170, 170, prog(T, w0(3) + .18, w0(3) + .6), { icon: (c, s) => { c.fillStyle = '#fff'; c.shadowColor = 'rgba(0,0,0,.3)'; c.shadowBlur = 8; c.beginPath(); c.moveTo(s * .08, -s * .32); c.lineTo(-s * .18, s * .04); c.lineTo(-s * .01, s * .04); c.lineTo(-s * .08, s * .32); c.lineTo(s * .18, -s * .06); c.lineTo(s * .01, -s * .06); c.closePath(); c.fill(); } }); selBox(c, x0 + g, 1170, 3 * g + 10, 215, prog(T, w0(3) + .2, w0(3) + .6)); label(c, 'montaj qildi', 80, 1330, prog(T, w0(4), w0(4) + .35), { size: 50 }); });
  wrap(sp(w0(7), w0(8) + .05, .4, .15), pi => { const sz = fit(c, 'ISHONASIZMI?', 860, 128); heavy(c, 'ISHONASIZMI?', 540, 1180, pi, { size: sz, rot: -.03 }); });
  // 2 intro
  wrap(sp(w0(8), w0(13) - .12), pi => { label(c, 'Men', 82, 1050, prog(T, w0(8), w0(8) + .3), { size: 48 }); heavy(c, 'Saidov', 70, 1150, prog(T, w0(9), w0(9) + .45), { size: 170, align: 'left', amber: false, rot: 0 }); heavy(c, 'Baxtiyor', 70, 1300, prog(T, w0(9) + .15, w0(9) + .6), { size: 170, align: 'left', amber: false }); wave(c, 1405, prog(T, w0(10), w0(10) + .9), 14, AM2, 700, 70); pill(c, 'MOBILOGRAF', 260, 1480, prog(T, w0(11), w0(11) + .4), { size: 38 }); });
  wrap(sp(w0(13), w1(17) + .2), pi => { tile(c, '2', 200, 1160, 190, prog(T, w0(13), w0(13) + .45)); heavy(c, 'YIL', 330, 1160, prog(T, w0(13) + .15, w0(13) + .6), { size: 190, align: 'left' }); label(c, 'ishlab kelmoqdaman', 82, 1330, prog(T, w0(16), w0(16) + .35), { size: 50 }); selBox(c, 340, 1160, 560, 230, prog(T, w0(13) + .1, w0(13) + .6)); });
  wrap(sp(w0(20), w1(26) + .15), pi => { ['1', '0', '+'].forEach((ch, i) => tile(c, ch, 190 + i * 195, 1160, 180, prog(T, w0(20) + i * .1, w0(20) + .45 + i * .1))); selBox(c, 385, 1160, 650, 225, prog(T, w0(20) + .2, w0(20) + .7)); heavy(c, 'LOYIHALAR', 70, 1340, prog(T, w0(23), w0(23) + .45), { size: 118, align: 'left', amber: false }); });
  // 4 grow (wide shot)
  wrap(sp(w0(38), w0(46) - .05, .4, .15), pi => { ['A', 'I'].forEach((ch, i) => tile(c, ch, 110 + i * 125, 300, 105, prog(T, w0(39) + i * .08, w0(39) + .4 + i * .08))); label(c, 'kundan kunga', 80, 1130, prog(T, w0(42), w0(42) + .35), { size: 54 }); heavy(c, 'RIVOJLANIB', 70, 1250, prog(T, w0(44), w0(44) + .45), { size: fit(c, 'RIVOJLANIB', 930, 150), align: 'left' });
    const p = prog(T, w0(43), w1(45)); if (p > 0) { c.save(); c.strokeStyle = AM2; c.lineWidth = 11; c.lineCap = 'round'; c.shadowColor = 'rgba(245,158,11,.6)'; c.shadowBlur = 20; c.beginPath(); const N = 80; for (let i = 0; i <= N * p; i++) { const x = i / N; const px = 80 + x * 900, py = 1540 - 260 * (Math.exp(3 * x) - 1) / (Math.exp(3) - 1); i ? c.lineTo(px, py) : c.moveTo(px, py); } c.stroke(); const x = p, px = 80 + x * 900, py = 1540 - 260 * (Math.exp(3 * x) - 1) / (Math.exp(3) - 1); c.fillStyle = '#fff'; c.beginPath(); c.arc(px, py, 14, 0, 7); c.fill(); c.restore(); } });
  // 5 want
  wrap(sp(w0(46), w1(52) + .5), pi => { label(c, 'siz ham xuddi shunday', 80, 1060, prog(T, w0(46), w0(46) + .35), { size: 46 });
    const q = prog(T, w0(52) + .05, w0(52) + .35), mo = 1 - q;
    if (mo > 0) { c.save(); c.globalAlpha *= mo; 'MOTION'.split('').forEach((ch, i) => tile(c, ch, 100 + i * 150, 1190, 134, prog(T, w0(50) + i * .06, w0(50) + .4 + i * .06))); heavy(c, 'videolar', 70, 1350, prog(T, w0(51), w0(51) + .4), { size: 120, align: 'left', amber: false }); c.restore(); }
    if (q > 0) { const sz = fit(c, 'YASAMOQCHIMISIZ?', 880, 118); heavy(c, 'YASAMOQCHIMISIZ?', 540, 1230, q, { size: sz, rot: -.03 }); flare(c, prog(T, w0(52), w0(52) + .7), 1200); } });
  // 7 silka
  wrap(sp(w0(74), w1(75) + .35), pi => { label(c, 'men sizga', 80, 1130, prog(T, w0(72), w0(72) + .3), { size: 52 }); heavy(c, 'SILKASINI', 70, 1250, prog(T, w0(74), w0(74) + .45), { size: fit(c, 'SILKASINI', 760, 150), align: 'left' }); tile(c, '', 900, 1090, 150, prog(T, w0(74) + .1, w0(74) + .5), { dark: true, icon: (c, s) => linkIconAmber(c, s * .8) }); });
  // 8 result
  wrap(sp(w0(84), w0(88) - .05, .4, .12), pi => { heavy(c, 'MOTION', 70, 1160, prog(T, w0(84), w0(84) + .45), { size: 160, align: 'left', amber: false }); heavy(c, 'VIDEOLARNI', 70, 1300, prog(T, w0(85), w0(85) + .45), { size: fit(c, 'VIDEOLARNI', 940, 150), align: 'left' }); label(c, 'osongina', 82, 1420, prog(T, w0(86), w0(86) + .35), { size: 52 }); wave(c, 1470, prog(T, w0(86), w0(86) + .9), 12, AM2, 440, 80); });
  wrap(sp(w0(88), w0(89) - .1, .4, .1), pi => { label(c, 'yasashni', 82, 1100, prog(T, w0(87), w0(87) + .3), { size: 52 }); heavy(c, 'O‘RGANASIZ', 540, 1210, pi, { size: fit(c, 'O‘RGANASIZ', 930, 150), italic: false }); wave(c, 1330, prog(T, w0(88), w0(88) + .9), 16, AM2, 820, 130); });
  // 9 CTA
  { const a = w0(89), b = w0(94) - .4; wrap(sp(a, b, .4, .15), pi => { const click = w0(91) + .2, done = T > click; const p0 = clamp(pop(prog(T, a, a + .6), 8, 10), 0, 1.1); c.save(); c.translate(540, 1180); c.scale(p0 * (1 - Math.max(0, 1 - Math.abs(T - click) / .09) * .06), p0 * (1 - Math.max(0, 1 - Math.abs(T - click) / .09) * .06)); const w = done ? 640 : 700, h = 150; c.shadowColor = 'rgba(0,0,0,.45)'; c.shadowBlur = 36; c.shadowOffsetY = 14; rr(c, -w / 2, -h / 2, w, h, 75); c.fillStyle = done ? '#16130d' : amber(c, 0, -h / 2, 0, h / 2); c.fill(); c.shadowBlur = 0; TXT(c, done ? 'Obuna bo‘lindi ✓' : 'Obuna bo‘lish', 36, 4, { size: 58, weight: 900, fill: done ? AM1 : INK }); const bell = done ? Math.sin((T - click) * 26) * .5 * Math.exp(-(T - click) * 2.2) : 0; emoji(c, '🔔', -w / 2 + 90, 0, 66, { rot: bell }); c.restore();
    cursor(c, lerp(900, 640, E.outC(prog(T, a + .2, click))), lerp(1400, 1215, E.outC(prog(T, a + .2, click))), 'Baxtiyor', prog(T, a + .2, a + .5), Math.max(0, 1 - Math.abs(T - click) / .09)); ring(c, 640, 1215, 20 + prog(T, click, click + .5) * 160, 5 * (1 - prog(T, click, click + .5)), AM1, 1 - prog(T, click, click + .5)); }); }
  wrap(sp(w0(94) - .3, w0(97) - .05, .4, .12), pi => { label(c, 'kommentga', 540, 1040, prog(T, w0(93), w0(93) + .35), { size: 54, align: 'center' }); tile(c, '+', 540, 1230, 250, prog(T, w0(94), w0(94) + .5)); const q = prog(T, w0(94), w0(94) + .8); for (let i = 0; i < 2; i++) { const k = clamp(q * 1.3 - i * .25); ring(c, 540, 1230, 130 + k * 480, 9 * (1 - k), i ? '#fff' : AM1, (1 - k) * .85); } flare(c, prog(T, w0(94) - .1, w0(94) + .7), 1230); });
  wrap(sp(w0(97), TOTAL + 1, .45, .1), pi => { const sz = fit(c, 'Ko‘rishguncha!', 940, 160); heavy(c, 'Ko‘rishguncha!', 540, 1200, pi, { size: sz, amber: false }); wave(c, 1310, prog(T, w0(97) + .2, w0(97) + 1.1), 14, AM2, 760, 160); pill(c, 'Saidov Baxtiyor', 540, 1420, prog(T, w0(97) + .5, w0(97) + .9), { size: 44, dark: true }); });
  // subtle cursor tag drifting while he talks (like the reference)
  if (!cutState(T) && T > 4.5 && T < w0(97)) { const p = (T * .13) % 1; cursor(c, 760 + Math.sin(T * .7) * 110, 1500 + Math.cos(T * .5) * 40, 'Baxtiyor', prog(T, 4.5, 5), 0); }
}
// ---------- frame ----------
async function renderEdit(T) {
  const i = Math.min(FACE.n - 1, Math.max(0, Math.floor(T * FPS + .5))); img.src = `frames/${String(i + 1).padStart(5, '0')}.jpg`; await img.decode();
  const c = CTX; c.setTransform(1, 0, 0, 1, 0, 0); c.globalAlpha = 1; c.globalCompositeOperation = 'source-over';
  drawVideo(c, T);
  const cs = cutState(T);
  if (!cs) { const g = c.createLinearGradient(0, 850, 0, 1650); g.addColorStop(0, 'rgba(8,6,2,0)'); g.addColorStop(.45, 'rgba(8,6,2,.34)'); g.addColorStop(1, 'rgba(8,6,2,.5)'); c.fillStyle = g; c.fillRect(0, 850, W, H - 850); }
  if (!cs) overlays(c, T);
  if (cs) {
    const pin = prog(T, cs.a - WIPE, cs.a), pout = prog(T, cs.b, cs.b + WIPE);
    if (T < cs.a) { c.save(); c.clip(cloudPath(lerp(-240, H + 280, E.inOutC(pin)), true)); drawCut(c, cs, Math.max(T, cs.a - .001)); c.restore(); }
    else if (T <= cs.b) drawCut(c, cs, T);
    else { c.save(); c.clip(cloudPath(lerp(-240, H + 280, E.inOutC(pout)), false)); drawCut(c, cs, T); c.restore(); }
    flare(c, Math.max(prog(T, cs.a - WIPE, cs.a + .1) * .999, 0) < 1 && T < cs.a + .1 ? prog(T, cs.a - WIPE, cs.a + .1) : 0, H * .5);
  }
  // overlay on top of speaker after wipe-out: show only when not in cutaway
  const v = c.createRadialGradient(540, 960, 650, 540, 960, 1300); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.28)'); c.fillStyle = v; c.globalAlpha = cs ? .3 : 1; c.fillRect(0, 0, W, H); c.globalAlpha = 1;
  const fo = 1 - prog(T, TOTAL - .25, TOTAL); if (fo < 1) { c.fillStyle = `rgba(0,0,0,${1 - fo})`; c.fillRect(0, 0, W, H); }
}
async function initEdit(words, face, total) {
  WD = words; FACE = face; TOTAL = total; CNV = document.getElementById('c'); CNV.width = W; CNV.height = H; CTX = CNV.getContext('2d');
  CUTS = [{ id: 'ai', a: w0(33) - .25, b: w1(36) + .15 }, { id: 'tg', a: w0(56) - .05, b: w1(62) + .1 }, { id: 'plus', a: w0(67) + .4, b: w1(71) + .6 }, { id: 'link', a: w0(78) - .35, b: w1(79) + .35 }];
  TRACK = trackExtra(buildTrack());
}
window.initEdit = initEdit; window.renderEdit = renderEdit;
