// ===== Scene 1: HOOK =====
function sceneHook(c, t, S, u) {
  const tD = u('dostlar'), tA = u('ai'), tM = u('montaj'), tI = u('ishon');
  const zoom = 1 + .05 * E.inOutS(prog(t, 0, 1.3)) + .07 * E.outE(prog(t, tI - .02, tI + .35));
  const [sx, sy] = shakeAt(t, tA, 14, .4), [sx2, sy2] = shakeAt(t, tI, 22, .5);
  c.save(); cam(c, zoom, 540, 960, 0, sx + sx2, sy + sy2);
  backdrop(c, t, { c1: C.blue, c2: C.org, px: t * 40 });
  // film-strip rows (video editing hint), drift sideways, glitch at AI beat
  for (let r = 0; r < 3; r++) {
    const y = 250 + r * 640 + (r === 1 ? 20 : 0), dir = r % 2 ? 1 : -1; c.save(); c.globalAlpha = .16 + .1 * pop(prog(t, 0, .6));
    c.translate(0, y); c.rotate(-.045); const off = (t * 90 * dir) % 260;
    for (let i = -1; i < 7; i++) { const x = i * 260 + off; rr(c, x, 0, 230, 150, 18); c.fillStyle = linGrad(c, x, 0, x + 230, 150, [[0, rgba(C.blue, .5)], [1, rgba(C.vio, .25)]]); c.fill(); c.strokeStyle = 'rgba(180,200,255,.35)'; c.lineWidth = 2; c.stroke(); }
    c.restore();
  }
  const pAI = prog(t, tA - .05, tA + .6);
  // 1: Do'stlar,  (also bu videoni) -> exits at AI beat
  const out1 = E.inQ(prog(t, tA - .08, tA + .22));
  if (out1 < 1) {
    c.save(); c.globalAlpha = 1 - out1; c.translate(0, -out1 * 60); c.scale(1 + out1 * .25, 1 + out1 * .25);
    letters(c, 'Do‘stlar,', 540, 760, t - tD, { size: 150, weight: 900, step: .03, dur: .45, glow: 30 });
    const pb = E.outC(prog(t, u('dostlar') + .45, u('dostlar') + .8));
    T(c, 'bu videoni', 540, 930, { size: 74, font: SERIF, italic: true, weight: 400, alpha: pb, fill: '#c7d2ee' , sy: 1, rot: 0 });
    c.restore();
  }
  // 2: AI  montaj qildi
  if (pAI > 0) {
    const sA = .5 + .5 * E.outB(pAI), a = clamp(pAI * 3);
    const gx = Math.sin(t * 60) * 5 * (1 - prog(t, tA, tA + .5));
    const gFill = linGrad(c, -200, -150, 200, 150, [[0, '#7db2ff'], [.5, '#a98bff'], [1, '#ff9a5a']]);
    // shockwave
    const pw = prog(t, tA, tA + .7); ring(c, 540, 700, 80 + pw * 700, 14 * (1 - pw), C.cyan, 1 - pw); ring(c, 540, 700, 40 + pw * 480, 6 * (1 - pw), '#fff', .7 * (1 - pw));
    c.save(); c.globalCompositeOperation = 'lighter';
    T(c, 'AI', 540 - 10 - gx, 690, { size: 470, s: sA, alpha: a * .55 * (1 - prog(t, tA + .35, tA + .6)), fill: '#ff2d55' });
    T(c, 'AI', 540 + 10 + gx, 690, { size: 470, s: sA, alpha: a * .55 * (1 - prog(t, tA + .35, tA + .6)), fill: '#00e5ff' });
    c.restore();
    c.save(); c.translate(540, 690); c.scale(sA, sA); c.globalAlpha = a; c.shadowColor = 'rgba(120,150,255,.8)'; c.shadowBlur = 60;
    c.font = font(900, 470); c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillStyle = gFill; c.fillText('AI', 0, 0); c.restore();
    const pm = E.outC(prog(t, tM - .02, tM + .4));
    T(c, 'montaj qildi', 540, 1040 + (1 - pm) * 60, { size: 128, alpha: pm, glow: 24, glowC: 'rgba(79,140,255,.8)', sx: 1 + (1 - pm) * .15 });
    const pe = pop(prog(t, tM + .25, tM + 1)); emoji(c, '🎬', 880, 480, 130, { s: pe, rot: -.2 + (1 - pe) * .6, alpha: clamp(pe) });
    const pd = E.outC(prog(t, u('ai') + .95, u('ai') + 1.25)); T(c, 'desam,', 540, 1190, { size: 72, font: SERIF, italic: true, weight: 400, fill: '#c7d2ee', alpha: pd * (1 - prog(t, tI - .02, tI + .12)) });
  }
  // exit of AI block at tI-0.02
  c.restore();
  // 3: ishonasizmi? (drawn above everything, own camera punch)
  const pI = prog(t, tI, tI + .5);
  if (pI > 0) {
    c.save();
    const flash = 1 - prog(t, tI, tI + .22); if (flash > 0) { c.fillStyle = `rgba(255,255,255,${.65 * flash})`; c.fillRect(0, 0, W, H); }
    // dim to isolate the question
    c.fillStyle = `rgba(3,5,12,${.95 * E.outC(prog(t, tI - .05, tI + .15))})`; c.fillRect(0, 0, W, H);
    const s = 1 + .5 * (1 - E.outE(prog(t, tI, tI + .45))) + (t - tI) * .012;
    const sh = shakeAt(t, tI, 16, .45);
    c.translate(sh[0], sh[1]);
    glowDot(c, 540, 880, 760, C.org, .28 * E.outC(pI));
    c.save(); c.translate(540, 900); c.scale(s, s);
    const o = { size: 112, weight: 900, glow: 40, glowC: 'rgba(255,138,61,.55)' };
    letters(c, 'ishonasizmi', -90, 0, t - tI, { ...o, step: .018, dur: .32, rise: .25 });
    T(c, '?', 335, -10, { size: 300, fill: C.org, sx: .4 + .6 * pop(prog(t, tI + .12, tI + .9), 8, 12), rot: .12 * Math.sin((t - tI) * 9) * (1 - prog(t, tI, tI + 1)), glow: 70, glowC: 'rgba(255,138,61,.8)', alpha: clamp((t - tI - .08) * 10) });
    c.restore();
    emoji(c, '🤯', 540, 1200, 190, { s: pop(prog(t, tI + .3, tI + 1.1)), alpha: clamp((t - tI - .3) * 8), rot: .08 * Math.sin(t * 8) });
    c.restore();
  }
  // opening sparkle at t=0
  const p0 = prog(t, 0, .5); if (p0 < 1) { glowDot(c, 540, 700, 1200 * p0 + 100, C.cyan, .35 * (1 - p0)); }
}

