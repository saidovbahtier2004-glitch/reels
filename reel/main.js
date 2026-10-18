const SCENE_FN = { hook: sceneHook, intro: sceneIntro, ai: sceneAI, grow: sceneGrow, want: sceneWant, tg: sceneTg, plus: scenePlus, link: sceneLink, cta: sceneCta };
const SUBY = { intro: 1440, ai: 1535, grow: 1520, tg: 255, link: 1520 };
// transition types between scene i -> i+1
const TRANS = ['flash', 'whipL', 'zoomthru', 'glitch', 'pushblue', 'whipU', 'zoomblast', 'dipwhite'];
const HW = .24;
let main, mc, offA, offB, ca, cb;
function initCanvases() {
  const mk = () => { const k = document.createElement('canvas'); k.width = W * SC; k.height = H * SC; return k; };
  main = document.getElementById('c'); main.width = W * SC; main.height = H * SC; mc = main.getContext('2d');
  offA = mk(); offB = mk(); ca = offA.getContext('2d'); cb = offB.getContext('2d');
}
function sceneAt(T) { const s = TL.scenes; for (let i = s.length - 1; i >= 0; i--) if (T >= s[i].start) return i; return 0; }
function drawScene(ctx, i, T) {
  const S = TL.scenes[i]; const t = Math.max(0, T - S.start);
  ctx.setTransform(SC, 0, 0, SC, 0, 0); ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over'; ctx.save();
  ctx.beginPath(); ctx.rect(0, 0, W, H); ctx.clip();
  SCENE_FN[S.id](ctx, t, S, n => { const v = S.cues[n]; if (v === undefined) throw new Error('cue ' + n); return v - S.start; });
  ctx.restore();
}
function drawTransition(i, T) {
  const B = TL.scenes[i + 1].start, p = clamp((T - (B - HW)) / (2 * HW)), type = TRANS[i];
  drawScene(ca, i, T); drawScene(cb, i + 1, T);
  mc.setTransform(1, 0, 0, 1, 0, 0); mc.globalAlpha = 1; mc.clearRect(0, 0, main.width, main.height);
  const w = main.width, h = main.height, e = E.inOutC(p);
  const put = (src, sx, sy, sc, a, rot = 0) => { mc.save(); mc.globalAlpha = a; mc.translate(w / 2 + sx * SC, h / 2 + sy * SC); mc.rotate(rot); mc.scale(sc, sc); mc.drawImage(src, -w / 2, -h / 2); mc.restore(); };
  const flash = (a, col = '255,255,255') => { mc.fillStyle = `rgba(${col},${a})`; mc.fillRect(0, 0, w, h); };
  if (type === 'flash') { const pk = Math.sin(p * Math.PI); put(offA, 0, 0, 1 + e * .5, p < .5 ? 1 : 0); put(offB, 0, 0, lerp(1.35, 1, E.outE(p)), p >= .5 ? 1 : 0); flash(.85 * Math.pow(pk, 1.5)); }
  else if (type === 'whipL' || type === 'whipU') { const v = type === 'whipU'; const amt = (v ? H : W);
    for (let k = 0; k < 7; k++) { const q = Math.max(0, e - k * .018); put(offA, v ? 0 : -q * amt * 1.05, v ? -q * amt * 1.05 : 0, 1, k ? .12 : 1); }
    mc.save(); mc.globalCompositeOperation = 'source-over'; for (let k = 0; k < 7; k++) { const q = Math.min(1, Math.max(0, e - k * .018)); put(offB, v ? 0 : (1 - q) * amt * 1.05, v ? (1 - q) * amt * 1.05 : 0, 1, k ? .12 : 1); } mc.restore();
    // proper layering: B in front once e>.5
    if (e > .5) put(offB, v ? 0 : (1 - e) * amt * 1.05, v ? (1 - e) * amt * 1.05 : 0, 1, 1); }
  else if (type === 'zoomthru') { put(offA, 0, 0, 1 + e * .9, 1 - e); put(offB, 0, 0, lerp(.7, 1, E.outC(p)), E.outC(p)); mc.save(); mc.globalCompositeOperation = 'lighter'; flash(.35 * Math.sin(p * Math.PI), '120,160,255'); mc.restore(); }
  else if (type === 'glitch') { put(offA, 0, 0, 1, 1); const r = rng(Math.floor(T * 40)); const n = 14, sh = h / n; for (let k = 0; k < n; k++) { const on = r() < p * 1.6 || p > .55; const off = (r() - .5) * 220 * Math.sin(p * Math.PI) * SC; if (p > .5 || r() < p) { mc.save(); mc.beginPath(); mc.rect(0, k * sh, w, sh + 1); mc.clip(); mc.drawImage(on && p > .5 ? offB : offA, off, 0); mc.restore(); } }
    mc.save(); mc.globalCompositeOperation = 'lighter'; mc.globalAlpha = .35 * Math.sin(p * Math.PI); mc.drawImage(p > .5 ? offB : offA, 14 * SC, 0); mc.restore(); if (p > .75) put(offB, 0, 0, 1, (p - .75) * 4); }
  else if (type === 'pushblue') { put(offA, 0, 0, 1 + e * 1.3, 1 - E.inQ(p)); put(offB, 0, 0, lerp(1.4, 1, E.outE(p)), E.outC(p)); flash(.55 * Math.sin(p * Math.PI), '55,174,226'); }
  else if (type === 'zoomblast') { put(offA, 0, 0, 1 + e * .8, 1 - prog(p, .35, .55)); put(offB, 0, 0, lerp(1.5, 1, E.outE(p)), prog(p, .4, .7)); flash(.8 * Math.pow(Math.sin(p * Math.PI), 2)); }
  else if (type === 'dipwhite') { put(offA, 0, 0, 1 + e * .35, p < .5 ? 1 : 0); put(offB, 0, 0, lerp(1.2, 1, E.outE(p)), p >= .5 ? 1 : 0); flash(Math.pow(Math.sin(p * Math.PI), 1.3)); }
}
// subtitles
function chunks(S) { const out = []; let cur = []; S.words.forEach((w, i) => { cur.push(i); if (cur.length >= 3 || /[,.?!]$/.test(w.w)) { out.push(cur); cur = []; } }); if (cur.length) out.push(cur); return out; }
const CH = {};
function drawSubs(now) {
  const si = sceneAt(now), S = TL.scenes[si]; if (!S.sub) return; const y = SUBY[S.id] ?? 1500;
  if (now > S.start + S.dur - .05) return; CH[si] = CH[si] || chunks(S);
  for (let ci = 0; ci < CH[si].length; ci++) {
    const ch = CH[si][ci], nx = CH[si][ci + 1];
    const a = S.words[ch[0]].t0 - .06; let b = S.words[ch[ch.length - 1]].t1 + .22; if (nx) b = Math.min(b, S.words[nx[0]].t0 - .06); if (now < a || now > b) continue;
    mc.setTransform(SC, 0, 0, SC, 0, 0); const al = clamp((now - a) / .1) * clamp((b - now) / .1), size = 60;
    const ws = ch.map(i => S.words[i].w), o = { size, weight: 900 }; const widths = ws.map(w => measure(mc, w, o) + size * .32); const tot = widths.reduce((x, y) => x + y, 0);
    const k = Math.min(1, 960 / tot); let x = 540 - tot * k / 2; const rise = (1 - E.outC(clamp((now - a) / .16))) * 18;
    mc.save(); mc.globalAlpha = al; mc.translate(0, rise);
    // soft pill
    rr(mc, 540 - tot * k / 2 - 28, y - 56, tot * k + 56, 112, 34); mc.fillStyle = 'rgba(4,6,14,.55)'; mc.fill();
    ch.forEach((wi, n) => { const w = S.words[wi], act = now >= w.t0 && now <= w.t1 + .05, pa = act ? pop(clamp((now - w.t0) / .3) , 9, 12) : 0;
      T(mc, ws[n], x, y, { size: size * k, weight: 900, align: 'left', fill: act ? '#ffcf5a' : '#fff', shadow: 10 }); x += widths[n] * k; });
    mc.restore();
  }
}
function T_(c, s, x, y, o, w) { c.save(); c.translate(x + w / 2 - measure(c, ' ', { size: o.size }) / 2, y); const ww = measure(c, s, { size: o.size }); T(c, s, -ww / 2 + 0, 0, { ...o, align: 'left', sx: o.s, sy: o.s }); c.restore(); }
function post(T) {
  mc.setTransform(SC, 0, 0, SC, 0, 0); mc.globalAlpha = 1;
  const v = mc.createRadialGradient(540, 960, 500, 540, 960, 1250); v.addColorStop(0, 'rgba(0,0,0,0)'); v.addColorStop(1, 'rgba(0,0,0,.42)'); mc.fillStyle = v; mc.fillRect(0, 0, W, H);
  const fo = 1 - prog(T, TL.total - .4, TL.total); if (fo < 1) { mc.fillStyle = `rgba(0,0,0,${1 - fo})`; mc.fillRect(0, 0, W, H); }
}
function renderFrame(T) {
  const i = sceneAt(T), next = TL.scenes[i + 1];
  const inTrans = next && T > next.start - HW, prev = TL.scenes[i - 1];
  if (inTrans) drawTransition(i, T);
  else if (prev && T < TL.scenes[i].start + HW) drawTransition(i - 1, T);
  else drawScene(mc, i, T);
  // subtitles hidden through transitions
  if (!(next && T > next.start - HW) && !(prev && T < TL.scenes[i].start + HW)) drawSubs(T);
  post(T);
}
window.renderFrame = renderFrame; window.initCanvases = initCanvases;