// ===== Scene 2: INTRO =====
function sceneIntro(c, t, S, u) {
  const tN = u('name'), tMob = u('mob'), tTwo = u('two'), tTen = u('ten');
  const z = 1 + .045 * E.inOutS(prog(t, 0, S.dur)) + .05 * (1 - E.outE(prog(t, tTen, tTen + .5))) * (t > tTen ? 1 : 0);
  c.save(); cam(c, z, 540, 960, .006 * Math.sin(t * .6), Math.sin(t * .5) * 8, 0);
  backdrop(c, t, { c1: C.blue, c2: C.vio, px: t * 18, py: 0, glow: .9 });
  // small intro label
  T(c, 'Men', 540, 395, { size: 70, font: SERIF, italic: true, weight: 400, fill: '#c7d2ee', alpha: E.outC(prog(t, .12, .5)), sy: 1 });
  // premium name with extruded depth + glint
  const lines = [['Saidov', 575], ['Baxtiyor', 735]];
  lines.forEach(([s, y], li) => {
    const tt = t - tN - li * .12, o = { size: 148, weight: 900, step: .045, dur: .55, rise: .7 };
    if (tt > 0) {
      const wdt = measure(c, s, o); const p = E.outC(prog(tt, 0, .7));
      // depth layers
      for (let d = 12; d >= 1; d--) { const a = (1 - d / 14) * .5 * p; letters(c, s, 540 + d * .5, y + d * 1.2, tt, { ...o, fill: rgba('#1e3a8a', a * 2), alpha: a }); }
      letters(c, s, 540, y, tt, { ...o, fill: '#fff', glow: 18, glowC: 'rgba(120,160,255,.6)' });
      // glint sweep clipped to text: draw bright band with source-atop on a temp canvas region
      const gp = prog(tt, .5, 1.1); if (gp > 0 && gp < 1) {
        c.save(); c.globalAlpha = .9 * Math.sin(gp * Math.PI); const gx = 540 - wdt / 2 - 80 + gp * (wdt + 160);
        c.beginPath(); c.rect(540 - wdt / 2, y - 90, wdt, 180); c.clip();
        c.translate(gx, y); c.rotate(.35); const g = c.createLinearGradient(-50, 0, 50, 0); g.addColorStop(0, 'rgba(255,255,255,0)'); g.addColorStop(.5, 'rgba(255,255,255,.55)'); g.addColorStop(1, 'rgba(255,255,255,0)');
        c.globalCompositeOperation = 'lighter'; c.fillStyle = g; c.fillRect(-50, -200, 100, 400); c.restore();
      }
    }
  });
  // underline accent
  const pu = E.outE(prog(t, tN + .5, tN + 1.0)); if (pu > 0) { c.fillStyle = linGrad(c, 300, 0, 780, 0, [[0, C.blue], [1, C.org]]); rr(c, 540 - 240 * pu, 835, 480 * pu, 8, 4); c.fill(); }
  // role chip
  const pc = pop(prog(t, tMob, tMob + .8)); if (pc > 0) {
    c.save(); c.translate(540, 925); c.scale(clamp(pc, 0, 1.15), clamp(pc, 0, 1.15)); c.globalAlpha = clamp(pc * 2);
    rr(c, -230, -48, 460, 96, 48); c.fillStyle = 'rgba(79,140,255,.16)'; c.fill(); c.strokeStyle = 'rgba(120,160,255,.6)'; c.lineWidth = 3; c.stroke();
    T(c, 'MOBILOGRAF', 40, 3, { size: 50, weight: 800, ls: 4, glow: 12 }); emoji(c, '📱', -165, 2, 56); c.restore();
  }
  // stat cards
  const card = (cx, p, label, big, sub, accent, hl) => {
    if (p <= 0) return; const s = clamp(pop(p, 7, 10), 0, 1.12) * (1 + hl * .06);
    c.save(); c.translate(cx, 1175); c.scale(s, s); c.globalAlpha = clamp(p * 3);
    rr(c, -215, -150, 430, 300, 38); c.fillStyle = 'rgba(14,20,40,.82)'; c.fill();
    c.strokeStyle = rgba(accent, .35 + hl * .5); c.lineWidth = 3 + hl * 3; c.stroke();
    // inner top light reflection
    c.save(); rr(c, -215, -150, 430, 300, 38); c.clip(); c.fillStyle = linGrad(c, 0, -150, 0, 20, [[0, 'rgba(255,255,255,.12)'], [1, 'rgba(255,255,255,0)']]); c.fillRect(-215, -150, 430, 170);
    glowDot(c, 0, 20, 330, accent, .20 + hl * .25); c.restore();
    T(c, big, 0, -25, { size: 190, fill: '#fff', glow: 28, glowC: rgba(accent, .8) });
    T(c, sub, 0, 95, { size: 52, font: SERIF, italic: true, weight: 400, fill: '#d4dcf2' });
    c.restore();
  };
  // counter "2": 0,1,2 quick ticks
  const pc1 = prog(t, tTwo - .05, tTwo + 1.0); const n2 = Math.min(2, Math.floor(prog(t, tTwo, tTwo + .55) * 3));
  card(300, pc1, '', String(n2), 'yil tajriba', C.cyan, 0);
  const pc2 = prog(t, tTen - .25, tTen + 1.2), cnt = Math.round(10 * E.outC(prog(t, tTen, tTen + .65))), hl = Math.max(0, 1 - Math.abs(t - tTen - .65) / .5) * (t > tTen ? 1 : 0);
  card(780, pc2, '', cnt + (cnt >= 10 ? '+' : ''), 'loyiha', C.org, E.outC(prog(t, tTen + .5, tTen + .7)) * (1 - prog(t, tTen + 1.3, tTen + 2)));
  if (t > tTen + .6) { const p = prog(t, tTen + .6, tTen + 1.4); ring(c, 780, 1175, 120 + p * 330, 10 * (1 - p), C.org, 1 - p); emoji(c, '🚀', 930, 985, 100, { s: pop(prog(t, tTen + .65, tTen + 1.3)), rot: .35, alpha: clamp((t - tTen - .65) * 6) }); }
  c.restore();
}

// ===== Scene 3: AI MAKES THE VIDEO (illustrative timeline) =====
function sceneAI(c, t, S, u) {
  const tCl = u('claude'), tAI = u('ai');
  const Z = lerp(1.4, 1.0, E.outC(prog(t, 0, 2.6)));
  const drift = Math.sin(t * .6) * 18, panY = lerp(120, 0, E.outC(prog(t, 0, 2.2)));
  const layer = (depth, fn) => { c.save(); const sc = lerp(1, Z, depth); c.translate(540 + drift * depth, 960 + panY * depth); c.scale(sc, sc); c.translate(-540, -960); fn(); c.restore(); };
  const [sx, sy] = shakeAt(t, tCl, 10, .3);
  c.save(); c.translate(sx, sy);
  layer(.15, () => backdrop(c, t, { c1: C.vio, c2: C.cyan, px: t * 25, glow: 1 }));
  // side panels (mid depth)
  layer(.55, () => {
    const pa = E.outC(prog(t, .2, .9));
    c.save(); c.globalAlpha = .55 * pa; rr(c, -130 + (1 - pa) * -120, 300, 330, 700, 28); c.fillStyle = '#0e1630'; c.fill(); c.strokeStyle = 'rgba(120,160,255,.3)'; c.lineWidth = 2; c.stroke();
    for (let i = 0; i < 4; i++) { rr(c, -100 + (1 - pa) * -120, 330 + i * 110, 270, 90, 14); c.fillStyle = `rgba(${[79, 139, 53, 255][i % 4]},${[140, 92, 208, 138][i % 4]},${[255, 246, 255, 61][i % 4]},.35)`; c.fill(); }
    rr(c, 880 + (1 - pa) * 120, 360, 330, 640, 28); c.fillStyle = '#0e1630'; c.fill(); c.stroke();
    for (let i = 0; i < 5; i++) { c.fillStyle = 'rgba(190,210,255,.25)'; rr(c, 905 + (1 - pa) * 120, 395 + i * 70, 200 + (i % 3) * 30, 14, 7); c.fill(); rr(c, 905 + (1 - pa) * 120, 425 + i * 70, 120, 10, 5); c.fill(); }
    c.restore();
  });
  // preview monitor (front-mid)
  layer(.8, () => {
    const pa = E.outB(prog(t, .1, .8)); const x = 270, y = 300, w = 540, h = 600;
    c.save(); c.translate(540, y + h / 2); c.scale(pa, pa); c.translate(-540, -y - h / 2); c.globalAlpha = clamp(pa * 2);
    c.shadowColor = 'rgba(79,140,255,.45)'; c.shadowBlur = 60; rr(c, x, y, w, h, 34); c.fillStyle = '#0b1226'; c.fill(); c.shadowBlur = 0;
    c.save(); rr(c, x + 14, y + 14, w - 28, h - 28, 24); c.clip();
    // evolving frame content: scenes of the "video" cycling
    const k = Math.floor(t * 1.7) % 4, ph = (t * 1.7) % 1;
    const pal = [[C.blue, C.vio], [C.org, C.pink], [C.cyan, C.blue], [C.vio, C.org]][k];
    c.fillStyle = linGrad(c, x, y, x + w, y + h, [[0, pal[0]], [1, pal[1]]]); c.fillRect(x, y, w, h);
    glowDot(c, x + w * (.3 + .4 * ph), y + h * .4, 300, '#fff', .25);
    for (let i = 0; i < 3; i++) { const ry = y + 180 + i * 120; c.fillStyle = 'rgba(255,255,255,.85)'; rr(c, x + 60, ry, 200 + ((k + i) % 3) * 90 * E.outC(clamp(ph * 3 - i * .4)), 46, 23); c.fill(); }
    star4(c, x + w - 110, y + 110, 46 + 10 * Math.sin(t * 5), t, '#fff', .9);
    c.restore();
    // timecode + rec
    T(c, `00:${String(Math.floor(t * 3) % 60).padStart(2, '0')}:${String(Math.floor(t * 30) % 30).padStart(2, '0')}`, x + 40, y + h - 46, { size: 30, weight: 700, align: 'left', font: 'DejaVu Sans Mono, monospace', fill: '#dbe5ff', shadow: 8 });
    c.fillStyle = C.pink; c.beginPath(); c.arc(x + w - 50, y + h - 46, 10 + 2 * Math.sin(t * 8), 0, 7); c.fill();
    c.restore();
  });
  // timeline (front)
  layer(1.0, () => {
    const pa = E.outC(prog(t, .5, 1.3)); const y0 = 1110, x0 = 70, w0 = 940;
    c.save(); c.globalAlpha = pa; c.translate(0, (1 - pa) * 90);
    rr(c, 40, y0 - 30, 1000, 395, 30); c.fillStyle = 'rgba(8,12,26,.92)'; c.fill(); c.strokeStyle = 'rgba(120,160,255,.28)'; c.lineWidth = 2; c.stroke();
    const trk = [{ col: C.blue, n: 5 }, { col: C.vio, n: 4 }, { col: C.org, n: 3 }, { col: C.mint, n: 0 }];
    const r = rng(11);
    trk.forEach((tr, ti) => {
      const y = y0 + 6 + ti * 88; c.fillStyle = 'rgba(255,255,255,.04)'; rr(c, x0, y, w0, 72, 12); c.fill();
      if (ti === 3) { // waveform
        const wp = E.outC(prog(t, 1.3, 2.6)); c.fillStyle = rgba(C.mint, .8); for (let i = 0; i < 118 * wp; i++) { const hh = (8 + 26 * Math.abs(Math.sin(i * .37) * Math.sin(i * .11 + 1))) ; c.fillRect(x0 + 8 + i * 7.9, y + 36 - hh / 2, 4, hh); } return;
      }
      let x = x0 + 4; for (let i = 0; i < tr.n; i++) {
        const wd = (w0 - 20) / tr.n * (.78 + r() * .2), st = 1.0 + ti * .22 + i * .16, p = E.outC(prog(t, st, st + .45));
        if (p > 0) { c.save(); rr(c, x, y + 5, wd * p, 62, 12); c.fillStyle = linGrad(c, x, y, x + wd, y, [[0, rgba(tr.col, .95)], [1, rgba(tr.col, .55)]]); c.fill(); c.fillStyle = 'rgba(255,255,255,.35)'; rr(c, x + 12, y + 17, 60 * p, 8, 4); c.fill(); c.restore(); }
        x += (w0 - 20) / tr.n;
      }
    });
    // playhead
    const px = lerp(x0 + 30, x0 + w0 - 30, prog(t, .8, S.dur - .2)), ph = prog(t, .6, 1);
    c.save(); c.globalAlpha = ph; c.strokeStyle = '#fff'; c.lineWidth = 4; c.shadowColor = '#fff'; c.shadowBlur = 16; c.beginPath(); c.moveTo(px, y0 - 14); c.lineTo(px, y0 + 360); c.stroke();
    c.fillStyle = '#fff'; c.beginPath(); c.moveTo(px - 16, y0 - 22); c.lineTo(px + 16, y0 - 22); c.lineTo(px, y0 + 4); c.fill(); c.restore();
    c.restore();
  });
  // Claude AI chip + task checklist (nearest layer)
  layer(1.25, () => {
    const p = pop(prog(t, tCl - .1, tCl + .7)); if (p > 0) {
      c.save(); c.translate(540, 235); c.scale(clamp(p, 0, 1.12), clamp(p, 0, 1.12)); c.globalAlpha = clamp(p * 2);
      rr(c, -250, -54, 500, 108, 54); c.fillStyle = 'rgba(20,14,12,.9)'; c.fill(); c.strokeStyle = 'rgba(255,150,100,.7)'; c.lineWidth = 3; c.stroke();
      star4(c, -170, 0, 32, t * .8, '#ff9a5a'); T(c, 'Claude AI', 30, 3, { size: 58, weight: 800, glow: 14, glowC: 'rgba(255,150,100,.6)' }); c.restore();
    }
    const items = ['kesish', 'zoom', 'ovoz', 'rang'];
    items.forEach((s, i) => {
      const st = tAI + i * .38, p = E.outB(prog(t, st, st + .35)); if (p <= 0) return; const done = t > st + .45;
      c.save(); c.translate(540 + (i - 1.5) * 235, 985); c.scale(p, p); c.globalAlpha = clamp(p * 2);
      rr(c, -105, -34, 210, 68, 34); c.fillStyle = done ? 'rgba(52,211,153,.18)' : 'rgba(79,140,255,.16)'; c.fill(); c.strokeStyle = done ? rgba(C.mint, .8) : rgba(C.blue, .6); c.lineWidth = 2.5; c.stroke();
      T(c, (done ? '✓ ' : '… ') + s, 0, 2, { size: 34, weight: 700, fill: done ? C.mint : '#cfe0ff' }); c.restore();
    });
  });
  c.restore();
}

// ===== Scene 4: AI GROWS =====
const NET = (() => { const r = rng(21); const n = Array.from({ length: 46 }, () => ({ x: r() * W, y: 260 + r() * 1050, z: .4 + r() * .9, ph: r() * 6.3 }));
  const e = []; n.forEach((a, i) => n.forEach((b, j) => { if (j > i) { const d = Math.hypot(a.x - b.x, a.y - b.y); if (d < 270) e.push([i, j, d]); } })); return { n, e }; })();
function sceneGrow(c, t, S, u) {
  const tAI = u('ai'), tK = u('kundan'), tR = u('riv');
  const z = 1.18 - .18 * E.outC(prog(t, 0, 2.4)) + .03 * prog(t, 2, S.dur);
  c.save(); cam(c, z, 540, 960, .012 * Math.sin(t * .8), Math.sin(t * .7) * 14, 0);
  backdrop(c, t, { c1: C.cyan, c2: C.vio, px: -t * 30 });
  // neural network
  const beat = (t * 1.867) % 1; // pulses on beat (112 bpm)
  const P = NET.n.map(n => ({ x: n.x + Math.sin(t * .7 + n.ph) * 22 * n.z, y: n.y + Math.cos(t * .6 + n.ph) * 22 * n.z, z: n.z }));
  const net = E.outC(prog(t, 0, 1.2)); c.save(); c.globalAlpha = net;
  NET.e.forEach(([i, j, d], k) => { const a = P[i], b = P[j]; c.strokeStyle = `rgba(110,170,255,${.22 * (1 - d / 270)})`; c.lineWidth = 2; c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y); c.stroke();
    const ph = ((t * 1.867 + k * .137) % 1); if (k % 3 === 0) { const x = lerp(a.x, b.x, ph), y = lerp(a.y, b.y, ph); glowDot(c, x, y, 26, C.cyan, .8); } });
  P.forEach((p, i) => { const pl = .5 + .5 * Math.sin(t * 3 + NET.n[i].ph); glowDot(c, p.x, p.y, 34 * p.z, i % 5 === 0 ? C.org : C.blue, .35 + .5 * pl * (beat < .3 ? 1.4 : 1)); c.fillStyle = '#fff'; c.beginPath(); c.arc(p.x, p.y, 4.5 * p.z, 0, 7); c.fill(); });
  c.restore();
  // dim center for legibility
  const dim = c.createRadialGradient(540, 760, 120, 540, 760, 640); dim.addColorStop(0, 'rgba(4,6,14,.82)'); dim.addColorStop(1, 'rgba(4,6,14,0)'); c.fillStyle = dim; c.fillRect(0, 160, W, 1200);
  // text stack
  T(c, 'Hozirda', 540, 370, { size: 66, font: SERIF, italic: true, weight: 400, fill: '#c7d2ee', alpha: E.outC(prog(t, .1, .5)) });
  const pa = pop(prog(t, tAI, tAI + .8), 7, 11);
  if (pa > 0) { c.save(); c.translate(540, 560); c.scale(clamp(pa, 0, 1.1), clamp(pa, 0, 1.1)); c.globalAlpha = clamp(pa * 2); c.fillStyle = linGrad(c, -200, -100, 200, 100, [[0, '#8ec1ff'], [1, '#b08cff']]); c.shadowColor = 'rgba(100,150,255,.8)'; c.shadowBlur = 50; c.font = font(900, 300); c.textAlign = 'center'; c.textBaseline = 'middle'; c.fillText('AI', 0, 0); c.restore();
    emoji(c, '⚡', 790, 440, 110, { s: pop(prog(t, tAI + .2, tAI + 1)), rot: .2, alpha: clamp((t - tAI - .2) * 6) }); ring(c, 540, 560, 100 + prog(t, tAI, tAI + .6) * 520, 8 * (1 - prog(t, tAI, tAI + .6)), C.cyan, 1 - prog(t, tAI, tAI + .6)); }
  const pk = E.outC(prog(t, tK - .05, tK + .45)); T(c, 'kundan kunga', 540 + (1 - pk) * 80, 770, { size: 98, font: SERIF, italic: true, weight: 400, alpha: pk, fill: '#fff' });
  const pr = E.outC(prog(t, tR - .05, tR + .45)); Tghost(c, 'rivojlanib', 540 - (1 - pr) * 400, 895, { size: 130, alpha: clamp(pr * 2), glow: 26 }, (1 - pr) * 160, 0, 6);
  const pr2 = E.outC(prog(t, tR + .12, tR + .6)); Tghost(c, 'ketmoqda', 540 + (1 - pr2) * 400, 1015, { size: 130, alpha: clamp(pr2 * 2), fill: C.org, glow: 26, glowC: 'rgba(255,138,61,.6)' }, -(1 - pr2) * 160, 0, 6);
  // exponential growth curve with glowing head
  const cp = E.inOutS(prog(t, tK - .1, S.dur - .1)), x0 = 90, x1 = 990, yb = 1360, yt = 1130;
  const f = x => yb - (yb - yt) * (Math.exp(3.2 * x) - 1) / (Math.exp(3.2) - 1);
  c.save(); c.lineCap = 'round'; c.lineWidth = 10; c.strokeStyle = linGrad(c, x0, 0, x1, 0, [[0, C.blue], [1, C.org]]); c.shadowColor = 'rgba(255,138,61,.6)'; c.shadowBlur = 24; c.beginPath();
  const N = 90; for (let i = 0; i <= N * cp; i++) { const x = i / N; i ? c.lineTo(lerp(x0, x1, x), f(x)) : c.moveTo(x0, f(0)); } c.stroke(); c.restore();
  if (cp > 0) { const hx = lerp(x0, x1, cp), hy = f(cp); glowDot(c, hx, hy, 70, C.org, .9); c.fillStyle = '#fff'; c.beginPath(); c.arc(hx, hy, 11, 0, 7); c.fill(); }
  c.restore();
}
